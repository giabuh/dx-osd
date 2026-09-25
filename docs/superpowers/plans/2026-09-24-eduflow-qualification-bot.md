# EduFlow Lead Qualification Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated conversational bot that qualifies Facebook Messenger leads through Quick Reply buttons (course interest + branch), then hands off to the best-match human agent.

**Architecture:** A new Frappe whitelist endpoint (`mmm_custom.bot_api.agent_bot_webhook`) receives Agent Bot webhooks from Chatwoot, runs a pure-Python state machine to determine the next response, sends Quick Reply messages via Chatwoot REST API, and on completion updates the CRM Lead and assigns the best-match agent via round-robin.

**Tech Stack:** Python 3.10+, Frappe Framework (AGPLv3), Chatwoot REST API v1, `requests` library, `unittest` + `unittest.mock`

**Spec:** `docs/superpowers/specs/2026-09-24-eduflow-lead-qualification-bot-design.md`

## Global Constraints

- 100% OSI-approved FOSS — all new code under MIT (inside `mmm_custom`).
- Every web port binds to `127.0.0.1` only.
- Edits in vendored directories (`chatwoot/`, `crm/`) must be recorded in `docs/vendored-upstreams.md`.
- Bot messages in Vietnamese; code, comments, commits in English.
- Security: HMAC-SHA256 webhook validation, no secrets in code.
- No new Docker containers — bot engine runs inside the existing Frappe bench.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `frappe-custom/mmm_custom/mmm_custom/bot_engine.py` | Create | Pure-logic state machine (zero side effects) |
| `frappe-custom/mmm_custom/mmm_custom/chatwoot_client.py` | Create | Thin REST client for Chatwoot API v1 |
| `frappe-custom/mmm_custom/mmm_custom/bot_api.py` | Create | Webhook endpoint + orchestrator |
| `frappe-custom/mmm_custom/mmm_custom/setup.py` | Modify | Add `branch` custom field to CRM Lead |
| `frappe-custom/mmm_custom/mmm_custom/tests/test_bot_engine.py` | Create | Unit tests for state machine |
| `frappe-custom/mmm_custom/mmm_custom/tests/test_chatwoot_client.py` | Create | Unit tests for Chatwoot client |
| `frappe-custom/mmm_custom/mmm_custom/tests/test_bot_api.py` | Create | Unit tests for webhook endpoint |
| `scripts/setup-agent-bot.py` | Create | One-time setup: create Agent Bot + link to inbox |

---

### Task 1: Bot Engine — State Machine (Pure Logic)

**Files:**
- Create: `frappe-custom/mmm_custom/mmm_custom/bot_engine.py`
- Test: `frappe-custom/mmm_custom/mmm_custom/tests/test_bot_engine.py`

**Interfaces:**
- Consumes: Nothing (self-contained pure logic)
- Produces: `transition(state, user_input, selected_courses) -> TransitionResult`, `COURSES`, `BRANCHES`, `DONE_TOKEN`, `TransitionResult` dataclass — used by Task 3 (`bot_api.py`)

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

    def test_await_branch_valid_selection_completes(self):
        """Selecting a branch transitions to completed with handoff actions."""
        result = transition("await_branch", "binh_thanh", ["tieng_anh"])
        self.assertEqual(result.next_state, "completed")
        self.assertIn("Tiếng Anh", result.message)
        self.assertIn("Bình Thạnh", result.message)
        self.assertIsNone(result.quick_replies)
        self.assertIn("update_lead", result.actions)
        self.assertIn("assign_agent", result.actions)
        self.assertIn("bot_handoff", result.actions)
        self.assertEqual(result.branch, "binh_thanh")

    def test_await_branch_invalid_input_resends_menu(self):
        """Free-text input re-sends branch menu."""
        result = transition("await_branch", "hello", ["boi_loi"])
        self.assertEqual(result.next_state, "await_branch")
        self.assertIn("chọn", result.message.lower())
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

