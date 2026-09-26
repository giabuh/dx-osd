# DX-OSD

An open-source, self-hosted lead-to-CRM platform for SMBs, built as a **DX-Lab** for the OLP Open Source Software 2026 competition. Leads from Facebook Lead Ads and conversations from Messenger/Instagram converge into one deduplicated CRM, on top of mature open-source products instead of reinventing them. The reference deployment is an education center (EduFlow Academy: English, swimming, and math courses across several branches).

License: **AGPL-3.0** (see [`LICENSE`](LICENSE)). Every bundled component is OSI-licensed — see [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md) and the audit in [`docs/foss-compliance-report.md`](docs/foss-compliance-report.md).

## Architecture (DX-OS H-P-D-I)

Two stacks: Chatwoot Community Edition and Frappe CRM, with our Frappe app `mmm_custom` running inside the CRM bench — no separate automation middleware.

| Space | Component | Role |
|---|---|---|
| **[H] Human** | Chatwoot CE (`chatwoot/`) | One inbox for staff; conversations routed to the right branch's agents (`scripts/seed-branch-agents.py`) |
| **[P] Process** | `mmm_custom` webhooks (`api.py`, `bot_api.py`, `bot_engine.py`) | Event-driven: HMAC-verified Chatwoot webhooks → 3-tier dedup → create/update CRM Lead; an agent bot qualifies the lead (course, branch) with Quick Replies and hands off to a human |
| **[D] Data** | Frappe CRM (`crm/`) + `mmm_custom` fields | Single source of truth for Lead/Contact/Deal; native Facebook Lead Ads sync; data-quality indicator per Lead |
| **[I] Intelligence** | `mmm_custom` AI agents on [TypeSafe Jev](https://docs.typesafe.ai) (optional) | Read each conversation and act on their own when confident: intent and hotness, the customer's phone/email picked out of the chat (possible duplicates flagged), conversation labels, a suggested reply; every morning, follow-up Tasks for quiet Leads |

Design rationale: [`docs/superpowers/specs/`](docs/superpowers/specs/) and [`docs/superpowers/plans/`](docs/superpowers/plans/); direction: [`ROADMAP.md`](ROADMAP.md).

## Repository layout

| Path | What it is |
|---|---|
| `chatwoot/` | Vendored Chatwoot Community Edition (MIT; proprietary `enterprise/` removed), built locally |
| `crm/` | Vendored Frappe CRM `v1.84.0` (AGPL-3.0), run from source |
| `frappe-custom/mmm_custom/` | Our Frappe app (MIT): webhook endpoints, dedup, agent bot, data quality, AI agents, custom fields |
| `docker-compose.yml` | Unified stack: Chatwoot + Frappe CRM |
| `docker/` | Per-stack overrides, Caddy reverse proxy |
| `scripts/` | Chatwoot/CRM setup, seeding, live integration test |
| `docs/` | Compliance report, spec, plans, vendored-source log |

## Build and run from source

Requirements: Docker with Compose v2, Python ≥ 3.10, `openssl`.

```bash
git clone https://github.com/giabuh/dx-osd.git && cd dx-osd

# 1. Chatwoot secrets (the file is gitignored)
cp chatwoot/.env.example chatwoot/.env
#    set SECRET_KEY_BASE, POSTGRES_PASSWORD, REDIS_PASSWORD (openssl rand -hex 32)

# 2. Build Chatwoot from chatwoot/ and start both stacks (first run: ~10 min for the build + CRM bench init)
docker compose build
docker compose run --rm chatwoot-rails bundle exec rails db:chatwoot_prepare
docker compose up -d
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000   # 200/302
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000   # 200 once the bench is ready

# 3. Wire Chatwoot to the CRM (account, inbox, webhook + its secret into the CRM site config), agent bot, branch agents
python scripts/configure-chatwoot.py
python scripts/setup-agent-bot.py
python scripts/seed-branch-agents.py

# 4. Tests
python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests
SECRET=$(docker exec crm-frappe-1 python3 -c "import json; print(json.load(open('/home/frappe/frappe-bench/sites/crm.localhost/site_config.json'))['chatwoot_webhook_secret'])")
python scripts/test-chatwoot-crm-sync.py --secret "$SECRET"
```

| Service | URL | Login |
|---|---|---|
| Chatwoot | http://127.0.0.1:3000 | set by `scripts/configure-chatwoot.py` |
| Frappe CRM | http://127.0.0.1:8000 | `Administrator` / `admin123` (dev only) |

All ports bind to `127.0.0.1`, so Chatwoot and the CRM reach each other by service name (`chatwoot-rails`, `crm-frappe`) on the unified stack's `shared_net` — run them with the root `docker-compose.yml`. Caddy (`docker/caddy/`) is the public entry once a domain exists. Never run `docker compose down -v` — the named volumes hold the data.

### Optional: [I] AI agents

The AI agents are off until a TypeSafe API key is set; the pipeline runs fully without them. See [`frappe-custom/mmm_custom/README.md`](frappe-custom/mmm_custom/README.md#ai-agents-optional).

## Contributing, bugs, changes

- How to contribute: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Bug reports and feature requests: [GitHub Issues](https://github.com/giabuh/dx-osd/issues)
- Release history: [`CHANGELOG.md`](CHANGELOG.md)
- Edits made to vendored upstream code: [`docs/vendored-upstreams.md`](docs/vendored-upstreams.md)
