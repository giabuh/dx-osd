# Activepieces flow: Messenger/Instagram → CRM

`flows/messenger-to-crm.json` is an Activepieces flow template with two steps:

1. **Chatwoot webhook** — Catch Webhook trigger (authentication `None`; the signature is checked in step 2 because Chatwoot signs `<timestamp>.<raw body>`, which the built-in HMAC option does not support).
2. **Sync to CRM** — Code step whose source is `logic/sync.mjs`, verbatim: verify the Chatwoot signature, then note / link / create the CRM Lead and write `crm_lead_id` back to the Chatwoot contact.

## Set up

1. Start the stack (`docker/activepieces/`, see `AGENTS.md`) and create the first user at http://127.0.0.1:8080.
2. **Flows → Import flow** → choose `flows/messenger-to-crm.json`.
3. Open the **Sync to CRM** step and replace the placeholder inputs — these are secrets, they stay on the instance and never go back into git:

   | Input | Value |
   |---|---|
   | `chatwootSigningSecret` | Signing secret shown when you create the Chatwoot webhook (step 5) |
   | `chatwootBaseUrl` | `http://127.0.0.1:3000` locally, `https://chat.<domain>` behind Caddy |
   | `chatwootAccountId` | Chatwoot account id (usually `1`) |
   | `chatwootApiToken` | Chatwoot → Profile Settings → Access Token |
   | `crmBaseUrl` | `http://127.0.0.1:8000` locally, `https://crm.<domain>` behind Caddy |
   | `crmApiToken` | `<api_key>:<api_secret>` of a CRM user (User → API Access → Generate Keys) |
   | `crmHost` | `crm.localhost` locally (Frappe picks the site from the Host header); leave empty behind Caddy |

4. **Publish**, then copy the trigger's webhook URL (`<AP_FRONTEND_URL>/api/v1/webhooks/<flow id>`).
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

## Changing the logic

1. Edit `logic/sync.mjs` test-first; run `node --test activepieces/logic/sync.test.mjs`.
2. Paste the new `sync.mjs` into the **Sync to CRM** step, with the inputs set back to the placeholders from the committed file.
3. Export the flow (flow menu → **Export**, or `GET /api/v1/flows/<id>/template`) over `flows/messenger-to-crm.json`, then re-enter your real inputs and republish.

The last test fails until the export's Code step matches `sync.mjs` byte for byte. Code steps cannot use `node:`-prefixed imports — the sandbox rejects them.
