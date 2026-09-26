# Third-party components and licenses

DX-OSD's own code is licensed under [AGPL-3.0](LICENSE); the `mmm_custom` Frappe app is MIT. Everything below keeps its original, OSI-approved license. The full audit is in [`docs/foss-compliance-report.md`](docs/foss-compliance-report.md).

## Vendored in this repository (source included, may be modified)

| Path | Upstream | Version | License | License file |
|---|---|---|---|---|
| `chatwoot/` | [chatwoot/chatwoot](https://github.com/chatwoot/chatwoot) | `4.18.0` | MIT (Community Edition — `enterprise/` removed) | [`chatwoot/LICENSE`](chatwoot/LICENSE) |
| `crm/` | [frappe/crm](https://github.com/frappe/crm) | `v1.84.0` | AGPL-3.0 | [`crm/LICENSE`](crm/LICENSE) |
| `frappe-custom/mmm_custom/` | ours | — | MIT | [`frappe-custom/mmm_custom/license.txt`](frappe-custom/mmm_custom/license.txt) |

Every modification to vendored code is logged in [`docs/vendored-upstreams.md`](docs/vendored-upstreams.md). Libraries bundled by each vendored project (Ruby gems, npm and Python packages) are declared in its own manifests (`chatwoot/Gemfile.lock`, `chatwoot/package.json`, `crm/pyproject.toml`, `crm/frontend/package.json`) under their own licenses. `mmm_custom` uses only the Python standard library, Frappe, and `requests` (Apache-2.0, installed with Frappe).

## Fetched at build/run time (not stored in this repository)

Images are pinned by digest (or exact tag) in `docker-compose.yml` and the per-stack overrides.

| Component | Used by | Version | License |
|---|---|---|---|
| [Frappe Framework](https://github.com/frappe/frappe) | CRM bench (`crm/docker/init.sh`) | `v15.121.1` | MIT |
| [frappe/bench](https://github.com/frappe/bench) image | CRM stack | `5.31.0` | GPL-3.0 |
| [MariaDB](https://mariadb.org/) | CRM database | `10.8.8` | GPL-2.0 |
| [Redis](https://redis.io/) | Chatwoot and CRM queues/cache | `7.2.4-alpine` | BSD-3-Clause (last release before the 7.4 SSPL/RSAL change) |
| [PostgreSQL](https://www.postgresql.org/) + [pgvector](https://github.com/pgvector/pgvector) | Chatwoot database | `16.15` / `0.8.6` | PostgreSQL License |
| [Activepieces](https://github.com/activepieces/activepieces) Community Edition | Optional alternative flow (`docker/activepieces/`), not deployed by default | `0.92.0` | MIT (`AP_EDITION=ce`; its `packages/ee/` is not used and not in this repository) |
| [Node.js](https://nodejs.org/), [Ruby](https://www.ruby-lang.org/) base images | Chatwoot build | `24-alpine`, `3.4.4-alpine3.21` | MIT, BSD-2-Clause |
| [Caddy](https://github.com/caddyserver/caddy) | Reverse proxy | `2.10.2-alpine` | Apache-2.0 |

## External services (called over HTTPS, no code in this repository)

| Service | Used by | Terms | Required? |
|---|---|---|---|
| [Meta Graph API](https://developers.facebook.com/docs/graph-api/) | Frappe CRM Lead Ads sync, Chatwoot Messenger/Instagram channels | Meta Platform Terms | For Facebook channels |
| [TypeSafe Jev](https://docs.typesafe.ai) (`api.typesafe.ai`) | Optional [I] AI agents in `mmm_custom` | Proprietary API, [TypeSafe terms](https://docs.typesafe.ai/legal) | No — off unless `typesafe_api_key` is set; nothing else depends on it |

## Removed for license reasons

| Component | License | Why removed |
|---|---|---|
| [n8n](https://github.com/n8n-io/n8n) (was `n8n/`, `docker/n8n/`) | Sustainable Use License | Not OSI-approved; replaced by the in-bench `mmm_custom` webhook |
| `messenger-platform-samples/` ([fbsamples](https://github.com/fbsamples/messenger-platform-samples)) | Facebook Platform License | Not OSI-approved; was reference code only |
| `chatwoot/enterprise/`, `chatwoot/spec/enterprise/` | Chatwoot Enterprise License | Proprietary; Chatwoot runs as Community Edition without it |
