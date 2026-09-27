### Task 1: Bot Engine â€” State Machine (Pure Logic)

**Files:**
- Create: `frappe-custom/mmm_custom/mmm_custom/bot_engine.py`
- Test: `frappe-custom/mmm_custom/mmm_custom/tests/test_bot_engine.py`

**Interfaces:**
- Consumes: Nothing (self-contained pure logic)
- Produces: `transition(state, user_input, selected_courses) -> TransitionResult`, `COURSES`, `BRANCHES`, `DONE_TOKEN`, `TransitionResult` dataclass â€” used by Task 3 (`bot_api.py`)

- [ ] **Step 1: Write the failing tests**

Create `frappe-custom/mmm_custom/mmm_custom/tests/test_bot_engine.py`:

```python
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
        result = transition(None, "xin chĂ o", [])
        self.assertEqual(result.next_state, "await_course")
        self.assertIn("EduFlow Academy", result.message)
        self.assertEqual(len(result.quick_replies), 3)
        titles = [qr["title"] for qr in result.quick_replies]
        self.assertIn("đŸ‡¬đŸ‡§ Tiáº¿ng Anh", titles)
        self.assertIn("đŸ BÆ¡i lá»™i", titles)
        self.assertIn("đŸ§® ToĂ¡n tÆ° duy", titles)
        self.assertEqual(result.actions, [])

    def test_greeting_empty_state_treated_as_greeting(self):
        result = transition("", "hi", [])
        self.assertEqual(result.next_state, "await_course")

    # --- await_course state ---

    def test_await_course_valid_selection_adds_and_offers_more(self):
        """Selecting a course adds it and offers remaining + done button."""
        result = transition("await_course", "tieng_anh", [])
        self.assertEqual(result.next_state, "await_course")
        self.assertIn("Tiáº¿ng Anh", result.message)
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
        self.assertIn("chá»n", result.message.lower())
        self.assertEqual(len(result.quick_replies), 3)  # all 3 courses

    def test_await_course_duplicate_selection_ignored(self):
        """Selecting an already-chosen course is treated as invalid input."""
        result = transition("await_course", "tieng_anh", ["tieng_anh"])
        self.assertEqual(result.next_state, "await_course")
        self.assertEqual(result.selected_courses, ["tieng_anh"])

    # --- await_branch state ---

    def test_await_branch_valid_selection_completes(self):
        """Selecting a branch transitions to completed with handoff actions."""
        result = transition("await_branch", "binh_thanh", ["tieng_anh"])
        self.assertEqual(result.next_state, "completed")
        self.assertIn("Tiáº¿ng Anh", result.message)
        self.assertIn("BĂ¬nh Tháº¡nh", result.message)
        self.assertIsNone(result.quick_replies)
        self.assertIn("update_lead", result.actions)
        self.assertIn("assign_agent", result.actions)
        self.assertIn("bot_handoff", result.actions)
        self.assertEqual(result.branch, "binh_thanh")

    def test_await_branch_invalid_input_resends_menu(self):
        """Free-text input re-sends branch menu."""
        result = transition("await_branch", "hello", ["boi_loi"])
        self.assertEqual(result.next_state, "await_branch")
        self.assertIn("chá»n", result.message.lower())
        self.assertEqual(len(result.quick_replies), 3)

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_bot_engine.py -v`
Expected: `ModuleNotFoundError: No module named 'mmm_custom.bot_engine'`

- [ ] **Step 3: Implement the bot engine**

Create `frappe-custom/mmm_custom/mmm_custom/bot_engine.py`:

```python
"""Pure-logic state machine for the EduFlow Lead Qualification Bot.

This module has ZERO side effects â€” no HTTP calls, no database access, no
imports of frappe or requests. It is a pure function: given the current state,
user input, and list of already-selected courses, it returns the next state,
the message to send, optional Quick Reply items, and a list of action tags
for the caller to execute.
"""

from dataclasses import dataclass, field


COURSES = {
    "tieng_anh": "đŸ‡¬đŸ‡§ Tiáº¿ng Anh",
    "boi_loi": "đŸ BÆ¡i lá»™i",
    "toan_tu_duy": "đŸ§® ToĂ¡n tÆ° duy",
}

BRANCHES = {
    "binh_thanh": "đŸ“ CS1 BĂ¬nh Tháº¡nh",
    "quan_1": "đŸ“ CS2 Quáº­n 1",
    "thu_duc": "đŸ“ CS3 Thá»§ Äá»©c",
}

DONE_TOKEN = "done"


@dataclass
class TransitionResult:
    next_state: str
    message: str
    quick_replies: list | None = None
    actions: list = field(default_factory=list)
    selected_courses: list = field(default_factory=list)
    branch: str | None = None


def _build_course_replies(exclude: list[str]) -> list[dict]:
    """Build Quick Reply items for courses not yet selected, plus a done button."""
    replies = []
    for key, label in COURSES.items():
        if key not in exclude:
            replies.append({"title": label, "value": key})
    replies.append({"title": "âœ… Xong, tiáº¿p tá»¥c", "value": DONE_TOKEN})
    return replies


def _build_branch_replies() -> list[dict]:
    """Build Quick Reply items for all branches."""
    return [{"title": label, "value": key} for key, label in BRANCHES.items()]


def _format_courses_display(course_keys: list[str]) -> str:
    """Format selected course keys into a human-readable Vietnamese string."""
    return ", ".join(COURSES.get(k, k) for k in course_keys)


def _greeting() -> TransitionResult:
    """Handle the initial greeting state."""
    replies = [{"title": label, "value": key} for key, label in COURSES.items()]
    return TransitionResult(
        next_state="await_course",
        message=(
            "đŸ“ ChĂ o báº¡n! EduFlow Academy ráº¥t vui Ä‘Æ°á»£c há»— trá»£.\n"
            "Báº¡n Ä‘ang quan tĂ¢m Ä‘áº¿n bá»™ mĂ´n nĂ o áº¡?"
        ),
        quick_replies=replies,
        selected_courses=[],
    )


def _ask_branch(selected_courses: list[str]) -> TransitionResult:
    """Transition to the branch selection step."""
    return TransitionResult(
        next_state="await_branch",
        message="đŸ“ Tuyá»‡t vá»i! Báº¡n muá»‘n há»c táº¡i cÆ¡ sá»Ÿ nĂ o áº¡?",
        quick_replies=_build_branch_replies(),
        selected_courses=list(selected_courses),
    )


def _invalid_input_reminder(state: str, quick_replies: list[dict],
                            selected_courses: list[str]) -> TransitionResult:
    """Re-send the current menu with a gentle reminder."""
    return TransitionResult(
        next_state=state,
        message="Báº¡n vui lĂ²ng chá»n má»™t trong cĂ¡c tĂ¹y chá»n bĂªn dÆ°á»›i nhĂ© đŸ‘‡",
        quick_replies=quick_replies,
        selected_courses=list(selected_courses),
    )


def transition(state: str | None, user_input: str,
               selected_courses: list[str]) -> TransitionResult | None:
    """Compute the next state given current state, user input, and context.

    Args:
        state: Current bot state (None/"" for new conversations).
        user_input: The text content of the customer's message, or the
                    Quick Reply ``value`` if they tapped a button.
        selected_courses: List of course keys already selected.

    Returns:
        A TransitionResult describing what to do next, or None if the
        conversation is completed and should be ignored.
    """
    if not state or state == "greeting":
        return _greeting()

    if state == "completed":
        return None

    if state == "await_course":
        user_input_clean = user_input.strip().lower() if user_input else ""

        # "Done" â†’ transition to branch if at least one course selected
        if user_input_clean == DONE_TOKEN and selected_courses:
            return _ask_branch(selected_courses)

        # Valid course selection
        if user_input_clean in COURSES and user_input_clean not in selected_courses:
            new_courses = list(selected_courses) + [user_input_clean]

            # All courses selected â†’ auto-transition to branch
            if len(new_courses) >= len(COURSES):
                result = _ask_branch(new_courses)
                courses_display = _format_courses_display(new_courses)
                result.message = (
                    f"ÄĂ£ ghi nháº­n {courses_display} âœ…\n\n" + result.message
                )
                return result

            # Still courses remaining â†’ offer more
            course_label = COURSES[user_input_clean]
            return TransitionResult(
                next_state="await_course",
                message=(
                    f"ÄĂ£ ghi nháº­n {course_label} âœ…\n"
                    "Báº¡n muá»‘n Ä‘Äƒng kĂ½ thĂªm bá»™ mĂ´n nĂ o khĂ´ng?"
                ),
                quick_replies=_build_course_replies(new_courses),
                selected_courses=new_courses,
            )

        # Invalid input (free-text or duplicate selection)
        return _invalid_input_reminder(
            "await_course",
            _build_course_replies(selected_courses) if selected_courses
            else [{"title": label, "value": key} for key, label in COURSES.items()],
            selected_courses,
        )

    if state == "await_branch":
        user_input_clean = user_input.strip().lower() if user_input else ""

        if user_input_clean in BRANCHES:
            branch_label = BRANCHES[user_input_clean]
            courses_display = _format_courses_display(selected_courses)
            return TransitionResult(
                next_state="completed",
                message=(
                    f"âœ… Cáº£m Æ¡n báº¡n Ä‘Ă£ cung cáº¥p thĂ´ng tin!\n"
                    f"đŸ“ Bá»™ mĂ´n: {courses_display}\n"
                    f"đŸ“ CÆ¡ sá»Ÿ: {branch_label}\n\n"
                    f"ChuyĂªn viĂªn tÆ° váº¥n sáº½ liĂªn há»‡ báº¡n ngay bĂ¢y giá» nhĂ©! đŸ˜"
                ),
                quick_replies=None,
                actions=["update_lead", "assign_agent", "bot_handoff"],
                selected_courses=list(selected_courses),
                branch=user_input_clean,
            )

        return _invalid_input_reminder(
            "await_branch", _build_branch_replies(), selected_courses
        )

    # Unknown state â€” treat as greeting
    return _greeting()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -p "test_bot_engine.py" -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/bot_engine.py frappe-custom/mmm_custom/mmm_custom/tests/test_bot_engine.py
git commit -m "feat(bot): add pure-logic state machine for lead qualification flow"
```

---


