# Admin Home, Trimmed CRM, Chatwoot ↔ CRM Links — Design Spec

## Purpose

Give each kind of user one obvious place to work:

- **Chatwoot** — consultants chat with customers.
- **Frappe CRM (`/crm`)** — consultants and managers track the customers they must follow up (Leads, Deals, Tasks, Dashboard).
- **`/admin`** (today's `/bot`) — managers administer branches, staff, course knowledge, the bot, and Facebook Lead Ads.

Today the CRM sidebar shows modules the education center never uses, Facebook Lead Ads settings are buried inside the CRM settings dialog, the admin page lives at `/bot`, and nothing lets a consultant jump between a Chatwoot conversation and its CRM Lead.

## Confirmed Decisions

- Frappe CRM stays the source of truth and the place leads are managed. It is trimmed, not hidden. Lead management is not rebuilt inside Chatwoot.
- `/bot` becomes `/admin`. The old URL redirects.
- Landing page after login depends on role: managers (System Manager or Sales Manager, the existing `BOT_ROLES`) land on `/admin`. Everyone else with desk access (consultants, Sales User) lands on `/crm`, which opens the Leads view. Consultants cannot open `/admin` (unchanged permission check).
- The CRM sidebar keeps **Dashboard, Leads, Deals, Tasks**. Contacts, Organizations, Notes, Call Logs leave the sidebar. Their routes and data stay, so links from a Lead page still work and the bot's conversation notes still show on each Lead.
- Facebook Lead Ads configuration moves into a new `/admin` tab. It reuses the existing `crm/lead_syncing` doctypes and methods; no sync logic is rewritten.
- Chatwoot → CRM: a link-type contact attribute `ho_so_crm` opens the Lead. CRM → Chatwoot: an **"Mở cuộc chat"** action on the Lead page opens the Chatwoot contact. No Chatwoot source change.
- Out of scope: creating Chatwoot contacts or conversations for Lead Ads form leads (they live in CRM Leads), any change to the bot's routing, and Vietnamese relabelling beyond the four kept sidebar items.

## Existing State

- `frappe-custom/mmm_custom/mmm_custom/www/bot.{html,py}` renders the admin page; `public/js/bot_page.js` drives its hash tabs (`overview`, `branches`, `staff`, `knowledge`, `playground`). `bot.py` redirects guests to `/login?redirect-to=/bot` and refuses users without `desk.can_open_bot()`.
- `hooks.py` registers the page on the apps screen as "Bot Sao Việt" → `/bot`. The desk workspace `bot_sao_viet.json` links `/bot`.
- Frappe v15.121.1 sends a logged-in desk user to `get_default_path()`: the user's `default_app`, else System Settings `default_app`, else the only permitted app, else `/apps`. The `on_session_creation` hook runs before this and cannot override it.
- `crm/frontend/src/components/Layouts/AppSidebar.vue` hard-codes the eight sidebar links. `crm/crm/locale/vi.po` already translates Dashboard, Leads, Tasks; "Deals" is left as "Deals".
- Lead Ads: doctypes `Lead Sync Source` (`type`, `access_token`, `facebook_page`, `facebook_lead_form`, `enabled`, `background_sync_frequency`, `last_synced_at`), `Facebook Page`, `Facebook Lead Form` (`page`, `id`, `form_name`, `questions`), `Facebook Lead Form Question` (`label`, `key`, `type`, `id`, `mapped_to_crm_field`), `Failed Lead Sync Log` (`type`, `lead_data`, `source`, `traceback`). Whitelisted: `facebook.fetch_and_store_pages_from_facebook(access_token)`, `facebook.get_pages_with_forms()`, doc methods `LeadSyncSource.sync_leads` and `FailedLeadSyncLog.retry_sync`.
- The bot writes the Chatwoot contact in `engine/effects.py::save_lead` via `engine/lead.py::contact_update(fields, courses, lead)`. `engine/chatwoot_setup.py` creates contact attribute definitions (`crm_lead_id`, `khoa_hoc_quan_tam`, `chi_nhanh`, `trang_thai_lead`) as text. Chatwoot supports `attribute_display_type: link`.
- CRM Leads carry `chatwoot_contact_id`. CRM Form Scripts (`CRM Form Script`, `dt`, `view`, `enabled`, `script`) return `actions` rendered as buttons on the Lead page; the script receives helpers including `call` and `toast`.

## Design

### A. `/admin`

1. Rename `www/bot.html` → `www/admin.html` and `www/bot.py` → `www/admin.py`. The guest redirect becomes `/login?redirect-to=/admin`. `bot_page.js` keeps its name (it is an asset, not a route).
2. `hooks.py`:
   - `website_redirects = [{"source": "/bot", "target": "/admin"}]`. Browsers keep the `#tab` fragment across the redirect.
   - Apps screen entry: title "Quản trị", route `/admin`.
3. Workspace `bot_sao_viet.json` shortcut URL `/bot` → `/admin`.
4. The admin sidebar "Mở CRM" link points at `/crm`.
5. **Home by role** — new `desk.apply_default_apps()`:
   - Sets System Settings `default_app = "crm"` when it is empty.
   - For each enabled system user: if the user has a `BOT_ROLES` role and `default_app` is empty, set it to `"mmm_custom"`; if the user has no `BOT_ROLES` role and `default_app == "mmm_custom"`, clear it. A user's own non-empty choice of another app is left alone.
   - The per-user decision is a pure function `default_app_for(roles, current)` returning the new value or `None` for "leave".
   - Runs from `after_migrate` and from `doc_events["User"]["on_update"]` (one user), so role changes and staff created by `staff_sync` pick it up.

### B. `/admin` → tab "Facebook Lead Ads"

New module `mmm_custom/lead_ads.py`. Every whitelisted function first checks `desk.can_open_bot()` and raises `frappe.PermissionError` otherwise; they write with `ignore_permissions=True` after that check.

| Function | Does |
|---|---|
| `list_sources()` | Sources with page name, form name, enabled, frequency, last synced, and a failure count from `Failed Lead Sync Log` (`type = "Failure"`). |
| `connect(access_token)` | Calls `fetch_and_store_pages_from_facebook`; returns `[{id, name, forms: [{id, name}]}]`. |
| `save_source(values)` | Insert (when no `name`) or update a `Lead Sync Source` (`type = "Facebook"`). Only the whitelisted fields are copied. The access token is required on insert and kept when left blank on update. |
| `set_enabled(name, enabled)` | Toggle a source. |
| `form_mapping(form)` | The form's questions plus the CRM Lead field choices. |
| `save_mapping(form, mapping)` | `{question_key: crm_field}` → `mapped_to_crm_field`; unknown fields are rejected. |
| `sync_now(name)` | `LeadSyncSource.sync_leads()`. |
| `failures(limit=50)` | Latest `Failure` logs with source, time, a short error line. |
| `retry(name)` | `FailedLeadSyncLog.retry_sync()`. |

Pure helpers, unit tested: `lead_field_choices(meta_fields)` (CRM Lead fields a question can map to: data-like field types, not hidden, not read-only, plus `first_name`, `email`, `mobile_no` always first) and `clean_source_values(values, is_new)`.

UI (`admin.html` + `bot_page.js`): a nav button "Facebook Lead Ads" (`data-tab="lead-ads"`) and a pane with:

- a sources table — Page, Form, Tần suất, Lần đồng bộ cuối, Lỗi, an enabled switch, and "Đồng bộ ngay" / "Sửa" buttons;
- "+ Kết nối form" opens the same inline form used by "Sửa": access token → "Tải Page" (`connect`) → Page select → Form select → frequency → Lưu; after save, the question-mapping table (question label → CRM field select) with its own Lưu;
- a "Lỗi đồng bộ gần đây" table with a "Thử lại" button per row.

It follows the existing pane markup, notice and error helpers in `bot_page.js`.

### C. Trimmed CRM sidebar

- `AppSidebar.vue`: remove the Contacts, Organizations, Notes and Call Logs entries from `links`, and their now-unused icon imports. Routes are untouched.
- `crm/crm/locale/vi.po`: `msgid "Deals"` gets `msgstr "Học viên đăng ký"`.
- The CRM frontend is rebuilt with `bench build --app crm`.

### D. Chatwoot ↔ CRM links

New module `mmm_custom/crm_links.py`:

- `lead_url(base, lead)` → `f"{base}/crm/leads/{lead}"` (pure). `base` is site config `crm_public_url`, default `http://127.0.0.1:8000`, trailing slash stripped.
- `chatwoot_contact_url(base, account_id, contact_id)` → `f"{base}/app/accounts/{account_id}/contacts/{contact_id}"` (pure). `base` is site config `chatwoot_base_url` (the key `/admin` already uses), default `http://127.0.0.1:3000`; account from `chatwoot_account_id`, default 1.
- Whitelisted `open_chat_url(lead)`: requires read permission on the Lead, returns the Chatwoot contact URL or `None` when the Lead has no `chatwoot_contact_id`.
- `ensure_lead_form_script()` (after_migrate): upserts `CRM Form Script` named "Mở cuộc chat (mmm_custom)" — `dt = "CRM Lead"`, `view = "Form"`, `enabled = 1` — whose script returns one action "Mở cuộc chat". On click it calls `open_chat_url` and opens the URL in a new tab, or toasts "Khách này chưa có cuộc chat trên Chatwoot".
- `backfill_contact_links()` (run by hand with `bench execute`): writes `ho_so_crm` onto every Chatwoot contact linked from a Lead's `chatwoot_contact_id`; returns counts of updated and failed.

Bot changes:

- `lead.contact_update(fields, courses, lead, crm_url="")` adds `ho_so_crm = lead_url(crm_url, lead)` when `crm_url` is given. `effects.save_lead` passes the configured base.
- `chatwoot_setup.CONTACT_ATTRIBUTES` gains `("ho_so_crm", "Hồ sơ CRM", "link")`; entries carry a display type (default `text`) passed to `create_custom_attribute`.

## Error Handling

- Lead Ads calls surface Facebook/Frappe error messages in the pane's notice area; a failed save leaves the form open with its values.
- `open_chat_url` never raises for a missing contact; it returns `None` and the script shows the toast.
- `backfill_contact_links` continues past a failing contact and reports the count.
- `apply_default_apps` is idempotent and touches only users whose value must change.

## Testing

Unit tests (`python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests`):

- `default_app_for` across manager/consultant × empty/`mmm_custom`/other app.
- `lead_ads.lead_field_choices`, `clean_source_values`, and a permission refusal for a non-manager.
- `crm_links.lead_url`, `chatwoot_contact_url`, `open_chat_url` without a contact.
- `contact_update` includes `ho_so_crm` only when `crm_url` is given.
- `plan_contact_attributes` returns the link display type for `ho_so_crm`.
- Existing tests updated from `/bot` to `/admin` (`test_bot_page.py`, `test_desk.py`, `test_workspace_json.py`).

Manual, on the running stack:

- `curl -I http://127.0.0.1:8000/bot` → 301/302 to `/admin`.
- Log in as Administrator → lands on `/admin`. Log in as a seeded consultant → lands on `/crm` (Leads). Consultant opening `/admin` is refused.
- CRM sidebar shows exactly Dashboard, Leads, Học viên đăng ký, Tasks.
- `/admin#lead-ads` lists sources and failures without console errors.
- A Lead with `chatwoot_contact_id` shows "Mở cuộc chat", which opens the Chatwoot contact. That contact shows "Hồ sơ CRM" as a clickable link back to the Lead.
- `python scripts/test-chatwoot-crm-sync.py --secret "$SECRET"` still passes 5/5.
