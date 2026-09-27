# Chatwoot Live Vietnamese Translations — Design Spec

## Purpose

Make the Chatwoot staff dashboard usable in Vietnamese without forcing Vietnamese on every staff member. Each person chooses their dashboard language in the existing profile control. Account administrators can correct or add Vietnamese UI translations in Chatwoot, and those edits take effect without rebuilding the image. Start with the Contacts screen in the supplied screenshot, then use the same mechanism to remove remaining English UI text throughout the staff dashboard.

## Confirmed Decisions

- Language selection remains per user. The account's current English default stays in place; users who choose Vietnamese see Vietnamese.
- Translation editing happens in the Chatwoot administration UI, not in source files for each subsequent copy change.
- Edits are shared by staff in the same account and isolated from other accounts.
- The existing Vue i18n catalog remains the base translation. Database entries override individual Vietnamese keys at runtime.
- This feature covers the staff dashboard. It does not translate customer messages, contact data, the public widget, or the CRM application.
- All code, identifiers, comments, and documentation are in English. User-facing Vietnamese copy is in Vietnamese.

## Existing State

Chatwoot already offers Vietnamese in the profile language selector and loads `dashboard/i18n/locale/vi`. The current development account uses English. The base Vietnamese catalog translates `SIDEBAR.CONVERSATIONS` as “Cuộc trò chuyện”, but many strings in the supplied Contacts screenshot remain English. A comparison of the current dashboard catalogs found 6,885 English keys, 302 keys missing from the Vietnamese files, and 3,807 Vietnamese values identical to English. Some identical values are proper names or technical terms; the editor must make those cases reviewable rather than blindly changing them.

## User Experience

### Staff member

1. In Profile settings, select Vietnamese. The choice persists through the existing `ui_settings.locale` mechanism.
2. On a dashboard page, the base Vietnamese catalog is combined with the account's saved Vietnamese overrides. An override changes the corresponding label, including “Conversations” → “Cuộc trò chuyện”.
3. A staff member who selects English continues to see English. Switching accounts loads that account's overrides; a previous account's wording never leaks into the next account.

### Account administrator

1. Open **Settings → Vietnamese translations**. The route and sidebar entry are visible only to account administrators.
2. Search by English text or translation key, and filter to entries that are missing, still identical to English, or already overridden. Each row shows the key, English source, base Vietnamese text, and effective Vietnamese text.
3. Edit one Vietnamese value and save. The current session updates immediately; other open sessions receive it on their next page load or account switch. No asset rebuild is required for copy changes.
4. Reset an override to return to the shipped Vietnamese value. Empty input is a reset action, not a saved blank label.
5. The editor shows a validation error for unknown keys, unsafe markup, excessive length, or altered interpolation placeholders. Failed saves leave the last working translation intact.

The first translation pass covers every visible fixed UI string in the supplied Contacts screenshot: sidebar labels, Contacts heading, search and message controls, and the empty-state title, description, and button. Subsequent passes use the same editor and its untranslated filter to cover the rest of the dashboard. The overall localization goal is not complete merely because the editor exists or the first screen looks correct.

## Architecture

### Catalog and storage

- The existing English and Vietnamese frontend catalogs define the available keys and the shipped baseline. The editor presents the effective merged catalog, using the same key precedence as the dashboard's existing `index.js` locale imports.
- A new `account_locale_overrides` table stores `account_id`, `locale`, `key`, `value`, timestamps, and the administrator who last edited the value. A unique index on `(account_id, locale, key)` prevents duplicate overrides. Initially the editor exposes `vi`; the storage and API accept supported locale codes so other languages can be added later without redesigning the data model.
- The server validates keys against the shipped frontend catalog. An override never creates a new UI key. Values are limited to 4,000 characters and must preserve the source string's interpolation placeholders. The server rejects markup outside a small allowlist of safe tags and attributes; the frontend retains its existing HTML sanitization on rich-text rendering.
- Deleting an override restores the shipped translation; it does not alter source catalog files.

### API and authorization

- `GET /api/v1/accounts/:account_id/locale_overrides?locale=vi` returns the account's overrides to authenticated members for runtime use.
- `PUT /api/v1/accounts/:account_id/locale_overrides` saves one `{ locale, key, value }` entry. `DELETE` at the same path removes one entry identified by `{ locale, key }`. Both writes require the existing account administrator authorization rule.
- All queries are scoped through the authenticated current account. A member of one account cannot read or write another account's translations. Unknown or invalid inputs return HTTP 422 without changing persisted values.
- The editor uses the same API. It does not receive special write access through frontend checks alone.

### Dashboard loading

- Keep an immutable copy of the shipped Vietnamese messages. For each active account, fetch its overrides and build a fresh Vietnamese message tree from that copy; replace the Vue i18n locale message tree rather than merging onto the previous account's tree.
- Load the account's overrides before showing its Vietnamese dashboard text, and ignore stale responses if the user switches accounts while a request is in flight.
- A failed fetch leaves the shipped Vietnamese catalog usable and surfaces a non-blocking error. It must not leave another account's overrides in place.
- Saving or resetting an override refreshes the current account's message tree so visible labels react without a page rebuild.
- The existing per-user language setting remains the sole selector of whether Vietnamese or English is displayed.

## Translation Coverage

The editor's untranslated filter identifies missing Vietnamese keys and values identical to English. It also supports review of intentional unchanged terms such as brand names without treating a numeric coverage report as proof of language quality. A small repository audit command can report counts by dashboard catalog file for review and regression checks; translation content itself remains editable in the admin UI.

Initial built-in Vietnamese corrections for the screenshot are included in the deployment so a new account can select Vietnamese and see that screen translated before an administrator enters overrides. Future wording changes are made through the editor. Further dashboard translation work continues until user-facing English leftovers have been reviewed and corrected; the first screen is a milestone, not a substitute for that broader goal.

## Verification

1. Model/API tests prove account isolation, member read access, administrator-only writes, key and placeholder validation, reset behavior, and persistence.
2. Frontend tests prove that language choice remains per user, overrides update rendered labels, account switching clears old overrides, stale fetches cannot overwrite the current account, and fetch failure falls back to shipped Vietnamese.
3. Editor tests prove search, untranslated filtering, save, reset, and validation feedback.
4. On the running Chatwoot stack, select Vietnamese for one staff user while another remains English. Verify the supplied Contacts view shows “Cuộc trò chuyện” and Vietnamese empty-state copy; edit a label in Settings and verify it changes without rebuilding. Switch accounts and verify translation isolation.
5. The Chatwoot stack still responds with HTTP 200 or 302 on `127.0.0.1:3000` after deployment.

## Limits

- This does not use automatic machine translation. Administrators retain control over wording and context.
- It adds no service or non-FOSS dependency; storage uses Chatwoot's existing PostgreSQL database.
- A newly saved override is immediate in the editing browser; another already open browser sees it after reload or account switch.
- The deployed image still needs a one-time build to install the editor, API, and initial baseline translations. Later copy edits do not need builds.
