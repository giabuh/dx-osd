"""D-130: a remark that asks nothing ("giá sao đắt thế", "trời ơi") gets one fixed line with the way to register
("tôi muốn đăng ký học"): no buttons, no next question, no Jev call, never a step into registration."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import ROBO as KNOWN, FakeJev, FakeRepo, demo_catalog, incoming, render

from mmm_custom.engine import enrol_flow
from mmm_custom.engine.cost_guard import allow_jev
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import parse_event, run_turn
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.text import fold, remark_kind
from mmm_custom.engine.tone import problems
from mmm_custom.engine.understand import understand

CAT = demo_catalog()
BRANCH_BUTTONS = {"TP.HCM": {"type": "parent", "slot": "branch", "value": "TP. Hồ Chí Minh"}}


class TestRemarkKind(unittest.TestCase):
    def test_price_complaints(self):
        for text in ("giá sao đắt thế", "đắt quá", "mắc quá vậy", "học phí cao quá", "hơi đắt nha"):
            self.assertEqual(remark_kind(fold(text)), "price", text)

    def test_exclamations(self):
        for text in ("trời ơi", "chán quá", "haizz", "ôi giời", "huhu", "mệt quá"):
            self.assertEqual(remark_kind(fold(text)), "exclaim", text)

    def test_questions_and_content_are_not_remarks(self):
        for text in ("học phí excel bao nhiêu", "có lớp buổi tối không", "tôi muốn đăng ký học", "ok", "", "dạ",
                     "khóa excel này học trong bao lâu vậy em, đắt quá thì em có ưu đãi gì không ạ"):
            self.assertEqual(remark_kind(fold(text)), "", text)


class TestRemarkTurn(unittest.TestCase):
    def turn(self, text, slots=None, pending=None):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        repo.jev = FakeJev({})
        state = repo.load_state(parse_event(incoming("x", 1)))
        state.turns, state.slots = 3, dict(slots if slots is not None else KNOWN)
        state.pending = pending or {"slot": "branch", "options": BRANCH_BUTTONS}
        repo.save_state(state)
        return run_turn(parse_event(incoming(text, 10)), repo, fx, render), repo, fx

    def test_price_complaint_gets_one_line_without_buttons(self):
        t, repo, fx = self.turn("giá sao đắt thế")
        text = " ".join(t.reply.messages)
        self.assertEqual(t.decision.type, "answer")
        self.assertEqual(t.decision.remark, "price")
        self.assertIn("tôi muốn đăng ký học", text)
        self.assertNotIn("chi nhánh nào", text)  # no next question
        self.assertEqual(t.reply.options(), {})
        self.assertEqual(repo.jev.calls, [])
        self.assertFalse(fx.of("handoff"))

    def test_exclamation_gets_the_fixed_line(self):
        t, repo, _ = self.turn("trời ơi")
        text = " ".join(t.reply.messages)
        self.assertEqual(t.decision.remark, "exclaim")
        self.assertIn("thông tin về khóa học", text)
        self.assertIn("tôi muốn đăng ký học", text)
        self.assertEqual(t.reply.options(), {})
        self.assertEqual(t.state.stuck_turns, 0)  # a remark is not a misunderstanding: it never leads to a handoff

    def test_a_real_question_is_answered_as_before(self):
        t, _, _ = self.turn("có lớp buổi tối không")
        self.assertEqual(t.decision.remark, "")

    def test_the_registration_phrase_still_starts_registration(self):
        t, _, _ = self.turn("tôi muốn đăng ký học")
        self.assertEqual(t.decision.remark, "")
        self.assertIn(enrol_flow.skill_key(CAT), t.decision.skills)

    def test_remark_skips_jev(self):
        s = ConversationState("1", turns=3, slots=KNOWN)
        u = understand("giá sao đắt thế", s, CAT)
        self.assertEqual(u.remark, "price")
        self.assertEqual(allow_jev(u, s, CAT, 0.0), (False, "remark"))

    def test_templates_keep_the_house_tone(self):
        for key in ("remark_price_template", "remark_template"):
            self.assertEqual(problems(CAT.settings[key]), [], key)


if __name__ == "__main__":
    unittest.main()