This module has ZERO side effects — no HTTP calls, no database access, no
imports of frappe or requests. It is a pure function: given the current state,
user input, and list of already-selected courses, it returns the next state,
the message to send, optional Quick Reply items, and a list of action tags
for the caller to execute.
"""

from dataclasses import dataclass, field


COURSES = {
    "tieng_anh": "🇬🇧 Tiếng Anh",
    "boi_loi": "🏊 Bơi lội",
    "toan_tu_duy": "🧮 Toán tư duy",
}

BRANCHES = {
    "binh_thanh": "📍 CS1 Bình Thạnh",
    "quan_1": "📍 CS2 Quận 1",
    "thu_duc": "📍 CS3 Thủ Đức",
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
    replies.append({"title": "✅ Xong, tiếp tục", "value": DONE_TOKEN})
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
            "🎓 Chào bạn! EduFlow Academy rất vui được hỗ trợ.\n"
            "Bạn đang quan tâm đến bộ môn nào ạ?"
        ),
        quick_replies=replies,
        selected_courses=[],
    )


def _ask_branch(selected_courses: list[str]) -> TransitionResult:
    """Transition to the branch selection step."""
    return TransitionResult(
        next_state="await_branch",
        message="📍 Tuyệt vời! Bạn muốn học tại cơ sở nào ạ?",
        quick_replies=_build_branch_replies(),
        selected_courses=list(selected_courses),
    )


def _invalid_input_reminder(state: str, quick_replies: list[dict],
                            selected_courses: list[str]) -> TransitionResult:
    """Re-send the current menu with a gentle reminder."""
    return TransitionResult(
        next_state=state,
        message="Bạn vui lòng chọn một trong các tùy chọn bên dưới nhé 👇",
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

        # "Done" → transition to branch if at least one course selected
        if user_input_clean == DONE_TOKEN and selected_courses:
            return _ask_branch(selected_courses)

        # Valid course selection
        if user_input_clean in COURSES and user_input_clean not in selected_courses:
            new_courses = list(selected_courses) + [user_input_clean]

            # All courses selected → auto-transition to branch
            if len(new_courses) >= len(COURSES):
                result = _ask_branch(new_courses)
                courses_display = _format_courses_display(new_courses)
                result.message = (
                    f"Đã ghi nhận {courses_display} ✅\n\n" + result.message
                )
                return result

            # Still courses remaining → offer more
            course_label = COURSES[user_input_clean]
            return TransitionResult(
                next_state="await_course",
                message=(
                    f"Đã ghi nhận {course_label} ✅\n"
                    "Bạn muốn đăng ký thêm bộ môn nào không?"
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
                    f"✅ Cảm ơn bạn đã cung cấp thông tin!\n"
                    f"📚 Bộ môn: {courses_display}\n"
                    f"📍 Cơ sở: {branch_label}\n\n"
                    f"Chuyên viên tư vấn sẽ liên hệ bạn ngay bây giờ nhé! 😊"
                ),
                quick_replies=None,
                actions=["update_lead", "assign_agent", "bot_handoff"],
                selected_courses=list(selected_courses),
                branch=user_input_clean,
            )

        return _invalid_input_reminder(
            "await_branch", _build_branch_replies(), selected_courses
        )

    # Unknown state — treat as greeting
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

### Task 2: Chatwoot REST Client

**Files:**
- Create: `frappe-custom/mmm_custom/mmm_custom/chatwoot_client.py`
- Test: `frappe-custom/mmm_custom/mmm_custom/tests/test_chatwoot_client.py`

**Interfaces:**
- Consumes: Nothing (self-contained HTTP wrapper)
- Produces: `ChatwootClient(base_url, api_token, account_id)` with methods:
  - `.send_message(conversation_id, content, content_type="text", content_attributes=None) -> dict`
  - `.send_quick_replies(conversation_id, content, items) -> dict`
  - `.update_contact(contact_id, custom_attributes) -> dict`
  - `.toggle_status(conversation_id, status) -> dict`
  - `.assign_conversation(conversation_id, assignee_id) -> dict`
  - `.list_agents() -> list[dict]`
  - `.list_agent_conversations(agent_id, status="open") -> list[dict]`

- [ ] **Step 1: Write the failing tests**

Create `frappe-custom/mmm_custom/mmm_custom/tests/test_chatwoot_client.py`:

```python
import sys
from pathlib import Path
import json
import unittest
from unittest.mock import patch, MagicMock

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

if "requests" not in sys.modules:
    sys.modules["requests"] = MagicMock()

from mmm_custom.chatwoot_client import ChatwootClient


class TestChatwootClient(unittest.TestCase):
    def setUp(self):
        self.client = ChatwootClient(
            base_url="http://localhost:3000",
            api_token="test_token_123",
            account_id=1,
        )

    @patch("mmm_custom.chatwoot_client.requests")
    def test_send_message_plain_text(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": 1}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        result = self.client.send_message(42, "Hello world")

        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        self.assertIn("/conversations/42/messages", call_args[0][0])
        body = call_args[1]["json"]
        self.assertEqual(body["content"], "Hello world")
        self.assertEqual(body["message_type"], "outgoing")

    @patch("mmm_custom.chatwoot_client.requests")
    def test_send_quick_replies(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": 2}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        items = [{"title": "A", "value": "a"}, {"title": "B", "value": "b"}]
        result = self.client.send_quick_replies(42, "Pick one", items)

        call_args = mock_requests.post.call_args
        body = call_args[1]["json"]
        self.assertEqual(body["content_type"], "input_select")
        self.assertEqual(body["content_attributes"]["items"], items)

    @patch("mmm_custom.chatwoot_client.requests")
    def test_update_contact(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": 10}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.patch.return_value = mock_resp

        self.client.update_contact(10, {"bot_state": "await_course"})

        call_args = mock_requests.patch.call_args
        self.assertIn("/contacts/10", call_args[0][0])
        body = call_args[1]["json"]
        self.assertEqual(body["custom_attributes"]["bot_state"], "await_course")

    @patch("mmm_custom.chatwoot_client.requests")
    def test_toggle_status(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "open"}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        self.client.toggle_status(42, "open")

        call_args = mock_requests.post.call_args
        self.assertIn("/conversations/42/toggle_status", call_args[0][0])
        self.assertEqual(call_args[1]["json"]["status"], "open")

    @patch("mmm_custom.chatwoot_client.requests")
    def test_assign_conversation(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        self.client.assign_conversation(42, 7)

        call_args = mock_requests.post.call_args
        self.assertIn("/conversations/42/assignments", call_args[0][0])
        self.assertEqual(call_args[1]["json"]["assignee_id"], 7)

    @patch("mmm_custom.chatwoot_client.requests")
    def test_list_agents(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"id": 1, "name": "Agent A"}]
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        agents = self.client.list_agents()

        self.assertEqual(len(agents), 1)
        mock_requests.get.assert_called_once()

    @patch("mmm_custom.chatwoot_client.requests")
    def test_auth_header_included(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        self.client.list_agents()

        call_args = mock_requests.get.call_args
        self.assertEqual(call_args[1]["headers"]["api_access_token"], "test_token_123")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_chatwoot_client.py -v`
Expected: `ModuleNotFoundError: No module named 'mmm_custom.chatwoot_client'`

- [ ] **Step 3: Implement the Chatwoot client**

Create `frappe-custom/mmm_custom/mmm_custom/chatwoot_client.py`:

```python
"""Thin REST client for the Chatwoot API v1.

