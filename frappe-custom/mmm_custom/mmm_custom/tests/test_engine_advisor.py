import sys
from datetime import date
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeJev, FakeRepo, demo_catalog, fill, render

from mmm_custom.engine.actions import run_action
from mmm_custom.engine.advisor import advisor_questions, score_courses
from mmm_custom.engine.context import base_context
from mmm_custom.engine.decide import Decision, decide, next_slot
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.jev_questions import build_questions
from mmm_custom.engine.pipeline import parse_event, run_turn
from mmm_custom.engine.reply import compose
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding, understand

CAT = demo_catalog()
TODAY = date(2026, 9, 28)
KIDS = ["TE-THUD", "TE-SCRATCH", "TE-PY", "TE-ROBO", "TE-ROBO-NC"]


def fits(goal, level, exclude=()):
    """Fake Jev answers: goal/level scores per course code (default 1), exclusion nouls."""
    def answer(questions):
        out = {}
        for key in questions:
            kind, _, code = key.partition(":")
            if kind == "goal_fit":
                out[key] = {"score": goal.get(code, 1), "confidence": 0.9}
            elif kind == "level_fit":
                out[key] = {"score": level.get(code, 1), "confidence": 0.9}
            elif kind == "exclude":
                out[key] = {"noul": 0.9 if code in exclude else 0.05}
        return out
    return answer


def act(skill_key, slots, jev=None):
    ctx = base_context(slots, CAT, ConversationState("1", slots=slots))
    return run_action(CAT.skills[skill_key], ctx, slots, CAT, FakeRepo(CAT), TODAY, jev, {"latest_message": "x"})


class TestAdvisorMath(unittest.TestCase):
    def test_three_questions_per_course(self):
        q = advisor_questions([CAT.courses["TE-ROBO"]])
        self.assertEqual(set(q), {"goal_fit:TE-ROBO", "level_fit:TE-ROBO", "exclude:TE-ROBO"})
        self.assertEqual((q["goal_fit:TE-ROBO"]["type"], q["exclude:TE-ROBO"]["type"]), ("score", "noul"))
        self.assertIn("Robotics cơ bản", q["goal_fit:TE-ROBO"]["instructions"])

    def test_composite_exclusion_and_order(self):
        courses = [CAT.courses[c] for c in KIDS]
        answers = fits({"TE-ROBO": 2, "TE-PY": 2}, {"TE-ROBO": 2}, exclude={"TE-SCRATCH"})(advisor_questions(courses))
        ranked = score_courses(courses, answers, CAT.settings)
        self.assertEqual([(c.code, s) for c, s in ranked],
                         [("TE-ROBO", 1.0), ("TE-PY", 0.8), ("TE-THUD", 0.5), ("TE-ROBO-NC", 0.5)])

    def test_unanswered_courses_are_left_out(self):
        courses = [CAT.courses["TE-ROBO"], CAT.courses["TE-PY"]]
        answers = {"goal_fit:TE-ROBO": {"score": 2}, "level_fit:TE-ROBO": {"score": 2}}
        self.assertEqual([c.code for c, _ in score_courses(courses, answers, CAT.settings)], ["TE-ROBO"])


class TestRecommendWithJev(unittest.TestCase):
    def test_advisor_without_jev_uses_data_filter(self):
        out = act("kids_courses", {})
        self.assertEqual([r["code"] for r in out["recommendations"]], ["TE-THUD", "TE-SCRATCH", "TE-PY"])
        self.assertNotIn("_jev", out)

    def test_jev_ranks_the_shortlist(self):
        jev = FakeJev(fits({"TE-ROBO": 2, "TE-PY": 2}, {"TE-ROBO": 2}, exclude={"TE-SCRATCH"}))
        out = act("kids_courses", {}, jev)
        self.assertEqual([(r["code"], r["score"]) for r in out["recommendations"]],
                         [("TE-ROBO", 1.0), ("TE-PY", 0.8), ("TE-THUD", 0.5)])
        self.assertEqual(out["_buttons"][0]["action"]["value"], "TE-ROBO")
        self.assertEqual((out["_jev"]["status"], len(jev.calls)), ("ok", 1))
        self.assertEqual(len(jev.calls[0][1]), 15)

    def test_shortlist_is_capped(self):
        jev = FakeJev(fits({}, {}))
        act("course_advisor", {"learner": fill("self")}, jev)
        self.assertEqual(len(jev.calls[0][1]), 3 * 8)

    def test_below_the_floor_asks_goal_then_level(self):
        low = FakeJev(fits({}, {}))  # every score 1 → composite 0.5; floor 0.5 is not "below"
        self.assertNotIn("_ask", act("kids_courses", {}, low))
        zero = fits({c: 0 for c in KIDS}, {c: 0 for c in KIDS})
        self.assertEqual(act("kids_courses", {}, FakeJev(zero))["_ask"], "goal")
        self.assertEqual(act("kids_courses", {"goal": fill("kids_start")}, FakeJev(zero))["_ask"], "level")
        both = act("kids_courses", {"goal": fill("kids_start"), "level": fill("beginner")}, FakeJev(zero))
        self.assertNotIn("_ask", both)
        self.assertEqual(len(both["recommendations"]), 3)

    def test_jev_failure_falls_back_to_the_data_filter(self):
        out = act("kids_courses", {}, FakeJev(status="unavailable"))
        self.assertEqual([r["code"] for r in out["recommendations"]], ["TE-THUD", "TE-SCRATCH", "TE-PY"])
        self.assertEqual(out["_jev"]["status"], "unavailable")


