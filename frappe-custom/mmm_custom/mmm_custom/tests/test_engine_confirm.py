import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, fill, render

from mmm_custom.engine.decide import Decision, decide
from mmm_custom.engine.reply import compose
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding, understand

CAT = demo_catalog()
CONFIRM = {"kind": "slot", "slot": "course", "value": "VKT-REVIT", "label": "Revit kiến trúc"}


def pending_state(confirm=CONFIRM):
    options = {"Đúng ạ": {"type": "confirm_yes", **confirm}, "Không phải": {"type": "confirm_no", **confirm}}
    return ConversationState("1", turns=1, pending={"slot": "", "options": options, "confirm": confirm})


class TestUnderstandConfirmation(unittest.TestCase):
    def test_yes_tap_fills_as_confirmed(self):
        u = understand("Đúng ạ", pending_state(), CAT)
        self.assertEqual(u.fills["course"], {"value": "VKT-REVIT", "source": "confirmed", "confidence": 1.0})

    def test_no_tap_rejects_and_focuses_the_slot(self):
        u = understand("Không phải", pending_state(), CAT)
        self.assertEqual((u.focus, u.rejected["value"], u.fills), ("course", "VKT-REVIT", {}))

    def test_typed_yes_or_no_answers_the_confirmation(self):
        self.assertEqual(understand("dung roi", pending_state(), CAT).fills["course"]["value"], "VKT-REVIT")
        u = understand("không", pending_state(), CAT)
        self.assertTrue(u.tapped)
        self.assertEqual(u.rejected["slot"], "course")

    def test_other_text_is_understood_normally(self):
        u = understand("revit", pending_state(), CAT)
        self.assertEqual((u.rejected, u.fills["course"]["value"]), ({}, "VKT-REVIT"))

    def test_skill_confirmation(self):
        c = {"kind": "skill", "skill": "fee_quote", "label": "học phí"}
        self.assertEqual(understand("Đúng ạ", pending_state(c), CAT).skills, ["fee_quote"])


class TestConfirmDecision(unittest.TestCase):
    def test_confirm_instead_of_asking_the_next_slot(self):
        d = decide(ConversationState("1", turns=1), Understanding(confirm=CONFIRM), CAT)
        self.assertEqual((d.type, d.confirm, d.ask, d.stuck_turns), ("confirm", CONFIRM, "", 0))
        self.assertIn("Revit kiến trúc", d.reason)

    def test_first_turn_confirmation_is_greeted(self):
        self.assertTrue(decide(ConversationState("1"), Understanding(confirm=CONFIRM), CAT).greet)

    def test_skills_are_still_answered_with_the_confirmation(self):
        d = decide(ConversationState("1", turns=1), Understanding(confirm=CONFIRM, skills=["hotline"]), CAT)
        self.assertEqual((d.type, d.skills), ("confirm", ["hotline"]))

    def test_handoff_button_beats_a_confirmation(self):
        d = decide(ConversationState("1", turns=1), Understanding(confirm=CONFIRM, handoff=True), CAT)
        self.assertEqual(d.type, "handoff")

    def test_required_filled_waits_for_the_confirmation(self):
        slots = {"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An"), "phone": fill("+84901234567")}
        c = {"kind": "slot", "slot": "preferred_shift", "value": "evening", "label": "Tối"}
        d = decide(ConversationState("1", turns=1, slots=slots), Understanding(confirm=c), CAT)
        self.assertEqual(d.type, "confirm")

    def test_rejected_confirmation_reasks_even_an_asked_optional_slot(self):
        slots = {"course": fill("VP-EXCEL"), "preferred_shift": {"asked": 1}}
        u = Understanding(focus="preferred_shift", rejected={"slot": "preferred_shift"})
        self.assertEqual(decide(ConversationState("1", turns=2, slots=slots), u, CAT).ask, "preferred_shift")


class TestConfirmReply(unittest.TestCase):
    def test_confirm_paragraph_and_two_buttons(self):
        r = compose(Decision("confirm", confirm=CONFIRM), ConversationState("1", turns=1), CAT, render)
        self.assertEqual(r.messages, ["Dạ ý anh/chị là Revit kiến trúc phải không ạ?"])
        self.assertEqual([b["title"] for b in r.buttons], ["Đúng ạ", "Không phải"])
        self.assertEqual(r.buttons[1]["action"], {"type": "confirm_no", **CONFIRM})

    def test_skill_confirmation_wording(self):
        c = {"kind": "skill", "skill": "fee_quote", "label": "học phí"}
        r = compose(Decision("confirm", confirm=c), ConversationState("1", turns=1), CAT, render)
        self.assertEqual(r.messages, ["Dạ anh/chị muốn hỏi về học phí phải không ạ?"])


if __name__ == "__main__":
    unittest.main()
