# EduFlow Lead Qualification Bot — Design Spec

## Purpose

Build an automated conversational bot that greets Facebook Messenger customers, collects structured qualification data (course interest + preferred branch) through interactive Quick Reply buttons, updates the CRM Lead, and hands off to the best-match human agent — all within the existing Chatwoot + Frappe CRM architecture, using zero additional services.

## Success Criteria

1. A customer messaging EduFlow Academy on Messenger receives an immediate automated greeting with Quick Reply buttons.
2. The bot collects **one or more course interests** and **one branch preference** through a multi-step Quick Reply flow.
3. After collection, the CRM Lead is created/updated with structured `course_interest` and `branch` fields.
4. The conversation is handed off from bot (`pending`) to a human agent (`open`) who matches the selected branch, using round-robin (fewest open conversations).
5. The customer sees a confirmation message naming what they selected and that an agent will follow up.
6. All code is 100% OSI-approved FOSS (MIT / AGPLv3). No new containers or external services.

## Constraints

- **FOSS purity**: All new code under MIT license (inside `mmm_custom`). No proprietary dependencies.
- **Facebook Messenger Quick Reply limit**: Maximum 13 quick replies per message. Each quick reply title max 20 characters. Only one button can be tapped per message (buttons disappear after tap).
- **No new Docker containers**: The bot engine runs inside the existing Frappe bench (`mmm_custom` app). Communication with Chatwoot is via its REST API.
- **Security**: The Agent Bot webhook endpoint must validate Chatwoot's HMAC-SHA256 signature (same pattern as `chatwoot_sync`).
- **Language**: Bot messages in Vietnamese. Code, comments, commits in English.

## Architecture

### System Context

```
Facebook Messenger
       │
       ▼
Chatwoot (/bot endpoint)
       │
       ├── Creates Contact + Conversation (status: pending)
       │   because Inbox has active AgentBot
       │
       └── AgentBotListener fires POST to AgentBot.outgoing_url
              │
              ▼
       mmm_custom.bot_api.agent_bot_webhook   (Frappe CRM, port 8000)
              │
              ├── Reads conversation state from Chatwoot Contact custom_attributes
              ├── Runs State Machine transition
              ├── Sends Quick Reply message via Chatwoot Messages API
              ├── Updates Contact custom_attributes (bot_state, bot_courses, bot_branch)
              ├── Creates/updates CRM Lead with structured data
              └── On final step: bot_handoff + assign best-match agent
```

### Components

| Component | File | Responsibility |
|---|---|---|
| Bot Webhook Endpoint | `mmm_custom/bot_api.py` | Receives Agent Bot webhook from Chatwoot, validates HMAC, dispatches to Bot Engine |
| Bot Engine (State Machine) | `mmm_custom/bot_engine.py` | Pure-logic state machine: given current state + user input → returns next state + actions |
| Chatwoot Client | `mmm_custom/chatwoot_client.py` | Thin wrapper around Chatwoot REST API v1 for sending messages, updating contacts, toggling status, assigning agents |
| Agent Bot Setup Script | `scripts/setup-agent-bot.py` | One-time script to create AgentBot record and link to EduFlow Messenger inbox in Chatwoot |
| Unit Tests | `mmm_custom/tests/test_bot_engine.py`, `mmm_custom/tests/test_bot_api.py` | Offline tests with mocked Chatwoot API |

### Data Flow

1. **Chatwoot → Bot Endpoint**: Chatwoot Agent Bot webhook sends `message_created` event with conversation and message payload.
2. **Bot Endpoint → Chatwoot API**: Bot reads contact's `custom_attributes.bot_state` via the webhook payload's contact data, then calls Chatwoot API to send the next Quick Reply message.
3. **Bot Endpoint → Frappe CRM**: On completion, creates/updates `CRM Lead` with `course_interest` and `branch` fields.
4. **Bot Endpoint → Chatwoot API**: Calls `toggle_status` (pending→open) and `assignments` to hand off to human agent.

## Conversation Flow

### Step 1: Greeting + Ask Course (state: `greeting` → `await_course`)

