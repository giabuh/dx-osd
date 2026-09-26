# Current State — Code Map (as of 2026-09-26, C1 + C2 done)

What exists today, where it lives, and which layer changes it. Line numbers drift; re-check with
`grep -n` before relying on one.

## Running configuration (local unified stack)

Site config keys present on `crm.localhost`: `chatwoot_api_token`, `chatwoot_api_url`,
`chatwoot_webhook_secret` (sync pipeline configured).

**Absent:** `chatwoot_bot_webhook_secret`, `chatwoot_bot_api_token`, `typesafe_api_key`.
→ The agent bot (the C2 engine) and the [I] AI agents are **off**; only Chatwoot → CRM lead sync runs. Turning the bot on
(`scripts/setup-agent-bot.py`) makes it answer real Messenger customers — a user decision. Chatwoot already has the 7 `bot_*`
conversation attributes (`engine.chatwoot_setup`).

## Modules in `frappe-custom/mmm_custom/mmm_custom/`

| File | What it does today | Changed by |
|---|---|---|
| `api.py` `chatwoot_sync` | Chatwoot webhook → HMAC + anti-replay → 3-tier dedup → create/update CRM Lead, note log; courses detected from the catalog (`detect_courses`) → Lead `products` + `course_interest` summary; forwards `message_created` to `intelligence.enqueue_analysis` | C3.2 |
| `bot_api.py` `agent_bot_webhook` | Agent Bot webhook: HMAC → `engine.pipeline.parse_event` → customer message enqueued (`job_id` = message id, deduplicated); human agent message → `consultant_replied`; resolved → conversation closed | — |
| `engine/catalog.py`, `state.py` | Immutable catalog snapshot (`build_catalog` from dataset-shaped dicts) and `ConversationState` | C3 reads |
| `engine/text.py`, `slot_types.py`, `understand.py` | Keyword tier: diacritic folding, whole-word longest-match phrases, VN phone; slot-type registry (catalog/choice/phone/number/text: understand + buttons); exact quick-reply mapping (D-034) | C3.2 adds the Jev tier |
| `engine/decide.py` | Pure `decide()` → answer / ask_slot / handoff / silent; stuck counter, pending skill, optional slots asked once | C3.2 adds confirm |
| `engine/context.py`, `render.py`, `actions.py`, `reply.py` | Template context contract (D-050), render guard + `vnd`/`date_vi` filters (also as Jinja hooks), action registry (D-049), reply composition + button source rule (D-072) | C3.6 advisor scoring, C6.3 `book_appointment` |
| `engine/lead.py`, `repo.py` | Slots ↔ Lead fields (`territory`, `products`, `learner_type`, `learner_age`, `preferred_shift`, `first_name`, `mobile_no`), returning-customer prefill; all database access (catalog cache cleared by `doc_events`) | — |
| `engine/log.py`, `learning.py` | AI Decision Log rows + learning signals; daily retention purge; `consultant_corrected` on CRM Lead update | C9.2 review UI |
| `engine/routing.py`, `handoff.py`, `chatwoot_setup.py` | C2.6 pick (Lead owner → least-loaded branch consultant → Tổng đài), team, labels, `bot_*` conversation attributes, summary note | C4.1 replaces routing with rule D |
| `engine/effects.py`, `events.py`, `pipeline.py` | `ChatwootEffects` / `RecordingEffects`; `lead_engine_events` hook; `run_turn` + RQ job `process_event` with per-conversation `filelock` | — |
| `engine/playground.py`, `mmm_custom/page/bot_playground/` | `/app/bot-playground`: simulate (dry), reset, replay a logged decision | C3.2 adds the Jev toggle |
| `intelligence.py:208` `analyze_conversation` | Jev: intent, hotness, customer phone/email, reply-template choice → Lead fields, labels, private note; gate 0.7 (`:38`) | C3.2–C3.4 (skips conversations with an active Bot Conversation, D-032) |
| `intelligence.py:74` `ask_jev` | One System One call (`/v1/systemone`), typed questions | Reused |
| `followup.py:39` `plan_followups` | Daily 08:00 (`hooks.py` cron): Jev picks follow-up for stale open leads → CRM Task | C6.4 |
| `dedupe.py`, `data_quality.py` | Email/phone normalisation and matching; data-quality label | Reused; C7.2 |
| `chatwoot_client.py` | Chatwoot REST v1 wrapper; C1 added inbox/agent/team methods | Reused/extended |
| `setup.py` | Custom fields on CRM Lead via `after_install` + patches (`patches.txt`); catalog custom fields on CRM Territory/CRM Product in `CATALOG_FIELDS`, applied idempotently by `create_catalog_fields()` on install and every migrate (`after_migrate` hook) | Add new catalog fields to `CATALOG_FIELDS` |
| `catalog_rules.py` | Pure validation rules + Select option constants (`SLOT_TYPES`, `ACTION_TYPES`, …) used by DocType controllers | C2 registries must use the same constants |
| `mmm_custom/doctype/` | C2 DocTypes: Bot Conversation, AI Decision Log, Bot Learning Signal. C1 DocTypes: Course Group, Consultant, Course Schedule, Course Promotion, Bot Slot, Bot Skill, Lead Engine Settings; child tables Course Link, Course Group Link, Territory Link, Bot Slot Option, Bot Slot Link, Bot Skill Template, Bot Skill Follow Up | C2–C3 read them |
| `demo/loader.py`, `demo/saoviet/*.json` | Idempotent Sao Việt demo loader (`bench execute mmm_custom.demo.loader.load`, optional `anchor`); `purge_demo()` | — |
| `demo/chatwoot_seed.py` | Creates demo agents, 15 teams (13 branches + B2B + Tổng đài), inbox membership; writes `Consultant.chatwoot_agent_id` | Supersedes `scripts/seed-branch-agents.py` |

