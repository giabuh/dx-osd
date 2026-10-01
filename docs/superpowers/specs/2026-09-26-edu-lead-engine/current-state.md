# Current State — Code Map (as of 2026-10-01, C1 + C2 + C3 done; staff assist D-109…D-115; customer lifecycle D-116/D-117; customer page D-122/D-123)

What exists today, where it lives, and which layer changes it. Line numbers drift; re-check with
`grep -n` before relying on one.

## Running configuration (local unified stack)

Site config keys present on the dev `crm.localhost` site include `chatwoot_api_token`, `chatwoot_api_url`,
`chatwoot_webhook_secret`, `typesafe_api_key`, `chatwoot_bot_webhook_secret` and `chatwoot_bot_api_token` (values
are never documented). On 2026-09-27 the user switched the bot on for real customers: `scripts/setup-agent-bot.py`
linked the Agent Bot "EduFlow Qualification Bot" to the Messenger inbox (id 2), and `jev_live` is **on** although
the gate left one critical error (u057, see README); the customer daily token budget is 0 (unlimited). Chatwoot has the 9 `bot_*`
conversation attributes (`engine.chatwoot_setup`, including `bot_goal` and `bot_level`).
The last full Jev gate (2026-09-27) **failed**: 104 items, 0 call errors, 1 wrong course/branch/skill
answer in the act band, 648,219 input tokens, model `jev-1.13.0`. The remaining case is a B2B
quotation request that Jev sometimes maps to the consumer office-computing bundle. Keep Jev off
for real customers until a later labelled gate passes.

## Modules in `frappe-custom/mmm_custom/mmm_custom/`