Used by the bot engine to send messages, update contacts, toggle conversation
status, and assign agents. All methods are synchronous and raise on HTTP errors.
"""

import logging

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # seconds


class ChatwootClient:
    """Wrapper around Chatwoot's Account-scoped REST API v1."""

    def __init__(self, base_url: str, api_token: str, account_id: int):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.account_id = account_id

    @property
    def _base(self) -> str:
        return f"{self.base_url}/api/v1/accounts/{self.account_id}"

    @property
    def _headers(self) -> dict:
        return {"api_access_token": self.api_token}

    def send_message(self, conversation_id: int, content: str,
                     content_type: str = "text",
                     content_attributes: dict | None = None) -> dict:
        """Send a message in a conversation."""
        payload = {
            "content": content,
            "message_type": "outgoing",
            "content_type": content_type,
        }
        if content_attributes:
            payload["content_attributes"] = content_attributes
        resp = requests.post(
            f"{self._base}/conversations/{conversation_id}/messages",
            headers=self._headers, json=payload, timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def send_quick_replies(self, conversation_id: int, content: str,
                           items: list[dict]) -> dict:
        """Send a message with Quick Reply buttons (input_select)."""
        return self.send_message(
            conversation_id, content,
            content_type="input_select",
            content_attributes={"items": items},
        )

    def update_contact(self, contact_id: int,
                       custom_attributes: dict) -> dict:
        """Update a contact's custom_attributes."""
        resp = requests.patch(
            f"{self._base}/contacts/{contact_id}",
            headers=self._headers,
            json={"custom_attributes": custom_attributes},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def toggle_status(self, conversation_id: int, status: str) -> dict:
        """Toggle a conversation's status (e.g. pending -> open)."""
        resp = requests.post(
            f"{self._base}/conversations/{conversation_id}/toggle_status",
            headers=self._headers, json={"status": status},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def assign_conversation(self, conversation_id: int,
                            assignee_id: int) -> dict:
        """Assign a conversation to an agent."""
        resp = requests.post(
            f"{self._base}/conversations/{conversation_id}/assignments",
            headers=self._headers, json={"assignee_id": assignee_id},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def list_agents(self) -> list[dict]:
        """List all agents in the account."""
        resp = requests.get(
            f"{self._base}/agents",
            headers=self._headers, timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def list_agent_conversations(self, agent_id: int,
                                 status: str = "open") -> list[dict]:
        """List conversations assigned to a specific agent."""
        resp = requests.get(
            f"{self._base}/conversations",
            headers=self._headers,
            params={"assignee_type": "assigned", "status": status},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        # Filter to only this agent's conversations
        convos = data.get("data", {}).get("payload", []) if isinstance(data, dict) else []
        return [c for c in convos
                if c.get("meta", {}).get("assignee", {}).get("id") == agent_id]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_chatwoot_client.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/chatwoot_client.py frappe-custom/mmm_custom/mmm_custom/tests/test_chatwoot_client.py
git commit -m "feat(bot): add Chatwoot REST API client for bot messaging"
```

---

### Task 3: Bot Webhook Endpoint + CRM Integration

**Files:**
- Create: `frappe-custom/mmm_custom/mmm_custom/bot_api.py`
- Modify: `frappe-custom/mmm_custom/mmm_custom/setup.py` (add `branch` field)
- Test: `frappe-custom/mmm_custom/mmm_custom/tests/test_bot_api.py`

**Interfaces:**
- Consumes:
  - `bot_engine.transition(state, user_input, selected_courses) -> TransitionResult` from Task 1
  - `ChatwootClient(base_url, api_token, account_id)` from Task 2
  - `dedupe.find_matching_lead(email, phone)` and `dedupe.normalize_phone(phone)` from existing code
- Produces: `agent_bot_webhook()` — Frappe whitelist endpoint at `mmm_custom.bot_api.agent_bot_webhook`

- [ ] **Step 1: Write the failing tests**

Create `frappe-custom/mmm_custom/mmm_custom/tests/test_bot_api.py`:

```python
import hashlib
import hmac
import json
import sys
from pathlib import Path
import time
import unittest
from unittest.mock import MagicMock, patch, call

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

if "requests" not in sys.modules:
    sys.modules["requests"] = MagicMock()

import mmm_custom.bot_api as bot_api_mod
from mmm_custom.bot_api import agent_bot_webhook


def compute_sig(secret: str, ts: str, body: bytes) -> str:
    msg = f"{ts}.".encode("utf-8") + body
    return "sha256=" + hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def make_message_created_payload(
    content="hello",
    message_type=0,
    conversation_id=1,
    contact_id=10,
    contact_name="Test User",
    custom_attributes=None,
):
    """Build a minimal Agent Bot webhook payload for message_created."""
    return {
        "event": "message_created",
        "content_type": "text",
        "content": content,
        "message_type": message_type,
        "conversation": {
            "id": conversation_id,
            "status": "pending",
            "contact_inbox": {
                "contact": {
                    "id": contact_id,
                    "name": contact_name,
                    "email": "test@example.com",
                    "phone_number": "0901234567",
                    "custom_attributes": custom_attributes or {},
                }
            },
        },
        "sender": {"id": contact_id, "name": contact_name, "type": "contact"},
    }


class TestBotApiWebhook(unittest.TestCase):
    def setUp(self):
        self.secret = "bot_webhook_secret_test"
        self.conf = {
            "chatwoot_bot_webhook_secret": self.secret,
            "chatwoot_bot_api_token": "mock_bot_token",
            "chatwoot_bot_account_id": 1,
            "chatwoot_base_url": "http://localhost:3000",
        }
        self.mock_frappe = MagicMock()
        self.mock_frappe.conf = self.conf
        self.mock_frappe.AuthenticationError = bot_api_mod.frappe.AuthenticationError
        self.mock_frappe.throw = bot_api_mod.frappe.throw

    def _setup_request(self, payload_dict, ts=None, sig=None):
        body = json.dumps(payload_dict).encode("utf-8")
        ts = ts or str(int(time.time()))
        sig = sig or compute_sig(self.secret, ts, body)
        mock_req = MagicMock()
        mock_req.headers = {
            "X-Chatwoot-Signature": sig,
            "X-Chatwoot-Timestamp": ts,
        }
        mock_req.get_data.return_value = body
        mock_req.data = body
        self.mock_frappe.request = mock_req
        return body

    def test_invalid_hmac_rejected(self):
        payload = make_message_created_payload()
        self._setup_request(payload, sig="sha256=invalid")
        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            with self.assertRaises(self.mock_frappe.AuthenticationError):
                agent_bot_webhook()

    def test_outgoing_message_ignored(self):
        payload = make_message_created_payload(message_type=1)
        self._setup_request(payload)
        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            with patch.object(bot_api_mod, "ChatwootClient"):
                result = agent_bot_webhook()
                self.assertEqual(result["status"], "ignored")

    def test_non_message_created_event_ignored(self):
        payload = {"event": "conversation_resolved"}
        self._setup_request(payload)
        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            result = agent_bot_webhook()
            self.assertEqual(result["status"], "ignored")

    def test_greeting_sends_course_quick_replies(self):
        payload = make_message_created_payload(content="xin chào")
        self._setup_request(payload)
        mock_client = MagicMock()
        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            with patch.object(bot_api_mod, "ChatwootClient", return_value=mock_client):
                result = agent_bot_webhook()
                self.assertEqual(result["status"], "ok")
                mock_client.send_quick_replies.assert_called_once()
                call_args = mock_client.send_quick_replies.call_args
                self.assertIn("EduFlow", call_args[0][1])
                mock_client.update_contact.assert_called_once()

    def test_completed_state_is_noop(self):
        payload = make_message_created_payload(
            content="any",
            custom_attributes={"bot_state": "completed"},
        )
        self._setup_request(payload)
        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            with patch.object(bot_api_mod, "ChatwootClient") as MockClient:
                result = agent_bot_webhook()
                self.assertEqual(result["status"], "ignored")
                MockClient.return_value.send_message.assert_not_called()
                MockClient.return_value.send_quick_replies.assert_not_called()

    def test_branch_selection_triggers_handoff(self):
        payload = make_message_created_payload(
            content="binh_thanh",
            custom_attributes={
                "bot_state": "await_branch",
                "bot_courses": ["tieng_anh"],
            },
        )
        self._setup_request(payload)
        mock_client = MagicMock()
        mock_client.list_agents.return_value = [
            {"id": 1, "name": "Agent A", "custom_attributes": {"branch": "binh_thanh"}},
            {"id": 2, "name": "Agent B", "custom_attributes": {"branch": "quan_1"}},
        ]
        mock_client.list_agent_conversations.return_value = []

        self.mock_frappe.db.exists.return_value = False
        mock_lead = MagicMock()
        mock_lead.name = "CRM-LEAD-BOT-001"
        mock_lead.insert.return_value = mock_lead
        self.mock_frappe.get_doc.return_value = mock_lead

        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            with patch.object(bot_api_mod, "ChatwootClient", return_value=mock_client):
                with patch("mmm_custom.bot_api.find_matching_lead", return_value=None):
                    result = agent_bot_webhook()

        self.assertEqual(result["status"], "ok")
        mock_client.send_message.assert_called_once()  # confirmation message
        mock_client.assign_conversation.assert_called_once_with(1, 1)  # agent 1 matches branch
        mock_client.toggle_status.assert_called_once_with(1, "open")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_bot_api.py -v`
Expected: `ModuleNotFoundError: No module named 'mmm_custom.bot_api'`

- [ ] **Step 3: Add `branch` custom field to setup.py**

Modify `frappe-custom/mmm_custom/mmm_custom/setup.py` — add this block after the `course_interest` block (around line 36), before `frappe.db.commit()`:

```python
	if not frappe.db.exists("Custom Field", "CRM Lead-branch"):
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "CRM Lead",
			"fieldname": "branch",
			"label": "Branch",
			"fieldtype": "Select",
			"options": "\nCS1 Bình Thạnh\nCS2 Quận 1\nCS3 Thủ Đức",
			"insert_after": "course_interest",
		}).insert(ignore_permissions=True)
		print("Custom field branch created")
	else:
		doc = frappe.get_doc("Custom Field", "CRM Lead-branch")
		doc.options = "\nCS1 Bình Thạnh\nCS2 Quận 1\nCS3 Thủ Đức"
		doc.save(ignore_permissions=True)
		print("Custom field branch updated")
```

Also add `"Messenger Bot"` to the lead sources list:

```python
def create_lead_sources():
	for source_name in ("Messenger", "Instagram", "Messenger Bot"):
		frappe.get_doc({"doctype": "CRM Lead Source", "source_name": source_name}).insert(ignore_if_duplicate=True)
	frappe.db.commit()
	print("Lead sources created")
```

- [ ] **Step 4: Implement the bot webhook endpoint**

Create `frappe-custom/mmm_custom/mmm_custom/bot_api.py`:

```python
"""Webhook endpoint for the Chatwoot Agent Bot.

Receives Agent Bot webhook events from Chatwoot, runs the state machine,
sends Quick Reply responses via Chatwoot API, and on completion creates/
updates the CRM Lead and hands off to a human agent.
"""

import hashlib
import hmac
import json
import logging
import time

try:
    import requests
except ImportError:
    requests = None

try:
    import frappe
except ImportError:
    from unittest.mock import MagicMock

    class AuthenticationError(Exception):
        pass

    frappe = MagicMock()

    def _whitelist(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

    def _throw(msg, exc=Exception, *args, **kwargs):
        if isinstance(exc, type) and issubclass(exc, BaseException):
            raise exc(msg)
        raise Exception(msg)

    frappe.whitelist = _whitelist
    frappe.AuthenticationError = AuthenticationError
    frappe.throw = _throw

from mmm_custom.bot_engine import BRANCHES, COURSES, transition
from mmm_custom.chatwoot_client import ChatwootClient
from mmm_custom.dedupe import find_matching_lead, normalize_phone

logger = logging.getLogger(__name__)


def _verify_hmac(raw_body: bytes, secret: str, timestamp: str, signature: str):
    """Validate HMAC-SHA256 signature and anti-replay timestamp."""
    if not timestamp:
        frappe.throw("Timestamp expired or missing", frappe.AuthenticationError)

    try:
        ts_val = float(timestamp)
    except (ValueError, TypeError):
        frappe.throw("Timestamp expired or missing", frappe.AuthenticationError)

    if abs(time.time() - ts_val) > 300:
        frappe.throw("Timestamp expired or missing", frappe.AuthenticationError)

    hex_digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + raw_body,
        hashlib.sha256,
    ).hexdigest()
    expected = "sha256=" + hex_digest

    if not signature or not (
        hmac.compare_digest(expected, signature)
        or hmac.compare_digest(hex_digest, signature)
    ):
        frappe.throw("Invalid HMAC signature", frappe.AuthenticationError)


def _find_best_agent(branch_key: str, client: ChatwootClient) -> int | None:
    """Find the best-match agent by branch, round-robin by fewest open convos."""
    try:
        agents = client.list_agents()
    except Exception:
        logger.exception("Failed to list agents")
        return None

    # Filter by branch
    branch_agents = [
        a for a in agents
        if (a.get("custom_attributes") or {}).get("branch") == branch_key
    ]
    candidates = branch_agents if branch_agents else agents

    if not candidates:
        return None

    # Find agent with fewest open conversations
    best_agent_id = None
    min_convos = float("inf")
    for agent in candidates:
        try:
            convos = client.list_agent_conversations(agent["id"], status="open")
            count = len(convos)
        except Exception:
            count = 0
        if count < min_convos:
            min_convos = count
            best_agent_id = agent["id"]

    return best_agent_id


def _create_or_update_lead(contact: dict, courses: list[str],
                           branch_key: str, contact_id: int | None):
    """Create or update a CRM Lead with bot-collected data."""
    email = contact.get("email")
    phone = contact.get("phone_number") or contact.get("phone")
    raw_name = contact.get("name")
    first_name = (
        str(raw_name).strip() if raw_name and str(raw_name).strip()
        else "EduFlow Student"
    )

    # Map course keys to display names
    course_display = ", ".join(
        COURSES.get(k, k) for k in courses
    )
    # Map branch key to display name
    branch_display = BRANCHES.get(branch_key, branch_key)

    custom_attrs = contact.get("custom_attributes") or {}
    crm_lead_id = custom_attrs.get("crm_lead_id")

    if crm_lead_id and frappe.db.exists("CRM Lead", crm_lead_id):
        lead_name = crm_lead_id
        frappe.db.set_value("CRM Lead", lead_name, "course_interest", course_display)
        frappe.db.set_value("CRM Lead", lead_name, "branch", branch_display)
        if contact_id:
            frappe.db.set_value("CRM Lead", lead_name, "chatwoot_contact_id", str(contact_id))
    else:
        matched = find_matching_lead(email, phone)
        if matched:
            lead_name = matched.name if hasattr(matched, "name") else matched.get("name")
            frappe.db.set_value("CRM Lead", lead_name, "course_interest", course_display)
            frappe.db.set_value("CRM Lead", lead_name, "branch", branch_display)
            if contact_id:
                frappe.db.set_value("CRM Lead", lead_name, "chatwoot_contact_id", str(contact_id))
        else:
            lead = frappe.get_doc({
                "doctype": "CRM Lead",
                "first_name": first_name,
                "email": email,
                "mobile_no": normalize_phone(phone),
                "source": "Messenger Bot",
                "course_interest": course_display,
                "branch": branch_display,
                "chatwoot_contact_id": str(contact_id) if contact_id else None,
            }).insert(ignore_permissions=True)
            lead_name = lead.name

    return lead_name


@frappe.whitelist(allow_guest=True)
def agent_bot_webhook():
    """Receive Agent Bot webhook events from Chatwoot."""
    req = frappe.request
    ts = req.headers.get("X-Chatwoot-Timestamp") if hasattr(req, "headers") else None
    sig = req.headers.get("X-Chatwoot-Signature", "") if hasattr(req, "headers") else ""

    if hasattr(req, "get_data") and callable(req.get_data):
        raw_body = req.get_data()
    elif hasattr(req, "data"):
        raw_body = req.data
    else:
        raw_body = b""

    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")
    elif not isinstance(raw_body, bytes):
        raw_body = bytes(raw_body or b"")

    conf = getattr(frappe, "conf", None)
    secret = (
        (conf.get("chatwoot_bot_webhook_secret") if conf else None)
        or "dx_osd_bot_webhook_secret_2026"
    )

    _verify_hmac(raw_body, secret, ts, sig)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {"status": "error", "message": "Invalid JSON body"}

    if not isinstance(payload, dict):
        return {"status": "error", "message": "Invalid JSON body"}

    # Only process message_created events
    if payload.get("event") != "message_created":
        return {"status": "ignored", "event": payload.get("event")}

    # Only process incoming messages (from customer, not bot/agent)
    message_type = payload.get("message_type", -1)
    if message_type != 0:
        return {"status": "ignored", "reason": "outgoing_message"}

    # Extract conversation and contact data
    conversation = payload.get("conversation") or {}
    contact_inbox = conversation.get("contact_inbox") or {}
    contact = contact_inbox.get("contact") or payload.get("sender") or {}
    contact_id = contact.get("id")
    custom_attrs = contact.get("custom_attributes") or {}
    conversation_id = conversation.get("id") or payload.get("conversation", {}).get("id")

    if not conversation_id:
        return {"status": "error", "message": "Missing conversation_id"}

    # Read bot state from contact custom_attributes
    bot_state = custom_attrs.get("bot_state")
    bot_courses = custom_attrs.get("bot_courses") or []

    # Get user input — Quick Reply value or plain text content
    user_input = payload.get("content") or ""

    # Run state machine
    result = transition(bot_state, user_input, bot_courses)

    if result is None:
        return {"status": "ignored", "reason": "completed"}

    # Initialize Chatwoot client
    bot_token = (conf.get("chatwoot_bot_api_token") if conf else None) or ""
    account_id = (conf.get("chatwoot_bot_account_id") if conf else None) or 1
    base_url = (conf.get("chatwoot_base_url") if conf else None) or "http://host.docker.internal:3000"

    client = ChatwootClient(base_url, bot_token, int(account_id))

    # Send the bot's response message
    try:
        if result.quick_replies:
            client.send_quick_replies(conversation_id, result.message, result.quick_replies)
        else:
            client.send_message(conversation_id, result.message)
    except Exception:
        logger.exception("Failed to send bot message")

    # Update contact custom_attributes with new state
    new_attrs = {
        "bot_state": result.next_state,
        "bot_courses": result.selected_courses,
    }
    if result.branch:
        new_attrs["bot_branch"] = result.branch

    try:
        if contact_id:
            client.update_contact(contact_id, new_attrs)
    except Exception:
        logger.exception("Failed to update contact attributes")

    # Execute actions if any
    if "update_lead" in result.actions:
        try:
            lead_name = _create_or_update_lead(
                contact, result.selected_courses, result.branch, contact_id,
            )
            # Write back crm_lead_id to Chatwoot
            if contact_id and lead_name:
                try:
                    client.update_contact(contact_id, {"crm_lead_id": lead_name})
                except Exception:
                    logger.exception("Failed to write crm_lead_id back to Chatwoot")
        except Exception:
            logger.exception("Failed to create/update CRM Lead")

    if "assign_agent" in result.actions:
        try:
            agent_id = _find_best_agent(result.branch, client)
            if agent_id:
                client.assign_conversation(conversation_id, agent_id)
        except Exception:
            logger.exception("Failed to assign agent")

    if "bot_handoff" in result.actions:
        try:
            client.toggle_status(conversation_id, "open")
        except Exception:
            logger.exception("Failed to toggle conversation status")

    return {"status": "ok", "next_state": result.next_state}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -v`
Expected: All existing tests (23) + new tests PASS

- [ ] **Step 6: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/bot_api.py frappe-custom/mmm_custom/mmm_custom/setup.py frappe-custom/mmm_custom/mmm_custom/tests/test_bot_api.py
git commit -m "feat(bot): add webhook endpoint with CRM lead integration and agent assignment"
```

---

### Task 4: Agent Bot Setup Script + End-to-End Wiring + Documentation

**Files:**
- Create: `scripts/setup-agent-bot.py`
- Modify: `ROADMAP.md` (add bot milestone)
- Modify: `AGENTS.md` (add bot webhook test command)

**Interfaces:**
- Consumes:
  - Running Chatwoot stack (port 3000) — creates AgentBot via Rails runner
  - Running Frappe CRM stack (port 8000) — sets site config + runs setup
  - `bot_api.agent_bot_webhook` endpoint from Task 3
- Produces: A fully wired Agent Bot connected to EduFlow Messenger inbox

- [ ] **Step 1: Create the Agent Bot setup script**

Create `scripts/setup-agent-bot.py`:

```python
#!/usr/bin/env python3
"""
scripts/setup-agent-bot.py

Creates the EduFlow Qualification Bot as a Chatwoot Agent Bot, links it
to the EduFlow Messenger inbox, and configures the Frappe CRM site with
the bot's API token and webhook secret.
"""

import subprocess
import sys

RUBY_SCRIPT = """
account = Account.first
raise "No account found — run scripts/configure-chatwoot.py first" unless account

# Find the Facebook Messenger inbox
inbox = account.inboxes.find_by(channel_type: 'Channel::FacebookPage')
inbox ||= account.inboxes.first
raise "No inbox found" unless inbox

# Create or find the Agent Bot
bot_name = 'EduFlow Qualification Bot'
bot = AgentBot.find_or_initialize_by(name: bot_name, account: account)
bot.description = 'Collects course interest and branch preference via Quick Reply buttons'
bot.outgoing_url = 'http://host.docker.internal:8000/api/method/mmm_custom.bot_api.agent_bot_webhook'

# Generate a webhook secret for HMAC validation
require 'securerandom'
bot.secret ||= SecureRandom.hex(32)
bot.save!

# Link bot to inbox
abi = AgentBotInbox.find_or_initialize_by(inbox: inbox, agent_bot: bot)
abi.status = :active
abi.save!

# Get or create access token for the bot
token = bot.access_token&.token
if token.blank?
  access_token = bot.create_access_token
  token = access_token.token
end

puts "SUCCESS"
puts "BOT_ID: #{bot.id}"
puts "BOT_NAME: #{bot.name}"
puts "BOT_SECRET: #{bot.secret}"
puts "BOT_TOKEN: #{token}"
puts "INBOX_ID: #{inbox.id}"
puts "INBOX_NAME: #{inbox.name}"
puts "OUTGOING_URL: #{bot.outgoing_url}"
"""


def run_ruby(script: str) -> str:
    proc = subprocess.run(
        ["docker", "exec", "-i", "chatwoot-rails-1",
         "bundle", "exec", "rails", "runner", "-"],
        input=script.encode("utf-8"),
        capture_output=True,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        print("STDERR:", stderr)
        sys.exit(proc.returncode)
    return stdout


def configure_frappe(bot_secret: str, bot_token: str):
    """Set Frappe site config keys for the bot."""
    cmds = [
        f'bench --site crm.localhost set-config chatwoot_bot_webhook_secret "{bot_secret}"',
        f'bench --site crm.localhost set-config chatwoot_bot_api_token "{bot_token}"',
        'bench --site crm.localhost set-config chatwoot_bot_account_id 1',
        'bench --site crm.localhost set-config chatwoot_base_url "http://host.docker.internal:3000"',
    ]
    for cmd in cmds:
        subprocess.run(
            ["docker", "compose", "-f", "crm/docker/docker-compose.yml",
             "-f", "crm/docker/docker-compose.override.yml",
             "exec", "-T", "frappe", "bash", "-c", cmd],
            check=True,
        )


def run_setup():
    """Run mmm_custom.setup.setup to create custom fields."""
    subprocess.run(
        ["docker", "compose", "-f", "crm/docker/docker-compose.yml",
         "-f", "crm/docker/docker-compose.override.yml",
         "exec", "-T", "frappe",
         "bench", "--site", "crm.localhost", "execute",
         "mmm_custom.setup.setup"],
        check=True,
    )


def main():
    print("=== Step 1: Creating Agent Bot in Chatwoot ===")
    output = run_ruby(RUBY_SCRIPT)
    print(output)

    # Parse output
    lines = output.strip().split("\n")
    data = {}
    for line in lines:
        if ": " in line:
            key, val = line.split(": ", 1)
            data[key.strip()] = val.strip()

    bot_secret = data.get("BOT_SECRET", "")
    bot_token = data.get("BOT_TOKEN", "")

    if not bot_secret or not bot_token:
        print("ERROR: Could not extract bot credentials")
        sys.exit(1)

    print("\n=== Step 2: Configuring Frappe CRM site config ===")
    configure_frappe(bot_secret, bot_token)

    print("\n=== Step 3: Running mmm_custom setup (custom fields) ===")
    run_setup()

    masked_token = f"{bot_token[:5]}...{bot_token[-4:]}" if len(bot_token) > 8 else "***"
    masked_secret = f"{bot_secret[:5]}...{bot_secret[-4:]}" if len(bot_secret) > 8 else "***"

    print("\n" + "=" * 60)
    print("Agent Bot setup complete!")
    print(f"  Bot Token: {masked_token}")
    print(f"  Bot Secret: {masked_secret}")
    print(f"  Inbox: {data.get('INBOX_NAME', 'N/A')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the setup script against live stacks**

Run: `python scripts/setup-agent-bot.py`
Expected: `SUCCESS` output with Bot ID, masked token/secret, inbox linked.

- [ ] **Step 3: Run the full Frappe setup on live bench**

Run:
```bash
docker compose -f crm/docker/docker-compose.yml -f crm/docker/docker-compose.override.yml exec -T frappe bench --site crm.localhost execute mmm_custom.setup.setup
```
Expected: `Custom field branch created` (or `updated`), `Lead sources created`

- [ ] **Step 4: Run all unit tests**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -v`
Expected: All tests pass (existing 23 + new bot tests)

- [ ] **Step 5: End-to-End verification**

Send a test message from the real Messenger app to EduFlow Academy. Verify:
1. Bot auto-replies with course Quick Reply buttons on Messenger
2. Tapping a course shows the next Quick Reply (remaining courses + "Xong")
3. Tapping "Xong" shows branch Quick Reply buttons
4. Tapping a branch shows the confirmation message
5. Check CRM at `http://127.0.0.1:8000/app/crm-lead` — new Lead has `course_interest` and `branch` populated
6. Check Chatwoot at `http://127.0.0.1:3000` — conversation status changed to `open` and assigned to an agent

- [ ] **Step 6: Update documentation**

Add to `ROADMAP.md` under the current phase:
```markdown
- ✅ **Conversational Bot**: Agent Bot with Quick Reply qualification flow (course + branch), intelligent round-robin agent assignment
```

Add to `AGENTS.md` Commands section:
```markdown
### Bot Engine Tests
```bash
python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -v
```
```

- [ ] **Step 7: Commit**

```bash
git add scripts/setup-agent-bot.py frappe-custom/mmm_custom/mmm_custom/setup.py ROADMAP.md AGENTS.md
git commit -m "feat(bot): add agent bot setup script and documentation"
```
