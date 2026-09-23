# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

DX-OSD stands on the shoulders of two mature, complete open-source products and builds a Facebook Lead Ads + Messenger/Instagram → CRM pipeline for an SMB business on top of them, rather than reinventing a CRM or an inbox from scratch:

- **Chatwoot** (`chatwoot/`) — inbox for Messenger/Instagram conversations, vendored in from [chatwoot/chatwoot](https://github.com/chatwoot/chatwoot).
- **Frappe CRM** (`crm/`) — source of truth for Lead/Contact/Deal/pipeline, vendored in from [frappe/crm](https://github.com/frappe/crm). Already has native Facebook Lead Ads polling built in (`crm/lead_syncing/`), no custom code needed for that flow.
- **n8n** (deployed via `docker/n8n/`) — glue layer: receives Chatwoot webhooks, dedups against CRM by email/phone, creates/updates CRM Leads.
- **`messenger-platform-samples/`** — reference sample code from Meta ([fbsamples/messenger-platform-samples](https://github.com/fbsamples/messenger-platform-samples)), vendored in for reference; not deployed anywhere in this architecture.

Full design rationale and every architectural decision is in **`docs/superpowers/specs/2026-09-22-facebook-integration-platform.md`** — read that before making any architecture-level change. The task-by-task build plan, with exact commands and the current pass/fail status of each task, is in **`docs/superpowers/plans/2026-09-22-facebook-integration-platform.md`**; its live execution ledger (what's done, parked, and why) is at `.superpowers/sdd/2026-09-22-facebook-integration-platform/progress.md`.

The product-level direction — vision, guiding principles, and milestone phases beyond this first pipeline — is in **`ROADMAP.md`**; new work should trace back to a phase there.

`REPO.md` is a leftover candidate-repo comparison table from before the architecture was decided — background context only, not the current design.

## Vendored source: `chatwoot/`, `crm/`, `messenger-platform-samples/`

These three directories are **first-class, tracked source in this repo now** — vendored in (their own `.git` histories removed) rather than kept as separate clones, so the whole product ships from one repo and one `git clone`. They are ordinary files here: edit them directly when a change belongs in Chatwoot or Frappe CRM itself, and commit at the top level like any other change in this repo.

- Each still carries its upstream `LICENSE` file — keep those; the copyright/license terms of the giants we're building on stay intact even though we no longer track upstream's CI/contribution workflow (their `.github/` directories were deliberately removed — this project doesn't run their CI or accept upstream-style PRs).
- Each has its own `AGENTS.md`/`CLAUDE.md` (`chatwoot/CLAUDE.md`, `chatwoot/AGENTS.md`, `crm/AGENTS.md`) with useful internal dev commands (build/test/lint) — this file does not duplicate those, but their conventions no longer bind changes made for DX-OSD's own purposes.
- There is no upstream remote wired up anymore. Pulling future upstream updates means fetching the new version manually and re-applying any local customizations — this repo has traded easy upstream syncing for a single self-contained codebase. **`docs/vendored-upstreams.md`** holds the baselines, the re-sync procedure, and the log of every edit made inside a vendored directory — add a row there whenever you edit one.
- **Runtime gap:** neither stack runs this vendored source yet — Chatwoot uses the `chatwoot/chatwoot:latest` image and CRM's `init.sh` does `bench get-app crm --branch main` from GitHub. Edits to Chatwoot/CRM application code have no effect until that is changed (Docker files under `crm/docker/` do take effect).

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
Site: `crm.localhost`, login `Administrator` / `admin123` (reset from upstream `crm/docker/init.sh`'s default, dev-only credential — see `scripts/seed-shared-accounts/` for seeding matching demo staff accounts across Chatwoot and CRM). This override also fixes two real upstream bugs (see the plan's Task 3 for full evidence): the named volume must mount at `/home/frappe`, not `/home/frappe/frappe-bench`, or `bench init` always fails "already exists"; and the `frappe` service needs an explicit `dns:` entry, or first-run network calls (PyPI, GitHub) can fail.

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
`n8n/logic/dedupe.js` exports `normalizePhone`, `buildLeadSearchFilters`, `buildNewLeadPayload` — these are copied verbatim into an n8n Code node (not imported) because n8n's Code node can't import local files; keep the two copies in sync if this logic changes. The last test in `dedupe.test.js` fails if the Code node in `n8n/workflows/messenger-to-crm.export.json` no longer embeds these functions verbatim.

## Architecture notes

- **Service boundary:** Frappe CRM is the only source of truth for Lead/Contact/Deal data. Chatwoot is inbox-only — its contact records are not canonical. n8n holds no business state; it's a stateless webhook-to-REST-API pipe.
- **Dedup:** a contact can arrive via Facebook Lead Ads (handled natively inside Frappe CRM) and later message on Messenger (handled by Chatwoot → n8n). The two are linked by a two-way custom field: `crm_lead_id` in Chatwoot's `contact.custom_attributes`, and `chatwoot_contact_id` as a Custom Field on the CRM Lead doctype (added via a dedicated Frappe app, `frappe-custom/mmm_custom/` — see the plan's Task 6).
- **Every web port binds to `127.0.0.1` only** on every stack; a Caddy reverse proxy (planned, not yet built — see Task 5) is meant to be the only public entry point once a real domain is available.
- All three stacks are deployed independently via separate `docker compose` projects under this repo's own `docker/` tree (plus `crm/docker/`, which is inside the vendored repo for the auto-load reason above) — there is no single top-level compose file tying them together.
