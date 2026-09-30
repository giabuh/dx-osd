"""D-111: the bot answers at once when no staff member is around; while one watches, has claimed or has written
in the conversation it only drafts (private note) and answers itself what nobody answered in time."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import ROBO, FakeJev, FakeRepo, demo_catalog, demo_consultants, event, fill, render

from mmm_custom.engine import copilot, presence
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.jev_questions import COURSE_FACT

from mmm_custom.engine.routing import pick_consultant
from mmm_custom.engine.state import ConversationState

CAT = demo_catalog()
WAIT = 5 * 60



class TestMode(unittest.TestCase):
    def test_nobody_around_is_auto(self):
        self.assertEqual(copilot.mode(ConversationState("1"), lambda: [], CAT.settings), copilot.AUTO)

    def test_watching_claimed_or_written_is_assist(self):
        for state, viewers in ((ConversationState("1"), ["lan@crm"]), (ConversationState("1", claimed_by="4"), []),
                               (ConversationState("1", consultant_replied=True), [])):
            self.assertEqual(copilot.mode(state, lambda: viewers, CAT.settings), copilot.ASSIST)

    def test_assist_off_sandbox_or_closed_is_auto(self):
        off = demo_catalog(assist_disabled=1)
        self.assertEqual(copilot.mode(ConversationState("1", claimed_by="4"), lambda: [], off.settings), copilot.AUTO)
        self.assertEqual(copilot.mode(ConversationState("1", is_sandbox=True), lambda: ["x"], CAT.settings), copilot.AUTO)
        self.assertEqual(copilot.mode(ConversationState("1", status="closed"), lambda: ["x"], CAT.settings), copilot.AUTO)

    def test_viewers_are_fresh_pings_only(self):
        self.assertEqual(presence.fresh({b"lan": 100.0, "4": 60.0, "bad": "x"}, now=120.0), ["lan"])


class TestHandle(unittest.TestCase):
    def setUp(self):
        self.repo, self.fx = FakeRepo(CAT), RecordingEffects()
        self.repo.jev = FakeJev({COURSE_FACT: {"choice": "duration", "confidence": 0.95}})
        self.repo.save_state(ConversationState("2", turns=3, slots=dict(ROBO), last_message_id=10))

    def test_nobody_around_the_bot_answers_at_once(self):
        turn = copilot.handle(event("khóa này kéo dài mấy tuần", 11), self.repo, self.fx, render)
        self.assertEqual(len(self.fx.of("send")), 1)
        self.assertEqual((turn.state.fallback_due, self.fx.of("note")), (0.0, []))

    def test_someone_watching_gets_a_draft_and_the_timer_starts(self):
        copilot.handle(event("khóa này kéo dài mấy tuần", 11), self.repo, self.fx, render, viewers=lambda: ["lan@crm"])
        self.assertEqual(self.fx.of("send"), [])
        self.assertIn("học trong 2 tháng", self.fx.of("note")[0]["text"])
        state = self.repo.states["2"]
        self.assertEqual(state.fallback_due, self.repo.clock + WAIT)
        self.assertEqual(state.assist["waiting"], [{"id": 11, "text": "khóa này kéo dài mấy tuần"}])
        self.assertEqual((state.turns, state.last_message_id), (3, 10), "nothing was answered yet")
        self.assertEqual(self.fx.of("assist_status")[-1]["bot_mode"], "assist")

    def test_a_second_message_keeps_the_first_deadline(self):
        copilot.handle(event("khóa này kéo dài mấy tuần", 11), self.repo, self.fx, render, viewers=lambda: ["lan"])
        self.repo.clock += 120
        copilot.handle(event("bé 8 tuổi học được không", 12), self.repo, self.fx, render, viewers=lambda: ["lan"])
        state = self.repo.states["2"]
        self.assertEqual(state.fallback_due, self.repo.clock - 120 + WAIT)
        self.assertEqual([w["id"] for w in state.assist["waiting"]], [11, 12])

    def test_a_staff_reply_empties_the_queue(self):
        self.assertEqual(copilot.human_replied({"waiting": [{"id": 1}], "held": True, "contact": {"id": 9}}, 50.0),
                         {"waiting": [], "held": False, "human_at": 50.0, "contact": {"id": 9}})


class TestAnswerDue(unittest.TestCase):
    def setUp(self):
        self.repo, self.fx = FakeRepo(CAT), RecordingEffects()
        self.repo.jev = FakeJev({COURSE_FACT: {"choice": "duration", "confidence": 0.95}})
        state = ConversationState("2", turns=3, slots=dict(ROBO), last_message_id=10, consultant_replied=True)
        self.repo.save_state(state)
        copilot.handle(event("khóa này kéo dài mấy tuần", 11), self.repo, self.fx, render)

    def test_not_before_the_deadline(self):
        self.repo.clock += WAIT - 1
        self.assertIsNone(copilot.answer("2", self.repo, self.fx, render))
        self.assertEqual(self.fx.of("send"), [])

    def test_after_the_deadline_the_bot_answers_even_after_a_person_wrote(self):
        self.repo.clock += WAIT
        turn = copilot.answer("2", self.repo, self.fx, render)
        self.assertIn("học trong 2 tháng", " ".join(self.fx.of("send")[0]["messages"]))
        state = self.repo.states["2"]
        self.assertEqual((state.fallback_due, state.assist["waiting"], state.last_message_id), (0.0, [], 11))
        self.assertTrue(state.consultant_replied, "the person still leads; the bot only filled the gap")
        self.assertEqual(turn.decision.type, "answer")

    def test_nothing_to_say_sends_the_hold_line_once_and_never_hands_off(self):
        self.repo.jev = FakeJev({"wants_human": {"noul": 0.95}})
        state = self.repo.states["2"]
        state.assist["waiting"] = [{"id": 11, "text": "cho mình gặp tư vấn viên"}]
        self.repo.clock += WAIT
        copilot.answer("2", self.repo, self.fx, render)
        self.assertEqual(self.fx.of("handoff"), [])
        self.assertIn("đã báo tư vấn viên", self.fx.of("send")[0]["messages"][0])
        self.assertEqual(self.fx.of("emit")[-1]["event"], "assist_timeout")
        copilot.handle(event("alo có ai không", 12), self.repo, self.fx, render)
        self.repo.clock += WAIT
        copilot.answer("2", self.repo, self.fx, render)
        self.assertEqual(len([s for s in self.fx.of("send") if "đã báo tư vấn viên" in s["messages"][0]]), 1)

    def test_when_the_person_left_the_next_message_answers_everything_waiting(self):
        state = self.repo.states["2"]
        state.consultant_replied = False
        copilot.handle(event("bé 8 tuổi học được không", 12), self.repo, self.fx, render)
        self.assertEqual(len(self.fx.of("send")), 1)
        self.assertEqual((self.repo.states["2"].assist["waiting"], self.repo.states["2"].last_message_id), ([], 12))


def updated(before, after):
    return {"id": 2, "changed_attributes": [{"custom_attributes": {"previous_value": before, "current_value": after}}]}


class TestBanner(unittest.TestCase):
    def test_claim_hand_back_and_reply_now_are_read_from_the_webhook(self):
        self.assertEqual(copilot.banner_changes(updated({}, {"claimed_by": "4"})), {"claimed_by": "4"})
        self.assertEqual(copilot.banner_changes(updated({"claimed_by": "4"}, {"claimed_by": ""})), {"claimed_by": ""})
        at = copilot.banner_changes(updated({"bot_fallback_at": "2026-09-30T10:05:00+00:00"},
                                            {"bot_fallback_at": "2026-09-30T10:01:00Z"}))["reply_at"]
        self.assertEqual(at, 1790762460.0)
        self.assertEqual(copilot.banner_changes({"changed_attributes": [{"status": {}}]}), {})

    def test_claim_makes_the_bot_suggest_and_hand_back_answers_now(self):
        state = ConversationState("2", assist={"waiting": [{"id": 1, "text": "?"}]}, fallback_due=500.0)
        copilot.apply_banner(state, {"claimed_by": "4"}, now=100.0)
        self.assertEqual(copilot.mode(state, lambda: [], CAT.settings), copilot.ASSIST)
        copilot.apply_banner(state, {"claimed_by": ""}, now=200.0)
        self.assertEqual((state.claimed_by, state.consultant_replied, state.fallback_due), ("", False, 200.0))

    def test_reply_now_only_moves_the_deadline_earlier(self):
        state = ConversationState("2", fallback_due=500.0)
        self.assertEqual(copilot.apply_banner(state, {"reply_at": 499.5}, now=0).fallback_due, 500.0, "the bot's own echo")
        self.assertEqual(copilot.apply_banner(state, {"reply_at": 300.0}, now=0).fallback_due, 300.0)
        self.assertEqual(copilot.apply_banner(ConversationState("2"), {"reply_at": 300.0}, now=0).fallback_due, 0.0)

    def test_typing_holds_the_bot_back_a_minute(self):
        self.assertEqual(copilot.typing(ConversationState("2", fallback_due=110.0), now=100.0).fallback_due, 160.0)
        self.assertEqual(copilot.typing(ConversationState("2", fallback_due=400.0), now=100.0).fallback_due, 400.0)
        self.assertEqual(copilot.typing(ConversationState("2"), now=100.0).fallback_due, 0.0)


class TestOnDuty(unittest.TestCase):
    def setUp(self):
        self.consultants = demo_consultants()
        self.branch = self.consultants[0]["branch"]
        self.same = [c for c in self.consultants if c["branch"] == self.branch]

    def test_people_on_duty_are_preferred(self):
        on = {str(self.same[-1]["chatwoot_agent_id"])}
        picked, why = pick_consultant(self.branch, self.consultants, {}, online=on)
        self.assertEqual((picked["name"], why.split(" · ")[1]), (self.same[-1]["name"], "đang trực"))

    def test_an_offline_owner_is_skipped(self):
        owner = self.same[0]
        picked, _ = pick_consultant(self.branch, self.consultants, {}, owner=owner["name"],
                                    online={str(self.same[-1]["chatwoot_agent_id"])})
        self.assertNotEqual(picked["name"], owner["name"])

    def test_without_presence_data_nothing_changes(self):
        self.assertEqual(pick_consultant(self.branch, self.consultants, {}, online=None),
                         pick_consultant(self.branch, self.consultants, {}))

    def test_timeout_moves_the_customer_only_off_an_offline_assignee(self):
        state = ConversationState("2", slots={"branch": fill(self.branch)})
        first, last = self.same[0]["chatwoot_agent_id"], self.same[-1]["chatwoot_agent_id"]
        self.assertIsNone(copilot.replacement(state, self.consultants, {}, {str(first)}, first, CAT))
        picked, _ = copilot.replacement(state, self.consultants, {}, {str(last)}, first, CAT)
        self.assertEqual(picked["chatwoot_agent_id"], last)
        self.assertIsNone(copilot.replacement(state, self.consultants, {}, set(), first, CAT))


if __name__ == "__main__":
    unittest.main()
