# Admin Home, Trimmed CRM, Chatwoot ↔ CRM Links — Implementation Plan

Spec: `docs/superpowers/specs/2026-09-27-admin-home-crm-trim-design.md`.

Area checks: CRM Integration (`python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests`), CRM customization (fresh bench, `/crm` build), live stack manual checks from the spec's Testing section.

## Task 1 — `/bot` → `/admin`

- `git mv www/bot.html www/admin.html`, `git mv www/bot.py www/admin.py`; guest redirect `/login?redirect-to=/admin`; refusal text says "trang quản trị".
- `hooks.py`: `website_redirects = [{"source": "/bot", "target": "/admin"}]`; apps entry title "Quản trị", route `/admin`.
- `bot_sao_viet.json` shortcut URL `/admin`.
- `crm/frontend/.../AppSidebar.vue` `openBotAdmin()` → `/admin` (the "Admin" item already exists for managers).
- Tests: `test_bot_page.py` loads `www/admin.py` and expects `/admin`; `test_desk.py` expects route `/admin`, title "Quản trị" and the redirect; `test_workspace_json.py` accepts `/crm` or `/admin` URLs.

## Task 2 — Home by role (`desk.py`)

- `default_app_for(roles, current)` (pure): manager + empty → `"mmm_custom"`; non-manager + `"mmm_custom"` → `""`; otherwise `None` (leave).
- `apply_default_apps()`: System Settings `default_app = "crm"` when empty; every enabled System User through `default_app_for` with `frappe.get_roles(user)`; writes with `frappe.db.set_value(..., update_modified=False)` only when the value changes.
- `apply_user_default_app(doc, method=None)`: same decision for one saved User (roles from `doc.roles`; Administrator counts as manager).
- Hooks: `after_migrate` += `mmm_custom.desk.apply_default_apps`; `doc_events["User"] = {"on_update": "mmm_custom.desk.apply_user_default_app"}`.
- Tests: the six manager/consultant × empty/`mmm_custom`/other cases; `apply_default_apps` writes only changed users and the empty System Setting, and is a no-op the second time.

## Task 3 — Lead Ads API (`lead_ads.py`)

- Whitelisted, each starts with `_require_access()` (`desk.can_open_bot()` → else `frappe.PermissionError`): `list_sources`, `pages` (stored Pages + forms for the edit form, no tokens), `connect`, `save_source`, `set_enabled`, `form_mapping`, `save_mapping`, `sync_now`, `failures`, `retry`.
- Pure helpers: `lead_field_choices(meta_fields)`, `clean_source_values(values, is_new)`, `clean_mapping(mapping, allowed)`, `page_choices(pages)` (strips Facebook tokens from `connect`'s result), `short_error(traceback)`.
- `save_source` names a new source by the entered name or the form name (`Lead Sync Source` is `autoname: prompt`).
- Tests: `test_lead_ads.py` for every pure helper and a refusal for a non-manager.

## Task 4 — Lead Ads tab (`admin.html`, `bot_page.js`)

- Nav button `data-tab="lead-ads"`, pane `#lead-ads`: sources table, "+ Kết nối form", inline source form (token → Tải Page → Page → Form → frequency → Lưu), question-mapping table, "Lỗi đồng bộ gần đây" with "Thử lại".
- JS: add `lead-ads` to `TABS` and `loaders`; reuse `call`, `escapeHtml`, `options`, `showError`, `.notice`.
- Check: `node --check public/js/bot_page.js`; HTML ids referenced from JS exist (small script run once).

## Task 5 — Trimmed CRM sidebar

- `AppSidebar.vue`: drop Contacts, Organizations, Notes, Call Logs from `links`. Their icon imports stay: `getIcon()` and the notes help item still use them.
- `crm/crm/locale/vi.po`: `Deals` → `Học viên đăng ký`.
- Deploy: `bench build --app crm` and `bench --site crm.localhost clear-cache` (translations reload from the `.po`).

## Task 6 — Chatwoot ↔ CRM links (`crm_links.py`, bot)

- `lead_url`, `chatwoot_contact_url` (pure); `crm_base(conf)`, `chatwoot_base(conf)`; whitelisted `open_chat_url(lead)`; `ensure_lead_form_script()` (after_migrate); `backfill_contact_links()`.
- `lead.contact_update(..., crm_url="")` adds `ho_so_crm`; `ChatwootEffects(bot, user, crm_url="")` passes it; `chatwoot_effects(conf)` passes `crm_base(conf)`.
- `chatwoot_setup.CONTACT_ATTRIBUTES` becomes `(key, name, display_type)`; `ho_so_crm` is `link`.
- Tests: `test_crm_links.py`; `test_engine_contact_sync.py` updated for `crm_url` and display types.
- Deploy: `bench execute mmm_custom.engine.chatwoot_setup.ensure_conversation_attributes` (creates the `ho_so_crm` definition), then `bench execute mmm_custom.crm_links.backfill_contact_links`.

## Task 7 — Docs

- `current-state.md` rows for `/admin`, `lead_ads.py`, `crm_links.py`; `/bot` mentions updated.

## Verification

- Unit tests pass (the one pre-existing `test_facebook_post` import error needs Pillow, which this container lacks).
- Live-stack checks from the spec (redirect, landing by role, sidebar, `/admin#lead-ads`, "Mở cuộc chat", `ho_so_crm`, `test-chatwoot-crm-sync.py` 5/5) need Docker and are run on the dev stack.
