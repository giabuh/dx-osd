# Task prompt — Bot admin UI: tidy the desk (A) + standalone `/bot` page (B)

Hand this whole file to the executing agent. It is self-contained; read the files it names before editing.

## Context

Repository `dx-osd` (read `AGENTS.md` first — its working rules are binding). Two products run side by side:

- **Frappe CRM** on `http://127.0.0.1:8000`. Two UIs on the same port:
  - `/crm` — the Vue CRM app (vendored in `crm/`). **Owned by a teammate. Do not edit anything under `crm/`.**
  - `/app` — the Frappe desk. Our custom Frappe app `mmm_custom` (`frappe-custom/mmm_custom/mmm_custom/`) holds the
    Messenger lead bot ("lead engine") and shows its pages and DocTypes here.
- **Chatwoot** on `http://127.0.0.1:3000` (inbox). Not touched by this task.

Work split (decision D-089 in `docs/superpowers/specs/2026-09-26-edu-lead-engine/decisions.md`): the bot owner works in
`mmm_custom` and Chatwoot; the CRM teammate works in `/crm`. The two meet only through standard CRM Lead fields.

What exists today (all in `frappe-custom/mmm_custom/mmm_custom/`):

| Piece | Where | Notes |
|---|---|---|
| Desk workspace "Bot Sao Việt" | `mmm_custom/workspace/bot_sao_viet/bot_sao_viet.json` | Name `Bot Sao Viet`, route `/app/bot-sao-viet`, 14 shortcuts, `"icon": "chat"` (**invalid**: not in Frappe's icon set, so the sidebar shows no icon) |
| Bot Knowledge page | `mmm_custom/page/bot_knowledge/` + `engine/knowledge.py` | Whitelisted `mmm_custom.engine.knowledge.overview()` (all courses, coverage) and `.course(product)` (one course: summary, syllabus, FAQs with rendered replies, schedules, fee, gaps, `jev_reads`). Roles: System Manager, Sales Manager |
| Bot Playground page | `mmm_custom/page/bot_playground/` + `engine/playground.py` | Whitelisted `simulate(session, text, lead=None, jev=0)`, `reset(session)`, `replay(log_name, jev=0)`; dry run, never sends or writes Leads |
| Lead qualification | `engine/qualify.py` | Bot sets CRM Lead `status` New / Qualified / Unqualified; public CRM views "Khách tiềm năng", "Không tiềm năng" |
| Workspace test | `tests/test_workspace_json.py` | Checks shortcuts resolve to real DocTypes/Pages |

Verified facts you can rely on:

- Frappe v15 icon names that exist include: `education`, `support`, `crm`, `customer`, `dashboard`, `tool`, `setting`,
  `users`, `message`, `chart` (from `frappe/public/icons/timeless/icons.svg` in the bench).
- The `/crm` UI's user dropdown (top-left logo menu) has an **Apps** submenu built from `frappe.apps.get_apps`
  (`crm/frontend/src/components/UserDropdown.vue`, `crmSiblingApps`). `get_apps` lists every installed app's
  `add_to_apps_screen` hook entries (`frappe/apps.py`), filtered by an optional `has_permission` callable. So an entry in
  `mmm_custom/hooks.py` appears in `/crm` without editing `crm/`. CRM's own entry is in `crm/crm/hooks.py` (copy its shape).
- `FCRM Settings.dropdown_items` (child DocType `CRM Dropdown Item`: `label`, `type` Route/Separator, `route`, `hidden`,
  `is_standard`, `icon`, `open_in_new_window`, `name1`) adds custom links to that same dropdown. It is **site data**, not code.
- Workspace visibility: `Workspace.is_hidden`; `frappe.desk.doctype.workspace.workspace.hide_unhide_page` exists.
  Standard workspaces of other apps are re-synced on `bench migrate`, so a hide must be re-applied by an
  `after_migrate` hook (`mmm_custom/hooks.py` already has `after_migrate = ["mmm_custom.setup.create_catalog_fields"]`).
- The desk sticky header hides the first sidebar item and the first workspace block at the user's browser zoom level;
  the same happens on the upstream "Frappe CRM" workspace. Not caused by our code.

## Global constraints

- **Never edit `crm/` or `chatwoot/`.** Everything goes in `frappe-custom/mmm_custom/` (and docs).
- TDD for every behaviour change: failing test first, watch it fail, then implement. Offline suite must stay green:
  `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests` (currently 402 tests, all OK).
- Code, comments, commits and docs in English; customer/user-facing UI text in Vietnamese.
- Commits: single-line conventional message (`feat(scope): ...`), no body, **no Co-Authored-By trailer**, stage explicit
  paths only (never `git add -A`/`.`). Commit per task. **Do not push.**
- Never print or commit secrets (`site_config.json` keys, `.env`, tokens).
- Never run `docker compose down -v`, `docker volume rm`, `docker system prune`.
- Apply to the running site: `docker exec crm-frappe-1 bash -lc "cd /home/frappe/frappe-bench && bench --site crm.localhost migrate"`,
  then `docker restart crm-frappe-1` (wait until `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/method/ping` → 200).
- Test logins: `admin@eduflow.vn` / `123456` (System Manager + Sales Manager) — dev only, never write it into code or docs.
- The bot serves real customers on Messenger; a CRM restart interrupts it for ~10 s. Do not change engine behaviour
  (`engine/decide.py`, `combine.py`, `pipeline.py`, …) in this task.

---

## Part A — Tidy the desk and link it from `/crm` (small, do first)

### A1. Valid workspace icon
- Change `"icon": "chat"` → `"icon": "education"` in `bot_sao_viet.json`.
- Test first: extend `tests/test_workspace_json.py` with a check that the icon is in an allow-list constant of known
  Frappe icon names (at least the names listed above).

### A2. Hide unused standard desk workspaces
- Hide **Website, Tools, Integrations, Build** for everyone. **Keep Users visible** (it is where staff accounts are made)
  unless the user says otherwise — list it as an open choice in your final report.
- Implement `mmm_custom/desk.py` (or a function in `setup.py`) `hide_unused_workspaces()` that sets `is_hidden = 1` on
  those Workspace records if they exist (skip missing ones silently — a site may not have them), idempotent, and add it to
  `after_migrate` in `hooks.py`. Keep the list as a module constant `HIDDEN_WORKSPACES`.
- Unit-test with a mocked `frappe` (see how `tests/test_catalog_setup.py` mocks `frappe`): only listed, existing workspaces
  are updated; running twice changes nothing the second time.
- They stay reachable by URL (`/app/website`, …) and the desk search bar — say so in the report.

### A3. Entry point from `/crm`
- Add to `mmm_custom/hooks.py`:
  ```python
  add_to_apps_screen = [{
      "name": "mmm_custom",
      "logo": "/assets/mmm_custom/images/bot.svg",
      "title": "Bot Sao Việt",
      "route": "/bot",            # the Part B page; use "/app/bot-sao-viet" if Part B is not merged
      "has_permission": "mmm_custom.desk.can_open_bot",
  }]
  ```
- `can_open_bot()` returns True for System Manager or Sales Manager (`frappe.get_roles()`); unit-test it.
- Add a simple SVG logo at `mmm_custom/public/images/bot.svg` (single-colour, no external assets). Run
  `bench build --app mmm_custom` if the asset is not served (check `curl -I http://127.0.0.1:8000/assets/mmm_custom/images/bot.svg`).
- Optional, data only: add a `CRM Dropdown Item` "Bot Sao Việt" (type Route, route `/bot`, `open_in_new_window` 0) to
  `FCRM Settings.dropdown_items` via an idempotent function called from `after_migrate`. Do it only if `add_to_apps_screen`
  does not show up in the `/crm` dropdown.

### A verification (quote real output)
- Suite green.
- Screenshot (Playwright) of `/app/bot-sao-viet`: icon visible; sidebar no longer shows Website/Tools/Integrations/Build.
- Screenshot of `/crm` with the logo dropdown open → Apps → "Bot Sao Việt" visible and it navigates to the target route.

---

## Part B — Standalone bot page at `8000/bot`

Goal: one clean page, outside the desk, where the bot owner runs the bot day to day and demos it. Vietnamese UI.
It reuses the existing whitelisted endpoints — no new business logic.

### B1. Route and access
- Frappe www page: `mmm_custom/www/bot.html` + `mmm_custom/www/bot.py`. In `get_context`: require login
  (`frappe.session.user == "Guest"` → redirect to `/login?redirect-to=/bot`), require `can_open_bot()` (else 403 via
  `frappe.throw(..., frappe.PermissionError)`), set `context.no_cache = 1`, `context.csrf_token = frappe.sessions.get_csrf_token()`.
- Full-page layout (do not rely on the website navbar/footer); must work at 1280 px and at 390 px wide (single column).
- Plain HTML + CSS + vanilla JS in the page (no build step, no new npm deps). Calls go to `/api/method/<dotted.path>` with
  `fetch`, `X-Frappe-CSRF-Token` header, `credentials: "same-origin"`. Escape every value inserted into HTML.

### B2. Layout — three tabs
1. **Tổng quan** (default)
   - Cards: new Leads created by the bot today; Qualified today; Unqualified today; bot conversations handed to a
     consultant today; average knowledge coverage (%).
   - Table "Khách tiềm năng mới nhất" (last 10 Qualified bot Leads): name, phone, course (`course_interest`), branch
     (`territory`), consultant (`lead_owner`), time; each row links to `/crm/leads/<name>` (open in same tab).
   - Needs one new whitelisted endpoint `mmm_custom.engine.dashboard.summary()` (roles as `can_open_bot`). Put the counting
     in a **pure** function (input: plain rows; output: dict) and unit-test it; the whitelisted wrapper only queries.
     Bot Leads = `source = "Messenger Bot"`; "today" = site timezone date; statuses from `engine/qualify.py` constants.
2. **Tri thức khóa học** — rebuild the Bot Knowledge view: course list grouped by course group with coverage bar and FAQ
   count, search box, click → detail (overview, syllabus, FAQ replies as the customer reads them, next classes, fee
   after promotion, gaps). Uses `knowledge.overview` / `knowledge.course`. Each course has a button "Sửa dữ liệu khóa học"
   → `/app/crm-product/<code>` (new tab) — editing stays in the desk form for now.
3. **Thử chat với bot** — chat box using `playground.simulate` / `playground.reset`, a "Dùng Jev" toggle, quick-reply
   buttons rendered as clickable chips, and a collapsible "Bot hiểu gì" panel showing `decision.reason`, keyword matches and
   Jev answers from the `simulate` result.
- Header: title "Bot Sao Việt", links "Mở CRM" (`/crm`), "Mở Chatwoot" (`http://127.0.0.1:3000` — read the URL from site
  config key `chatwoot_base_url` if present; never expose tokens), "Quản trị nâng cao" (`/app/bot-sao-viet`).

### B3. Tests
- Offline: pure dashboard function (counts, today boundary, only bot-source Leads, latest-10 ordering); `get_context`
  access rules with mocked `frappe` (guest → redirect, wrong role → PermissionError, manager → context has csrf token).
- JS: `node --check` on any extracted `.js` file (if the JS is inline, keep it in a separate `mmm_custom/public/js/bot_page.js`
  loaded by the page so it can be checked).

### B verification (quote real output)
- Suite green; `node --check` clean.
- On the running site, logged in as the test admin: Playwright screenshots of each tab at 1280 px and the overview at
  390 px; no console errors (`browser_console_messages` level error → 0).
- Logged out, `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/bot` → 302/303 to login (quote it).
- In "Thử chat với bot", send "mình muốn học excel" then "khóa này học những gì" with Jev on → the reply contains the
  Excel syllabus (bullet lines). Quote the reply text.
- Part A3's Apps entry now points to `/bot` and opens it.

---

## Docs (last commit)

- `docs/superpowers/specs/2026-09-26-edu-lead-engine/decisions.md`: append D-091 (desk tidy + `/crm` entry point via
  `add_to_apps_screen`) and D-092 (standalone `/bot` page: tabs, endpoints, access) — format like the existing rows,
  status `approved`.
- `docs/superpowers/specs/2026-09-26-edu-lead-engine/current-state.md`: rows for `desk.py`, `www/bot.*`, `engine/dashboard.py`.
- No row in `docs/vendored-upstreams.md` is needed (nothing vendored is edited) — if you find you must edit `crm/`, stop
  and ask instead.

## Final report (to the user, in Vietnamese)

What changed, the commits, the verification output quoted, anything not done, and the open choice about hiding **Users**.
