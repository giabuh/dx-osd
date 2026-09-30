"""D-109: a greeting or a laugh ("hihi", "chào em") is greeted back with an invitation, never read as a button,
never counted as a stuck turn and never a reason to hand off."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import ROBO as KNOWN, FakeJev, FakeRepo, demo_catalog, incoming, render

from mmm_custom.engine.combine import combine
from mmm_custom.engine.cost_guard import allow_jev
from mmm_custom.engine.decide import decide
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.jev_questions import REPLY_TO_BOT, build_questions
from mmm_custom.engine.pipeline import parse_event, run_turn
from mmm_custom.engine.reply import compose
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.text import fold, is_smalltalk
from mmm_custom.engine.understand import understand

CAT = demo_catalog()
REGISTER = {"Đăng ký giữ chỗ": {"type": "skill", "skill": "register"}, "Xem lịch khác": {"type": "ask", "slot": "branch"}}
HUMAN = {"Báo lỗi": {"type": "skill", "skill": "complaint"}, "Xem lịch khác": {"type": "ask", "slot": "branch"}}



class TestIsSmalltalk(unittest.TestCase):
    def test_greetings_and_laughs(self):
        for text in ("hihi", "chào em", "Alo ad ơi", "hello shop ạ", "chào buổi sáng", "xin chào", "hehe", "chàooo", "hjhj"):
            self.assertTrue(is_smalltalk(fold(text)), text)

    def test_anything_with_content_is_not(self):
        for text in ("dạ", "ok", "chào em, cho hỏi học phí excel", "hi em muốn học robotics", "tôi", "", "ha"):
            self.assertFalse(is_smalltalk(fold(text)), text)


class TestUnderstanding(unittest.TestCase):
    def test_greeting_is_flagged_and_skips_jev(self):
        s = ConversationState("1", turns=3, slots=KNOWN, pending={"slot": "", "options": REGISTER})
        u = understand("hihi", s, CAT)
        self.assertTrue(u.greeting)
        self.assertFalse(u.tapped)
        self.assertEqual(allow_jev(u, s, CAT, 0.0), (False, "greeting"))

    def test_jev_is_never_asked_about_a_greeting_even_with_buttons_or_library_replies(self):
        s = ConversationState("1", turns=3, slots=KNOWN, pending={"slot": "", "options": REGISTER})
        u = understand("hihi", s, CAT)
        self.assertEqual(allow_jev(u, s, CAT, 0.0, text="hihi"), (False, "greeting"))

    def test_typed_reply_mapped_to_a_handoff_skill_is_asked_back(self):
        s = ConversationState("1", turns=3, slots=KNOWN, pending={"slot": "", "options": HUMAN})
        u = understand("được đó em", s, CAT)
        questions = build_questions(s, u, CAT)
        out = combine(u, {REPLY_TO_BOT: {"choice": "0", "confidence": 0.95}}, questions, s, CAT)
        self.assertNotIn("complaint", out.skills)
        self.assertEqual((out.confirm["kind"], out.confirm["skill"]), ("skill", "complaint"))
        d = decide(s, out, CAT)
        self.assertEqual(d.type, "confirm")

    def test_typed_yes_to_register_starts_the_registration_dialogue(self):
        s = ConversationState("1", turns=3, slots=KNOWN, pending={"slot": "", "options": REGISTER})
        u = understand("được đó em", s, CAT)
        questions = build_questions(s, u, CAT)
        out = combine(u, {REPLY_TO_BOT: {"choice": "0", "confidence": 0.95}}, questions, s, CAT)
        self.assertIn("register", out.skills)
        d = decide(s, out, CAT)
        self.assertEqual((d.type, d.skills), ("answer", ["register"]))  # no handoff before the class and phone (D-121)


class TestDecide(unittest.TestCase):
    def test_greeting_later_invites_a_course_and_is_not_stuck(self):
        s = ConversationState("1", turns=3, stuck_turns=1)
        d = decide(s, understand("chào em", s, CAT), CAT)
        self.assertEqual((d.type, d.ask, d.greet, d.stuck_turns, d.handoff_reason), ("ask_slot", "course", True, 0, ""))

    def test_greeting_with_a_known_course_greets_back_without_a_question(self):
        s = ConversationState("1", turns=3, stuck_turns=1, slots=KNOWN)
        d = decide(s, understand("hihi", s, CAT), CAT)
        self.assertEqual((d.type, d.ask, d.greet, d.handoff_reason), ("answer", "", True, ""))

    def test_greeting_after_handoff_is_answered(self):
        s = ConversationState("1", turns=3, status="handed_off", slots=KNOWN)
        d = decide(s, understand("chào em", s, CAT), CAT)
        self.assertEqual((d.type, d.greet), ("answer", True))

    def test_first_message_greeting_keeps_the_introduction(self):
        s = ConversationState("1")
        d = decide(s, understand("hihi", s, CAT), CAT)
        self.assertEqual((d.type, d.ask, d.greet), ("ask_slot", "course", True))
        text = " ".join(compose(d, s, CAT, render).messages)
        self.assertIn(CAT.settings["bot_name"], text)

    def test_greeting_back_names_the_course(self):
        s = ConversationState("1", turns=3, slots=KNOWN)
        d = decide(s, understand("hihi", s, CAT), CAT)
        text = " ".join(compose(d, s, CAT, render).messages)
        self.assertIn("chào", text)
        self.assertIn(CAT.courses["TE-ROBO"].name, text)
        self.assertNotIn("đăng ký", text.lower())


class TestConversation(unittest.TestCase):
    def test_hihi_after_the_register_button_never_registers(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        repo.jev = FakeJev({REPLY_TO_BOT: {"choice": "0", "confidence": 0.95}, "skill:register": {"noul": 0.95}})
        state = repo.load_state(parse_event(incoming("x", 1)))
        state.turns, state.slots, state.pending = 3, dict(KNOWN), {"slot": "", "options": REGISTER}
        repo.save_state(state)
        t = run_turn(parse_event(incoming("hihi", 10)), repo, fx, render)
        self.assertEqual((t.decision.type, t.state.status), ("answer", "active"))
        self.assertEqual(repo.jev.calls, [])
        self.assertFalse(fx.of("handoff"))


if __name__ == "__main__":
    unittest.main()
