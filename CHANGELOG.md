# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- DX-OS [I] Intelligence layer in `mmm_custom` (optional, TypeSafe Jev API, off until `typesafe_api_key` is set): every incoming message is analyzed for intent and hotness, the customer's phone/email is picked out of the chat (a possible duplicate Lead is flagged, never merged), the Chatwoot conversation is labelled and a reply template suggested as a private note — only when Jev's confidence is above the threshold; a daily job creates follow-up Tasks for open Leads that went quiet. CRM Lead gets `ai_intent` / `ai_hotness` fields.
- Agent bot: Quick Reply qualification (course, branch) with a pure state machine, hand-off to the branch's least-busy agent, conversation labels, CRM `lead_owner` assignment.
- In-bench Chatwoot webhook endpoint `mmm_custom.api.chatwoot_sync`: HMAC-SHA256 + anti-replay, 3-tier dedup (`crm_lead_id` → `chatwoot_contact_id` → email/phone), course-interest detection, FCRM Note log, `crm_lead_id` write-back.
- `course_interest` / branch fields and a data-quality indicator on CRM Lead (list view badge).
- Unified `docker-compose.yml` for Chatwoot + Frappe CRM.
- Project `LICENSE` (AGPL-3.0), `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `THIRD_PARTY_LICENSES.md`, GitHub issue templates, FOSS compliance report.

### Changed
- Docker images pinned by digest (or exact tag) so a build from source reproduces the verified stack; Redis pinned to `7.2.4-alpine` (BSD-3-Clause).
- Unified stack volumes are no longer `external`, so `docker compose up` works on a fresh clone while reusing existing dev volumes.

### Removed
- n8n (`n8n/`, `docker/n8n/`) — Sustainable Use License is not OSI-approved; replaced by the in-bench webhook.
- `messenger-platform-samples/` — Facebook Platform License is not OSI-approved; reference code only.
- `chatwoot/enterprise/` and `chatwoot/spec/enterprise/` — proprietary Chatwoot Enterprise License; Chatwoot runs as Community Edition (MIT).

### Fixed
- Security: the webhook endpoints no longer fall back to a hardcoded secret published in the repository; `scripts/configure-chatwoot.py` generates the secret and copies it into the CRM site config.
- Chatwoot and the CRM could not reach each other: `host.docker.internal` cannot reach ports bound to `127.0.0.1`. Webhooks, the agent bot and the `crm_lead_id` write-back now use service names on the unified stack's `shared_net`, and `configure-chatwoot.py` sets the CRM's Chatwoot API URL and token (the write-back had never run).
- Agent bot: Chatwoot rejects Agent Bot tokens on `/contacts` and `/agents` (401), so the bot never saved its state or picked a branch agent; those calls now use the user token.
- Adding conversation labels replaced the existing ones (Chatwoot's API sets the whole list); labels are now merged.
- A failed Chatwoot write-back raised on the Error Log title length and rolled back the new Lead.
- A fresh bench's Administrator password is `admin123`, matching the docs and seed scripts (upstream default `admin`).
- `frappe-custom/mmm_custom/license.txt` had an unfilled `[year] [fullname]` placeholder.

## [0.1.0] - 2026-09-23

First working pipeline (Roadmap Phase 0).

### Added
- Vendored Chatwoot `4.18.0` and Frappe CRM `v1.84.0`, both run from source (Chatwoot image built locally; CRM on pinned Frappe `v15.121.1`).
- `mmm_custom` Frappe app: `chatwoot_contact_id` custom field on CRM Lead, `Messenger`/`Instagram` lead sources.
- n8n workflow Chatwoot → CRM with dedup by email/phone.
- Docker Compose stacks for Chatwoot, CRM, n8n (all ports on `127.0.0.1`); Caddy reverse-proxy config.
- Seed scripts for matching demo accounts across Chatwoot and CRM.
- Product `ROADMAP.md`, design spec, and build plan.
