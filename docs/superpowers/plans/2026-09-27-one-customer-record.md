# One Customer Record — Implementation Plan

Spec: `docs/superpowers/specs/2026-09-27-one-customer-record-design.md`. One commit per step; each step works on its own.

1. **S — Staff switch**: `staff_switch.py` (+ tests); CRM banner (`components/StaffSwitchBanner.vue` in the desktop and mobile layouts); "Xem như nhân viên này" in `AdminStaff.vue`.
2. **B1 — One record, two views**: Lead default columns and quick filters (`crm_lead.py`, mmm_custom after_migrate for the global quick filters); `?filters=` in `ViewControls.vue`; links from `AdminCustomers.vue`.
3. **B2 — Branch scope**: `crm_record_scope` hook in `org_hierarchy.py`; `mmm_custom/scope.py` (+ tests).
4. **B3 — Messages (read)**: `lead_chat.py` (`conversation_of`, `messages`) + client methods (+ tests); `components/Activities/LeadChat.vue` as a Lead tab; "Nhắn tin" header button.
5. **B4 — Answer from the CRM**: Platform App in `configure-chatwoot.py`; Consultant `chatwoot_access_token`; `staff_sync` token fetch; `lead_chat.send`; reply box + polling (+ tests).
6. **Docs + verify**: current-state, decisions; unit tests, `yarn build`, mocked-browser screenshots.
