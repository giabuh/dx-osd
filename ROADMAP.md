# DX-OSD Roadmap

The north star for this project: where the product is going, in what order, and how we know each stage is done. It sits above the per-feature specs and plans in `docs/superpowers/` — every phase below gets its own spec + plan when work on it starts.

_Last updated: 2026-09-24 (v2 — 100% FOSS Architecture)_

---

## Vision

An open-source, self-hosted customer-acquisition and sales platform for SMBs. Leads and conversations from every channel an SMB actually uses (Facebook Lead Ads, Messenger, Instagram, then Zalo, web, email) converge into **one** CRM, deduplicated, owned by a salesperson, and traceable back to the ad that produced them. Built on mature open-source products — Chatwoot Community Edition and Frappe CRM with a custom in-bench extension (`mmm_custom`) — rather than reinvented, maintaining **100% pure FOSS/OSI compliance** without proprietary or fair-code automation middleware, and packaged so that a new SMB customer can be onboarded repeatably, not hand-built.

## Guiding principles

Every phase must respect these. If a proposed change breaks one, it needs an explicit decision recorded in its spec.

1. **Stand on giants.** Configure or extend Chatwoot and Frappe CRM before writing custom code. If upstream already does it (e.g. Frappe CRM's native Lead Ads sync), use it.
2. **One source of truth.** Frappe CRM owns Lead/Contact/Deal data. Chatwoot is inbox-only. In-bench webhook processing (`mmm_custom`) holds no separate business state — it is a stateless handler and deduplication pipeline that directly orchestrates CRM transactions and note logging inside the Frappe bench.
3. **100% Pure FOSS & OSI Compliance.** All components, dependencies, and vendored code must strictly adhere to OSI-approved open source licenses (GNU AGPLv3, MIT, Apache 2.0, BSD-3, GPLv2). Non-OSI licensed software (such as n8n's Sustainable Use License, Redis 7.4+ dual SSPL/RSAL, or proprietary enterprise editions) is strictly barred from the architecture.
4. **Extend first, edit vendored when needed — and record it.** Prefer upstream extension points (`frappe-custom/mmm_custom/` hooks/custom fields/REST APIs, Chatwoot `custom_attributes`/webhooks/REST API, `docker/`). Editing vendored `chatwoot/` or `crm/` directly is allowed when no extension point fits (e.g. CRM UI changes, upstream bug fixes, or stripping proprietary enterprise directories to enforce pure MIT license), but every such edit is recorded so it can be re-applied when re-syncing with upstream.
5. **Secure by default.** Services bind to `127.0.0.1`; Caddy reverse proxy is the only public entry. Webhooks are HMAC-SHA256 verified with timestamp-based anti-replay protection. Service-to-service calls use API keys, never session cookies. No secret ever lands in git.
6. **Done means verified.** A phase is complete when its exit criteria are demonstrated on running systems — not when the code is written.
7. **Multi-SMB from the start of productization.** Once Phase 2 begins, nothing is built that only works for a single hard-coded customer.

## Current state (2026-09-24)

| Area | Status |
|---|---|
| Chatwoot & Frappe CRM stacks | 2-stack architecture running locally via Docker Compose, each bound to `127.0.0.1` (Chatwoot on `:3000`, Frappe CRM on `:8000`). n8n decommissioned and purged. |
| Facebook Lead Ads → CRM | Native to Frappe CRM (`crm/lead_syncing/`); not yet configured against a real Meta App |
| Messenger/IG → Chatwoot → CRM | Direct webhook via `mmm_custom.api.chatwoot_sync` verified against running local stacks. Lead convergence verified: matches existing lead (phone/email/`crm_lead_id`), attaches conversation note, updates `course_interest`, creates zero duplicate leads. |
| CRM customization | `mmm_custom` app: `chatwoot_contact_id` field, `course_interest` field, `Messenger`/`Instagram` lead sources, keyword course interest detection, HMAC-SHA256 webhook security with anti-replay protection. |
| Dedup & Ingestion logic | `frappe-custom/mmm_custom/mmm_custom/dedupe.py` & `api.py` with 23 unit tests (100% pass) + 5 live end-to-end sync verification tests. |
| FOSS / License Compliance | 100% OSI-compliant. Chatwoot stripped of `enterprise/` (pure MIT), Redis pinned to `7.2.4-alpine` (BSD-3-Clause), Frappe CRM (AGPLv3), MariaDB (GPLv2), Caddy (Apache 2.0). n8n and messenger-platform-samples purged. |
| [I] Intelligence (optional) | `mmm_custom/intelligence.py` + `followup.py` on TypeSafe Jev, off unless `typesafe_api_key` is set; confidence-gated (0.7). Same decisions and thresholds as the Activepieces prototype, which was verified on the real local stacks with the real Jev API: on 10 hand-labelled Vietnamese chats every wrong answer came back below 0.7. |
| Shared demo accounts | `scripts/seed-shared-accounts/` & `scripts/configure-chatwoot.py` |
| Security checklist | Passed (no secrets in git history; anti-replay timestamp & HMAC-SHA256 verification on webhook). |
| Meta App (plan Task 0) | **Not started** — needs Business Manager access |
| Caddy reverse proxy | **Config only** (`docker/caddy/`) — needs a real domain + VPS |
| Production deployment, backups, monitoring | **None yet** |
| Vendored source at runtime | **Used** — Chatwoot Community built from `chatwoot/`, CRM `v1.84.0` runs from `crm/` on pinned Frappe `v15.121.1` (see `docs/vendored-upstreams.md`) |

Source of detail: `docs/superpowers/plans/2026-09-24-foss-meta-integration.md` (Execution Status table).

---

## Phases

Phases are ordered by dependency, not by date. A phase may start early work in parallel, but it is only **done** when its exit criteria are met.

### Phase 0 — Foundation cleanup & FOSS Architecture Transition ✅ Done (2026-09-24)

**Goal:** the repo tells the truth about itself, establishes 100% OSI FOSS compliance, and ensures later phases build on a stable, high-performance 2-stack foundation.

**Key deliverables**
- Decommission non-OSI middleware (`n8n`) and excise proprietary code (`chatwoot/enterprise/`, `messenger-platform-samples/`).
- Implement native in-bench webhook handler and deduplication engine (`frappe-custom/mmm_custom`).
- Pin infrastructure services (Redis `7.2.4-alpine` for BSD-3-Clause license preservation).
- Achieve 100% test coverage for deduplication, security signature verification, and keyword detection (23 unit tests + 5 live integration tests).
- Document upstream re-sync and FOSS compliance audit trail in `docs/vendored-upstreams.md` and `docs/foss-compliance-report.md`.
- ✅ **Conversational Bot**: Agent Bot with Quick Reply qualification flow (course + branch), intelligent round-robin agent assignment

**Exit criteria**
- Fresh `git clone` + documented commands bring up both stacks with `mmm_custom` installed, zero manual steps.
- All unit and integration tests pass cleanly with 100% pass rate.
- Spec, plan, `REPO.md`, `AGENTS.md`, and `CLAUDE.md` agree with the code.

**Depends on:** nothing.

### Phase 1 — Pilot go-live (one SMB, production)

**Goal:** one real SMB receives real leads and messages in production, reliably.

**Key deliverables**
- Meta App created, permissions granted, long-lived Page token (plan Task 0).
- VPS + domain; Caddy live with TLS for `chat.` and `crm.` subdomains.
- Real end-to-end test: Chatwoot → `mmm_custom` (CRM) live webhook delivery.
- Production-grade Frappe CRM deployment (replace the dev/quickstart compose).
- Backups for all stateful data (Postgres, MariaDB, volumes) + a tested restore drill.
- Basic monitoring and alerting: service up/down, failed webhook deliveries, Lead Ads sync errors.
- Ops runbook: deploy, restart, rotate secrets, restore, common failures.

**Exit criteria**
- Pilot SMB runs for an agreed period (e.g. 2–4 weeks) on real traffic with zero lost and zero duplicated leads.
- A restore from backup has been performed successfully at least once.
- An alert has been triggered and observed end-to-end at least once.

**Depends on:** Phase 0.

### Phase 2 — Productize for many SMBs

**Goal:** onboarding a new SMB is a repeatable procedure, not a project.

**Key deliverables**
- Tenancy model decided and documented in a spec — expected shape: one Chatwoot account per tenant, one Frappe site per tenant, per-tenant webhook secrets and API token routing.
- Provisioning script: create a new tenant (Chatwoot account, Frappe site with `mmm_custom`, webhook registration, API keys) in one command.
- Onboarding checklist, including connecting the tenant's own Facebook Page / Instagram account and Lead Ads forms.
- Meta App Review / advanced access so one app can serve multiple businesses.
- Unified staff accounts across Chatwoot and CRM per tenant (extends `scripts/seed-shared-accounts/`).
- Upgrade path: how a new version of DX-OSD (and of vendored upstreams) rolls out to all tenants.

**Exit criteria**
- A second tenant is onboarded using only the script + checklist, with no code changes.
- Tenant data is isolated (verified: tenant A cannot see tenant B's leads or conversations).

**Depends on:** Phase 1.

### Phase 3 — Channel expansion

**Goal:** every channel an SMB uses to acquire customers converges into the same CRM.

**Key deliverables**
- Zalo OA (a key channel for Vietnamese SMBs).
- Website live-chat widget (Chatwoot native) and web lead forms.
- Email inbox.
- All channels flow through the same dedup pipeline (email/phone match → link or create Lead) with the correct `source`.

**Exit criteria**
- For each channel, a test contact produces exactly one CRM Lead, and a contact reaching out on two channels is merged into one Lead.

**Depends on:** Phase 2 (so channels are built multi-tenant from day one).

### Phase 4 — Sales automation & analytics

**Goal:** the SMB owner sees which ads make money, and no lead is left without follow-up.

**Key deliverables**
- Lead assignment rules (round-robin / by source / by territory).
- Response SLA and follow-up reminders.
- Per-tenant pipeline stages.
- Attribution: ad → lead → deal, preserving campaign/ad identifiers from Lead Ads and click-to-message ads.
- Dashboards: leads, conversion rate, and cost-per-lead per campaign (ingest ad spend from the Meta Marketing API).

**Exit criteria**
- The owner can answer "which campaign produced the most closed deals, and at what cost per lead" from a dashboard, without exporting data.
- No lead in the pilot tenant stays unassigned or un-contacted past its SLA without an alert.

**Depends on:** Phase 1 (pilot data); benefits from Phase 3.

### Phase 5 — AI assistance

**Goal:** faster, more consistent first response without adding staff.

**Key deliverables**
- FAQ / qualification bot on inbound chat, with clean handoff to a human agent.
- Reply suggestions for agents in Chatwoot.
- Lead scoring in CRM from conversation and form data.

**Exit criteria**
- Measurable reduction in first-response time on the pilot tenant versus the Phase 1 baseline, with no drop in lead-to-deal conversion.

**Depends on:** Phase 4 (baseline metrics to measure against).

---

## Out of scope / non-goals

- Rewriting a CRM or an inbox — we extend Chatwoot and Frappe CRM.
- Multi-region, high-availability deployment — single VPS per deployment is the target.
- Proprietary or fair-code middleware (e.g. n8n) — all integration logic is native Python inside `mmm_custom`.
- Building our own ads-management / campaign-editing tool — we read from Meta, we don't replace Ads Manager.
- Airbyte or a separate data warehouse — only reconsidered if Phase 4 dashboards can't be served from CRM data.

## How to use this roadmap

- **Starting a phase:** write its spec and plan under `docs/superpowers/specs/` and `docs/superpowers/plans/`, linking back to the phase here. Task-level detail belongs there, not in this file.
- **Finishing a phase:** verify every exit criterion on running systems, then update the _Current state_ table and mark the phase done here.
- **Changing direction:** edit this file deliberately (with a commit that says why). If a spec or plan contradicts this roadmap, either the roadmap is updated or the spec is — never silent drift.
