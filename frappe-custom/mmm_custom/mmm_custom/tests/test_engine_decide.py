import sys
from dataclasses import replace
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, fill

from mmm_custom.engine.decide import decide
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding

CAT = demo_catalog()


def state(**kw):
    return ConversationState(conversation_id="1", **kw)


class TestDecide(unittest.TestCase):
    def test_first_message_not_understood_greets_and_asks_course(self):
        d = decide(state(), Understanding(), CAT)
        self.assertEqual((d.type, d.ask, d.greet, d.fallback, d.stuck_turns), ("ask_slot", "course", True, False, 0))
        self.assertEqual(d.slots["course"]["asked"], 1)

    def test_a_customer_giving_a_short_number_is_not_asked_about_our_hotline(self):
        hotline = {"kind": "skill", "skill": "hotline", "label": "hotline, Zalo"}
        u = Understanding(confirm=hotline, phone_suspect="039182384")
        d = decide(state(turns=3, slots={"course": fill("VP-EXCEL")}), u, CAT)
        self.assertEqual((d.type, d.confirm, d.phone_check), ("ask_slot", {}, "039182384"))

    def test_a_hot_customer_with_a_short_number_is_asked_to_check_it_first(self):
        hot = {"value": "hot", "confidence": 0.95}
        u = Understanding(phone_suspect="039182384", hotness=hot)
        d = decide(state(turns=3, slots={"course": fill("VP-EXCEL")}), u, CAT)
        self.assertEqual((d.type, d.phone_check), ("ask_slot", "039182384"))
        d = decide(state(turns=3, slots={"course": fill("VP-EXCEL")}), Understanding(hotness=hot), CAT)
        self.assertEqual((d.type, d.handoff_reason), ("handoff", "hot"))

    def test_a_skill_marked_alone_drops_the_other_answers(self):
        u = Understanding(skills=["fee_quote", "corporate_training"], fills={"course": fill("VP-EXCEL")})
        d = decide(state(turns=1), u, CAT)
        self.assertEqual((d.type, d.skills, d.handoff_reason), ("handoff", ["corporate_training"], "skill"))

    def test_course_filled_asks_branch_and_records_parent(self):
        d = decide(state(turns=1), Understanding(fills={"course": fill("VP-EXCEL")}), CAT)
        self.assertEqual((d.type, d.ask, d.new_slots), ("ask_slot", "branch", ["course"]))
        self.assertEqual(d.slots["course"]["parent"], "Tin học văn phòng")
        self.assertFalse(d.greet)

    def test_required_slots_filled_hands_off(self):
        u = Understanding(fills={"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An"), "phone": fill("+84901234567")})
        d = decide(state(), u, CAT)
        self.assertEqual((d.type, d.handoff_reason), ("handoff", "required_filled"))

    def test_stuck_turns_hand_off(self):
        d = decide(state(turns=3, stuck_turns=1), Understanding(), CAT)
        self.assertEqual((d.type, d.handoff_reason, d.stuck_turns), ("handoff", "stuck", 2))

    def test_unclear_later_turn_uses_fallback_and_counts_stuck(self):
        d = decide(state(turns=2), Understanding(), CAT)
        self.assertEqual((d.type, d.fallback, d.stuck_turns), ("ask_slot", True, 1))

    def test_skill_with_params_answers_and_asks_next(self):
        u = Understanding(fills={"course": fill("VP-EXCEL")}, skills=["fee_quote"])
        d = decide(state(turns=1), u, CAT)
        self.assertEqual((d.type, d.skills, d.ask, d.pending_skill), ("answer", ["fee_quote"], "branch", ""))

    def test_skill_missing_param_is_remembered_then_answered(self):
        d = decide(state(turns=1), Understanding(skills=["fee_quote"]), CAT)
        self.assertEqual((d.type, d.pending_skill, d.ask), ("ask_slot", "fee_quote", "course"))
        d2 = decide(state(turns=2, pending_skill="fee_quote"), Understanding(fills={"course": fill("VP-EXCEL")}), CAT)
        self.assertEqual((d2.type, d2.skills, d2.pending_skill), ("answer", ["fee_quote"], ""))

    def test_waiting_skill_param_is_asked_first(self):
        cat = demo_catalog()
        cat.skills["branch_info"] = replace(cat.skills["branch_info"], params=("branch",))
        d = decide(state(turns=1), Understanding(skills=["branch_info"]), cat)
        self.assertEqual((d.ask, d.pending_skill), ("branch", "branch_info"))

    def test_skill_count_is_capped_and_ordered(self):
        cat = demo_catalog(max_skills_per_reply=2)
        keys = ["payment", "hotline", "shifts"]
        d = decide(state(turns=1), Understanding(skills=keys), cat)
        expected = sorted(keys, key=lambda k: cat.skills[k].order)[:2]
        self.assertEqual(d.skills, expected)

    def test_handoff_skill_and_button(self):
        self.assertEqual(decide(state(turns=1), Understanding(skills=["talk_to_human"]), CAT).handoff_reason, "skill")
        self.assertEqual(decide(state(turns=1), Understanding(handoff=True), CAT).handoff_reason, "button")

    def test_silent_when_consultant_replied_or_closed(self):
        self.assertEqual(decide(state(consultant_replied=True), Understanding(skills=["hotline"]), CAT).type, "silent")
        self.assertEqual(decide(state(status="closed"), Understanding(skills=["hotline"]), CAT).type, "silent")

    def test_after_handoff_only_skills_are_answered(self):
        self.assertEqual(decide(state(status="handed_off", turns=4), Understanding(), CAT).type, "silent")
        d = decide(state(status="handed_off", turns=4), Understanding(skills=["hotline"]), CAT)
        self.assertEqual((d.type, d.skills, d.ask), ("answer", ["hotline"], ""))

    def test_parent_change_drops_course_of_other_group(self):
        s = state(turns=2, slots={"course": {**fill("VP-EXCEL"), "parent": "Tin học văn phòng"}})
        d = decide(s, Understanding(parents={"course": "Thiết kế đồ họa"}), CAT)
        self.assertNotIn("value", d.slots["course"])
        self.assertEqual((d.slots["course"]["parent"], d.ask), ("Thiết kế đồ họa", "course"))

    def test_ambiguous_values_become_candidates(self):
        d = decide(state(turns=1), Understanding(ambiguous={"course": ["DH-AI", "DH-PTS"]}), CAT)
        self.assertEqual(d.slots["course"]["candidates"], ["DH-AI", "DH-PTS"])
        self.assertEqual(d.stuck_turns, 0)

    def test_optional_slot_asked_once_and_dependency_respected(self):
        slots = {"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An"), "learner": {"asked": 1}}
        tested = {"excel_quiz": "declined"}  # else the level test is offered first (D-106)
        d = decide(state(turns=3, slots=slots, offers=tested), Understanding(), CAT)
        self.assertEqual(d.ask, "preferred_shift")
        d2 = decide(state(turns=3, slots={**slots, "learner": fill("child")}, offers=tested), Understanding(), CAT)
        self.assertEqual(d2.ask, "learner_age")

    def test_focus_asks_that_slot(self):
        d = decide(state(turns=1), Understanding(focus="preferred_shift"), CAT)
        self.assertEqual(d.ask, "preferred_shift")


if __name__ == "__main__":
    unittest.main()
