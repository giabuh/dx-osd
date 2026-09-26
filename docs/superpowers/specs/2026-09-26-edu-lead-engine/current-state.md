# Current State — Code Map (as of 2026-09-26, commit 615cc82)

What exists today, where it lives, and which layer changes it. Line numbers drift; re-check with
`grep -n` before relying on one.

## Running configuration (local unified stack)

Site config keys present on `crm.localhost`: `chatwoot_api_token`, `chatwoot_api_url`,
`chatwoot_webhook_secret` (sync pipeline configured).

**Absent:** `chatwoot_bot_webhook_secret`, `chatwoot_bot_api_token`, `typesafe_api_key`.
→ The agent bot and the [I] AI agents are **off**; only Chatwoot → CRM lead sync runs.

## Modules in `frappe-custom/mmm_custom/mmm_custom/`

| File | What it does today | Changed by |
|---|---|---|
| `api.py:77` `chatwoot_sync` | Chatwoot webhook → HMAC + anti-replay → 3-tier dedup → create/update CRM Lead, note log; forwards `message_created` to `intelligence.enqueue_analysis` | Layer 7 (write `territory`/`products`), 12 |
| `api.py:50` `detect_course_interest` | Keyword match for 3 hardcoded courses (Tiếng Anh, Bơi lội, Toán tư duy) | Layer 7/12 (replaced by data-driven matching) |
| `bot_engine.py:15` `COURSES`, `:21` `BRANCHES` | Hardcoded 3 courses, 3 branches (EduFlow demo) | Layer 7 (read from CRM data) |
| `bot_engine.py:191` `transition` | Pure state machine: greeting → await_course (multi-select) → await_branch → await_phone → completed | Layer 7 (slot-filling engine) |
| `bot_api.py:191` `agent_bot_webhook` | Chatwoot Agent Bot webhook; state kept in contact `custom_attributes` (`bot_state`, `bot_courses`, `bot_branch`) | Layer 7–10 |
| `bot_api.py:134` `branch_owners` | Hardcoded branch → lead_owner email map | Layer 15 (Consultant DocType) |
| `bot_api.py:78` `_find_best_agent` | Filter Chatwoot agents by `custom_attributes.branch`, pick fewest open conversations | Layer 15 (rule D) |
| `bot_api.py:115` `_create_or_update_lead` | Writes `course_interest`, `branch`, `lead_owner`, `mobile_no` | Layer 7 |
| `intelligence.py:208` `analyze_conversation` | Jev: intent, hotness, customer phone/email, reply-template choice → Lead fields, labels, private note; gate 0.7 (`:38`) | Layer 12–14 (extended, not replaced) |
| `intelligence.py:74` `ask_jev` | One System One call (`/v1/systemone`), typed questions | Reused |
| `followup.py:39` `plan_followups` | Daily 08:00 (`hooks.py` cron): Jev picks follow-up for stale open leads → CRM Task | Layer 26 |
| `dedupe.py`, `data_quality.py` | Email/phone normalisation and matching; data-quality label | Reused; layer 29 |
| `chatwoot_client.py` | Chatwoot REST v1 wrapper | Reused/extended |
| `setup.py` | Custom fields on CRM Lead via `after_install` + patches (`patches.txt`) | Extended by layers 1–5 |

## CRM Lead custom fields (from `setup.py`)

`chatwoot_contact_id` (Data, unique) · `course_interest` (Data) · `branch` (Select, **3 hardcoded
options**) · `data_quality` (Select) · `ai_intent` (Select) · `ai_hotness` (Select).

## Standard Frappe CRM pieces we will reuse (vendored `crm/`, not edited)

| DocType | Relevant fields | Used for |
|---|---|---|
| CRM Territory (tree) | `territory_name`, `parent_crm_territory`, `is_group`, `territory_manager` | Area → branch (layer 1) |
| CRM Product | `product_code`, `product_name`, `standard_rate`, `description`, `disabled` | Course catalog (layer 2) |
| CRM Lead | `territory`, `products` (CRM Products table), `total`/`net_total`, `lead_owner`, `sla*`, `lost_reason`, `facebook_lead_id` | Branch, courses, lead value, SLA, loss |
| CRM Service Level Agreement, CRM Holiday List | — | Layers 16, 24 |
| CRM Deal, CRM Lead Status, CRM Lost Reason, CRM Status Change Log | — | Layers 23, 28 |
| CRM Task, FCRM Note, CRM Dashboard | — | Layers 10, 19, 25 |
| `crm/lead_syncing/` | Native Facebook Lead Ads polling | Layer 30 |

## Scripts

| Script | Today | Changed by |
|---|---|---|
| `scripts/seed-branch-agents.py` | Seeds 3 EduFlow consultants in Chatwoot (`custom_attributes.branch`) and CRM | Superseded by layer 6 loader |
| `scripts/setup-agent-bot.py` | Creates the Chatwoot AgentBot and links it to the Messenger inbox | Reused |
| `scripts/configure-chatwoot.py` | Creates the sync webhook, writes `chatwoot_webhook_secret` to site config | Reused |
| `scripts/seed-shared-accounts/` | Demo staff accounts across both apps | Reused |

## Also present, not default

`activepieces/logic/` — alternative pipeline (writes the same Lead fields). Must never run alongside
`mmm_custom`. Layers here target `mmm_custom` only.
