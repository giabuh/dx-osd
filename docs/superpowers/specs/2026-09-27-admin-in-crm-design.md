# Admin Inside the CRM — Design Spec

## Purpose

The manager screens (overview, branches, staff, course knowledge, bot playground) live on `/admin`, a hand-written HTML page with vanilla JavaScript (`www/admin.html`, `public/js/bot_page.js`). It looks and behaves unlike `/crm`, and every new screen adds string-built HTML. Move these screens into the Frappe CRM frontend so managers work in one app with the CRM's own components and style.

Builds on `2026-09-27-admin-home-crm-trim-design.md` (which created `/admin`).

## Confirmed Decisions

- The screens become Vue pages in `crm/frontend`, built with the same frappe-ui components and Tailwind tokens the CRM pages use (LayoutHeader + Breadcrumbs, Tabs, ListView, Dialog, FormControl, Button, Badge, toast).
- One route per tab: `/crm/admin/overview`, `/crm/admin/branches`, `/crm/admin/staff`, `/crm/admin/knowledge`, `/crm/admin/playground`; `/crm/admin` opens the overview.
- Same operations, same data: the pages call the existing whitelisted methods unchanged (`engine.dashboard.summary`, `bot_admin.*`, `engine.knowledge.*`, `engine.playground.*`). The only backend addition is a read-only `bot_admin.app_links()` for the Chatwoot URL the page used to get from its template context.
- Access: only managers (System Manager, Sales Manager) see the sidebar item and reach the route; others are sent to the CRM home. The server keeps its own checks on every method.
- `/admin` and `/bot` redirect to `/crm/admin`; an old `#tab` fragment opens that tab. The apps screen entry and the managers' landing page point at `/crm/admin`.
- `www/admin.*` and `public/js/bot_page.js` are removed. The hidden Facebook Lead Ads pane is not ported; `lead_ads.py` stays as an API without a screen.

## Screens

| Tab | Content | Methods |
|---|---|---|
| Tổng quan | Five stat cards; latest qualified Leads (links to the Lead page) | `engine.dashboard.summary` |
| Chi nhánh | Branches grouped by area; add/edit dialog (area select or new area, button label, code, address, hotline, map link, aliases); staff count opens the staff tab filtered to that branch | `bot_admin.branches`, `save_branch` |
| Nhân viên | Search + branch filter (incl. "Tổng đài / B2B"); table with level, specialties, status, Chatwoot sync badge; add/edit dialog; reload 8 s after save to show the sync | `bot_admin.staff`, `save_staff` |
| Tri thức khóa học | Searchable course list grouped by course group with coverage bars; detail panel (gaps, overview, fee/promotions, syllabus, FAQs, next classes, desk edit link); add-course dialog with FAQ rows; import one course from a JSON file into that dialog | `engine.knowledge.overview`, `course`, `bot_admin.course_groups`, `save_course` |
| Thử chat với bot | Chat log, quick-reply chips, "Dùng Jev" toggle, inspector (reason, matched keywords, Jev answer), new conversation | `engine.playground.simulate`, `reset` |

Header actions: "Mở Chatwoot" (new tab) and "Quản trị nâng cao" (`/app/bot-sao-việt`).

## Testing

- Unit tests: hooks (redirects, apps route), `app_links` access, removed page tests.
- `yarn build` in `crm/frontend` succeeds.
- Screenshot each tab against mocked API responses; on the running stack, walk every tab as a manager and confirm a consultant is sent home.
