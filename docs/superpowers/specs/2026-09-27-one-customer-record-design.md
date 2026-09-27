# One Customer Record, Branch Messaging, Staff Switch — Design Spec

Visual walkthrough shared with the owner: "Một khách hàng, một hồ sơ" (artifact). The owner chose option A
(messaging inside the CRM) and asked for a way for an admin to switch into a staff account for demos.

## Purpose

- The CRM Leads list and `/crm/admin/customers` read the same `CRM Lead` rows but look like two systems:
  the list lacks source, course, branch and hotness; the admin dashboard does not lead to the list.
- Consultants only see Leads they own or are assigned (Frappe CRM default for Sales User), not the rest
  of their branch.
- Reading or answering a customer means leaving the Lead for the Chatwoot inbox.
- Demos need a quick way to show what a consultant sees.

## Confirmed Decisions

- Option A: consultants read and answer a Lead's conversation on the Lead page, through the Chatwoot API
  and under their own Chatwoot identity. The full Chatwoot inbox stays for managers and the central team.
- Branch scope: a consultant sees every Lead/Deal of their branch (`territory = Consultant.branch`), plus
  what they own or are assigned. A consultant without a branch (Tổng đài) sees Leads without a territory.
  A B2B consultant sees Leads owned by any B2B consultant. Managers keep seeing everything.
- Staff switch: a System Manager can switch the session into an active Consultant account (never into a
  manager) and back, reusing Frappe's `LoginManager.impersonate`. Every switch is written to the Activity
  Log. A site config flag `disable_staff_switch` turns it off.

## Design

### S · Staff switch (`mmm_custom/staff_switch.py`)

- `state()` → `{user, full_name, impersonated_by, can_switch}`; the CRM reads it on load.
- `switch_to(user)`: caller is a System Manager, not already switched, flag not set; target is an enabled
  User with an active Consultant record and no manager role. Writes an Activity Log row, then
  `frappe.local.login_manager.impersonate(user)` (session data `impersonated_by` = the manager).
- `switch_back()`: only when the session has `impersonated_by`; logs, then
  `login_manager.login_as(original)` (a fresh session without the flag).
- UI: "Xem như nhân viên này" on each active row of `/crm/admin/staff`; a banner across the CRM while
  switched: "Đang xem với tư cách … · Quay lại tài khoản quản trị".

### B1 · One record, two views

- `CRMLead.default_list_data()` columns: name, branch (`territory`), course (`course_interest`), source,
  hotness (`ai_hotness`), status, mobile, owner, modified.
- Quick filters for Lead: name, status, branch, source, hotness (CRM Global Settings "Quick Filters").
- Leads list accepts `?filters=<json>` once: it applies them as the user's list filters and drops the
  query. `/crm/admin/customers` uses it: stat cards, source cards and staff rows open the filtered list
  (the "Đã ghi danh" card opens Deals); lead rows open the Lead. Chart bars are not links yet.
- Hotness shows as a coloured badge (Nóng/Ấm/Lạnh) in the list; clicking it filters by it.

### B2 · Branch scope

- `crm/permissions/org_hierarchy.py` ORs in criteria from a new hook `crm_record_scope`
  (`fn(user, doctype, DT) -> criterion | None`). mmm_custom provides `mmm_custom.scope.record_scope`
  implementing the rules above for CRM Lead and CRM Deal. List queries and single-document checks share it.

### B3 · Messages on the Lead (read)

- `mmm_custom/lead_chat.py`: `conversation_of(lead)` = the newest `Bot Conversation` with `lead`, else the
  newest conversation of the Lead's `chatwoot_contact_id` (Chatwoot contact conversations API).
- `messages(lead)`: `frappe.has_permission("CRM Lead", "read", lead)` (so branch scope applies), then the
  conversation's messages mapped to `{id, kind: customer|bot|staff|note, text, sender, at}`; activity and
  private notes are kept apart. `None` when the Lead has no conversation.
- Lead page: a "Tin nhắn" tab and a "Nhắn tin" header button that opens it. Replaces the "Mở cuộc chat"
  form script action, which migrate switches off (the tab links to Chatwoot too). Not yet: a per-row
  "Nhắn tin" button on the Leads list, and the mobile Lead page.

### B4 · Answer from the CRM

- Chatwoot Platform App: `scripts/configure-chatwoot.py` creates it (once), grants it every account user,
  and copies its token to the site config (`chatwoot_platform_token`).
- `staff_sync` stores each consultant's own Chatwoot access token (Consultant field
  `chatwoot_access_token`, Password type) from `GET /platform/api/v1/users/{id}`.
- `lead_chat.send(lead, text)`: read permission on the Lead, a conversation exists, the sender has a stored
  token; posts as that agent. Chatwoot's webhook then marks the conversation consultant-replied, as when
  answering inside Chatwoot. Managers without a Consultant record send with the admin token.
- The tab polls every 15 s while open.

## Testing

- Unit: switch rules (who may switch, into whom, back); scope criteria per role; conversation lookup and
  message mapping; send refusals (no permission, no conversation, no token); platform token fetch.
- `yarn build`; mocked-browser check of the banner, the Leads columns/filter link and the Tin nhắn tab.
- Live: switch into a CN Dĩ An consultant, see only CN Dĩ An Leads, open one, read and answer; the answer
  shows in Chatwoot under that consultant.
