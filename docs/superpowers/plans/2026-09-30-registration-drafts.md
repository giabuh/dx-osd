# Plan: registration drafts, one way to "Đã đăng ký", VND, classes page

Spec: `docs/superpowers/specs/2026-09-30-registration-drafts-design.md`. One commit per layer.

- [x] **Layer 1 (+VND)** `lifecycle.py` (Awaiting Confirmation, `guard_converted`), `enrolment.py`
  (`lead_after_deal_change`, layouts, defaults), `setup.py` (`ensure_vnd`, no `payment_due_date`), `followup.py`,
  `hooks.py`, patch `v1_2/simplify_registration`, `vi.po`. Tests: `test_lifecycle`, `test_enrolment`,
  `test_followup`, `test_currency`.
- [x] **Layer 2** `ConvertToDealModal.vue` (no Contact block, live registration notice), `Lead.vue` / `MobileLead.vue`
  status guard, kanban error toast (`ViewControls.vue`), bulk edit refusal (`EditValueModal.vue`).
- [x] **Layer 3** action `enrol` (`engine/actions.py`, registries, `effects.py`, `pipeline.enrol_drafts`),
  `enrolment.create_draft`, `open_schedules` returns `name` / `title`, demo bot data, patch `v1_2/draft_registration`.
  Tests: `test_engine_enrol`, `test_enrolment`.
- [x] **Layer 4** `intelligence.py`: `enrol_eligible`, the `enrol` question, `decide_actions(..., enrol_floor)`,
  `_draft_registration`. Tests: `test_intelligence`.
- [x] **Layer 5** `classes.py`, `pages/Classes.vue`, `components/Classes/*`, route, sidebar. Tests: `test_classes`.
- [ ] **Ops** check `Facebook Post` rows with status Scheduled, then `bench --site crm.localhost scheduler enable`
  (starts follow-up at 08:00, the 5-minute fallback, quiz reminders, staff sync, autopilot publishing).
- [ ] **Browser check** (needs a login): the modal, the status dropdown, kanban drop, the classes page.

Deploy: `bench --site crm.localhost migrate && bench build --app crm` (or `npx vite build` in `crm/frontend`), then
restart `crm-frappe-1` so the worker loads the new engine code.
