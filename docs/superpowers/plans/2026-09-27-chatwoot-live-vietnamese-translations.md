# Chatwoot Live Vietnamese Translations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Chatwoot staff opt into Vietnamese and let account administrators edit dashboard translations in Chatwoot without rebuilding, beginning with the supplied Contacts screen.

**Architecture:** Keep the shipped Vue i18n catalogs as the baseline and store account-scoped key overrides in PostgreSQL. An authenticated API supplies overrides to a dashboard loader that resets to the baseline on each account switch. An administrator page searches the shipped catalog and writes overrides through the same API.

**Tech Stack:** Rails 7.2.3.1, PostgreSQL, Pundit, RSpec, Vue 3, Vue i18n, Vitest, existing Chatwoot dashboard components.

**Spec:** `docs/superpowers/specs/2026-09-27-chatwoot-live-vietnamese-translations-design.md`

## Global Constraints

- Language choice stays in each user's existing `ui_settings.locale`; the development account's English default stays unchanged.
- Overrides are shared within one account, never across accounts. Only account administrators may save or delete them.
- English and Vietnamese dashboard catalogs remain the source key set and baseline. The editor initially exposes Vietnamese; backend storage accepts supported locale codes.
- Values are at most 4,000 characters, preserve interpolation placeholders, and reject unsafe markup. Invalid writes return HTTP 422 without changing a previous value.
- Saving changes the editing browser immediately. Other open browsers see changes on reload or account switch. Copy edits after installation need no image rebuild.
- No new service or non-FOSS dependency. Code, identifiers, comments, and docs are English; Vietnamese UI copy is Vietnamese.
- Keep the root account's persistent Docker volumes. The Chatwoot HTTP gate is 200 or 302 on `127.0.0.1:3000`.
- Repository guidance permits commits only when asked; do not run the per-task commits normally shown in this skill's template.

## Review Focus

1. A key such as `__proto__` or an unknown dotted path must return 422 and never modify another object; Task 1 model and Task 3 client tests cover it.
2. A value that drops `{name}` or changes a pluralization placeholder must return 422 and preserve the old value; Task 1 tests cover it.
3. Markup with an event handler or script tag must return 422; Task 1 tests cover it.
4. A slow response from account A after a switch to B must not reapply A's text; Task 3 tests cover it.
5. An agent or a member of another account must not write translations, while an agent of the current account may read them; Task 2 request tests cover it.

---

## File Structure

| Unit | Files | Responsibility |
|---|---|---|
| Catalog and persisted override | `chatwoot/app/services/dashboard_locale_catalog.rb`, `chatwoot/app/models/account_locale_override.rb`, migration, account association | Resolve valid English keys, validate value, store one account/key/locale edit |
| Account API | `chatwoot/app/controllers/api/v1/accounts/locale_overrides_controller.rb`, `chatwoot/config/routes.rb` | Read scoped values; authorize and persist writes/deletes |
| Runtime locale adapter | `chatwoot/app/javascript/dashboard/api/localeOverrides.js`, `chatwoot/app/javascript/dashboard/i18n/accountOverrides.js`, `chatwoot/app/javascript/entrypoints/dashboard.js`, `chatwoot/app/javascript/dashboard/App.vue` | Fetch, reset, apply, and refresh overrides without cross-account leakage |
| Translation editor | `chatwoot/app/javascript/dashboard/routes/dashboard/settings/translations/`, settings routes, sidebar, English/Vietnamese settings locale JSON | Search catalog and save/reset one value |
| Baseline and audit | Vietnamese contact/settings locale JSON, `scripts/audit-chatwoot-i18n.py` | Translate the screenshot and report remaining dashboard English values |

## Task 1: Persist and Validate Account Translation Overrides

**Files:**
- Create: `chatwoot/db/migrate/20260927000000_create_account_locale_overrides.rb`
- Create: `chatwoot/app/services/dashboard_locale_catalog.rb`
- Create: `chatwoot/app/models/account_locale_override.rb`
- Modify: `chatwoot/app/models/account.rb`
- Create: `chatwoot/spec/factories/account_locale_overrides.rb`
- Test: `chatwoot/spec/services/dashboard_locale_catalog_spec.rb`, `chatwoot/spec/models/account_locale_override_spec.rb`

