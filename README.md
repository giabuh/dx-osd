# DX-OSD

An open-source, self-hosted lead-to-CRM platform for SMBs, built as a **DX-Lab** for the OLP Open Source Software 2026 competition. Leads from Facebook Lead Ads and conversations from Messenger/Instagram converge into one deduplicated CRM, on top of mature open-source products instead of reinventing them. The reference deployment is an education center (EduFlow Academy: English, swimming, and math courses across several branches).

License: **AGPL-3.0** (see [`LICENSE`](LICENSE)). Every bundled component is OSI-licensed — see [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md) and the audit in [`docs/foss-compliance-report.md`](docs/foss-compliance-report.md).

## Architecture (DX-OS H-P-D-I)

Two stacks: Chatwoot Community Edition and Frappe CRM, with our Frappe app `mmm_custom` running inside the CRM bench — no separate automation middleware.

| Space | Component | Role |
|---|---|---|
| **[H] Human** | Chatwoot CE (`chatwoot/`) | Inbox only: every Facebook page gets the bot, each conversation is handed to the consultant the CRM rule picks. Agents and branch teams are mirrored from CRM `Consultant` (`mmm_custom/staff_sync.py`) — manage staff in CRM, not here |
| **[P] Process** | `mmm_custom` webhooks (`api.py`, `bot_api.py`, `bot_engine.py`) | Event-driven: HMAC-verified Chatwoot webhooks → 3-tier dedup → create/update CRM Lead; an agent bot qualifies the lead (course, branch) with Quick Replies and hands off to a human |
| **[D] Data** | Frappe CRM (`crm/`) + `mmm_custom` fields | Single source of truth for Lead/Contact/Deal; native Facebook Lead Ads sync; data-quality indicator per Lead |
| **[I] Intelligence** | `mmm_custom` AI agents on [TypeSafe Jev](https://docs.typesafe.ai) (optional) | Read each conversation and act on their own when confident: intent and hotness, the customer's phone/email picked out of the chat (possible duplicates flagged), conversation labels, a suggested reply; every morning, follow-up Tasks for quiet Leads |

Design rationale: [`docs/superpowers/specs/`](docs/superpowers/specs/) and [`docs/superpowers/plans/`](docs/superpowers/plans/).

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

## Quick start (reviewers)

Requirements: Linux or macOS, Docker with Compose v2 (≥ 8 GB RAM for Docker, ~15 GB free disk), Python ≥ 3.10, `openssl`, `curl`, and internet access on the first run. Ports `3000`, `8000`, `9000`, `15432`, `16379` must be free.

```bash
git clone https://github.com/giabuh/dx-osd.git && cd dx-osd
./scripts/quickstart.sh            # add --verify to also run the tests at the end
```

One command does everything, and it is safe to run again (every step is idempotent, data is kept):

1. checks the requirements and generates `chatwoot/.env` with random secrets (gitignored);
2. builds Chatwoot from `chatwoot/` and prepares its database;
3. starts the unified stack and waits until both apps answer (Frappe CRM installs its bench and builds its frontend on the first start);
4. wires Chatwoot to the CRM: account, inbox, HMAC webhook, agent bot, and the shared secrets in the CRM site config;
5. loads the demo education center (branches, consultants, courses, schedules, promotions, bot skills) and mirrors the staff into Chatwoot.

The **first run takes about 20–40 minutes** (mostly the Chatwoot image build and the CRM bench init); later runs take a minute. To follow the CRM while it installs: `docker compose logs -f crm-frappe`.

When it finishes:

| Service | URL | Login |
|---|---|---|
| Frappe CRM | http://127.0.0.1:8000 | `Administrator` / `admin123` |
| Chatwoot | http://127.0.0.1:3000 | `admin@eduflow.vn` / `admin123` |

These are dev-only credentials. Stop with `docker compose stop` and start again with `docker compose up -d`. **Never run `docker compose down -v`** — the named volumes hold the data.

### What to try

- **Chatwoot → CRM pipeline without a Facebook page:** `./scripts/quickstart.sh --verify` (or the commands under [Tests](#tests)) sends signed Chatwoot webhooks to the CRM; it checks that bad signatures and replayed requests are rejected, that a Lead is created, and that a second conversation from the same person lands on the same Lead; open *Leads* in the CRM to see it.
- **CRM:** the demo branches, consultants and courses; a Lead's *Messages* tab reads and answers its Chatwoot conversation.
- **Chatwoot:** the *EduFlow Academy Facebook* inbox, the *EduFlow Qualification Bot* on it, and the agents and teams mirrored from CRM consultants.
- **Real Messenger/Instagram and Lead Ads** need a Facebook Page and a Meta app: `scripts/setup-facebook-channel.py` and the spec in [`docs/superpowers/specs/`](docs/superpowers/specs/).

### Troubleshooting

| Symptom | Fix |
|---|---|
| `permission denied` on the Docker socket | Add your user to the `docker` group (then log in again) or run with `sudo` |
| `port is already allocated` | Free the port listed above (another Postgres/Redis/app), then run the script again |
| CRM not ready after 45 min | `docker compose logs crm-frappe` — usually a network failure reaching PyPI/GitHub/npm during `bench init`; run the script again |
| Chatwoot shows 502/500 right after start | Wait a minute for Rails to boot; `docker compose logs chatwoot-rails` |
| Start over from zero | `docker compose down -v` deletes **all** data of this stack (only on a machine where it holds nothing you need), then run the script again |

## Build and run step by step

What `scripts/quickstart.sh` does, for anyone who wants to run it by hand:

```bash
# 1. Chatwoot secrets (the file is gitignored)
cp chatwoot/.env.example chatwoot/.env
#    set SECRET_KEY_BASE, POSTGRES_PASSWORD, REDIS_PASSWORD (openssl rand -hex 32),
#    FRONTEND_URL=http://127.0.0.1:3000, RAILS_ENV=production

# 2. Build Chatwoot from chatwoot/ and start both stacks
docker compose build chatwoot-rails
docker compose run --rm chatwoot-rails bundle exec rails db:chatwoot_prepare
docker compose up -d
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000   # 200/302
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000   # 200 once the bench is ready

# 3. Wire Chatwoot to the CRM (account, inbox, webhook + its secret into the CRM site config), agent bot
python3 scripts/configure-chatwoot.py
python3 scripts/setup-agent-bot.py
# Demo data (branches, staff, course groups + courses with their knowledge, schedules, promotions, bot skills);
# idempotent, from frappe-custom/mmm_custom/mmm_custom/demo/saoviet/*.json
docker exec crm-frappe-1 bash -lc "cd /home/frappe/frappe-bench && bench --site crm.localhost execute mmm_custom.demo.loader.load"
# Staff: add Consultants in CRM; they sync to Chatwoot on save and every 10 min, or right away with:
docker exec crm-frappe-1 bash -lc "cd /home/frappe/frappe-bench && bench --site crm.localhost execute mmm_custom.staff_sync.sync_now"
# After editing branches/staff/courses in the CRM, write them back into the demo dataset to share them:
docker exec crm-frappe-1 bash -lc "cd /home/frappe/frappe-bench && bench --site crm.localhost execute mmm_custom.demo.exporter.export"
```

### Tests

```bash
python3 -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests
SECRET=$(docker exec crm-frappe-1 python3 -c "import json; print(json.load(open('/home/frappe/frappe-bench/sites/crm.localhost/site_config.json'))['chatwoot_webhook_secret'])")
python3 scripts/test-chatwoot-crm-sync.py --secret "$SECRET"
```

All ports bind to `127.0.0.1`, so Chatwoot and the CRM reach each other by service name (`chatwoot-rails`, `crm-frappe`) on the unified stack's `shared_net` — run them with the root `docker-compose.yml`. Caddy (`docker/caddy/`) is the public entry once a domain exists.

### Optional: [I] AI agents

The AI agents are off until a TypeSafe API key is set; the pipeline runs fully without them. Turn them on at setup with `TYPESAFE_API_KEY=<key> ./scripts/quickstart.sh`. See [`frappe-custom/mmm_custom/README.md`](frappe-custom/mmm_custom/README.md#ai-agents-optional).

## Contributing, bugs, changes

- How to contribute: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Bug reports and feature requests: [GitHub Issues](https://github.com/giabuh/dx-osd/issues)
- Release history: [`CHANGELOG.md`](CHANGELOG.md)
- Edits made to vendored upstream code: [`docs/vendored-upstreams.md`](docs/vendored-upstreams.md)
