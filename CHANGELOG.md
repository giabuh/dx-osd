# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Activepieces Community Edition (MIT) stack in `docker/activepieces/` and flow `activepieces/flows/messenger-to-crm.json`: Chatwoot webhook → one Code step (`activepieces/logic/sync.mjs`) that verifies the signature, dedups by email/phone, creates or links the CRM Lead and writes `crm_lead_id` back to Chatwoot. Tests now cover signature checks and every sync branch, not only the dedup helpers.
- Project `LICENSE` (AGPL-3.0), `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `THIRD_PARTY_LICENSES.md`, GitHub issue templates.

### Removed
- n8n (`n8n/`, `docker/n8n/`) — Sustainable Use License is not OSI-approved; replaced by Activepieces with the same behavior.
- `messenger-platform-samples/` — Facebook Platform License is not OSI-approved; it was reference code only and never deployed.
- `chatwoot/enterprise/` and `chatwoot/spec/enterprise/` — proprietary Chatwoot Enterprise License; Chatwoot now runs as Community Edition (MIT).

### Changed
- Docker images pinned (by digest where upstream uses floating tags) so a build from source reproduces the verified stack.

### Fixed
- `frappe-custom/mmm_custom/license.txt` had an unfilled `[year] [fullname]` placeholder.

## [0.1.0] - 2026-09-23

First working pipeline (Roadmap Phase 0).

### Added
- Vendored Chatwoot `4.18.0` and Frappe CRM `v1.84.0`, both run from source (Chatwoot image built locally; CRM on pinned Frappe `v15.121.1`).
- `mmm_custom` Frappe app: `chatwoot_contact_id` custom field on CRM Lead, `Messenger`/`Instagram` lead sources.
- n8n workflow Chatwoot → CRM with dedup by email/phone (`n8n/logic/dedupe.js` + `node:test` suite).
- Docker Compose stacks for Chatwoot, CRM, n8n (all ports on `127.0.0.1`); Caddy reverse-proxy config.
- Seed scripts for matching demo accounts across Chatwoot and CRM.
- Product `ROADMAP.md`, design spec, and build plan.

### Fixed
- CRM Docker override: bench volume at `/home/frappe`, explicit DNS for first-run network calls.
- n8n workflow: existing Lead update uses `PUT`; dedup filter ignores blank email/phone and uses OR.
- Caddy rewrites the `Host` header so Frappe resolves the right site.