**Interfaces:**
- Produces `DashboardLocaleCatalog.value(locale, key) -> String?`, reading `app/javascript/dashboard/i18n/locale/<locale>/*.json` and accepting only shipped leaf keys. `DashboardLocaleCatalog.supported_locale?(locale) -> Boolean` uses Chatwoot's enabled languages.
- Produces `AccountLocaleOverride` with `account`, `edited_by` (`User`), `locale`, `key`, and `value`, plus uniqueness on account/locale/key. `value` validation uses the English source key for placeholder and safe-markup checks.
- The controller in Task 2 calls these interfaces; the frontend never trusts its own catalog as authorization.

- [x] **Step 1: Write failing catalog and model tests.** Assert `value('en', 'SIDEBAR.CONVERSATIONS') == 'Conversations'`, an unknown or prototype-like key is rejected, and a valid `vi` override persists. Assert values over 4,000 characters, missing `{name}`, changed plural placeholders, and `<img onerror=...>` or `<script>` are invalid; failed updates preserve the saved value. Test account/locale/key uniqueness.
- [x] **Step 2: Run the focused tests and observe failures.** From `chatwoot/`, run `bundle exec rspec spec/services/dashboard_locale_catalog_spec.rb spec/models/account_locale_override_spec.rb`; expect missing classes or failed assertions before implementation.
- [x] **Step 3: Implement the catalog and model.** Flatten the shipped JSON catalogs into dotted leaf keys; reject path segments `__proto__`, `prototype`, and `constructor`. Preserve both Vue `{name}` and Rails-style `%{name}` placeholders and the placeholders in each `|` plural branch. Use a Rails HTML allowlist for existing safe rich-text tags/attributes and reject values whose sanitization changes them. Add the unique index and associations.
- [x] **Step 4: Run the focused tests and migration check.** Run the same RSpec command; expect 0 failures. Run `bundle exec rails db:migrate:status` in the Chatwoot test environment after migrating there; expect the new migration `up`.

## Task 2: Expose an Account-Scoped API

**Files:**
- Create: `chatwoot/app/controllers/api/v1/accounts/locale_overrides_controller.rb`
- Modify: `chatwoot/config/routes.rb`
- Test: `chatwoot/spec/requests/api/v1/accounts/locale_overrides_spec.rb`

**Interfaces:**
- Produces `GET /api/v1/accounts/:account_id/locale_overrides?locale=vi` -> `{ overrides: { "SIDEBAR.CONVERSATIONS": "Cuộc trò chuyện" } }` for a current-account member.
- Produces `PUT /api/v1/accounts/:account_id/locale_overrides` with `{ locale, key, value }` -> saved `{ locale, key, value }`; `DELETE` with `{ locale, key }` -> 204. Empty `value` triggers deletion. Writes authorize `Current.account` with `AccountPolicy#update?`; reads use `AccountPolicy#show?`.

- [x] **Step 1: Write failing request tests.** Test unauthenticated 401, current-account agent GET 200, current-account admin PUT/DELETE success, agent PUT/DELETE forbidden, another account ID inaccessible, and invalid key/value returning 422 without altering the stored row.
- [x] **Step 2: Run the request spec and observe failures.** `bundle exec rspec spec/requests/api/v1/accounts/locale_overrides_spec.rb`; expect routing/controller failures.
- [x] **Step 3: Add routes and controller.** Use `Api::V1::Accounts::BaseController`, `Current.account.account_locale_overrides`, account policy authorization, and explicit permitted params. Return the response shapes above; treat deletion of an absent valid key as 204.
- [x] **Step 4: Run model and API specs.** `bundle exec rspec spec/services/dashboard_locale_catalog_spec.rb spec/models/account_locale_override_spec.rb spec/requests/api/v1/accounts/locale_overrides_spec.rb`; expect 0 failures.

## Task 3: Load Overrides into Vue i18n Safely

