import sys
from pathlib import Path
import unittest

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.bot_engine import (
    BRANCHES,
    COURSES,
    DONE_TOKEN,
    TransitionResult,
    transition,
)


class TestBotEngineTransitions(unittest.TestCase):
    """Tests for the pure state machine transition function."""

    # --- greeting state ---

    def test_greeting_any_message_sends_course_menu(self):
        """First message from customer triggers greeting + course Quick Replies."""
        result = transition(None, "xin chào", [])
        self.assertEqual(result.next_state, "await_course")
        self.assertIn("EduFlow Academy", result.message)
        self.assertEqual(len(result.quick_replies), 3)
        titles = [qr["title"] for qr in result.quick_replies]
        self.assertIn("🇬🇧 Tiếng Anh", titles)
        self.assertIn("🏊 Bơi lội", titles)
        self.assertIn("🧮 Toán tư duy", titles)
        self.assertEqual(result.actions, [])

    def test_greeting_empty_state_treated_as_greeting(self):
        result = transition("", "hi", [])
        self.assertEqual(result.next_state, "await_course")

    # --- await_course state ---

    def test_await_course_valid_selection_adds_and_offers_more(self):
        """Selecting a course adds it and offers remaining + done button."""
        result = transition("await_course", "tieng_anh", [])
        self.assertEqual(result.next_state, "await_course")
        self.assertIn("Tiếng Anh", result.message)
        self.assertEqual(len(result.quick_replies), 3)  # 2 remaining + done
        values = [qr["value"] for qr in result.quick_replies]
        self.assertNotIn("tieng_anh", values)
        self.assertIn(DONE_TOKEN, values)
        self.assertEqual(result.selected_courses, ["tieng_anh"])

    def test_await_course_second_selection(self):
        """Selecting a second course narrows options further."""
        result = transition("await_course", "boi_loi", ["tieng_anh"])
        self.assertEqual(result.next_state, "await_course")
        self.assertEqual(len(result.quick_replies), 2)  # 1 remaining + done
        self.assertEqual(result.selected_courses, ["tieng_anh", "boi_loi"])

    def test_await_course_all_three_selected_auto_transitions(self):
        """Selecting all 3 courses auto-transitions to await_branch."""
        result = transition("await_course", "toan_tu_duy", ["tieng_anh", "boi_loi"])
        self.assertEqual(result.next_state, "await_branch")
        self.assertEqual(len(result.quick_replies), 3)  # 3 branches
        values = [qr["value"] for qr in result.quick_replies]
        self.assertIn("binh_thanh", values)
        self.assertEqual(result.selected_courses, ["tieng_anh", "boi_loi", "toan_tu_duy"])

    def test_await_course_done_token_transitions_to_branch(self):
        """Tapping 'Xong' transitions to await_branch."""
        result = transition("await_course", DONE_TOKEN, ["tieng_anh"])
        self.assertEqual(result.next_state, "await_branch")
        self.assertEqual(len(result.quick_replies), 3)  # 3 branches
        self.assertEqual(result.selected_courses, ["tieng_anh"])

    def test_await_course_invalid_input_resends_menu(self):
        """Free-text input re-sends course menu with reminder."""
        result = transition("await_course", "random text", [])
        self.assertEqual(result.next_state, "await_course")
        self.assertIn("chọn", result.message.lower())
        self.assertEqual(len(result.quick_replies), 3)  # all 3 courses

    def test_await_course_duplicate_selection_ignored(self):
        """Selecting an already-chosen course is treated as invalid input."""
        result = transition("await_course", "tieng_anh", ["tieng_anh"])
        self.assertEqual(result.next_state, "await_course")
        self.assertEqual(result.selected_courses, ["tieng_anh"])

    # --- await_branch state ---

    def test_await_branch_valid_selection_transitions_to_phone(self):
        """Selecting a branch transitions to await_phone (asks for SĐT)."""
        result = transition("await_branch", "binh_thanh", ["tieng_anh"])
        self.assertEqual(result.next_state, "await_phone")
        self.assertIn("số điện thoại", result.message.lower())
        self.assertIsNotNone(result.quick_replies)  # skip button
        self.assertEqual(result.branch, "binh_thanh")

    def test_await_branch_invalid_input_resends_menu(self):
        """Free-text input re-sends branch menu."""
        result = transition("await_branch", "hello", ["boi_loi"])
        self.assertEqual(result.next_state, "await_branch")
        self.assertIn("chọn", result.message.lower())
        self.assertEqual(len(result.quick_replies), 3)

    # --- button title & flexible input matching ---

    def test_await_course_facebook_button_title_matched(self):
        """Facebook Messenger sends the button title '🇬🇧 Tiếng Anh' instead of 'tieng_anh'."""
        result = transition("await_course", "🇬🇧 Tiếng Anh", [])
        self.assertEqual(result.next_state, "await_course")
        self.assertIn("Tiếng Anh", result.message)
        self.assertEqual(result.selected_courses, ["tieng_anh"])

    def test_await_course_done_button_title_matched(self):
        """Facebook Messenger sends '✅ Xong, tiếp tục' when the user taps Done."""
        result = transition("await_course", "✅ Xong, tiếp tục", ["tieng_anh"])
        self.assertEqual(result.next_state, "await_branch")
        self.assertEqual(result.selected_courses, ["tieng_anh"])

    def test_await_branch_facebook_button_title_matched(self):
        """Facebook Messenger sends '📍 CS1 Bình Thạnh' when the user taps Branch."""
        result = transition("await_branch", "📍 CS1 Bình Thạnh", ["tieng_anh"])
        self.assertEqual(result.next_state, "await_phone")
        self.assertEqual(result.branch, "binh_thanh")

    # --- await_phone state ---

    def test_await_phone_valid_number_completes(self):
        """A valid VN phone number completes the flow with handoff actions."""
        result = transition("await_phone", "0901234567", ["tieng_anh"])
        self.assertEqual(result.next_state, "completed")
        self.assertEqual(result.phone, "+84901234567")
        self.assertIn("update_lead", result.actions)
        self.assertIn("assign_agent", result.actions)
        self.assertIn("bot_handoff", result.actions)
        self.assertIn("+84901234567", result.message)

    def test_await_phone_plus84_format(self):
        """Phone with +84 prefix is accepted."""
        result = transition("await_phone", "+84901234567", ["boi_loi"])
        self.assertEqual(result.next_state, "completed")
        self.assertEqual(result.phone, "+84901234567")

    def test_await_phone_with_spaces(self):
        """Phone with spaces/dashes is accepted."""
        result = transition("await_phone", "090 123 4567", ["boi_loi"])
        self.assertEqual(result.next_state, "completed")
        self.assertEqual(result.phone, "+84901234567")

    def test_await_phone_skip(self):
        """Skip button works — completes without phone."""
        result = transition("await_phone", "skip_phone", ["tieng_anh"])
        self.assertEqual(result.next_state, "completed")
        self.assertIsNone(result.phone)
        self.assertIn("update_lead", result.actions)

    def test_await_phone_skip_vietnamese(self):
        """Vietnamese skip works too."""
        result = transition("await_phone", "bỏ qua", ["tieng_anh"])
        self.assertEqual(result.next_state, "completed")
        self.assertIsNone(result.phone)

    def test_await_phone_invalid_resends(self):
        """Invalid phone re-asks with error message."""
        result = transition("await_phone", "abc123", ["tieng_anh"])
        self.assertEqual(result.next_state, "await_phone")
        self.assertIn("chưa đúng", result.message.lower())
        self.assertIsNotNone(result.quick_replies)

    def test_await_phone_too_short(self):
        """Too-short number is rejected."""
        result = transition("await_phone", "0901234", ["tieng_anh"])
        self.assertEqual(result.next_state, "await_phone")

    # --- completed state ---

    def test_completed_state_returns_noop(self):
        """Messages in completed state are ignored (human agent handles)."""
        result = transition("completed", "any message", ["tieng_anh"])
        self.assertIsNone(result)


class TestTransitionResultDataclass(unittest.TestCase):
    def test_fields_exist(self):
        r = TransitionResult(
            next_state="await_course",
            message="hello",
            quick_replies=[{"title": "A", "value": "a"}],
            actions=[],
            selected_courses=["tieng_anh"],
            branch=None,
        )
        self.assertEqual(r.next_state, "await_course")
        self.assertEqual(r.branch, None)


if __name__ == "__main__":
    unittest.main()