## Live demo data (crm.localhost, loaded 2026-09-26, anchor 2026-09-28)

18 territories (root + 4 areas + 13 branches), 8 course groups, 46 courses, 44 users/consultants, 1,070 course
schedules, 10 promotions, 7 bot slots, 30 bot skills, Lead Engine Settings; Chatwoot: 44 agents, 15 teams.

## CRM Lead custom fields (from `setup.py`)

`chatwoot_contact_id` (Data, unique) · `course_interest` (Data, summary) · `learner_type`, `learner_age`, `preferred_shift` (C2.4) · `branch` (Select, **3 hardcoded
options**, no longer written) · `data_quality` (Select) · `ai_intent` (Select) · `ai_hotness` (Select).

## Standard Frappe CRM pieces we will reuse (vendored `crm/`, not edited)

| DocType | Relevant fields | Used for |
|---|---|---|
| CRM Territory (tree) | `territory_name`, `parent_crm_territory`, `is_group`, `territory_manager` | Area → branch (C1.1) |
| CRM Product | `product_code`, `product_name`, `standard_rate`, `description`, `disabled` | Course catalog (C1.2) |
| CRM Lead | `territory`, `products` (CRM Products table), `total`/`net_total`, `lead_owner`, `sla*`, `lost_reason`, `facebook_lead_id` | Branch, courses, lead value, SLA, loss |
| CRM Service Level Agreement, CRM Holiday List | — | C4.2, C6.2 |
| CRM Deal, CRM Lead Status, CRM Lost Reason, CRM Status Change Log | — | C6.1, C7.1 |
| CRM Task, FCRM Note, CRM Dashboard | — | C2.6, C5.1, C6.3 |
| `crm/lead_syncing/` | Native Facebook Lead Ads polling | C8.1 |

## Scripts

| Script | Today | Changed by |
|---|---|---|
| `scripts/seed-branch-agents.py` | Seeds 3 EduFlow consultants in Chatwoot (`custom_attributes.branch`) and CRM | Superseded by the C1.6 loader |
| `scripts/setup-agent-bot.py` | Creates the Chatwoot AgentBot and links it to the Messenger inbox | Reused |
| `scripts/configure-chatwoot.py` | Creates the sync webhook, writes `chatwoot_webhook_secret` to site config | Reused |
| `scripts/seed-shared-accounts/` | Demo staff accounts across both apps | Reused |

## Also present, not default

`activepieces/logic/` — alternative pipeline (writes the same Lead fields). Must never run alongside
`mmm_custom`. Layers here target `mmm_custom` only.
