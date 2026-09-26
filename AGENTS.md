# AGENTS.md

Shared guidance for every AI coding agent working in this repository — Claude Code, Codex, Gemini CLI. This is the single source: `CLAUDE.md` imports it and `.gemini/settings.json` points Gemini at it. Put agent-agnostic knowledge here, not in the per-agent files.

## Working rules (all agents)

- **Trace work to the roadmap.** New work belongs to a phase in `ROADMAP.md`; respect its guiding principles.
- **Know which area you are in** (see the map below) and run that area's check before calling a change done. Quote the actual output — "should work" is not "works".
- **Vendored edits get recorded.** Any change inside `chatwoot/` or `crm/` needs a row in `docs/vendored-upstreams.md`.
- **Never destroy shared state.** Do not run `docker compose down -v`, `docker volume rm`, or `docker system prune` on the `chatwoot` or `crm` projects — they hold the working dev data. To test from scratch, use a separate compose project (`docker compose -p <name>-verify ...`) and remove only that.
- **Secrets stay out.** Never commit or print `.env` files or `scripts/seed-shared-accounts/credentials.local.json`.
- **Language:** code, identifiers, comments, commit messages, and docs in English.
- **Commits:** single-line conventional message (`feat(scope): ...`); stage explicit paths only (never `git add -A`/`.`); commit only when asked.

## Repository map

| Area | Paths | Check before done |
|---|---|---|
| CRM customization | `frappe-custom/mmm_custom/`, `crm/docker/` | Fresh bench via a `-p crmverify` project: `bench --site crm.localhost list-apps` shows `mmm_custom`; CRM answers 200 on `:8000` |
| Chatwoot | `docker/chatwoot/`, `chatwoot/` (vendored) | Chatwoot answers 200/302 on `:3000` |
| CRM Integration & Webhooks | `frappe-custom/mmm_custom/mmm_custom/`, `scripts/test-chatwoot-crm-sync.py` | `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests` passes; `python scripts/test-chatwoot-crm-sync.py --secret "$SECRET"` passes (5/5) against running stacks |
| [I] AI agents (optional) | `frappe-custom/mmm_custom/mmm_custom/intelligence.py`, `followup.py` | Unit tests pass; with `typesafe_api_key` set, an incoming message on a Lead's conversation updates `ai_intent`/`ai_hotness` and labels the conversation |
| Activepieces alternative (not deployed by default) | `activepieces/logic/`, `activepieces/flows/`, `docker/activepieces/` | `node --test activepieces/logic/*.test.mjs` passes. It duplicates the in-bench `mmm_custom` pipeline: never run both against the same Chatwoot/CRM (duplicate Leads) |
| Deployment / ops | `docker/`, `docker/caddy/`, `scripts/` | Affected stack comes up with the documented commands; ports still bind `127.0.0.1` only |
| Docs & planning | `ROADMAP.md`, `REPO.md`, `docs/` | Claims match the code and `git log` |

## What this repository is

DX-OSD stands on the shoulders of two mature, complete open-source products and builds a Facebook Lead Ads + Messenger/Instagram → CRM pipeline for an SMB business on top of them, rather than reinventing a CRM or an inbox from scratch, strictly enforcing **100% pure FOSS (OSI-approved)** licensing:

- **Chatwoot** (`chatwoot/`) — inbox for Messenger/Instagram conversations, vendored in from [chatwoot/chatwoot](https://github.com/chatwoot/chatwoot) under the MIT Expat license. Proprietary `enterprise/` directory was excised to enforce pure Community Edition compliance.
- **Frappe CRM** (`crm/`) — source of truth for Lead/Contact/Deal/pipeline, vendored in from [frappe/crm](https://github.com/frappe/crm) under GNU AGPLv3. Already has native Facebook Lead Ads polling built in (`crm/lead_syncing/`), no custom code needed for that flow.
- **mmm_custom** (`frappe-custom/mmm_custom/`) — native in-bench Frappe custom app under MIT license: receives Chatwoot webhooks directly via `@frappe.whitelist(allow_guest=True)` endpoint `mmm_custom.api.chatwoot_sync`, validates HMAC-SHA256 signature and timestamp anti-replay, dedups against CRM by email/phone/`crm_lead_id`, detects course interest keywords, attaches `FCRM Note` conversation logs, and synchronizes `crm_lead_id` back to Chatwoot contacts. Replaced external n8n middleware for 100% FOSS purity and zero-overhead execution.

Full design rationale and every architectural decision is in **`docs/superpowers/specs/2026-09-22-facebook-integration-platform.md`** and **`docs/superpowers/plans/2026-09-24-foss-meta-integration.md`**.

The product-level direction — vision, guiding principles, and milestone phases beyond this first pipeline — is in **`ROADMAP.md`**; new work should trace back to a phase there.

`REPO.md` provides the full component matrix and FOSS technology evaluation summary.

## Vendored source: `chatwoot/`, `crm/`

These two directories are **first-class, tracked source in this repo now** — vendored in (their own `.git` histories removed) rather than kept as separate clones, so the whole product ships from one repo and one `git clone`. They are ordinary files here: edit them directly when a change belongs in Chatwoot or Frappe CRM itself, and commit at the top level like any other change in this repo.

- Each still carries its upstream `LICENSE` file — keep those; the copyright/license terms of the giants we're building on stay intact.
- Each has its own `AGENTS.md`/`CLAUDE.md` (`chatwoot/CLAUDE.md`, `chatwoot/AGENTS.md`, `crm/AGENTS.md`) with useful internal dev commands (build/test/lint) — this file does not duplicate those.
- There is no upstream remote wired up anymore. Pulling future upstream updates means fetching the new version manually and re-applying any local customizations — this repo has traded easy upstream syncing for a single self-contained codebase. **`docs/vendored-upstreams.md`** holds the baselines, the re-sync procedure, and the log of every edit made inside a vendored directory — add a row there whenever you edit one.
- **Both stacks run this vendored source:** Chatwoot is built locally from `chatwoot/` (image `dx-osd/chatwoot:local`), and `crm/` is bind-mounted into the CRM bench on a pinned Frappe (`v15.121.1`). Rebuild/restart to see an edit — details in `docs/vendored-upstreams.md`.

## Commands

### Unified Stack (Chatwoot + Frappe CRM)
Run the entire platform from the repository root:
```bash
docker compose up -d          # brings up both Chatwoot (:3000) and Frappe CRM (:8000)
docker compose ps             # verify all 7 services running
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000   # expect 200/302
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000   # expect 200
```
To stop the entire stack safely (preserving persistent dev data):
```bash
docker compose stop
```
*Never pass `-v` to `docker compose down` as named volumes hold the active database state.*

### Individual Stacks (Optional / Component-specific dev)

#### Chatwoot
```bash
cd chatwoot
docker compose -f docker-compose.production.yaml -f ../docker/chatwoot/docker-compose.override.yaml up -d --build   # builds dx-osd/chatwoot:local from chatwoot/
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000   # expect 200/302
```
Secrets live in `chatwoot/.env` (gitignored, generated via `openssl rand -hex`, not committed).

#### Frappe CRM
```bash
cd crm/docker
docker compose up -d          # auto-loads docker-compose.override.yml from this same directory
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000   # expect 200
```
Site: `crm.localhost`, login `Administrator` / `admin123` (reset from upstream `crm/docker/init.sh`'s default, dev-only credential — see `scripts/seed-shared-accounts/` for seeding matching demo staff accounts across Chatwoot and CRM). This override also fixes two real upstream bugs: the named volume must mount at `/home/frappe`, not `/home/frappe/frappe-bench`, or `bench init` always fails "already exists"; and the `frappe` service needs an explicit `dns:` entry, or first-run network calls (PyPI, GitHub) can fail.

### In-Bench Integration Tests & Webhook Verification
Run the Python unit test suite:
```bash
python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests
```
Run live end-to-end integration tests against running Frappe CRM and Chatwoot stacks. The endpoints have no fallback secret: `scripts/configure-chatwoot.py` generates the webhook secret and copies it into the site config (`chatwoot_webhook_secret`), and the test reads it from there:
```bash
SECRET=$(docker exec crm-frappe-1 python3 -c "import json; print(json.load(open('/home/frappe/frappe-bench/sites/crm.localhost/site_config.json'))['chatwoot_webhook_secret'])")
python scripts/test-chatwoot-crm-sync.py --secret "$SECRET"
```

### Bot Engine Tests
```bash
python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -v
```

## Architecture notes

- **Service boundary:** Frappe CRM is the only source of truth for Lead/Contact/Deal data. Chatwoot is inbox-only — its contact records are not canonical. `mmm_custom` holds no separate persistent database state; it executes as an in-bench extension directly operating on the CRM database.
- **Dedup:** a contact can arrive via Facebook Lead Ads (handled natively inside Frappe CRM) and later message on Messenger (handled by Chatwoot → `mmm_custom.api.chatwoot_sync`). The two are linked by a two-way custom field: `crm_lead_id` in Chatwoot's `contact.custom_attributes`, and `chatwoot_contact_id` as a Custom Field on the CRM Lead doctype (added via a dedicated Frappe app, `frappe-custom/mmm_custom/`).
- **Course Interest Detection:** incoming messages are analyzed in `mmm_custom.api.detect_course_interest` to automatically categorize prospective students into course interests (`Tiếng Anh`, `Bơi lội`, `Toán tư duy`) directly visible on the CRM Lead.
- **Security:** Every web port binds to `127.0.0.1` only on every stack; Caddy reverse proxy (`docker/caddy/`) is the only public entry point once a real domain is configured. Webhook endpoints enforce HMAC-SHA256 signature verification and a 300-second anti-replay timestamp window.
- Both stacks are deployed independently via separate `docker compose` projects (`docker/chatwoot/` and `crm/docker/`) — there is no single monolithic compose file tying them together.
