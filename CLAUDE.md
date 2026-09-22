# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This is an **integration project**, not a single application. It wires three independent, self-hosted platforms together into one Facebook Lead Ads + Messenger/Instagram → CRM pipeline for an SMB business:

- **Chatwoot** (`chatwoot/`) — inbox for Messenger/Instagram conversations.
- **Frappe CRM** (`crm/`) — source of truth for Lead/Contact/Deal/pipeline. Already has native Facebook Lead Ads polling built in (`crm/lead_syncing/`), no custom code needed for that flow.
- **n8n** (deployed via `docker/n8n/`) — glue layer: receives Chatwoot webhooks, dedups against CRM by email/phone, creates/updates CRM Leads.

The three systems are **never merged into one codebase**. This repo only contains the glue: deployment config, the n8n-side integration logic, and the planning docs that drive the whole build.

Full design rationale and every architectural decision is in **`docs/superpowers/specs/2026-09-22-facebook-integration-platform.md`** — read that before making any architecture-level change. The task-by-task build plan, with exact commands and the current pass/fail status of each task, is in **`docs/superpowers/plans/2026-09-22-facebook-integration-platform.md`**; its live execution ledger (what's done, parked, and why) is at `.superpowers/sdd/2026-09-22-facebook-integration-platform/progress.md`.

`REPO.md` is a leftover candidate-repo comparison table from before the architecture was decided — background context only, not the current design.

## Critical: the three vendored directories are foreign git repos

`chatwoot/`, `crm/`, and `messenger-platform-samples/` are each independent clones of their own upstream repo (`chatwoot/chatwoot`, `frappe/crm`, `fbsamples/messenger-platform-samples`), with their own `.git` and their own remote. They are gitignored here.

- **Never run `git` commands inside them** (no commits, no staging) — that's this repo's job only, at the top level.
- **Never modify a tracked file inside them.** The only files ever added there are new, untracked deployment files (e.g. `crm/docker/docker-compose.override.yml`) needed because Docker Compose auto-loads an override file only when it sits next to the base `docker-compose.yml` — everything else lives in this repo's own `docker/` directory instead.
- Each has its own `AGENTS.md`/`CLAUDE.md` (`chatwoot/CLAUDE.md`, `chatwoot/AGENTS.md`, `crm/AGENTS.md`) if you need their internal dev commands — this file does not duplicate those.
- `messenger-platform-samples/` is reference-only sample code from Meta; it is not deployed anywhere in this architecture.

## Commands

### Chatwoot (uses its own upstream compose file, plus our port/DNS override)
```bash
cd chatwoot
docker compose -f docker-compose.production.yaml -f ../docker/chatwoot/docker-compose.override.yaml up -d
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000   # expect 200/302
```
Secrets live in `chatwoot/.env` (gitignored, generated via `openssl rand -hex`, not committed).

### Frappe CRM (uses its own upstream compose file + our override in the same directory)
```bash
cd crm/docker
docker compose up -d          # auto-loads docker-compose.override.yml from this same directory
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000   # expect 200
```
Site: `crm.localhost`, admin password `admin` (from upstream `crm/docker/init.sh`, dev-only credential). This override also fixes two real upstream bugs (see the plan's Task 3 for full evidence): the named volume must mount at `/home/frappe`, not `/home/frappe/frappe-bench`, or `bench init` always fails "already exists"; and the `frappe` service needs an explicit `dns:` entry, or first-run network calls (PyPI, GitHub) can fail.

### n8n
```bash
cd docker/n8n
docker compose up -d
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5678   # expect 200
```
Secrets live in `docker/n8n/.env` (gitignored).

### n8n integration logic (dedup/mapping)
Plain Node, no `package.json`/dependencies — uses the built-in `node:test` runner:
```bash
node --test n8n/logic/dedupe.test.js
```
`n8n/logic/dedupe.js` exports `normalizePhone`, `buildLeadSearchFilters`, `buildNewLeadPayload` — these are copied verbatim into an n8n Code node (not imported) because n8n's Code node can't import local files; keep the two copies in sync if this logic changes.

## Architecture notes

- **Service boundary:** Frappe CRM is the only source of truth for Lead/Contact/Deal data. Chatwoot is inbox-only — its contact records are not canonical. n8n holds no business state; it's a stateless webhook-to-REST-API pipe.
- **Dedup:** a contact can arrive via Facebook Lead Ads (handled natively inside Frappe CRM) and later message on Messenger (handled by Chatwoot → n8n). The two are linked by a two-way custom field: `crm_lead_id` in Chatwoot's `contact.custom_attributes`, and `chatwoot_contact_id` as a Custom Field on the CRM Lead doctype (added via a dedicated Frappe app, not by editing `crm/` directly — see the plan's Task 6).
- **Every web port binds to `127.0.0.1` only** on every stack; a Caddy reverse proxy (planned, not yet built — see Task 5) is meant to be the only public entry point once a real domain is available.
- All three stacks are deployed independently via separate `docker compose` projects under this repo's own `docker/` tree (plus `crm/docker/`, which is inside the vendored repo for the auto-load reason above) — there is no single top-level compose file tying them together.
