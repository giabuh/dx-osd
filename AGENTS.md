# AGENTS.md

Shared guidance for every AI coding agent working in this repository — Claude Code, Codex, Gemini CLI. This is the single source: `CLAUDE.md` imports it and `.gemini/settings.json` points Gemini at it. Put agent-agnostic knowledge here, not in the per-agent files.

## Working rules (all agents)

- **Trace work to the roadmap.** New work belongs to a phase in `ROADMAP.md`; respect its guiding principles.
- **Know which area you are in** (see the map below) and run that area's check before calling a change done. Quote the actual output — "should work" is not "works".
- **Vendored edits get recorded.** Any change inside `chatwoot/` or `crm/` needs a row in `docs/vendored-upstreams.md`.
- **Never destroy shared state.** Do not run `docker compose down -v`, `docker volume rm`, or `docker system prune` on the `chatwoot`, `crm`, or `activepieces` projects — they hold the working dev data. To test from scratch, use a separate compose project (`docker compose -p <name>-verify ...`) and remove only that.
- **Secrets stay out.** Never commit or print `.env` files or `scripts/seed-shared-accounts/credentials.local.json`.
- **Language:** code, identifiers, comments, commit messages, and docs in English.
- **Commits:** single-line conventional message (`feat(scope): ...`); stage explicit paths only (never `git add -A`/`.`); commit only when asked.

## Repository map

| Area | Paths | Check before done |
|---|---|---|
| CRM customization | `frappe-custom/mmm_custom/`, `crm/docker/` | Fresh bench via a `-p crmverify` project: `bench --site crm.localhost list-apps` shows `mmm_custom`; CRM answers 200 on `:8000` |
| Chatwoot | `docker/chatwoot/`, `chatwoot/` (vendored) | Chatwoot answers 200/302 on `:3000` |
| Activepieces integration | `activepieces/logic/`, `activepieces/flows/`, `docker/activepieces/` | `node --test activepieces/logic/sync.test.mjs` passes; flow re-imported and exercised if it changed |
| Deployment / ops | `docker/`, `docker/caddy/`, `scripts/` | Affected stack comes up with the documented commands; ports still bind `127.0.0.1` only |
| Docs & planning | `ROADMAP.md`, `docs/` | Claims match the code and `git log` |

## What this repository is

DX-OSD stands on the shoulders of two mature, complete open-source products and builds a Facebook Lead Ads + Messenger/Instagram → CRM pipeline for an SMB business on top of them, rather than reinventing a CRM or an inbox from scratch:

- **Chatwoot** (`chatwoot/`) — inbox for Messenger/Instagram conversations, vendored in from [chatwoot/chatwoot](https://github.com/chatwoot/chatwoot).
- **Frappe CRM** (`crm/`) — source of truth for Lead/Contact/Deal/pipeline, vendored in from [frappe/crm](https://github.com/frappe/crm). Already has native Facebook Lead Ads polling built in (`crm/lead_syncing/`), no custom code needed for that flow.
- **Activepieces** Community Edition (deployed via `docker/activepieces/`) — glue layer: receives Chatwoot webhooks, dedups against CRM by email/phone, creates/updates CRM Leads. It replaced n8n on 2026-09-25 because n8n's Sustainable Use License is not OSI-approved (the spec and plan in `docs/superpowers/` still describe the n8n version).

**Every component must be OSI-licensed** (OLP 2026 competition requirement). Check a new dependency's license before adding it and list it in `THIRD_PARTY_LICENSES.md`.

Full design rationale and every architectural decision is in **`docs/superpowers/specs/2026-09-22-facebook-integration-platform.md`** — read that before making any architecture-level change. The task-by-task build plan, with exact commands and the current pass/fail status of each task, is in **`docs/superpowers/plans/2026-09-22-facebook-integration-platform.md`**; its live execution ledger (what's done, parked, and why) is at `.superpowers/sdd/2026-09-22-facebook-integration-platform/progress.md`.

The product-level direction — vision, guiding principles, and milestone phases beyond this first pipeline — is in **`ROADMAP.md`**; new work should trace back to a phase there.

`REPO.md` is a leftover candidate-repo comparison table from before the architecture was decided — background context only, not the current design.

## Vendored source: `chatwoot/`, `crm/`

These two directories are **first-class, tracked source in this repo now** — vendored in (their own `.git` histories removed) rather than kept as separate clones, so the whole product ships from one repo and one `git clone`. They are ordinary files here: edit them directly when a change belongs in Chatwoot or Frappe CRM itself, and commit at the top level like any other change in this repo.

- Each still carries its upstream `LICENSE` file — keep those, and keep every dependency OSI-licensed (competition requirement; see `THIRD_PARTY_LICENSES.md`). `chatwoot/` is Community Edition: `enterprise/` is proprietary and must not be re-added on a re-sync; the copyright/license terms of the giants we're building on stay intact even though we no longer track upstream's CI/contribution workflow (their `.github/` directories were deliberately removed — this project doesn't run their CI or accept upstream-style PRs).
- Each has its own `AGENTS.md`/`CLAUDE.md` (`chatwoot/CLAUDE.md`, `chatwoot/AGENTS.md`, `crm/AGENTS.md`) with useful internal dev commands (build/test/lint) — this file does not duplicate those, but their conventions no longer bind changes made for DX-OSD's own purposes.
- There is no upstream remote wired up anymore. Pulling future upstream updates means fetching the new version manually and re-applying any local customizations — this repo has traded easy upstream syncing for a single self-contained codebase. **`docs/vendored-upstreams.md`** holds the baselines, the re-sync procedure, and the log of every edit made inside a vendored directory — add a row there whenever you edit one.
- **Both stacks run this vendored source:** Chatwoot is built locally from `chatwoot/` (image `dx-osd/chatwoot:local`), and `crm/` is bind-mounted into the CRM bench on a pinned Frappe (`v15.121.1`). Rebuild/restart to see an edit — details in `docs/vendored-upstreams.md`.

## Commands

### Chatwoot (uses its own upstream compose file, plus our override: local source build + port binds)
```bash
cd chatwoot
docker compose -f docker-compose.production.yaml -f ../docker/chatwoot/docker-compose.override.yaml up -d --build   # builds dx-osd/chatwoot:local from chatwoot/ (first build takes a while)
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

### Activepieces
```bash
cd docker/activepieces
cp .env.example .env   # fill the empty values (openssl rand -hex 32; AP_ENCRYPTION_KEY: openssl rand -hex 16)
docker compose up -d
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/api/v1/flags   # expect 200
```
Secrets live in `docker/activepieces/.env` (gitignored). The worker runs with `network_mode: host` so it reaches the app, Chatwoot and CRM on `127.0.0.1`. Flow import/configuration: `activepieces/README.md`.

### Sync logic (signature, dedup, CRM/Chatwoot calls)
Plain Node, no `package.json`/dependencies — uses the built-in `node:test` runner:
```bash
node --test activepieces/logic/sync.test.mjs
```
`activepieces/logic/sync.mjs` is the whole source of the flow's "Sync to CRM" Code step (Activepieces Code steps can't import local files). The last test fails if the Code step in `activepieces/flows/messenger-to-crm.json` is not byte-identical to `sync.mjs`.

## Architecture notes

- **Service boundary:** Frappe CRM is the only source of truth for Lead/Contact/Deal data. Chatwoot is inbox-only — its contact records are not canonical. Activepieces holds no business state; it's a stateless webhook-to-REST-API pipe.
- **Dedup:** a contact can arrive via Facebook Lead Ads (handled natively inside Frappe CRM) and later message on Messenger (handled by Chatwoot → Activepieces). The two are linked by a two-way custom field: `crm_lead_id` in Chatwoot's `contact.custom_attributes`, and `chatwoot_contact_id` as a Custom Field on the CRM Lead doctype (added via a dedicated Frappe app, `frappe-custom/mmm_custom/` — see the plan's Task 6).
- **Every web port binds to `127.0.0.1` only** on every stack; a Caddy reverse proxy (planned, not yet built — see Task 5) is meant to be the only public entry point once a real domain is available.
- All three stacks are deployed independently via separate `docker compose` projects under this repo's own `docker/` tree (plus `crm/docker/`, which is inside the vendored repo for the auto-load reason above) — there is no single top-level compose file tying them together.
