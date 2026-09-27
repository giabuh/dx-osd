import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, fill

from mmm_custom.engine.jev_questions import NONE, build_questions, jev_state
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding, understand

CAT = demo_catalog()


class TestQuestions(unittest.TestCase):
    def test_new_conversation_asks_open_slots_skills_and_signals(self):
        q = build_questions(ConversationState("1"), Understanding(), CAT)
        for key in ("parent:course", "slot:course", "parent:branch", "slot:branch", "slot:learner",
                    "slot:preferred_shift", "intent", "hotness", "wants_human"):
            self.assertIn(key, q)
        for key in ("slot:learner_age", "slot:customer_name", "slot:phone"):
            self.assertNotIn(key, q)
        self.assertEqual(len(q["slot:course"]["criteria"]), 47)  # 46 courses + none
        self.assertIn(NONE, q["slot:course"]["criteria"])
        self.assertEqual(sum(k.startswith("skill:") for k in q), 30)
        self.assertEqual(q["skill:fee_quote"]["type"], "noul")
        self.assertEqual((q["hotness"]["type"], q["wants_human"]["type"]), ("score", "noul"))

    def test_criteria_carry_vietnamese_aliases(self):
        q = build_questions(ConversationState("1"), Understanding(), CAT)
        self.assertIn("excel", q["slot:course"]["criteria"]["VP-EXCEL"])
        self.assertIn("di an", q["slot:branch"]["criteria"]["CN Dĩ An"])

    def test_filled_slots_are_not_asked_but_this_turns_keyword_matches_are(self):
        filled_before = ConversationState("1", slots={"course": fill("VP-EXCEL")})
        self.assertNotIn("slot:course", build_questions(filled_before, Understanding(), CAT))
        u = understand("excel", ConversationState("1"), CAT)
        self.assertIn("slot:course", build_questions(ConversationState("1"), u, CAT))

    def test_candidates_and_parent_narrow_the_choice(self):
        u = Understanding(ambiguous={"course": ["DH-AI", "DH-PTS"]})
        q = build_questions(ConversationState("1"), u, CAT)
        self.assertEqual(set(q["slot:course"]["criteria"]), {"DH-AI", "DH-PTS", NONE})
        self.assertNotIn("parent:course", q)
        q = build_questions(ConversationState("1", slots={"course": {"parent": "Kế toán"}}), Understanding(), CAT)
        self.assertEqual(len(q["slot:course"]["criteria"]), 6)

    def test_number_slot_asked_only_when_active(self):
        s = ConversationState("1", slots={"learner": fill("child")})
        q = build_questions(s, Understanding(), CAT)
        self.assertEqual(len(q["slot:learner_age"]["criteria"]), 100)
        self.assertEqual(q["slot:learner_age"]["criteria"]["9"], "9")

    def test_skills_can_be_left_out(self):
        self.assertFalse(any(k.startswith("skill:") for k in build_questions(ConversationState("1"), Understanding(), CAT, skills=False)))

    def test_state_for_jev(self):
        s = ConversationState("1", slots={"course": fill("VP-EXCEL")}, pending={"slot": "branch"},
                              history=[{"from": "customer", "text": str(i)} for i in range(30)])
        st = jev_state("ở dĩ an", s, CAT)
        self.assertEqual(st["latest_message"], "ở dĩ an")
        self.assertEqual(st["known"], {"course": "Excel từ cơ bản đến nâng cao"})
        self.assertEqual(st["bot_question"], "Chi nhánh")
        self.assertEqual(len(st["recent_turns"]), 20)


if __name__ == "__main__":
    unittest.main()
