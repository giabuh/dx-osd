import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, fill

from mmm_custom.engine.combine import combine
from mmm_custom.engine.jev_questions import NONE, build_questions
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding

CAT = demo_catalog()
NEW = ConversationState("1")


def pick(choice, confidence):
    return {"choice": choice, "confidence": confidence}


def run(answers, u=None, state=NEW):
    u = u or Understanding()
    return combine(u, answers, build_questions(state, u, CAT), state, CAT)


class TestSlots(unittest.TestCase):
    def test_act_band_fills_from_jev(self):
        out = run({"slot:course": pick("VKT-REVIT", 0.93)})
        self.assertEqual(out.fills["course"], {"value": "VKT-REVIT", "source": "jev", "confidence": 0.93})
        self.assertIn({"slot": "course", "kind": "jev", "value": "VKT-REVIT", "confidence": 0.93}, out.matches)
        self.assertEqual(out.confirm, {})

    def test_confirm_band_asks_to_confirm(self):
        out = run({"slot:course": pick("VKT-REVIT", 0.7)})
        self.assertNotIn("course", out.fills)
        self.assertEqual(out.confirm, {"kind": "slot", "slot": "course", "value": "VKT-REVIT", "label": "Revit kiến trúc"})

    def test_low_band_and_none_change_nothing(self):
        self.assertEqual(run({"slot:course": pick("VKT-REVIT", 0.4)}), Understanding())
        self.assertEqual(run({"slot:course": pick(NONE, 0.99)}), Understanding())

    def test_choice_slot_uses_its_own_thresholds(self):
        self.assertEqual(run({"slot:preferred_shift": pick("evening", 0.81)}).fills["preferred_shift"]["value"], "evening")
        self.assertEqual(run({"slot:preferred_shift": pick("evening", 0.6)}).confirm["label"], "Tối")

    def test_keyword_and_confident_jev_disagree_asks_to_confirm(self):
        u = Understanding(fills={"course": fill("VP-EXCEL")})
        out = run({"slot:course": pick("VP-WORD", 0.95)}, u)
        self.assertNotIn("course", out.fills)
        self.assertEqual(out.confirm["value"], "VP-WORD")

    def test_keyword_wins_over_unsure_or_silent_jev(self):
        u = Understanding(fills={"course": fill("VP-EXCEL")})
        self.assertEqual(run({"slot:course": pick("VP-WORD", 0.7)}, u).fills["course"]["value"], "VP-EXCEL")
        self.assertEqual(run({"slot:course": pick(NONE, 0.99)}, u).fills["course"]["value"], "VP-EXCEL")

    def test_jev_picks_among_ambiguous_candidates(self):
        u = Understanding(ambiguous={"course": ["VP-EXCEL", "VP-WORD"]})
        out = run({"slot:course": pick("VP-WORD", 0.9)}, u)
        self.assertEqual((out.fills["course"]["value"], out.ambiguous), ("VP-WORD", {}))

    def test_answer_outside_the_question_is_ignored(self):
        u = Understanding(ambiguous={"course": ["VP-EXCEL", "VP-WORD"]})
        self.assertNotIn("course", run({"slot:course": pick("VKT-REVIT", 0.99)}, u).fills)
        self.assertEqual(run({"slot:course": pick("NOT-A-COURSE", 0.99)}), Understanding())

    def test_button_choice_is_never_overridden(self):
        u = Understanding(fills={"course": fill("VP-EXCEL", "button")}, tapped=True)
        out = combine(u, {"slot:course": pick("VP-WORD", 0.99)}, {"slot:course": {"criteria": {"VP-WORD": ""}}}, NEW, CAT)
        self.assertEqual((out.fills["course"]["value"], out.confirm), ("VP-EXCEL", {}))

    def test_partial_answers_only_touch_answered_questions(self):
        out = run({"slot:branch": pick("CN Dĩ An", 0.9), "slot:course": "garbage", "parent:course": None})
        self.assertEqual(list(out.fills), ["branch"])

    def test_parent_mismatch_drops_child_keeps_parent(self):
        out = run({"slot:course": pick("VP-EXCEL", 0.9), "parent:course": pick("Kế toán", 0.92)})
        self.assertNotIn("course", out.fills)
        self.assertEqual(out.parents["course"], "Kế toán")

    def test_confident_parent_alone_is_kept(self):
        out = run({"parent:branch": pick("Bình Dương", 0.9)})
        self.assertEqual(out.parents, {"branch": "Bình Dương"})
        self.assertEqual(run({"parent:branch": pick("Bình Dương", 0.6)}).parents, {})

    def test_number_slot(self):
        state = ConversationState("1", slots={"learner": fill("child")})
        self.assertEqual(run({"slot:learner_age": pick("9", 0.9)}, state=state).fills["learner_age"]["value"], 9)

    def test_only_one_confirmation_per_turn_in_slot_order(self):
        out = run({"slot:course": pick("VKT-REVIT", 0.7), "slot:branch": pick("CN Dĩ An", 0.7)})
        self.assertEqual(out.confirm["slot"], "course")

    def test_input_is_not_mutated(self):
        u = Understanding()
        run({"slot:course": pick("VKT-REVIT", 0.93)}, u)
        self.assertEqual(u, Understanding())


def yes(n):
    return {"noul": n}


class TestSkills(unittest.TestCase):
    def test_every_confident_skill_is_answered(self):
        out = run({"skill:hotline": yes(0.93), "skill:opening_hours": yes(0.9), "skill:payment": yes(0.2)})
        self.assertEqual(sorted(out.skills), ["hotline", "opening_hours"])
        self.assertIn({"skill": "hotline", "kind": "jev", "confidence": 0.93}, out.matches)

    def test_confirm_band_asks_about_the_skill(self):
        out = run({"skill:fee_quote": yes(0.7)})
        self.assertEqual((out.skills, out.confirm), ([], {"kind": "skill", "skill": "fee_quote", "label": "học phí"}))

    def test_alias_match_is_kept_when_jev_agrees_or_is_silent(self):
        self.assertEqual(run({"skill:hotline": yes(0.9)}, Understanding(skills=["hotline"])).skills, ["hotline"])
        self.assertEqual(run({}, Understanding(skills=["hotline"])).skills, ["hotline"])

    def test_alias_match_with_a_low_score_is_lifted_to_confirm(self):
        out = run({"skill:hotline": yes(0.1)}, Understanding(skills=["hotline"]))
        self.assertEqual((out.skills, out.confirm["skill"]), ([], "hotline"))

    def test_a_slot_confirmation_wins_over_a_skill_confirmation(self):
        out = run({"slot:course": pick("VKT-REVIT", 0.7), "skill:fee_quote": yes(0.7)})
        self.assertEqual(out.confirm["kind"], "slot")

    def test_malformed_noul_is_ignored(self):
        self.assertEqual(run({"skill:hotline": {"noul": "yes"}, "skill:payment": {"choice": "x"}}).skills, [])


if __name__ == "__main__":
    unittest.main()
