# Build From Source Guide

This guide explains how to install, build, run, and verify **DX-OSD (Open-Core DX-Lab)** from source using 100% open-source tools, adhering to the Olympic Tin học Sinh viên (OLP) 2026 Open Source Software criteria.

---

## 1. Overview & Build Paths

DX-OSD stands on the shoulders of two mature, pure open-source products to build an education/SMB digital transformation operating system:
1. **Chatwoot Community Edition (`chatwoot/`)** — Multi-channel communication inbox (MIT). Built locally from source into `dx-osd/chatwoot:local`.
2. **Frappe CRM (`crm/`)** — Business pipeline, Lead/Contact/Deal single source of truth (AGPL-3.0). Run from source on Frappe Framework v15.
3. **mmm_custom (`frappe-custom/mmm_custom/`)** — In-bench open-core extension (MIT) coordinating event webhooks, deduplication, AI agent routing, and lead nurturing.

Two build workflows are supported:
- **Unified Stack (Recommended)**: Runs both Chatwoot (`:3000`) and Frappe CRM (`:8000`) together via the root `docker-compose.yml`.
- **Individual Stacks**: For component-level development and debugging.

---

## 2. Requirements

All tools required to build and run the platform are 100% free and open-source:

| Tool | Minimum Version | Purpose |
|---|---|---|
| **Git** | 2.30+ | Clone repository and manage version history |
| **Docker Engine** | 24.0+ | Containerized execution environment |
| **Docker Compose** | v2.20+ | Multi-service orchestration |
| **Python** | 3.10+ | In-bench test execution and test scripts |
| **curl / openssl** | Standard | Webhook verification and secret generation |

### Port Allocation (127.0.0.1 binding only)
Ensure the following local ports are available:
- `3000`: Chatwoot Web UI & API
- `8000`: Frappe CRM Web Desk & REST API
- `9000`: Frappe Socket.io real-time bus
- `15432`: PostgreSQL (Chatwoot database)
- `16379`: Redis (Chatwoot & CRM queues/caching)

---

## 3. Quick Start (Automated Build & Setup)

Clone the repository and run the automated quickstart script:

```bash
git clone https://github.com/giabuh/dx-osd.git
cd dx-osd

# Run quickstart with verification
./scripts/quickstart.sh --verify
```

The script executes the following steps idempotently:
1. Validates local system dependencies and generates secure random secrets in `chatwoot/.env`.
2. Builds the Chatwoot image `dx-osd/chatwoot:local` from `chatwoot/` and prepares PostgreSQL.
3. Starts the unified stack and waits for healthchecks (`:3000` and `:8000`).
4. Configures Chatwoot inboxes, HMAC-SHA256 webhook subscriptions, and syncs shared secrets into CRM `site_config.json`.
5. Loads seed data (EduFlow Academy branches, consultants, course catalogs, promotions).

---

## 4. Manual Step-by-Step Build

### Step 4.1: Unified Stack Build & Launch

From the repository root:

```bash
# Build and bring up all containers in the background
docker compose up -d --build

# Verify all services are healthy and running
docker compose ps
```

### Step 4.2: Component-Specific Builds (Optional)

#### Chatwoot Local Build
To rebuild the Chatwoot image directly from `chatwoot/`:
```bash
cd chatwoot
docker compose -f docker-compose.production.yaml -f ../docker/chatwoot/docker-compose.override.yaml up -d --build
```

#### Frappe CRM Bench
To start the Frappe CRM bench:
```bash
cd crm/docker
docker compose up -d
```

---

## 5. Verification & Testing

### 5.1 Service Healthchecks
Confirm web endpoints return valid HTTP response codes:
```bash
# Chatwoot inbox (expects 200 or 302 redirect)
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000

# Frappe CRM (expects 200 OK)
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000
```

### 5.2 Python Unit Test Suite
Execute the full unit test suite (1000+ tests including bot engine, dedup, catalog rules, memory, and timeout fallback):
```bash
python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -v
```

### 5.3 Live Webhook & Sync Integration Test
Verify end-to-end communication between Chatwoot and Frappe CRM against running containers:
```bash
SECRET=$(docker exec crm-frappe-1 python3 -c "import json; print(json.load(open('/home/frappe/frappe-bench/sites/crm.localhost/site_config.json'))['chatwoot_webhook_secret'])")
python scripts/test-chatwoot-crm-sync.py --secret "$SECRET"
```

---

## 6. Dependency & Licensing Compliance

- **No Proprietary Compilers**: The entire codebase compiles and runs with standard GCC/Clang (inside alpine containers), Node.js, and Python.
- **Pure FOSS**: Proprietary packages (such as `chatwoot/enterprise`) have been excised to ensure 100% compliance with OSI-approved licenses (AGPL-3.0, MIT, Apache-2.0, BSD-3-Clause).
- **Third-Party Declarations**: Complete license breakdown and audits are documented in [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).

---

## 7. Stopping & Resetting

To safely stop the stack while preserving all database and test data:
```bash
docker compose stop
```

> [!WARNING]
> Never pass `-v` to `docker compose down` unless you explicitly want to wipe dev databases. Persistent named volumes hold the active MariaDB and PostgreSQL states.
