# Admin Inside the CRM — Implementation Plan

Spec: `docs/superpowers/specs/2026-09-27-admin-in-crm-design.md`.

1. **Frontend shell** — `crm/frontend/src/pages/Admin.vue` (header, breadcrumbs, tabs bound to `/admin/:tab?`), route + manager guard in `router.js`, sidebar "Admin" item → `{ name: 'Admin' }`, `#tab` from old links → tab.
2. **Shared helpers** — `components/Admin/adminApi.js`: `adminCall` (frappe-ui `call`, readable error), `money`, `displayTime`.
3. **Tabs** — `components/Admin/AdminOverview.vue`, `AdminBranches.vue` + `BranchDialog.vue`, `AdminStaff.vue` + `StaffDialog.vue`, `AdminKnowledge.vue` + `CourseDialog.vue`, `AdminPlayground.vue`; each ports the behaviour of the matching part of `bot_page.js`.
4. **Backend** — `bot_admin.app_links()`; hooks: apps route `/crm/admin`, redirects `/admin` and `/bot` → `/crm/admin`; workspace shortcut `/crm/admin`; delete `www/admin.*`, `public/js/bot_page.js`, `tests/test_bot_page.py`; update `test_desk.py`, add `app_links` test.
5. **Docs** — `current-state.md`, decision D-096.
6. **Verify** — unit tests; `yarn build`; Playwright screenshots of each tab with mocked APIs.
