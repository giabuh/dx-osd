# DX-OSD Roadmap

The north star for this project: where the product is going, in what order, and how we know each stage is done. It sits above the per-feature specs and plans in `docs/superpowers/` — every phase below gets its own spec + plan when work on it starts.

_Last updated: 2026-09-23_

---

## Vision

An open-source, self-hosted customer-acquisition and sales platform for SMBs. Leads and conversations from every channel an SMB actually uses (Facebook Lead Ads, Messenger, Instagram, then Zalo, web, email) converge into **one** CRM, deduplicated, owned by a salesperson, and traceable back to the ad that produced them. Built on mature open-source products — Chatwoot, Frappe CRM, Activepieces — rather than reinvented, and packaged so that a new SMB customer can be onboarded repeatably, not hand-built.

## Guiding principles

Every phase must respect these. If a proposed change breaks one, it needs an explicit decision recorded in its spec.

1. **Stand on giants.** Configure or extend Chatwoot and Frappe CRM before writing custom code. If upstream already does it (e.g. Frappe CRM's native Lead Ads sync), use it.
2. **One source of truth.** Frappe CRM owns Lead/Contact/Deal data. Chatwoot is inbox-only. Activepieces holds no business state — it is a stateless pipe.
3. **Extend first, edit vendored when needed — and record it.** Prefer upstream extension points (`frappe-custom/mmm_custom/` hooks/custom fields, Chatwoot `custom_attributes`/webhooks/API, `activepieces/`, `docker/`). Editing vendored `chatwoot/` or `crm/` directly is allowed when no extension point fits (e.g. CRM UI changes, upstream bug fixes), but every such edit is recorded so it can be re-applied when re-syncing with upstream.
4. **Secure by default.** Services bind to `127.0.0.1`; one reverse proxy is the only public entry. Webhooks are HMAC-verified. Service-to-service calls use API keys, never session cookies. No secret ever lands in git.
5. **Done means verified.** A phase is complete when its exit criteria are demonstrated on running systems — not when the code is written.
6. **Multi-SMB from the start of productization.** Once Phase 2 begins, nothing is built that only works for a single hard-coded customer.

## Current state (2026-09-23)

| Area | Status |
|---|---|
| Chatwoot, Frappe CRM, Activepieces stacks | Run locally via Docker Compose, each on `127.0.0.1` |
| Facebook Lead Ads → CRM | Native to Frappe CRM (`crm/lead_syncing/`); not yet configured against a real Meta App |
| Messenger/IG → Chatwoot → Activepieces → CRM | Flow `activepieces/flows/messenger-to-crm.json` verified against the real local stacks with signed webhooks (create, link, note, bad signature), including the Lead-Ads-then-Messenger convergence case (1 Lead, not duplicated). Replaced n8n on 2026-09-25 (n8n's Sustainable Use License is not OSI-approved) |
| CRM customization | `mmm_custom` app: `chatwoot_contact_id` field, `Messenger`/`Instagram` lead sources |
| Sync + dedup logic | `activepieces/logic/sync.mjs` + `node:test` suite |
| Shared demo accounts | `scripts/seed-shared-accounts/` |
| Security checklist | Passed (no secrets in git history) |
| Meta App (plan Task 0) | **Not started** — needs Business Manager access |
| Caddy reverse proxy (Task 5) | **Config only** — needs a real domain + VPS |
| Real end-to-end webhook test (Task 10 steps 2–5) | **Blocked** on Task 5 |
| Production deployment, backups, monitoring | **None yet** |
| Vendored source at runtime | **Used** — Chatwoot built from `chatwoot/`, CRM `v1.84.0` runs from `crm/` on pinned Frappe `v15.121.1` (see `docs/vendored-upstreams.md`) |

Source of detail: `docs/superpowers/plans/2026-09-22-facebook-integration-platform.md` (Execution Status table).

---

## Phases

Phases are ordered by dependency, not by date. A phase may start early work in parallel, but it is only **done** when its exit criteria are met.

### Phase 0 — Foundation cleanup ✅ Done (2026-09-23)

**Goal:** the repo tells the truth about itself, so later phases build on a stable base.

**Key deliverables**
- Commit the in-progress `mmm_custom` auto-install in `crm/docker/init.sh` + override.
- Update the Facebook integration spec to reflect the vendored reality (the "never modify `chatwoot/`/`crm/`, keep `git pull`" constraint and old `/home/giabao/dev/MMM` paths are stale).
- Document the upstream re-sync procedure for vendored `chatwoot/` and `crm/` (how to pull a new upstream version and re-apply local changes).
- Single source for sync logic: a test fails when the flow's Code step drifts from `activepieces/logic/sync.mjs` (done); consider generating the flow export from it instead.

**Exit criteria**
- Fresh `git clone` + documented commands bring up all three stacks with `mmm_custom` installed, no manual steps.
- Spec, plan, and `CLAUDE.md` agree with the code.

**Depends on:** nothing.

### Phase 1 — Pilot go-live (one SMB, production)

**Goal:** one real SMB receives real leads and messages in production, reliably.

**Key deliverables**
- Meta App created, permissions granted, long-lived Page token (plan Task 0).
- VPS + domain; Caddy live with TLS for `chat.` / `crm.` / `automation.` subdomains (Task 5).
- Real end-to-end test: Chatwoot → Activepieces → CRM webhook delivery (Task 10 steps 2–5).
- Production-grade Frappe CRM deployment (replace the dev/quickstart compose).
- Backups for all stateful data (Postgres, MariaDB, volumes) + a tested restore drill.
- Basic monitoring and alerting: service up/down, failed Activepieces runs, Lead Ads sync errors.
- Ops runbook: deploy, restart, rotate secrets, restore, common failures.

**Exit criteria**
- Pilot SMB runs for an agreed period (e.g. 2–4 weeks) on real traffic with zero lost and zero duplicated leads.
- A restore from backup has been performed successfully at least once.
- An alert has been triggered and observed end-to-end at least once.

**Depends on:** Phase 0.

### Phase 2 — Productize for many SMBs

**Goal:** onboarding a new SMB is a repeatable procedure, not a project.

**Key deliverables**
- Tenancy model decided and documented in a spec — expected shape: one Chatwoot account per tenant, one Frappe site per tenant, per-tenant Activepieces project and flow inputs.
- Provisioning script: create a new tenant (Chatwoot account, Frappe site with `mmm_custom`, Activepieces flow, API keys) in one command.
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
- Building our own ads-management / campaign-editing tool — we read from Meta, we don't replace Ads Manager.
- Airbyte or a separate data warehouse — only reconsidered if Phase 4 dashboards can't be served from CRM data.

## How to use this roadmap

- **Starting a phase:** write its spec and plan under `docs/superpowers/specs/` and `docs/superpowers/plans/`, linking back to the phase here. Task-level detail belongs there, not in this file.
- **Finishing a phase:** verify every exit criterion on running systems, then update the _Current state_ table and mark the phase done here.
- **Changing direction:** edit this file deliberately (with a commit that says why). If a spec or plan contradicts this roadmap, either the roadmap is updated or the spec is — never silent drift.