**Files:**
- Create: `chatwoot/app/javascript/dashboard/api/localeOverrides.js`
- Create: `chatwoot/app/javascript/dashboard/i18n/accountOverrides.js`
- Modify: `chatwoot/app/javascript/entrypoints/dashboard.js`
- Modify: `chatwoot/app/javascript/dashboard/App.vue`
- Test: `chatwoot/app/javascript/dashboard/i18n/specs/accountOverrides.spec.js`

**Interfaces:**
- Produces `LocaleOverridesAPI.list(accountId, locale)`, `.save(accountId, { locale, key, value })`, and `.remove(accountId, { locale, key })`, using explicit account IDs rather than the singleton API client's current route.
- Produces `createAccountOverrideLoader({ composer, fetchOverrides, baseMessages })` with async `load(accountId)`, synchronous `clear()`, and `refresh(accountId)` methods. `composer` is the global Vue i18n composer; `baseMessages` is the shipped `vi` tree. Each load starts from a deep copy, sets only known safe dotted leaf keys, and uses a generation counter to ignore stale fetches.
- The dashboard entrypoint creates one loader and provides it as `accountOverrideLoader` to Vue; `App.vue` and the Task 4 editor inject the same instance. Task 4 calls `refresh(accountId)` after a save/reset and reads the same API client.

- [x] **Step 1: Write failing loader tests.** Assert account A's text appears in Vietnamese, English remains unchanged, switching to account B without overrides resets A's text, a late A response cannot win over B, `__proto__` is ignored, and a failed fetch restores shipped Vietnamese with a reportable error.
- [x] **Step 2: Run the focused test and observe failure.** `pnpm test app/javascript/dashboard/i18n/specs/accountOverrides.spec.js`; expect missing module or failed assertions.
- [x] **Step 3: Implement API client and loader.** Use `composer.setLocaleMessage('vi', freshTree)`; never mutate imported locale JSON. Discard stale responses by generation and account ID. Return a structured failure state for App.vue to show an alert while keeping base Vietnamese usable.
- [x] **Step 4: Integrate with the dashboard entrypoint and `App.vue`.** Create/provide the shared loader after `createI18n`. During account initialization, hold the existing dashboard loading view until the current account's override load finishes, then apply the user's `ui_settings.locale` or account locale. Clear the loader synchronously on account switch. Keep the profile selector's existing per-user behavior and allow a user to switch to Vietnamese after preloading.
- [x] **Step 5: Run the loader spec and lint changed JS/Vue files.** `pnpm test app/javascript/dashboard/i18n/specs/accountOverrides.spec.js`; expect all tests pass. Run `pnpm exec eslint app/javascript/dashboard/api/localeOverrides.js app/javascript/dashboard/i18n/accountOverrides.js app/javascript/entrypoints/dashboard.js app/javascript/dashboard/App.vue`; expect exit 0.

## Task 4: Build the Administrator Translation Editor

**Files:**
- Create: `chatwoot/app/javascript/dashboard/routes/dashboard/settings/translations/translations.routes.js`
- Create: `chatwoot/app/javascript/dashboard/routes/dashboard/settings/translations/Index.vue`
- Create: `chatwoot/app/javascript/dashboard/routes/dashboard/settings/translations/catalog.js`
- Modify: `chatwoot/app/javascript/dashboard/routes/dashboard/settings/settings.routes.js`
- Modify: `chatwoot/app/javascript/dashboard/components-next/sidebar/Sidebar.vue`
- Modify: `chatwoot/app/javascript/dashboard/i18n/locale/en/settings.json`, `chatwoot/app/javascript/dashboard/i18n/locale/vi/settings.json`
- Test: `chatwoot/app/javascript/dashboard/routes/dashboard/settings/translations/catalog.spec.js`, `chatwoot/app/javascript/dashboard/routes/dashboard/settings/translations/Index.spec.js`

**Interfaces:**
- Produces `buildTranslationRows({ english, vietnamese, overrides }) -> Array<{ key, source, base, effective, status }>` where `status` is `missing`, `unchanged`, `overridden`, or `translated`.
- Produces route `accounts/:accountId/settings/translations`, name `settings_vietnamese_translations`, administrator-only. `Index.vue` uses `LocaleOverridesAPI` and the Task 3 loader to save/reset and update the current page.

