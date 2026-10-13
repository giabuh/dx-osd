# Conversational AI Experience & Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade DX-OSD conversational bot to simulate human typing indicators, send rich course image brochures, maintain long-term returning customer memory, and enforce a strict 2.5s AI timeout with instant CRM rule-based fallback.

**Architecture:** Native In-Bench extension on top of Frappe CRM + Chatwoot v1 REST API. The agent bot webhook triggers a typing status (`typing_on`) on incoming messages, calculates a natural typing delay (1.5s–2.5s), enriches course replies with local/CRM poster attachments, restores returning customer context from MariaDB, and wraps LLM calls with a hard 2.5s timeout falling back to CRM keyword templates.

**Tech Stack:** Python 3.11, Frappe Framework v15, Chatwoot REST API v1, MariaDB 10.8, Redis 7.2, Python `unittest`.

**Spec:** [`docs/superpowers/specs/2026-10-09-conversational-ai-and-memory-design.md`](file:///C:/TepD/HUTECH/OLP1/dx-osd/docs/superpowers/specs/2026-10-09-conversational-ai-and-memory-design.md)

## Global Constraints

- 100% OSI-approved FOSS licensing (all new code under MIT license).
- Zero new Docker containers or middleware proxies (pure in-bench Frappe custom app execution).
- Code, identifiers, comments, and commit messages in English; user-facing dialogue labels and messages in Vietnamese.
- Never destroy persistent database state (never run `docker compose down -v`).
- Stage explicit paths only (never `git add -A` or `git add .`).
- Test suite verification: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -v`.

---

### Task 1: Chatwoot Typing Status Control & Attachment Dispatch

**Files:**
- Modify: `frappe-custom/mmm_custom/mmm_custom/chatwoot_client.py:90-110`
- Modify: `frappe-custom/mmm_custom/mmm_custom/engine/effects.py:20-75`
- Test: `frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py`

**Interfaces:**
- Consumes: Chatwoot REST API v1 (`POST /api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_typing_status`)
- Produces:
  - `ChatwootClient.toggle_typing(conversation_id: int, status: str = "on") -> dict`
  - `ChatwootEffects.send(conversation_id: str, reply: Reply)` with typing simulation and attachment handling
  - `RecordingEffects.toggle_typing(conversation_id: str, status: str)`

- [ ] **Step 1: Write the failing test for typing control and typing delay calculation**

Create `frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py`:

```python
import unittest
from unittest.mock import MagicMock, patch
from mmm_custom.chatwoot_client import ChatwootClient
from mmm_custom.engine.effects import ChatwootEffects, RecordingEffects
from mmm_custom.engine.reply import Reply


class TestConversationalExperience(unittest.TestCase):
    def test_chatwoot_client_toggle_typing(self):
        client = ChatwootClient("http://test.local", "token123", 1)
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"status": "ok"}
            mock_post.return_value.status_code = 200
            res = client.toggle_typing(123, "on")
            mock_post.assert_called_once_with(
                "http://test.local/api/v1/accounts/1/conversations/123/toggle_typing_status",
                headers={"api_access_token": "token123"},
                json={"typing_status": "on"},
                timeout=3,
            )
            self.assertEqual(res, {"status": "ok"})

    def test_recording_effects_tracks_typing(self):
        rec = RecordingEffects()
        rec.toggle_typing("123", "on")
        self.assertEqual(rec.of("toggle_typing"), [{"conversation_id": "123", "status": "on"}])

    def test_chatwoot_effects_typing_and_attachments(self):
        bot = MagicMock()
        user = MagicMock()
        effects = ChatwootEffects(bot, user)
        reply = Reply(
            messages=["Khóa học Excel nâng cao học phí 1.500.000đ."],
            attachments=[{"type": "image", "url": "/images/excel.jpg", "title": "Excel Poster"}]
        )
        with patch("time.sleep") as mock_sleep:
            effects.send("10", reply)
            # Verify typing turned on
            bot.toggle_typing.assert_called_with(10, "on")
            # Verify attachment sent
            bot.send_message.assert_any_call(
                10,
                "![Excel Poster](/images/excel.jpg)",
                content_attributes={"image_url": "/images/excel.jpg"}
            )
            # Verify text message sent
            bot.send_message.assert_any_call(10, "Khóa học Excel nâng cao học phí 1.500.000đ.")
            # Verify natural sleep called (between 1.5s and 2.5s)
            mock_sleep.assert_called_once()
            delay = mock_sleep.call_args[0][0]
            self.assertGreaterEqual(delay, 1.5)
            self.assertLessEqual(delay, 2.5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
python -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py -v
```
Expected: FAIL (`AttributeError: 'ChatwootClient' object has no attribute 'toggle_typing'`).

- [ ] **Step 3: Implement typing toggle and effects simulation**

In `frappe-custom/mmm_custom/mmm_custom/chatwoot_client.py`:
Add method:
```python
    def toggle_typing(self, conversation_id: int, status: str = "on") -> dict:
        """Toggle typing indicator (typing_on / typing_off) for a conversation."""
        resp = requests.post(
            f"{self._base}/conversations/{conversation_id}/toggle_typing_status",
            headers=self._headers,
            json={"typing_status": status},
            timeout=3,
        )
        resp.raise_for_status()
        return resp.json()
```

In `frappe-custom/mmm_custom/mmm_custom/engine/effects.py`:
Add to `RecordingEffects`:
```python
    def toggle_typing(self, conversation_id, status):
        self.calls.append(("toggle_typing", {"conversation_id": str(conversation_id), "status": status}))
```

In `ChatwootEffects.send(self, conversation_id, reply)`:
```python
    def send(self, conversation_id, reply):
        import time
        cid = int(conversation_id) if str(conversation_id).isdigit() else conversation_id
        # 1. Activate typing indicator
        try:
            self.bot.toggle_typing(cid, "on")
        except Exception:
            pass

        # 2. Simulate natural typing pause based on text length (1.5s - 2.5s)
        total_len = sum(len(m) for m in reply.messages)
        delay = min(2.5, max(1.5, total_len * 0.012))
        time.sleep(delay)

        # 3. Dispatch media attachments if present
        for att in getattr(reply, "attachments", []) or []:
            if att.get("type") == "image" and att.get("url"):
                img_url = att["url"]
                title = att.get("title") or "Hình ảnh"
                self.bot.send_message(
                    cid,
                    f"![{title}]({img_url})",
                    content_attributes={"image_url": img_url}
                )

        # 4. Dispatch messages & quick replies
        last = len(reply.messages) - 1
        for i, text in enumerate(reply.messages):
            if i == last and reply.buttons:
                items = [{"title": b["title"], "value": b["title"]} for b in reply.buttons]
                self.bot.send_quick_replies(cid, text, items)
            else:
                self.bot.send_message(cid, text)
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
python -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py -v
```
Expected: PASS (3 tests passing).

---

### Task 2: Course Image & Rich Media Attachment Generation

**Files:**
- Modify: `frappe-custom/mmm_custom/mmm_custom/engine/reply.py:90-140`
- Test: `frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py`

**Interfaces:**
- Consumes: `decision.slots.get("course")`, `catalog.courses`, `Course.image`
- Produces: `Reply.attachments` populated with `{"type": "image", "url": course_image, "title": course_name}`

- [ ] **Step 1: Write test for course image attachment in reply composer**

Add to `frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py`:

```python
    def test_reply_compose_attaches_course_image(self):
        from mmm_custom.engine.reply import compose
        from mmm_custom.engine.decide import Decision
        from mmm_custom.engine.state import ConversationState
        from mmm_custom.engine.catalog import Course, Catalog, DEFAULT_SETTINGS

        course = Course(
            code="VP-EXCEL",
            name="Excel từ cơ bản đến nâng cao",
            fee=1500000,
            image="/files/excel_poster.jpg",
            button_label="Excel",
        )
        catalog = Catalog(courses={"VP-EXCEL": course}, settings=dict(DEFAULT_SETTINGS))
        state = ConversationState("conv1", slots={"course": "VP-EXCEL"})
        decision = Decision(type="answer", skills=[], slots={"course": "VP-EXCEL"})

        reply = compose(decision, state, catalog, render=lambda t, c: t)
        self.assertTrue(any(att.get("url") == "/files/excel_poster.jpg" for att in reply.attachments))
```

- [ ] **Step 2: Run test to verify failure**

Run:
```powershell
python -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py -v
```
Expected: FAIL (`AssertionError: False is not true`).

- [ ] **Step 3: Implement image attachment in `compose()`**

In `frappe-custom/mmm_custom/mmm_custom/engine/reply.py` inside `compose()`:
```python
    # Attach course brochure image when course is selected
    course_code = decision.slots.get("course") or state.slots.get("course")
    if course_code and catalog.courses.get(course_code):
        c = catalog.courses[course_code]
        img_url = getattr(c, "image", None) or (c.get("image") if isinstance(c, dict) else None)
        if img_url:
            reply.attachments.append({
                "type": "image",
                "url": img_url,
                "title": getattr(c, "name", course_code),
            })
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
python -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py -v
```
Expected: PASS.

---

### Task 3: Long-term Contact Memory & Personalized Returning Context

**Files:**
- Modify: `frappe-custom/mmm_custom/mmm_custom/engine/repo.py:402-422`
- Modify: `frappe-custom/mmm_custom/mmm_custom/engine/context.py:40-70`
- Test: `frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py`

**Interfaces:**
- Consumes: `CRM Lead` (fields: `first_name`, `course_interest`, `territory`, `mobile_no`), `Bot Conversation`
- Produces:
  - `state.is_returning = True`
  - `base_context`: `customer.previous_course`, `customer.previous_branch`, `customer.is_returning`
  - Zero-redundancy slot prefill: `state.slots["phone"]` and `state.slots["branch"]` initialized from previous record.

- [ ] **Step 1: Write test for returning customer memory and zero-redundancy prefill**

Add to `frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py`:

```python
    def test_returning_customer_memory_context(self):
        from mmm_custom.engine.context import base_context
        from mmm_custom.engine.state import ConversationState
        from mmm_custom.engine.catalog import Catalog, DEFAULT_SETTINGS

        catalog = Catalog(settings=dict(DEFAULT_SETTINGS))
        state = ConversationState(
            "conv_ret",
            contact_id="c_100",
            lead="LEAD-001",
            is_returning=True,
            slots={"phone": "0901234567", "branch": "CN-Q7"},
        )
        state.customer_name = "Chị Hà"
        state.previous_course = "Tin học văn phòng"
        state.previous_branch = "Chi nhánh Quận 7"

        ctx = base_context(state.slots, catalog, state)
        self.assertTrue(ctx["customer"]["is_returning"])
        self.assertEqual(ctx["customer"]["previous_course"], "Tin học văn phòng")
        self.assertEqual(ctx["customer"]["previous_branch"], "Chi nhánh Quận 7")
        self.assertEqual(ctx["slots"]["phone"], "0901234567")
        self.assertEqual(ctx["slots"]["branch"], "CN-Q7")
```

- [ ] **Step 2: Run test to verify failure**

Run:
```powershell
python -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py -v
```
Expected: FAIL (`KeyError: 'previous_course'`).

- [ ] **Step 3: Implement returning context in `engine/context.py` & `engine/repo.py`**

In `frappe-custom/mmm_custom/mmm_custom/engine/context.py` inside `base_context()`:
```python
    customer["previous_course"] = getattr(state, "previous_course", "") or ""
    customer["previous_branch"] = getattr(state, "previous_branch", "") or ""
```

In `frappe-custom/mmm_custom/mmm_custom/engine/repo.py` inside `new_state()`:
Populate `state.previous_course` and `state.previous_branch` from `CRM Lead`:
```python
        if state.is_returning and lead and frappe:
            lead_doc = frappe.db.get_value("CRM Lead", lead, ["first_name", "lead_name", "course_interest", "territory", "mobile_no"], as_dict=True) or {}
            state.customer_name = lead_doc.get("first_name") or lead_doc.get("lead_name") or ""
            state.previous_course = lead_doc.get("course_interest") or ""
            state.previous_branch = lead_doc.get("territory") or ""
            if lead_doc.get("mobile_no") and not state.slots.get("phone"):
                state.slots["phone"] = lead_doc["mobile_no"]
            if lead_doc.get("territory") and not state.slots.get("branch"):
                state.slots["branch"] = lead_doc["territory"]
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
python -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py -v
```
Expected: PASS.

---

### Task 4: Zero-Stall AI Timeout & Fallback Resilience

**Files:**
- Modify: `frappe-custom/mmm_custom/mmm_custom/engine/jev.py:100-140`
- Modify: `frappe-custom/mmm_custom/mmm_custom/engine/pipeline.py:85-110`
- Test: `frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py`

**Interfaces:**
- Consumes: Gemini / Jev HTTP API requests
- Produces:
  - Hard timeout limit: `timeout=2.5` seconds
  - `JevResult("timeout_fallback")` on timeout/network failure
  - Seamless fallback to `understand()` rule-based entity matching without crashing or duplicate queue retries.

- [ ] **Step 1: Write test for 2.5s AI timeout and instant fallback**

Add to `frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py`:

```python
    def test_jev_client_strict_timeout_and_fallback(self):
        from mmm_custom.engine.jev import JevClient, JevResult
        import requests

        client = JevClient("http://fake-ai-api.local", "fake_key", "gemini-pro")
        with patch("requests.post", side_effect=requests.exceptions.Timeout("Read timed out")):
            result = client.ask({}, [{"question": "intent"}])
            self.assertEqual(result.status, "timeout_fallback")
            self.assertIn("timed out", result.error)

    def test_pipeline_understand_turn_timeout_fallback(self):
        from mmm_custom.engine.pipeline import understand_turn
        from mmm_custom.engine.jev import JevResult
        from mmm_custom.engine.state import ConversationState
        from mmm_custom.engine.catalog import Catalog, DEFAULT_SETTINGS

        mock_jev = MagicMock()
        mock_jev.ask.return_value = JevResult("timeout_fallback", error="Read timed out after 2.5s")

        catalog = Catalog(settings=dict(DEFAULT_SETTINGS))
        state = ConversationState("conv_timeout")
        u, result = understand_turn("Học phí Excel bao nhiêu", state, catalog, mock_jev)

        # Result is timeout fallback, but understanding succeeds via local keyword rules
        self.assertEqual(result.status, "timeout_fallback")
        self.assertIsNotNone(u)
```

- [ ] **Step 2: Run test to verify failure**

Run:
```powershell
python -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py -v
```
Expected: FAIL (`AssertionError: 'error' != 'timeout_fallback'`).

- [ ] **Step 3: Implement hard 2.5s timeout in `engine/jev.py`**

In `frappe-custom/mmm_custom/mmm_custom/engine/jev.py`:
Update `ask()` method to set `timeout=2.5`:
```python
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=2.5)
        resp.raise_for_status()
        ...
    except requests.exceptions.Timeout as e:
        logger.warning("AI/Jev call timed out after 2.5s: %s", e)
        return JevResult("timeout_fallback", error=str(e))
    except (requests.exceptions.RequestException, Exception) as e:
        logger.warning("AI/Jev call failed: %s", e)
        return JevResult("error", error=str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```powershell
python -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_conversational_experience.py -v
```
Expected: PASS (all tests in `test_conversational_experience.py` pass).

---

### Task 5: End-to-End Regression Verification & Live Bench Check

**Files:**
- Test: Full unit test suite (`tests/`)

- [ ] **Step 1: Run the full Python test suite**

Run:
```powershell
python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -v
```
Expected: All tests pass (123+ unit tests).

- [ ] **Step 2: Clear cache in live Frappe CRM container**

Run:
```powershell
docker exec crm-frappe-1 bench --site crm.localhost clear-cache
```
Expected: Cache cleared cleanly.
