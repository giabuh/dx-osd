# Autonomous Marketing Multi-Agent System (EduFlow Autopilot) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an autonomous weekly marketing agent pipeline that plans 4 balanced weekly posts (Mon/Wed/Fri/Sun), writes captions with Gemini, renders 1080x1080 banners with Pillow, supports 1-click batch approval, and provides a 3-tier rollback/redesign flow, integrated directly into the existing `Facebook Post` DocType and list view.

**Architecture:** A pure-logic planner + batch orchestrator in `autopilot.py` that interacts with existing `FacebookPost` model. Controls are integrated directly into the existing `Facebook Post` list view (`facebook_post_list.js`) and form view (`facebook_post.js`). Background execution is scheduled via Frappe hooks cron.

**Tech Stack:** Python 3, Frappe Framework v15, Google Gemini API, Pillow, Facebook Graph API, JavaScript.

**Spec:** [`docs/superpowers/specs/2026-09-27-autonomous-marketing-agent-design.md`](file:///C:/TepD/HUTECH/OLP1/dx-osd/docs/superpowers/specs/2026-09-27-autonomous-marketing-agent-design.md)

## Global Constraints
- 100% OSI-approved FOSS (MIT/AGPLv3).
- Build upon existing `Facebook Post` DocType and pages — avoid creating redundant DocTypes.
- Port bindings remain `127.0.0.1` only.
- Never destroy persistent dev databases or named volumes.
- All code, comments, commits in English; user-facing labels and captions in Vietnamese.

---

### Task 1: Schema Extension on Existing `Facebook Post` DocType

**Files:**
- Modify: `frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/facebook_post/facebook_post.json`
- Test: `frappe-custom/mmm_custom/mmm_custom/tests/test_autopilot.py`

**Interfaces:**
- Produces: `Facebook Post` with updated status options (`Draft\nPending Approval\nScheduled\nPosted\nFailed\nCancelled`), `batch_id` (Data), `boss_directive` (Small Text), `day_of_week` (Select).

- [ ] **Step 1: Write failing unit test for schema fields**

```python
# frappe-custom/mmm_custom/mmm_custom/tests/test_autopilot.py
import unittest
from unittest.mock import MagicMock, patch
from mmm_custom.mmm_custom.doctype.facebook_post.facebook_post import FacebookPost

class TestAutopilotSchema(unittest.TestCase):
    def test_post_has_autopilot_fields(self):
        doc = FacebookPost()
        doc.status = "Pending Approval"
        doc.batch_id = "BATCH-2026-W39"
        doc.boss_directive = "Ưu đãi 50% bơi lội hè"
        doc.day_of_week = "Thứ Hai"
        self.assertEqual(doc.status, "Pending Approval")
        self.assertEqual(doc.batch_id, "BATCH-2026-W39")
        self.assertEqual(doc.boss_directive, "Ưu đãi 50% bơi lội hè")
        self.assertEqual(doc.day_of_week, "Thứ Hai")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -p "test_autopilot.py" -v`  
Expected: Module/test not found or fails.

- [ ] **Step 3: Update `facebook_post.json` schema**

Add fields to `facebook_post.json`:
- `batch_id` (Data, in_standard_filter=1)
- `boss_directive` (Small Text)
- `day_of_week` (Select: `Thứ Hai\nThứ Ba\nThứ Tư\nThứ Năm\nThứ Sáu\nThứ Bảy\nChủ Nhật`)
- Update `status` options to `Draft\nPending Approval\nScheduled\nPosted\nFailed\nCancelled`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -p "test_autopilot.py" -v`  
Expected: PASS

- [ ] **Step 5: Run bench migrate to update database table**

```bash
docker exec crm-frappe-1 bench --site crm.localhost migrate
```

- [ ] **Step 6: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/facebook_post/facebook_post.json frappe-custom/mmm_custom/mmm_custom/tests/test_autopilot.py
git commit -m "feat(autopilot): add batch_id, boss_directive, and day_of_week fields to Facebook Post"
```

---

### Task 2: Core Autopilot Engine & Batch Generator

**Files:**
- Create: `frappe-custom/mmm_custom/mmm_custom/autopilot.py`
- Modify: `frappe-custom/mmm_custom/mmm_custom/tests/test_autopilot.py`

**Interfaces:**
- Produces:
  - `generate_weekly_batch(boss_directive=None, target_date=None)` -> dict with `batch_id`, `posts` count
  - `approve_weekly_batch(batch_id=None)` -> dict with approved count
  - `rollback_weekly_batch(batch_id=None, new_directive=None)` -> dict with new `batch_id`
  - `recall_post(post_name)` -> dict with status

- [ ] **Step 1: Write failing tests for batch planning and approval**

```python
# Add to test_autopilot.py
from mmm_custom import autopilot

class TestAutopilotEngine(unittest.TestCase):
    @patch("mmm_custom.autopilot.frappe")
    def test_plan_weekly_matrix(self, mock_frappe):
        matrix = autopilot.get_weekly_matrix()
        self.assertEqual(len(matrix), 4)
        self.assertEqual(matrix[0]["course"], "Tiếng Anh")
        self.assertEqual(matrix[1]["course"], "Toán tư duy")
        self.assertEqual(matrix[2]["course"], "Bơi lội")
        self.assertEqual(matrix[3]["course"], "Chung")
        
    @patch("mmm_custom.autopilot.frappe")
    def test_generate_batch_creates_pending_posts(self, mock_frappe):
        mock_doc = MagicMock()
        mock_frappe.new_doc.return_value = mock_doc
        res = autopilot.generate_weekly_batch(boss_directive="Tập trung tuyển sinh hè")
        self.assertTrue(res["status"], "success")
        self.assertEqual(mock_frappe.new_doc.call_count, 4)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -p "test_autopilot.py" -v`  
Expected: FAIL (autopilot module not found).

- [ ] **Step 3: Implement `autopilot.py`**

Implement:
- `WEEKLY_MATRIX`: Define the 4 standard post slots (Mon 08:30, Wed 11:30, Fri 19:30, Sun 09:00).
- `generate_weekly_batch(boss_directive=None, target_date=None)`:
  - Computes `batch_id` for current/target week (e.g. `BATCH-2026-W39`).
  - Iterates over slots, creates `Facebook Post` with `status="Pending Approval"`.
  - Calls `doc.generate_ai_content(user_feedback=boss_directive)`.
  - Calls `doc.generate_banner(user_feedback=boss_directive)`.
  - Saves docs.
- `approve_weekly_batch(batch_id=None)`:
  - Finds all posts in `batch_id` (or all with `status == "Pending Approval"`).
  - Transitions them to `status = "Scheduled"`.
- `rollback_weekly_batch(batch_id=None, new_directive=None)`:
  - Cancels/deletes pending posts in target batch.
  - Re-runs `generate_weekly_batch(boss_directive=new_directive)`.
- `recall_post(post_name)`:
  - Reverts a `Scheduled` post back to `Pending Approval`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -p "test_autopilot.py" -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/autopilot.py frappe-custom/mmm_custom/mmm_custom/tests/test_autopilot.py
git commit -m "feat(autopilot): implement batch generation, approval, and rollback logic"
```

---

### Task 3: Background Scheduler Hooks for Auto-Publishing

**Files:**
- Modify: `frappe-custom/mmm_custom/mmm_custom/autopilot.py`
- Modify: `frappe-custom/mmm_custom/mmm_custom/hooks.py`
- Test: `frappe-custom/mmm_custom/mmm_custom/tests/test_autopilot.py`

**Interfaces:**
- Produces: `autopilot.publish_scheduled_posts()` which runs via cron every 5 minutes and automatically publishes due posts to Facebook.

- [ ] **Step 1: Write failing test for `publish_scheduled_posts`**

```python
    @patch("mmm_custom.autopilot.frappe")
    def test_publish_scheduled_posts(self, mock_frappe):
        mock_post = MagicMock()
        mock_post.post_now = MagicMock(return_value={"status": "success"})
        mock_frappe.get_all.return_value = [{"name": "FB-POST-1"}]
        mock_frappe.get_doc.return_value = mock_post
        
        res = autopilot.publish_scheduled_posts()
        self.assertEqual(res["published"], 1)
        mock_post.post_now.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -p "test_autopilot.py" -v`  
Expected: FAIL (`publish_scheduled_posts` not implemented).

- [ ] **Step 3: Implement `publish_scheduled_posts` in `autopilot.py` and register in `hooks.py`**

In `autopilot.py`:
- Query `frappe.get_all("Facebook Post", filters={"status": "Scheduled", "scheduled_time": ["<=", frappe.utils.now_datetime()]})`.
- For each post, call `doc.post_now()`.
- Wrap in try/except to ensure one post error does not stop others.

In `hooks.py`:
- Add `*/5 * * * *`: `["mmm_custom.autopilot.publish_scheduled_posts"]` to `scheduler_events["cron"]`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -p "test_autopilot.py" -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/autopilot.py frappe-custom/mmm_custom/mmm_custom/hooks.py frappe-custom/mmm_custom/mmm_custom/tests/test_autopilot.py
git commit -m "feat(autopilot): wire background publisher cron job for scheduled posts"
```

---

### Task 4: UI Integration on Existing List View (`facebook_post_list.js`)

**Files:**
- Create: `frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/facebook_post/facebook_post_list.js`
- Modify: `frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/facebook_post/facebook_post.js`

**Interfaces:**
- User clicks `🤖 Lên kế hoạch tuần mới` directly on `/app/facebook-post` list view.
- User clicks `✅ Duyệt tất cả tuần này` to approve pending posts in 1 click.
- User clicks `🔄 Làm lại cả tuần` to rollback and re-plan with new guidance.
- On form view, added `⏪ Thu hồi lịch đăng` button if post is `Scheduled`.

- [ ] **Step 1: Create `facebook_post_list.js` with action buttons**

Implement `frappe.listview_settings["Facebook Post"]`:
- `onload(listview)`:
  - Add button `🤖 Agent: Lên kế hoạch tuần`: Opens `frappe.prompt` asking for optional boss directive, calls `mmm_custom.autopilot.generate_weekly_batch`.
  - Add button `✅ Duyệt tất cả tuần này`: Confirms and calls `mmm_custom.autopilot.approve_weekly_batch`, then refreshes list.
  - Add button `🔄 Làm lại cả tuần`: Prompts for new directive, calls `mmm_custom.autopilot.rollback_weekly_batch`, then refreshes list.
- Custom indicators for status:
  - `Draft`: gray
  - `Pending Approval`: orange / yellow
  - `Scheduled`: blue
  - `Posted`: green
  - `Failed`: red

- [ ] **Step 2: Add `⏪ Thu hồi lịch đăng` to `facebook_post.js`**

If `frm.doc.status === "Scheduled"`:
- Show button `⏪ Thu hồi lịch đăng`.
- Confirms and calls `mmm_custom.autopilot.recall_post` to set status back to `Pending Approval`.

- [ ] **Step 3: Clear Frappe cache & test list view**

Run:
```bash
docker exec crm-frappe-1 bench --site crm.localhost clear-cache
```

- [ ] **Step 4: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/facebook_post/facebook_post_list.js frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/facebook_post/facebook_post.js
git commit -m "feat(ui): integrate weekly autopilot batch controls directly into Facebook Post list and form"
```

---

### Task 5: End-to-End Verification & Documentation

**Files:**
- Test: Full unit test discovery across all `mmm_custom` tests.
- Modify: `ROADMAP.md`

- [ ] **Step 1: Run full test suite**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -v`  
Expected: ALL tests pass (115+ tests).

- [ ] **Step 2: Verify live endpoint via bench execute**

Call `generate_weekly_batch` via bench execute and verify 4 posts created:
```bash
docker exec crm-frappe-1 bench --site crm.localhost execute mmm_custom.autopilot.generate_weekly_batch --kwargs "{'boss_directive': 'Tuần lễ vàng học bơi'}"
```

- [ ] **Step 3: Update `ROADMAP.md`**

Record the autonomous marketing agent milestone under current phase.

- [ ] **Step 4: Final commit**

```bash
git add ROADMAP.md
git commit -m "docs(roadmap): record autonomous marketing agent pipeline milestone"
```