| File | What it does today | Changed by |
|---|---|---|
| `api.py` `chatwoot_sync` | Chatwoot webhook → HMAC + anti-replay → `repo.ensure_lead` (3-tier dedup shared with the bot, one create claim per contact) → create/update CRM Lead, note log; courses detected from the catalog (`detect_courses`) → Lead `products` + `course_interest` summary; forwards `message_created` to `intelligence.enqueue_analysis` | C3.2 |
| `bot_api.py` `agent_bot_webhook` | Agent Bot webhook: HMAC → `engine.pipeline.parse_event` → customer message enqueued (`job_id` = message id, deduplicated) → `engine.copilot.process`; human agent message → `consultant_replied`, assist timer stopped, banner refreshed and the text captured into the staff reply library (D-111, D-114); resolved → conversation closed | — |
| `engine/catalog.py`, `state.py` | Immutable catalog snapshot, Jev/cost/advisor settings, and `ConversationState` with bounded history and call timestamps | C4+ reads |
| `engine/text.py`, `slot_types.py`, `understand.py`, `reply_match.py` | Keyword tier: diacritic folding, phrase and phone matching (a number with a digit missing is read back, D-107), customer names (`person_name`), quick replies tapped or typed (folded titles, quiz letters, yes/no to the test offer, trial dates, D-107) and confirmation responses; an explicit "not X, Y" correction reopens a filled catalog slot | C4+ reads |
| `engine/jev.py`, `jev_questions.py`, `combine.py` | TypeSafe Jev client; questions generated from live slots, course catalog and skills; keyword/Jev merge with act, confirm and low bands | C4+ reads |
| `engine/cost_guard.py`, `evaluate.py`, `eval/utterances.json` | Per-conversation and daily budget checks; 104 labelled utterances and D-033 go-live gate | C4+ reads |
| `engine/advisor.py` | Audience/age/group shortlist and bounded Jev composite ranking, with a data-only fallback | C4+ reads |
| `engine/decide.py` | Pure `decide()` → answer / confirm / ask_slot / handoff / silent; wants-human and hot handoff, spam close, pending skill | C4+ reads |
| `engine/enrol_flow.py` | Pure registration dialogue (D-121): class → phone → handoff `enrol_ready`; Jev `enrol_step` (answer, question, any_class, no_phone, later, cancel) | — |
| `engine/context.py`, `render.py`, `actions.py`, `reply.py` | Template context, render guard + filters, action registry (incl. `trial_offer`/`book_trial`, D-102; the Task is created by `pipeline.book_trials` → `repo.create_trial_task`), advisor recommendations and combined replies | C6.3 `book_appointment` |
| `engine/lead.py`, `repo.py` | Slots ↔ Lead fields (`territory`, `products`, `learner_type`, `learner_age`, `preferred_shift`, `first_name`, `mobile_no`), returning-customer prefill; all database access (catalog cache cleared by `doc_events`) | — |
| `engine/log.py`, `learning.py` | AI Decision Log rows + learning signals; daily retention purge; `consultant_corrected` on CRM Lead update | C9.2 review UI |
| `engine/routing.py`, `handoff.py`, `chatwoot_setup.py` | Rule D pick (D-087: Lead owner → B2B consultants for a skill with `route: b2b` (D-099) → branch or Tổng đài → Team Lead if confidently hot → course-group specialist → least loaded), team, labels, `bot_*` conversation and contact attribute definitions, summary note | C4.1 CRM toggles |
| `engine/effects.py`, `events.py`, `pipeline.py` (Lead writes also update the Chatwoot contact, D-088) | Effects interface and hook; `run_turn` calls `understand_turn` with Jev/fallback and token accounting; RQ job guarded by per-conversation `filelock` | — |
| `engine/qualify.py` | Pure `lead_status()` → the bot's target: Qualified / Unqualified (support) / Junk (spam) (D-083, D-116); `repo.save_lead` applies it only through `lifecycle.auto_update` (forward moves; a Lost status carries its reason) | C6.5 |
| `lifecycle.py` | The customer journey (D-116/D-117): Lead statuses New → Qualified (Đủ thông tin) → Contacted (Đang tư vấn) → Trial Booked → Converted (Đã đăng ký), Nurture (On Hold), Unqualified / Junk (Lost) and Deal statuses Pending Payment → Deposit Paid → Won / Lost; `can_auto_move` / `auto_update` for every automatic move (handoff and first consultant reply → Contacted, `book_trial` → Trial Booked with `trial_date`); `LABELS`; lost reasons; `migrate()` (patch v1_1, after_install) and `ensure_statuses_hook` (after_migrate); `on_lead_update` pushes the real status to the Chatwoot contact (`trang_thai_lead`) | — |
| `enrolment.py` | The registration record (D-117): Deal fields (course, class, fee, promotion, deposit, paid, balance — `setup.CATALOG_FIELDS["CRM Deal"]`), `before_insert` / `validate` / `on_update` hooks (fee maths, deposit → Deposit Paid, class must match the course; the Lead follows its registration: `lead_after_deal_change`, D-119), `create_draft` (the draft registration of the bot / Jev, D-118), Deal page layouts (`update_deal_layouts`, `rewrite_layouts`), Deal defaults (status, VND), `seats_taken` for `FrappeRepo.open_schedules` | — |
| `classes.py` | "Khóa học & Lớp" page API (D-120): `context`, `schedules` (seats held / left, registrations waiting), `save_schedule`; access is the Course Schedule doctype's | — |
| `followup.py` | Daily nurturing by status (D-116): Qualified not called in 24 h, quiet New/Contacted (Jev picks call/message, without AI a message), after the trial date, Nurture every 14 days × 4 with the next class, unpaid registrations; runs without an AI key; `lead_nurture` site config | — |
| `branches.py` | One branch field: the legacy `branch` select is hidden and its values fill `territory` (validate hook, after_migrate backfill) | — |
| `mmm_custom/workspace/bot_sao_viet/` | Desk workspace grouping the bot pages and data (D-089) | — |
| `engine/knowledge.py`, `mmm_custom/page/bot_knowledge/`, `public/js/crm_product.js`, `mmm_custom/doctype/course_faq/` | Course knowledge overview and coverage table (D-086); CRM Product fields `syllabus` + `faqs` (`setup.CATALOG_FIELDS`), answered through `jev_questions.faq_course`/`combine._course_faq` (D-085) | — |
| `engine/playground.py`, `mmm_custom/page/bot_playground/`, `AdminPlayground.vue`, `engine/eval/demo_scripts.json` | `/app/bot-playground` and `/crm/admin/playground`: dry simulation, replay and an independent **Use Jev** toggle with question/answer/token inspector; `simulate` also returns a plain-language `summary` (what the customer wants, decision, facts known with the new ones marked, keyword sources, what a real chat would write) shown above the raw JSON; sample chats played message by message from `demo_scripts.json` (`{"tap": n}` taps a button of the last reply), each checked offline to end in a handoff | Add a sample chat = one entry in `demo_scripts.json` |
| `desk.py`, `hooks.py` | Role gate for bot administration, migrate-time hiding of unused desk workspaces, an Apps entry "Quản trị" to `/crm/admin` (D-091, D-096), `/bot` and `/admin` → `/crm/admin` redirects, and landing by role (`default_app_for`: managers → `/crm/admin`, others → `/crm`; after_migrate + User on_update) | — |
| `crm/frontend/src/pages/Admin.vue`, `crm/frontend/src/components/Admin/` | Manager screens inside the CRM frontend at `/crm/admin/<tab>` (overview, customers, branches, staff, course knowledge, level tests, playground, scenarios), frappe-ui components, managers only (router guard + server checks); replaced the standalone `/bot` → `/admin` page (D-092, D-096) | — |
| `engine/quiz.py`, `offers.py`, `voucher.py`, `tone.py` | Level quizzes (D-104, adaptive D-106): easy → hard per goal, early stop, survey mode, missed topics; `offers.py` decides when Jev offers the test (course known, level not) and tracks `Bot Conversation.quiz_offers`; after the result the phone is asked, then `pipeline.issue_reward` sends the syllabus and a voucher code (Lead `quiz_detail`, `voucher_code`); `tone.py` checks every customer-facing template (Dạ … ạ, brand pronouns, ≤ 1 emoji) | Add a quiz = one Bot Skill, or the Bài test tab |
| `quiz_reminders.py`, `mmm_custom/doctype/quiz_attempt/` | One Quiz Attempt per conversation and quiz (offered → started → done, phone, voucher); cron every 15 min reminds a customer who stopped half-way once, 2–20 h after their last message (D-106) | — |
| `quiz_admin.py`, `crm/frontend/src/components/Admin/AdminQuizzes.vue`, `QuizDialog.vue` | `/crm/admin/quizzes`: funnel per quiz (offered, took it, finished, phone, enrolled, back after reminder) and the quiz editor (questions, levels, topics, goals, score bands, bot wording, checked by `quiz.validate` + `tone.problems`) (D-106) | — |
| `engine/copilot.py`, `presence.py` | Staff assist (D-111…D-113): AUTO (bot answers) vs ASSIST (a person watches — Chatwoot fork `GET …/viewers` or the Lead-page chat —, claimed or wrote): draft note + `Bot Conversation.assist` queue + `fallback_due_at`; cron every minute `run_due` → `run_turn(fallback=True)`; banner buttons and typing via the account webhook; `assist_timeout` → `escalate` to someone on duty | Lead Engine Settings: `assist_*`, `hold_template` |
| `engine/draft.py` | The bot's own answer for staff (D-110): `run_turn(draft=True)` on a write-nothing repo, never a handoff; the note names its sources | — |
| `engine/staff_replies.py`, `mmm_custom/doctype/staff_reply/`, `demo/saoviet/staff_replies.json` | Staff reply library (D-114): capture + mask + templatize, retrieval for Jev's `staff_reply` choice, review endpoints for `/crm/admin/knowledge` (AdminKnowledge.vue), 567-reply seed | Approve in "Tri thức khóa học" |
| `llm.py`, `engine/llm_draft.py` | Gemini draft for staff when the bot has no answer (D-115), checked by Jev and by `numbers_ok`; never sent to customers | `gemini_api_key`, `llm_draft_*` |
| `chatwoot/` (fork) | `RoomChannel#update_presence` records the open conversation (`OnlineStatusTracker.update_conversation_viewer`), `ConversationsController#viewers`, `BotAssistBanner.vue` above the reply box (D-112) | — |
| `engine/scenarios.py`, `engine/eval/scenarios.json` | Acceptance scenarios (D-098): scripted chats → expected team, consultant kind, Lead fields; dry runs offline (unit test) and on live data (`bench execute mmm_custom.engine.scenarios.report`, API `run_all`) | Add a scenario per new routing rule |
| `engine/customers.py`, `crm/frontend/src/components/Admin/AdminCustomers.vue`, `AdminScenarios.vue` | Customer dashboard (D-101) and the scenario runner tab | — |
| `engine/dashboard.py`, `AdminOverview.vue` | Role-gated summary of bot Lead creation, qualification, handoffs, knowledge coverage and latest qualified Leads (`summary`); `overview(period)` for `/crm/admin/overview`: today / 7 (default) / 30 / 90 days, the customer journey funnel of `customers.report`, tuition received and due from confirmed registrations (`fees`, drafts and cancelled excluded), latest Leads | — |
| `intelligence.py:208` `analyze_conversation` | Jev intent/hotness/phone/email analysis and labels; skips conversations handled by an active Bot Conversation | — |
| `intelligence.py:74` `ask_jev` | One System One call (`/v1/systemone`), typed questions | Reused |
| `referral.py` | Referral codes (D-103): code per Lead, `find_code`, CRM Lead `before_insert`/`validate` hooks resolving `referred_by`, migrate backfill | — |
| `sources.py` | Channel list (D-100): Chatwoot channel → CRM Lead Source for new Leads, `source_campaign`, statuses for planned channels (Zalo, TikTok) | Add a channel = one row |
| `dedupe.py`, `data_quality.py` | Email/phone normalisation and matching; data-quality label | Reused; C7.2 |
| `chatwoot_client.py` | Chatwoot REST v1 wrapper; C1 added inbox/agent/team methods | Reused/extended |
| `setup.py` | Custom fields on CRM Lead via `after_install` + patches (`patches.txt`); catalog custom fields on CRM Territory/CRM Product in `CATALOG_FIELDS`, applied idempotently by `create_catalog_fields()` on install and every migrate (`after_migrate` hook); the grouped Lead side panel `LEAD_SIDE_PANEL` written once by `update_lead_side_panel` (sentinel `needs_section`, D-122), `REMOVE_FROM_LEAD` includes `organization`, `link_goal_level_slots` (goal / level → `learning_goal` / `current_level`, D-123) | Add new catalog fields to `CATALOG_FIELDS` |
| `catalog_rules.py` | Pure validation rules + Select option constants (`SLOT_TYPES`, `ACTION_TYPES`, …) used by DocType controllers | C2 registries must use the same constants |
| `mmm_custom/doctype/` | Bot Conversation adds `history`, `ai_signals`, `jev_calls`; AI Decision Log adds `jev_extra`; Bot Slot adds `ask_on_demand`; Lead Engine Settings adds Jev/cost/advisor sections; existing C1–C2 DocTypes and child tables remain | C4+ reads |
| `demo/loader.py`, `demo/saoviet/*.json` | Idempotent Sao Việt demo loader (`bench execute mmm_custom.demo.loader.load`, optional `anchor`); `purge_demo()` | — |
| `staff_sync.py` | CRM → Chatwoot staff sync: an agent per Consultant, one team per branch (+ B2B, Tổng đài) holding exactly its active consultants, bot attached to every Facebook page inbox; writes `Consultant.chatwoot_agent_id`. Runs on Consultant save and every 10 min; handoff adds the consultant to the conversation's inbox (`engine/effects.py`) | Staff are managed in CRM only |
| `bot_admin.py`, `lead_ads.py` | APIs behind `/crm/admin`: branches (CRM Territory by area), staff (User + Consultant, synced to Chatwoot on save), course import/creation, `app_links`; reached from the "Quản trị" item in the `/crm` sidebar (`AppSidebar.vue`, managers only). `lead_ads.py` configures Facebook Lead Ads over `crm/lead_syncing` but has no screen | Add admin screens as tabs in `pages/Admin.vue` |
| `staff_switch.py`, `crm/frontend/src/components/StaffSwitchBanner.vue` | Demo staff switch: a System Manager views the CRM as an active consultant (Frappe impersonation, Activity Log, `disable_staff_switch`), banner with the way back; "Xem như" on `/crm/admin/staff` (D-105) | — |
| `scope.py`, `crm/crm/permissions/org_hierarchy.py` | Branch scope: consultants see every Lead/Deal of their branch (central team: no territory; B2B: the B2B team's) through the `crm_record_scope` hook (D-105) | — |
| `lead_chat.py`, `crm/frontend/src/components/Activities/LeadChat.vue` | Lead page "Tin nhắn" tab: the Lead's Chatwoot conversation, read and answered under the consultant's own Chatwoot token (`Consultant.chatwoot_access_token`, fetched by `staff_sync` through the Platform App) (D-105) | — |
| `customer_profile.py`, `crm/frontend/src/components/Customer/` | Customer page (D-122): `profile` (registrations, the bot's conversation, level tests, referrals; Lead read permission) and `class_card` (seats left); `LeadSidePanel.vue` wraps `SidePanelLayout` (`showEmpty`, `highlight`, `after-fields` slot, `custom` sections) on both Lead pages; `ClassCard.vue` and `FeeProgress.vue` on the Deal pages. Tabs on Lead/Deal pages: Tin nhắn first, Hoạt động last, no Data / Attachments; URLs open `#messages` (`router.js`) | — |
| `lead_views.py`, `crm/crm/fcrm/doctype/crm_lead/crm_lead.py` | Leads list default columns (branch, course, source, hotness badge) and quick filters; `?filters=` links from `/crm/admin/customers` (D-105) | — |
| `crm_links.py` | Chatwoot ↔ CRM links: contact attribute `ho_so_crm` (link type, written by `effects.save_lead` from `crm_public_url`; `backfill_contact_links` for older contacts) and the "Mở cuộc chat" CRM Form Script on the Lead page (`open_chat_url`, created on migrate) | — |
| `demo/chatwoot_seed.py` | Runs `staff_sync.sync_all()` for the loaded demo consultants | Supersedes `scripts/seed-branch-agents.py` |

## Live demo data (crm.localhost, checked 2026-09-27)

18 territories (root + 4 areas + 13 branches), 8 course groups, 46 courses (the dataset now has 9 groups and 51 courses, D-097; reload with `bench execute mmm_custom.demo.loader.load`), 44 users/consultants, 1,070 course
schedules, 10 promotions, 9 bot slots (including on-demand `goal`/`level`), 30 bot skills, Lead Engine Settings;
Chatwoot: 44 agents, 15 teams.

## CRM Lead custom fields (from `setup.py`)

`chatwoot_contact_id` (Data, unique) · `source_campaign` (Data, D-100) · `referral_code`, `referred_by_code`, `referred_by` (D-103) · `placement_result` (D-104) · `quiz_detail`, `voucher_code` (D-106) · `course_interest` (Data, summary) · `learner_type`, `learner_name`, `learner_age`, `preferred_shift` (C2.4, D-123) · `learning_goal`, `current_level` (D-123) · `branch` (Select, **3 hardcoded
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