**Trigger**: First `message_created` event for a conversation where `bot_state` is empty/null.

**Bot sends**:
```
🎓 Chào bạn! EduFlow Academy rất vui được hỗ trợ.
Bạn đang quan tâm đến bộ môn nào ạ?
```
Quick Replies: `🇬🇧 Tiếng Anh` | `🏊 Bơi lội` | `🧮 Toán tư duy`

**State update**: `bot_state = "await_course"`, `bot_courses = []`

### Step 2: Multi-select Course Loop (state: `await_course`)

**Trigger**: Customer taps a course Quick Reply button.

**Logic**:
- Append selected course to `bot_courses` list.
- Remove selected course from available options.
- If all 3 courses selected OR customer taps "✅ Xong, tiếp tục" → transition to `await_branch`.
- Otherwise → send another Quick Reply with remaining courses + "✅ Xong, tiếp tục".

**Bot sends (after first selection)**:
```
Đã ghi nhận {course} ✅
Bạn muốn đăng ký thêm bộ môn nào không?
```
Quick Replies: `{remaining courses}` | `✅ Xong, tiếp tục`

**Bot sends (after "Xong" or all selected)**:
→ Immediately transitions to Step 3.

### Step 3: Ask Branch (state: `await_branch`)

**Bot sends**:
```
📍 Tuyệt vời! Bạn muốn học tại cơ sở nào ạ?
```
Quick Replies: `📍 CS1 Bình Thạnh` | `📍 CS2 Quận 1` | `📍 CS3 Thủ Đức`

### Step 4: Summary + Handoff (state: `await_branch` → `completed`)

**Trigger**: Customer taps a branch Quick Reply button.

**Actions** (in order):
1. Update Chatwoot Contact `custom_attributes`: `bot_state = "completed"`, `bot_branch = "{branch_value}"`.
2. Create or update CRM Lead via `frappe.get_doc` / `frappe.new_doc`:
   - `course_interest`: comma-joined selected courses (e.g., "Tiếng Anh, Bơi lội")
   - `branch`: selected branch value
   - `source`: "Messenger Bot"
3. Find best-match agent: query Chatwoot agents with `custom_attributes.branch == selected_branch`, pick the one with fewest open conversations.
4. Send confirmation message via Chatwoot API (plain text, no quick replies).
5. Assign agent via Chatwoot Assignments API.
6. Bot handoff: `POST /conversations/{id}/toggle_status` with `status: "open"`.

**Bot sends**:
```
✅ Cảm ơn bạn đã cung cấp thông tin!
📚 Bộ môn: {courses_display}
📍 Cơ sở: {branch_display}

Chuyên viên tư vấn sẽ liên hệ bạn ngay bây giờ nhé! 😊
```

### Edge Cases

| Scenario | Handling |
|---|---|
| Customer sends free-text instead of tapping Quick Reply | Bot re-sends the current step's Quick Reply with a gentle reminder: "Bạn vui lòng chọn một trong các tùy chọn bên dưới nhé 👇" |
| Customer sends message after bot completed (state=completed) | Ignored by bot — human agent handles |
| Bot webhook receives `message_type: outgoing` (bot's own messages) | Ignored — only process `message_type: 0` (incoming) |
| Agent Bot webhook receives non-`message_created` events | Ignored — only process `message_created` |
| Chatwoot API call fails | Log error, do not crash. Retry once. If still fails, bot_handoff immediately so customer isn't stuck. |
| No agent matches the branch | Assign to any available agent (fallback to no branch filter) |

## State Machine Definition

```python
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

DONE_TOKEN = "done"  # value for "✅ Xong, tiếp tục"
```

**State transitions** (pure function, no side effects):

```python
def transition(state: str, user_input: str, selected_courses: list[str]) -> TransitionResult:
    """
    Returns: TransitionResult(
        next_state: str,
        message: str,
        quick_replies: list[dict] | None,
        actions: list[str]  # e.g. ["update_lead", "assign_agent", "bot_handoff"]
    )
    """
```

## Agent Assignment Algorithm

```python
def find_best_agent(branch_key: str, chatwoot_client) -> int | None:
    """
    1. GET /api/v1/accounts/{id}/agents → list all agents
    2. Filter agents where custom_attributes.branch == branch_key
    3. For each matching agent, GET /api/v1/accounts/{id}/agents/{agent_id}/conversations?status=open
       → count open conversations
    4. Return agent_id with fewest open conversations
    5. If no branch match → fallback: return agent with fewest open conversations overall
    """
```

## Chatwoot API Interactions

All calls use the Agent Bot's `access_token` (created during Agent Bot setup, stored in Chatwoot's `access_tokens` table via `AccessTokenable` concern).

