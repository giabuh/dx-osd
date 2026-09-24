# Component Architecture & FOSS Technology Evaluation

DX-OSD is built on an evaluation of the open-source ecosystem for customer relationship management, messaging inboxes, and omnichannel lead acquisition. DX-OSD strictly enforces **100% pure Free and Open Source Software (FOSS)** compliant with the Open Source Initiative (OSI) standards.

---

## Active Architecture Components (2-Stack Model)

DX-OSD replaces complex, multi-system middleware with a streamlined, high-performance two-stack architecture:

| Component / Subsystem | Repository Path | Core Functionality | License (OSI-Approved) | Role in DX-OSD |
|---|---|---|---|---|
| **Frappe CRM** | `crm/` (vendored v1.84.0) | Central source of truth for Leads, Contacts, Deals, and Pipelines. Features native polling for Meta/Facebook Lead Ads (`crm/lead_syncing/`). | **GNU AGPLv3** | Core CRM Platform & Lead Store |
| **Chatwoot Community** | `chatwoot/` (vendored 4.18.0) | Omnichannel inbox managing real-time conversations across Facebook Messenger, Instagram Direct, web live-chat, and email. Stripped of proprietary `enterprise/` code. | **MIT Expat** | Customer Communication Inbox |
| **Frappe In-Bench App (`mmm_custom`)** | `frappe-custom/mmm_custom/` | High-performance Python webhook handler running inside the Frappe bench (`mmm_custom.api.chatwoot_sync`). Provides HMAC-SHA256 signature verification, anti-replay validation, intelligent phone/email deduplication, course interest keyword detection, and bi-directional Chatwoot-CRM synchronization. | **MIT** | Direct Integration & Synchronization Layer |
| **Caddy Server** | `docker/caddy/` | High-performance edge reverse proxy providing automated TLS termination, security header enforcement, and subpath routing for `chat.` and `crm.` domains. | **Apache 2.0** | Secure Public Edge Gateway |
| **MariaDB** | `mariadb:10.8` (in `crm/docker`) | High-performance relational database backing Frappe Framework and Frappe CRM. | **GPLv2** | Primary Database |
| **Redis** | `redis:7.2.4-alpine` (Chatwoot & CRM) | In-memory key-value cache and background worker queue. Specifically pinned to version `7.2.4-alpine` to maintain strict BSD-3 compliance before upstream Redis relicensed under non-OSI SSPL/RSAL. | **BSD-3-Clause** | Cache & Job Queue |

---

## Ecosystem Alternatives Evaluated & Architectural Decisions

During the development and architectural refinement of DX-OSD, several candidate platforms and tools were evaluated:

| Technology Evaluated | Original Purpose | Decision & Architectural Rationale |
|---|---|---|
| **n8n** | Workflow automation pipe | **Decommissioned & Purged.** n8n is distributed under the *Sustainable Use License* (Fair-code), which is not OSI-approved and restricts commercial and hosting rights. Replaced entirely by the native, zero-overhead Frappe custom app `frappe-custom/mmm_custom/` executing directly in Python within the Frappe bench. |
| **Messenger Platform Samples** | Meta reference code | **Purged.** Vendored reference samples from Meta (`messenger-platform-samples/`) contained proprietary and non-FOSS licensing constraints. Cleanly excised; Chatwoot handles all Messenger and Instagram Graph API interactions natively. |
| **Activepieces** | Workflow automation | **Excluded.** Evaluated as an alternative to n8n, but discarded in favor of zero-dependency, in-bench Python execution in `mmm_custom`, eliminating external node processes and network hops. |
| **Airbyte** | Data integration / ETL | **Excluded.** Heavyweight overhead; marketing and lead attribution data is captured directly upon webhook ingress and stored in Frappe CRM. |
| **Meta Business SDK** | Direct Meta API client | **Excluded.** Redundant because Frappe CRM natively handles Facebook Lead Ads webhooks/polling, and Chatwoot natively handles Messenger Graph API protocols. |

---

## Compliance Summary

- **Total FOSS Purity:** 100% OSI-compliant.
- **Licenses Present:** GNU AGPLv3, MIT Expat, Apache 2.0, BSD-3-Clause, GPLv2.
- **Proprietary / Source-Available Code:** 0%. All non-FOSS code and dependencies have been audited, decommissioned, and purged from the repository.