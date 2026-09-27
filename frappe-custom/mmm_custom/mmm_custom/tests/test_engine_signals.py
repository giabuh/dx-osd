import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeJev, FakeRepo, demo_catalog, demo_consultants, fill, render

from mmm_custom.engine.combine import combine
from mmm_custom.engine.decide import Decision, decide
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.handoff import plan_handoff
from mmm_custom.engine.jev_questions import build_questions
from mmm_custom.engine.pipeline import ai_fields, parse_event, run_turn
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding

CAT = demo_catalog()
NEW = ConversationState("1")
CONFIRM = {"kind": "slot", "slot": "course", "value": "VKT-REVIT", "label": "Revit kiến trúc"}


def run(answers):
    u = Understanding()
    return combine(u, answers, build_questions(NEW, u, CAT), NEW, CAT)


class TestCombineSignals(unittest.TestCase):
    def test_intent_hotness_and_wants_human(self):
        out = run({"intent": {"choice": "purchase", "confidence": 0.9}, "hotness": {"score": 1.8, "confidence": 0.8},
                   "wants_human": {"noul": 0.75}})
        self.assertEqual(out.intent, {"value": "purchase", "confidence": 0.9})
        self.assertEqual(out.hotness, {"value": "hot", "score": 1.8, "confidence": 0.8})
        self.assertEqual(out.wants_human, 0.75)

    def test_out_of_range_or_malformed_answers_are_ignored(self):
        out = run({"intent": {"choice": "buy_now", "confidence": 0.9}, "hotness": {"score": "x"}, "wants_human": {}})
        self.assertEqual((out.intent, out.hotness, out.wants_human), ({}, {}, 0.0))
        self.assertEqual(run({"hotness": {"score": 7, "confidence": 1}}).hotness["value"], "hot")


class TestEarlyHandoff(unittest.TestCase):
    def test_wants_human_hands_off_even_with_a_pending_confirmation(self):
        d = decide(ConversationState("1", turns=1), Understanding(wants_human=0.8, confirm=CONFIRM), CAT)
        self.assertEqual((d.type, d.handoff_reason), ("handoff", "wants_human"))

    def test_hot_customer_hands_off(self):
        u = Understanding(hotness={"value": "hot", "score": 1.9, "confidence": 0.8})
        d = decide(ConversationState("1", turns=1, slots={"course": fill("VP-EXCEL")}), u, CAT)
        self.assertEqual((d.type, d.handoff_reason), ("handoff", "hot"))
        self.assertEqual(d.ai["hotness"]["value"], "hot")

    def test_below_threshold_does_not_hand_off(self):
        u = Understanding(wants_human=0.6, hotness={"value": "hot", "score": 1.6, "confidence": 0.5})
        self.assertEqual(decide(ConversationState("1", turns=1), u, CAT).type, "ask_slot")

    def test_hot_waits_for_a_pending_confirmation(self):
        u = Understanding(hotness={"value": "hot", "score": 1.9, "confidence": 0.9}, confirm=CONFIRM)
        self.assertEqual(decide(ConversationState("1", turns=1), u, CAT).type, "confirm")


class TestHandoffPlanSignals(unittest.TestCase):
    def test_hot_label_and_summary_line(self):
        repo = FakeRepo(CAT)
        repo.consultant_rows = demo_consultants()
        ai = {"hotness": {"value": "hot", "score": 1.9, "confidence": 0.82}, "intent": {"value": "purchase", "confidence": 0.9}}
        d = Decision("handoff", slots={"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An")}, handoff_reason="hot",
                     reason="Khách hot, sẵn sàng đăng ký", ai=ai)
        plan = plan_handoff(ConversationState("1"), d, CAT, repo, render)
        self.assertIn("hot", plan.labels)
        self.assertIn("🔥 hot (0.82) · ý định: purchase", plan.summary)

    def test_no_signal_no_line(self):
        repo = FakeRepo(CAT)
        repo.consultant_rows = demo_consultants()
        d = Decision("handoff", slots={"course": fill("VP-EXCEL")}, handoff_reason="button", reason="x")
        plan = plan_handoff(ConversationState("1"), d, CAT, repo, render)
        self.assertNotIn("hot", plan.labels)
        self.assertNotIn("🔥", plan.summary)


class TestLeadSignals(unittest.TestCase):
    def test_ai_fields_need_confidence(self):
        u = Understanding(intent={"value": "price_inquiry", "confidence": 0.9},
                          hotness={"value": "warm", "score": 1.0, "confidence": 0.5})
        self.assertEqual(ai_fields(u, CAT.settings), {"ai_intent": "price_inquiry"})

    def test_bot_writes_intent_and_hotness_to_the_lead_once(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        repo.prefill = {}
        repo.jev = FakeJev({"intent": {"choice": "price_inquiry", "confidence": 0.9},
                            "hotness": {"score": 1.0, "confidence": 0.8}})
        state = ConversationState("7", contact_id="9", lead="CRM-LEAD-1", turns=1)
        repo.states["7"] = state
        run_turn(parse_event(incoming("cho hỏi chút")), repo, fx, render)
        run_turn(parse_event(incoming("cho hỏi thêm", 6)), repo, fx, render)
        writes = fx.of("save_lead")
        self.assertEqual(len(writes), 1)
        self.assertEqual((writes[0]["fields"]["ai_intent"], writes[0]["fields"]["ai_hotness"]), ("price_inquiry", "warm"))
        self.assertEqual(repo.states["7"].ai, {"ai_intent": "price_inquiry", "ai_hotness": "warm"})


def incoming(text, message_id=5):
    return {"event": "message_created", "id": message_id, "content": text, "message_type": "incoming",
            "private": False, "sender": {"id": 9, "name": "Lan", "type": "contact"},
            "conversation": {"id": 7, "inbox_id": 3, "meta": {"sender": {"id": 9, "name": "Lan", "custom_attributes": {}}}}}


if __name__ == "__main__":
    unittest.main()