| Action | Method | Endpoint | Key Body Fields |
|---|---|---|---|
| Send Quick Reply message | POST | `/api/v1/accounts/{a}/conversations/{c}/messages` | `content`, `message_type: "outgoing"`, `content_type: "input_select"`, `content_attributes.items` |
| Send plain text message | POST | `/api/v1/accounts/{a}/conversations/{c}/messages` | `content`, `message_type: "outgoing"` |
| Update contact attributes | PATCH | `/api/v1/accounts/{a}/contacts/{contact_id}` | `custom_attributes: {bot_state, bot_courses, bot_branch}` |
| Toggle status (handoff) | POST | `/api/v1/accounts/{a}/conversations/{c}/toggle_status` | `status: "open"` |
| Assign agent | POST | `/api/v1/accounts/{a}/conversations/{c}/assignments` | `assignee_id` |
| List agents | GET | `/api/v1/accounts/{a}/agents` | — |

## Security

- **Webhook HMAC validation**: The Agent Bot webhook endpoint (`agent_bot_webhook`) validates the `X-Chatwoot-Signature` header using the Agent Bot's `secret` — same pattern as the existing `chatwoot_sync` endpoint.
- **Chatwoot API auth**: Uses the Agent Bot's `access_token` in `Authorization: Bearer {token}` header. Token is stored as a site config in Frappe (`bot_chatwoot_api_token`), never committed.
- **No secrets in code**: All tokens configured via `scripts/setup-agent-bot.py` at runtime.

## Configuration Data

Stored as Frappe site config keys (set via `bench --site crm.localhost set-config`):

| Key | Value | Description |
|---|---|---|
| `chatwoot_bot_api_token` | (runtime) | Agent Bot's access_token for Chatwoot API |
| `chatwoot_bot_account_id` | `1` | Chatwoot account ID |
| `chatwoot_base_url` | `http://host.docker.internal:3000` | Chatwoot API base URL (internal Docker network) |

## Testing Strategy

### Unit Tests (offline, no Docker required)

- **`test_bot_engine.py`**: Test every state transition:
  - `greeting` → sends course Quick Reply
  - `await_course` + valid course → adds to list, sends remaining + "Xong"
  - `await_course` + "done" → transitions to `await_branch`
  - `await_course` + all 3 selected → auto-transitions to `await_branch`
  - `await_branch` + valid branch → transitions to `completed` with actions
  - Any state + invalid input → re-sends current Quick Reply
  - `completed` → returns no-op

- **`test_bot_api.py`**: Test webhook endpoint:
  - Valid HMAC → processes message
  - Invalid HMAC → returns 401
  - Outgoing message → ignored
  - Non-message_created event → ignored

### Integration Test (requires live stacks)

- Send simulated Agent Bot webhook → verify Quick Reply message appears in Chatwoot conversation
- Full flow: simulate 3 messages → verify CRM Lead created with correct fields → verify agent assigned

## Relationship to Existing Code

- **`mmm_custom/api.py` (chatwoot_sync)**: Remains unchanged. It handles the *general* Chatwoot webhook (conversation events for Lead sync). The new `bot_api.py` handles specifically the *Agent Bot* webhook (bot conversation logic). They are separate endpoints with separate webhook sources.
- **`mmm_custom/dedupe.py`**: Reused by `bot_engine.py` when creating/updating CRM Leads — same dedup logic (email/phone/name match).
- **`mmm_custom/setup.py`**: Will add `branch` as a new custom field on CRM Lead alongside the existing `course_interest` and `chatwoot_contact_id`.
