# Third-party components and licenses

DX-OSD's own code is licensed under [AGPL-3.0](LICENSE). It builds on the components below; each keeps its original license.

## Vendored in this repository (source included, may be modified)

| Path | Upstream | Version | License | License file |
|---|---|---|---|---|
| `chatwoot/` | [chatwoot/chatwoot](https://github.com/chatwoot/chatwoot) | `4.18.0` | MIT (Community Edition — `enterprise/` removed) | [`chatwoot/LICENSE`](chatwoot/LICENSE) |
| `crm/` | [frappe/crm](https://github.com/frappe/crm) | `v1.84.0` | AGPL-3.0 | [`crm/LICENSE`](crm/LICENSE) |
| `frappe-custom/mmm_custom/` | ours | — | MIT | [`frappe-custom/mmm_custom/license.txt`](frappe-custom/mmm_custom/license.txt) |

Every modification we made to vendored code is logged in [`docs/vendored-upstreams.md`](docs/vendored-upstreams.md). Libraries bundled by each vendored project (Ruby gems, npm and Python packages) are declared in that project's own manifests (`chatwoot/Gemfile.lock`, `chatwoot/package.json`, `crm/pyproject.toml`, `crm/frontend/package.json`) under their own licenses.

## Fetched at build/run time (not stored in this repository)

| Component | Used by | Version | License |
|---|---|---|---|
| [Frappe Framework](https://github.com/frappe/frappe) | CRM bench (`crm/docker/init.sh`) | `v15.121.1` | MIT |
| [frappe/bench](https://github.com/frappe/bench) image | CRM stack | `latest` | GPL-3.0 |
| [MariaDB](https://mariadb.org/) | CRM database | `10.8` | GPL-2.0 |
| [Redis](https://redis.io/) | Chatwoot and CRM queues/cache | `alpine` (8.x) | AGPL-3.0 (Redis 8 tri-license option) |
| [PostgreSQL](https://www.postgresql.org/) + [pgvector](https://github.com/pgvector/pgvector) | Chatwoot database | `pg16` | PostgreSQL License |
| [PostgreSQL](https://www.postgresql.org/) | n8n database | `16-alpine` | PostgreSQL License |
| [Node.js](https://nodejs.org/), [Ruby](https://www.ruby-lang.org/) base images | Chatwoot build | `24-alpine`, `3.4.4-alpine3.21` | MIT, BSD-2-Clause |
| [Caddy](https://github.com/caddyserver/caddy) | Reverse proxy | `2-alpine` | Apache-2.0 |
| [n8n](https://github.com/n8n-io/n8n) | Integration workflow | `latest` | Sustainable Use License — **not OSI-approved; being replaced by Activepieces (MIT)** |

## Removed for license reasons

| Component | License | Why removed |
|---|---|---|
| `messenger-platform-samples/` ([fbsamples](https://github.com/fbsamples/messenger-platform-samples)) | Facebook Platform License | Not OSI-approved; was reference code only |
| `chatwoot/enterprise/`, `chatwoot/spec/enterprise/` | Chatwoot Enterprise License | Proprietary; Chatwoot runs as Community Edition without it |
