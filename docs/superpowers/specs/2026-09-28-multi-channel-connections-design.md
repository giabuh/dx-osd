# Multi-Page Channel Connections — Design Spec

## Purpose

Messages came from one Facebook page only: `scripts/setup-facebook-channel.py` created one Chatwoot channel from a page token in `.env`, and `scripts/refresh-facebook-token.py` had the page id hard-coded. Managers now connect any number of pages from the CRM admin, in one Facebook login, and choose which branch's staff work each page. The same screen lists the next providers (Instagram, Zalo OA, TikTok) so each can be added with the same shape.

## Confirmed Decisions

- **Where:** a "Kênh kết nối" tab at `/crm/admin/channels` (`AdminChannels.vue`). CRM is where channels are managed, as it already is for branches and staff; Chatwoot stays the inbox.
- **One login, many pages:** Facebook OAuth (server-side code flow) → long-lived user token → `/me/accounts`. Page tokens obtained this way do not expire. A "Dán token" fallback accepts a user token pasted from Graph API Explorer, for a site Facebook cannot redirect to (no public HTTPS yet).
- **Per page, on connect:** Chatwoot `POST /api/v1/accounts/:id/callbacks/connect_facebook_page` (added to our fork: idempotent, admin only; creates the channel and inbox or renews the token of a page connected before, and subscribes the page's Messenger webhooks); the CRM `Facebook Page` doc is upserted and its Lead Ads forms fetched (`crm/lead_syncing`); a `Channel Connection` row records inbox, branch and status. Lead Sync Sources are still chosen per form (`mmm_custom.lead_ads`); connecting a page does not start syncing every old form.
- **Disconnect** unsubscribes the page (`callbacks/disconnect_facebook_page`). The inbox and its conversations stay; connecting the page again resumes it.
- **Staff (decided with the owner):** a page may have a branch. That branch's active consultants are added as members of the page's inbox by the staff sync (every 10 minutes and on save), so they see every conversation of their page. A page without a branch works as before: the bot answers first and the handoff adds the chosen consultant to the inbox (`engine/effects.py`). Membership is only added, never removed, because a handoff can give a conversation to a consultant of another branch.
- **Health:** daily `mmm_custom.channels.facebook.check_health` calls `debug_token` for each page token and sets Connected / Token expired / Error (missing `pages_messaging` or `pages_manage_metadata`). "Kiểm tra token" runs it on demand; "Kết nối lại" restarts the login.
- **Tokens** are never sent to the browser. They live in Chatwoot (`Channel::FacebookPage`, encrypted when Chatwoot encryption is configured) and in the CRM `Facebook Page` doc; the user token stays in the cache for 30 minutes while pages are picked.
- **Scope of this round:** Facebook Messenger + Lead Ads. Instagram, Zalo OA and TikTok show as "Sắp có"; each gets its own `mmm_custom/channels/<provider>.py` (start login, list accounts, connect, disconnect, health) and reuses `Channel Connection`.

## Code Map

| Piece | Path |
|---|---|
| Providers list | `frappe-custom/mmm_custom/mmm_custom/channels/__init__.py` |
| Facebook login, pages, connect, disconnect, health | `.../channels/facebook.py` |
| Tab data, branch per page | `.../channels/api.py` |
| Connection record | doctype `Channel Connection` (`.../mmm_custom/doctype/channel_connection/`) |
| Branch staff → inbox members | `.../staff_sync.py` (`plan_branch_inboxes`) |
| Chatwoot endpoints | `chatwoot/app/controllers/api/v1/accounts/callbacks_controller.rb` (`connect_facebook_page`, `disconnect_facebook_page`) |
| Screen | `crm/frontend/src/components/Admin/AdminChannels.vue`, `FacebookPagesDialog.vue` |
| App config | `scripts/configure-chatwoot.py` copies `FB_APP_ID`/`FACEBOOK_APP_ID`, `FB_APP_SECRET`/`FACEBOOK_APP_SECRET`, `FB_VERIFY_TOKEN` into Chatwoot and the CRM site config |

## Setting Up the Meta App (real pages)

1. `.env`: `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FB_VERIFY_TOKEN` (any random string). Run `python scripts/configure-chatwoot.py`.
2. Public HTTPS through Caddy (`docker/caddy/Caddyfile`). The CRM behind Caddy sees `Host: crm.localhost`, so set the public callback explicitly:
   `bench --site crm.localhost set-config facebook_redirect_uri https://<crm-domain>/api/method/mmm_custom.channels.facebook.callback`
   The channels tab shows the URL it uses.
3. Meta App → Facebook Login → Valid OAuth Redirect URIs: that URL.
4. Meta App → Messenger → Webhooks: callback `https://<chatwoot-domain>/bot`, verify token = `FB_VERIFY_TOKEN`, fields `messages, messaging_postbacks, message_deliveries, message_reads, message_echoes, standby, messaging_handovers`.
5. Until App Review: only pages managed by people with a role on the app (admin, developer, tester) can be connected, and only those people's messages arrive in Development mode. For customers' messages the app must be **Live** with **Advanced Access** to `pages_messaging`, `pages_manage_metadata`, `pages_show_list`, `pages_read_engagement`, `leads_retrieval`, `business_management`, which needs Business Verification and App Review.

## Not in This Round

- `scripts/auto-post.py`, `scripts/comment-reply.py` and the `Facebook Post` autopilot still post to the one page in `FACEBOOK_PAGE_ID`; choosing a page per post is a follow-up.
- The CRM `Facebook Page.access_token` field is plain text (upstream doctype); moving it to a Password field needs a data migration.

## Testing

- `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests` (`test_channels.py`: login state, Graph calls and paging, page picker, selection, health, branch inbox plan, client endpoints).
- `bundle exec rspec spec/controllers/api/v1/accounts/callbacks_controller_spec.rb` in `chatwoot/`.
- `yarn build` in `crm/frontend`.
- Live: connect two real pages with different branches → two inboxes with the bot → a message to each page creates a Lead, lands in the right inbox, and that branch's consultants see it; `scripts/test-chatwoot-crm-sync.py` still passes.
