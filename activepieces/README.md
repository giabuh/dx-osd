# Activepieces flow: Messenger/Instagram → CRM

`flows/messenger-to-crm.json` is an Activepieces flow template with two steps:

1. **Chatwoot webhook** — Catch Webhook trigger (authentication `None`; the signature is checked in step 2 because Chatwoot signs `<timestamp>.<raw body>`, which the built-in HMAC option does not support).
2. **Sync to CRM** — Code step whose source is `logic/sync.mjs`, verbatim: verify the Chatwoot signature, then note / link / create the CRM Lead and write `crm_lead_id` back to the Chatwoot contact.

## Set up

1. Start the stack (`docker/activepieces/`, see `AGENTS.md`) and create the first user at http://127.0.0.1:8080.
2. **Automations → Import** → choose `flows/messenger-to-crm.json` → **Import** ([screenshot](../docs/screenshots/activepieces-flow-imported.png)).
3. Open the **Sync to CRM** step ([screenshot](../docs/screenshots/activepieces-sync-step-inputs.png)) and replace the placeholder inputs — these are secrets, they stay on the instance and never go back into git:

   | Input | Value |
   |---|---|
   | `chatwootSigningSecret` | Signing secret shown when you create the Chatwoot webhook (step 5) |
   | `chatwootBaseUrl` | `http://127.0.0.1:3000` locally, `https://chat.<domain>` behind Caddy |
   | `chatwootAccountId` | Chatwoot account id (usually `1`) |
   | `chatwootApiToken` | Chatwoot → Profile Settings → Access Token |
   | `crmBaseUrl` | `http://127.0.0.1:8000` locally, `https://crm.<domain>` behind Caddy |
   | `crmApiToken` | `<api_key>:<api_secret>` of a CRM user (User → API Access → Generate Keys) |
   | `crmHost` | Locally only: add it with **+ Add Item**, value `crm.localhost` (Frappe picks the site from the Host header). Not in the export because Activepieces drops empty inputs; not needed behind Caddy |

4. **Publish**. On a fresh install the piece catalog syncs for about a minute after startup; publishing before that fails with "missing piece" (`@activepieces/piece-webhook@0.1.42`) — wait and publish again. Then copy the trigger's webhook URL (`<AP_FRONTEND_URL>/api/v1/webhooks/<flow id>`).
5. Chatwoot → Settings → Integrations → Webhooks → add that URL, subscribe to `conversation_created`, and put its signing secret into step 3.

Chatwoot calls the webhook from inside its container, so it needs a URL it can reach — in practice the public `automation.<domain>` behind Caddy (`docker/caddy/Caddyfile`). Locally you can exercise the flow with a signed `curl`:

```bash
BODY='{"event":"conversation_created","id":1,"channel":"Channel::FacebookPage","meta":{"sender":{"id":<contact id>,"name":"Test","email":"test@example.com","phone_number":"","custom_attributes":{}}}}'
TS=$(date +%s)
SIG="sha256=$(printf '%s' "$TS.$BODY" | openssl dgst -sha256 -hmac '<signing secret>' -hex | awk '{print $NF}')"
curl -X POST http://127.0.0.1:8080/api/v1/webhooks/<flow id> -H 'Content-Type: application/json' \
  -H "x-chatwoot-timestamp: $TS" -H "x-chatwoot-signature: $SIG" --data-raw "$BODY"
```

The run's output (**Runs** page) is `{ action: "lead_created" | "lead_linked" | "note_logged", leadId }`; a bad signature makes the run fail with `Invalid Chatwoot webhook signature`.

## [I] Intelligence flows (optional, TypeSafe Jev)

Both flows call [TypeSafe Jev](https://docs.typesafe.ai) (`POST https://api.typesafe.ai/v1/systemone`), which returns typed decisions with a confidence instead of generated text. An agent acts only when the confidence is at least `confidenceThreshold` (default `0.7`); otherwise it records what it skipped in the run output and changes nothing. Jev is strongest in English, so check the run outputs on your own Vietnamese chats before lowering the threshold.

Import them like the first flow, then set the inputs (same Chatwoot/CRM values as above, plus `jevApiKey` from the [TypeSafe console](https://console.typesafe.ai/keys); add `crmHost` locally).

**`flows/lead-intelligence.json`** — Catch Webhook → **Analyze with Jev** (`logic/intelligence.mjs`, retry on failure on). Add its webhook URL as a second Chatwoot webhook subscribed to `message_created`. For each incoming message it reads the last 20 chat messages and, in one Jev call, decides:

| Decision | Applied when confident |
|---|---|
| Intent (`purchase`, `price_inquiry`, `support`, `complaint`, `spam`, `other`) | CRM Lead `ai_intent`; Chatwoot label `ai-<intent>` |
| Hotness (`cold`, `warm`, `hot`) | CRM Lead `ai_hotness`; label `hot` |
| Which phone/email found in the chat (regex) is the customer's own | Filled in on the Lead if it has none; if another Lead already has it, a "Possible duplicate" note — never an automatic merge |
| Best template from `replyTemplates` (JSON, editable in the step) | Private note in the conversation for the agent to send or ignore (never for spam) |

If the first message arrives before the "Messenger to CRM" flow has linked the contact, the step fails with "Contact not linked to a CRM Lead yet" and Activepieces retries it.

**`flows/cold-lead-followup.json`** — every day at 08:00 (Asia/Ho_Chi_Minh) → **Plan follow-ups with Jev** (`logic/followup.mjs`). For up to `maxLeads` Leads in `openStatuses` not modified for `staleDays`, Jev picks `call` / `message` / `review_close` / `wait`, and the agent creates a CRM Task for the Lead owner (due tomorrow). Leads with an open Task are skipped, so it never piles up duplicates; it never changes a Lead's status.

## Changing the logic

1. Edit the flow's file in `logic/` test-first; run `node --test activepieces/logic/*.test.mjs`.
2. Paste it into the flow's Code step, with the inputs set back to the placeholders from the committed file.
3. Export the flow (flow menu → **Export**, or `GET /api/v1/flows/<id>/template`) over its file in `flows/`, then re-enter your real inputs and republish.

Tests fail until each export's Code step matches its `.mjs` byte for byte. Code steps cannot use `node:`-prefixed imports — the sandbox rejects them.