- [x] **Step 1: Write failing catalog/editor tests.** Test dotted-key flattening, source-text/key search, missing/unchanged/overridden filters, saving one translation, resetting it, immediate visible update, and validation error display without changing the last saved value. Test the route permission is administrator-only.
- [x] **Step 2: Run the focused tests and observe failures.** `pnpm test app/javascript/dashboard/routes/dashboard/settings/translations/catalog.spec.js app/javascript/dashboard/routes/dashboard/settings/translations/Index.spec.js`; expect missing modules/components.
- [x] **Step 3: Implement catalog and editor.** Use existing settings layout, inputs, buttons, and alerts. Show English source, shipped Vietnamese, effective Vietnamese, and the key. Keep the locale fixed to `vi` in this first editor; a later locale option can reuse the API/storage. Put editor copy under one `LOCALE_OVERRIDES` locale subtree in both `en/settings.json` and `vi/settings.json`.
- [x] **Step 4: Add route and sidebar entry.** Include only for administrators under Settings, using a new `SIDEBAR.VIETNAMESE_TRANSLATIONS` key. Ensure navigating directly to the route enforces the same permission.
- [x] **Step 5: Run focused tests and lint.** Repeat the Vitest command; expect all tests pass. Run `pnpm exec eslint app/javascript/dashboard/routes/dashboard/settings/translations app/javascript/dashboard/components-next/sidebar/Sidebar.vue app/javascript/dashboard/routes/dashboard/settings/settings.routes.js`; expect exit 0.

## Task 5: Translate the Screenshot and Establish Coverage Evidence

**Files:**
- Modify: `chatwoot/app/javascript/dashboard/i18n/locale/vi/contact.json`, `chatwoot/app/javascript/dashboard/i18n/locale/vi/settings.json`
- Create: `scripts/audit-chatwoot-i18n.py`

**Interfaces:**
- Produces `python scripts/audit-chatwoot-i18n.py` with counts per dashboard JSON file: English leaf keys, Vietnamese missing keys, identical values. Exit nonzero only for malformed JSON or catalog conflicts; untranslated content is reported for review.
- The built-in Vietnamese catalog supplies every fixed UI label in the supplied Contacts screenshot even before administrators add overrides.

- [x] **Step 1: Implement the read-only audit command.** Compare dotted string leaf keys in `en` and `vi` catalogs, print per-file and total counts, and flag duplicate effective keys. Do not print contact data or secrets.
- [x] **Step 2: Translate screenshot keys in the shipped Vietnamese catalog.** Include `CONTACTS_LAYOUT.EMPTY_STATE.TITLE = "Không có liên hệ nào trong tài khoản này"`, `SUBTITLE = "Bắt đầu thêm liên hệ bằng nút bên dưới"`, and `BUTTON_LABEL = "Thêm liên hệ"`; verify already translated sidebar and heading keys, and correct any other fixed English strings visible in the screenshot.
- [x] **Step 3: Verify catalog and output.** Run `python scripts/audit-chatwoot-i18n.py`; expect valid JSON, no duplicate keys, and fewer identical Vietnamese values than the measured baseline of 3,807. Inspect each screenshot key in the effective merged catalog, not merely as text in one JSON file.
- [ ] **Step 4: Run the affected stack and product check.** Build/restart only Chatwoot through the documented root compose commands while preserving named volumes. Verify HTTP 200/302 on `127.0.0.1:3000`. In a browser, set one staff user's profile language to Vietnamese and leave another English; inspect the supplied Contacts view, save/reset an override without rebuilding, reload another session, and switch accounts to verify isolation. Record the actual command and observed UI result.
- [x] **Step 5: Run focused regression checks.** Run the Task 1–4 RSpec and Vitest commands and lint changed files after integration; quote their actual output before calling the work done.

## Completion Boundary

Task 5 completes the editable translation system and the screenshot milestone. The wider goal remains active while the audit/editor still finds user-facing English text in the Chatwoot staff dashboard. Continue translation review in subsequent work until remaining English UI strings are either translated or explicitly identified as terms that should stay unchanged; do not equate a working editor with complete localization.
