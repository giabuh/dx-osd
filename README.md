# DX-OSD

An open-source, self-hosted lead-to-CRM platform for SMBs, built as a **DX-Lab** for the OLP Open Source Software 2026 competition. Leads from Facebook Lead Ads and conversations from Messenger/Instagram converge into one deduplicated CRM, on top of mature open-source products instead of reinventing them.

License: **AGPL-3.0** (see [`LICENSE`](LICENSE)). Third-party components keep their own OSI-approved licenses — see [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).

## Architecture (DX-OS H-P-D-I)

| Space | Component | Role |
|---|---|---|
| **[H] Human** | Chatwoot (`chatwoot/`) | One inbox for staff: Messenger/Instagram conversations, shared accounts (`scripts/seed-shared-accounts/`) |
| **[P] Process** | n8n workflow (`n8n/`) | Event-driven: Chatwoot webhook → dedup by email/phone → create/update CRM Lead |
| **[D] Data** | Frappe CRM (`crm/`, `frappe-custom/mmm_custom/`) | Single source of truth for Lead/Contact/Deal; native Facebook Lead Ads sync |
| **[I] Intelligence** | Planned — see [`ROADMAP.md`](ROADMAP.md) | |

Design rationale: [`docs/superpowers/specs/2026-09-22-facebook-integration-platform.md`](docs/superpowers/specs/2026-09-22-facebook-integration-platform.md).

## Repository layout

| Path | What it is |
|---|---|
| `chatwoot/` | Vendored Chatwoot Community Edition (MIT), built locally |
| `crm/` | Vendored Frappe CRM `v1.84.0` (AGPL-3.0), run from source |
| `frappe-custom/mmm_custom/` | Our Frappe app: custom fields and lead sources |
| `n8n/` | Integration workflow and dedup logic (`n8n/logic/`) |
| `docker/` | Compose overrides, n8n stack, Caddy reverse proxy |
| `scripts/` | Seed scripts for demo accounts |
| `docs/` | Spec, plan, vendored-source log |

## Build and run from source

Requirements: Docker with Compose v2, Node.js ≥ 18, `openssl`.

```bash
git clone https://github.com/giabuh/dx-osd.git && cd dx-osd

# 1. Chatwoot — built from chatwoot/ (first build takes a while)
cd chatwoot
cp .env.example .env    # then set SECRET_KEY_BASE, POSTGRES_PASSWORD (openssl rand -hex 32)
docker compose -f docker-compose.production.yaml -f ../docker/chatwoot/docker-compose.override.yaml up -d --build
cd ..

# 2. Frappe CRM — crm/ is bind-mounted into the bench
cd crm/docker && docker compose up -d && cd ../..

# 3. n8n — docker/n8n/.env needs POSTGRES_PASSWORD and N8N_ENCRYPTION_KEY (openssl rand -hex 32)
cd docker/n8n && docker compose up -d && cd ../..

# 4. Run the tests
node --test n8n/logic/dedupe.test.js
```

| Service | URL | Login |
|---|---|---|
| Chatwoot | http://127.0.0.1:3000 | created on first visit |
| Frappe CRM | http://127.0.0.1:8000 | `Administrator` / `admin123` (dev only) |
| n8n | http://127.0.0.1:5678 | created on first visit |

All ports bind to `127.0.0.1`. Import `n8n/workflows/messenger-to-crm.export.json` into n8n and point a Chatwoot webhook at it. Full step-by-step setup: [`docs/superpowers/plans/2026-09-22-facebook-integration-platform.md`](docs/superpowers/plans/2026-09-22-facebook-integration-platform.md).

## Contributing, bugs, changes

- How to contribute: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Bug reports and feature requests: [GitHub Issues](https://github.com/giabuh/dx-osd/issues)
- Release history: [`CHANGELOG.md`](CHANGELOG.md)
- Edits made to vendored upstream code: [`docs/vendored-upstreams.md`](docs/vendored-upstreams.md)
