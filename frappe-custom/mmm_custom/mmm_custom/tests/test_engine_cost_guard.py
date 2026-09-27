import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeJev, FakeRepo, demo_catalog, fill, render

from mmm_custom.engine.cost_guard import allow_jev, recent_calls
from mmm_custom.engine.decide import decide
from mmm_custom.engine.effects import ChatwootEffects, RecordingEffects
from mmm_custom.engine.pipeline import parse_event, run_turn
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding

CAT = demo_catalog()
NOW = 1_800_000_000.0
SPAM = {"intent": {"choice": "spam", "confidence": 0.95}}


def incoming(text, message_id=5):
    return {"event": "message_created", "id": message_id, "content": text, "message_type": "incoming",
            "private": False, "sender": {"id": 9, "name": "Lan", "type": "contact"},
            "conversation": {"id": 7, "inbox_id": 3, "meta": {"sender": {"id": 9, "name": "Lan", "custom_attributes": {}}}}}


class TestAllowJev(unittest.TestCase):
    def test_no_call_when_the_bot_will_stay_silent(self):
        u = Understanding(unmatched=["x"])
        self.assertEqual(allow_jev(u, ConversationState("1", status="closed"), CAT, NOW), (False, "bot_silent"))
        self.assertEqual(allow_jev(u, ConversationState("1", consultant_replied=True), CAT, NOW), (False, "bot_silent"))

    def test_button_tap(self):
        self.assertEqual(allow_jev(Understanding(tapped=True), ConversationState("1"), CAT, NOW), (False, "button"))

    def test_keywords_explained_everything(self):
        state = ConversationState("1", pending={"slot": "course"})
        u = Understanding(fills={"course": fill("VP-EXCEL")})
        self.assertEqual(allow_jev(u, state, CAT, NOW), (False, "keywords_resolved"))
        self.assertEqual(allow_jev(Understanding(), ConversationState("1"), CAT, NOW), (False, "keywords_resolved"))

    def test_leftover_words_or_unanswered_question_need_jev(self):
        state = ConversationState("1", pending={"slot": "course"})
        u = Understanding(fills={"course": fill("VP-EXCEL")}, unmatched=["nua"])
        self.assertEqual(allow_jev(u, state, CAT, NOW), (True, ""))
        self.assertEqual(allow_jev(Understanding(fills={"branch": fill("CN Dĩ An")}), state, CAT, NOW), (True, ""))

    def test_hourly_cap(self):
        u = Understanding(unmatched=["x"])
        busy = ConversationState("1", jev_calls=[NOW - 10] * 20)
        self.assertEqual(allow_jev(u, busy, CAT, NOW), (False, "hourly_cap"))
        old = ConversationState("1", jev_calls=[NOW - 4000] * 20)
        self.assertEqual(allow_jev(u, old, CAT, NOW), (True, ""))
        self.assertEqual(recent_calls([NOW - 4000, NOW - 5], NOW), [NOW - 5])

    def test_daily_budget(self):
        u = Understanding(unmatched=["x"])
        self.assertEqual(allow_jev(u, ConversationState("1"), CAT, NOW, 1000, 1000), (False, "daily_budget"))
        self.assertEqual(allow_jev(u, ConversationState("1"), CAT, NOW, 10**9, 0), (True, ""))


class TestGuardInTheTurn(unittest.TestCase):
    def setUp(self):
        self.repo, self.fx = FakeRepo(CAT), RecordingEffects()
        self.repo.jev = FakeJev({"slot:course": {"choice": "VKT-REVIT", "confidence": 0.93}})

    def turn(self, text, message_id=5):
        return run_turn(parse_event(incoming(text, message_id)), self.repo, self.fx, render)

    def test_call_and_tokens_are_counted(self):
        self.turn("mình muốn học vẽ nhà nha bạn")
        self.assertEqual((self.repo.states["7"].jev_calls, self.repo.tokens), ([NOW], 120))

    def test_hourly_cap_skips_jev(self):
        self.repo.states["7"] = ConversationState("7", contact_id="9", turns=1, jev_calls=[NOW - 1] * 20)
        t = self.turn("mình muốn học vẽ nhà nha bạn")
        self.assertEqual((t.jev.status, t.jev.error, self.repo.jev.calls), ("skipped_cost_guard", "hourly_cap", []))
        self.assertEqual(self.repo.logs[0]["jev_status"], "skipped_cost_guard")

    def test_budget_reached_warns(self):
        self.repo.tokens, self.repo.budget = 500, 500
        t = self.turn("mình muốn học vẽ nhà nha bạn")
        self.assertEqual((t.jev.error, self.repo.warnings), ("daily_budget", 1))

    def test_spam_closes_without_lead(self):
        self.repo.jev = FakeJev(SPAM)
        t = self.turn("Vay tiền nhanh lãi suất thấp giải ngân trong ngày")
        self.assertEqual((t.decision.type, t.decision.close, self.repo.states["7"].status), ("silent", True, "closed"))
        self.assertEqual(self.fx.of("mark_spam"), [{"conversation_id": "7"}])
        self.assertEqual((self.fx.of("send"), self.fx.of("save_lead")), ([], []))
        self.assertIn("rác", self.repo.logs[0]["reason"])

    def test_spam_guess_never_closes_a_known_customer(self):
        self.repo.jev = FakeJev(SPAM)
        self.repo.states["7"] = ConversationState("7", contact_id="9", lead="CRM-LEAD-1", turns=1)
        t = self.turn("Vay tiền nhanh lãi suất thấp giải ngân trong ngày")
        self.assertFalse(t.decision.close)
        self.assertEqual(self.repo.states["7"].status, "active")

    def test_low_spam_confidence_is_not_spam(self):
        self.repo.jev = FakeJev({"intent": {"choice": "spam", "confidence": 0.6}})
        self.assertFalse(self.turn("abc xyz").decision.close)


class TestSpamDecisionAndEffects(unittest.TestCase):
    def test_decide(self):
        d = decide(ConversationState("1", turns=1), Understanding(spam=0.9, skills=["hotline"]), CAT)
        self.assertEqual((d.type, d.close, d.skills), ("silent", True, []))

    def test_chatwoot_marks_and_resolves(self):
        bot = MagicMock()
        ChatwootEffects(bot, MagicMock()).mark_spam("7")
        bot.add_labels.assert_called_once_with("7", ["spam"])
        bot.toggle_status.assert_called_once_with("7", "resolved")


if __name__ == "__main__":
    unittest.main()