class TestComposeAdvisor(unittest.TestCase):
    def test_advisor_makes_one_call(self):
        jev = FakeJev(fits({}, {}))
        d = Decision("answer", slots={"learner": fill("child")}, skills=["kids_courses", "course_advisor"])
        r = compose(d, ConversationState("1", turns=1), CAT, render, FakeRepo(CAT), TODAY, jev=jev, jev_state={})
        self.assertEqual((len(jev.calls), len(r.jev_extra)), (1, 1))

    def test_advisor_ask_replaces_the_answer(self):
        zero = fits({c: 0 for c in KIDS}, {c: 0 for c in KIDS})
        d = Decision("answer", slots={}, skills=["kids_courses"], ask="course")
        r = compose(d, ConversationState("1", turns=1), CAT, render, FakeRepo(CAT), TODAY, jev=FakeJev(zero), jev_state={})
        self.assertEqual((r.ask, r.pending_skill), ("goal", "kids_courses"))
        self.assertEqual(r.messages, ["Anh/chị học để phục vụ mục tiêu gì ạ?"])
        self.assertEqual([b["action"]["slot"] for b in r.buttons], ["goal"] * 5)


class TestOnDemandSlots(unittest.TestCase):
    def test_never_in_the_normal_sequence(self):
        slots = {"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An"), "learner": fill("self"),
                 "preferred_shift": fill("evening"), "customer_name": fill("Lan")}
        self.assertEqual(next_slot(slots, CAT), "phone")
        self.assertEqual(next_slot(slots, CAT, first=["goal"]), "goal")

    def test_matched_and_asked_only_while_pending(self):
        self.assertNotIn("level", understand("muốn nâng cao excel", ConversationState("1"), CAT).fills)
        pending = ConversationState("1", pending={"slot": "level"})
        self.assertEqual(understand("muốn nâng cao", pending, CAT).fills["level"]["value"], "advanced")
        self.assertNotIn("slot:goal", build_questions(ConversationState("1"), Understanding(), CAT))
        self.assertIn("slot:goal", build_questions(ConversationState("1", pending={"slot": "goal"}), Understanding(), CAT))


class TestAdvisorTurn(unittest.TestCase):
    def test_goal_question_then_recommendation(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        zero = fits({c: 0 for c in KIDS}, {c: 0 for c in KIDS})
        repo.jev = FakeJev(lambda q: {"skill:kids_courses": {"noul": 0.95}, **zero(q)})
        msg = {"event": "message_created", "id": 5, "content": "bé nhà mình học khóa nào được nhỉ", "message_type": "incoming",
               "private": False, "sender": {"id": 9, "type": "contact"},
               "conversation": {"id": 7, "inbox_id": 3, "meta": {"sender": {"id": 9, "custom_attributes": {}}}}}
        t = run_turn(parse_event(msg), repo, fx, render)
        state = repo.states["7"]
        self.assertEqual((state.pending["slot"], state.pending_skill), ("goal", "kids_courses"))
        self.assertEqual(state.slots["goal"]["asked"], 1)
        self.assertEqual(len(repo.jev.calls), 2)  # the turn's call + one advisor call
        self.assertEqual((state.jev_calls, repo.tokens), ([repo.clock, repo.clock], 240))
        self.assertIn("goal_fit:TE-ROBO", repo.logs[0]["jev_extra"])


if __name__ == "__main__":
    unittest.main()
