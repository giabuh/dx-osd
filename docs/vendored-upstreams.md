# Vendored upstreams

`chatwoot/`, `crm/`, and `messenger-platform-samples/` are vendored copies of upstream repos (nested `.git` removed in `3a0e4ef`). There is no upstream remote — this file is the record of where each copy came from, what we changed inside it, and how to re-sync.

## Baselines

| Directory | Upstream | Baseline | Vendored on |
|---|---|---|---|
| `chatwoot/` | https://github.com/chatwoot/chatwoot | `4.18.0` (`chatwoot/VERSION`) | 2026-09-22 |
| `crm/` | https://github.com/frappe/crm | tag `v1.84.0` (`crm/crm/__init__.py`) | 2026-09-23 (was `main`/`2.0.0-dev` on 2026-09-22 — needs unreleased Frappe `develop`, so replaced by the stable tag) |
| `messenger-platform-samples/` | https://github.com/fbsamples/messenger-platform-samples | default branch | 2026-09-22 |

Update this table on every re-sync.

**Pinned, not vendored:** Frappe framework `v15.121.1` (https://github.com/frappe/frappe), cloned by `bench init --frappe-branch` in `crm/docker/init.sh`. `crm` `v1.84.0` accepts `frappe>=15,<17`. When bumping `crm`, check its `[tool.bench.frappe-dependencies]` and that every `frappe.*` module it imports exists in the pinned tag.

## What actually runs

Both stacks run the vendored source, so an edit in `chatwoot/` or `crm/` takes effect on the next build/start:

- **Chatwoot** — image `dx-osd/chatwoot:local`, built from `chatwoot/docker/Dockerfile` (`docker/chatwoot/docker-compose.override.yaml`). Rebuild after changes: `up -d --build` (see AGENTS.md).
- **Frappe CRM** — `crm/` is bind-mounted into the container at `/home/frappe/crm` and symlinked into the bench as `apps/crm` (`crm/docker/init.sh`). Python changes load on restart; frontend changes need `bench build --app crm`.

## Local edits inside vendored directories

Every change we make inside a vendored directory is listed here, so it can be re-applied after a re-sync. Customizations that live outside vendored directories (`frappe-custom/mmm_custom/`, `n8n/`, `docker/`, `scripts/`) do not belong here.

| File | Change | Why |
|---|---|---|
| `crm/docker/docker-compose.override.yml` | New file (ours): `127.0.0.1` port binds, `dns:` + DNS wait loop, bench volume at `/home/frappe`, bind-mount `frappe-custom/mmm_custom` at `/home/frappe/mmm_custom` | Upstream quickstart does not persist the bench and can fail first-run network calls; see plan Task 3 |
| `crm/docker/init.sh` | Symlink `mmm_custom` into `apps/`, `pip install -e` it, add it to `sites/apps.txt`, `install-app mmm_custom` | Fresh bench comes up with our custom app installed, no manual steps |
| `crm/docker/init.sh` | Pin Frappe with `--frappe-branch v15.121.1`; replace `bench get-app crm --branch main` with symlinking the bind-mounted vendored `crm/` (plus `/home/frappe/frappe` → bench frappe, for the frontend's `link:../../frappe/ui`), `pip install -e`, `yarn install`, `bench build --app crm` | Run the vendored CRM source at a pinned framework version |
| `crm/docker/docker-compose.override.yml` | Bind-mount `..` (vendored `crm/`) at `/home/frappe/crm` | Same |
| `chatwoot/docker/Dockerfile` | `git rev-parse HEAD > /app/.git_sha` falls back to `vendored` | Vendored copy has no `.git`; upstream line fails the build |
| chatwoot/config/application.rb | Guard enterprise/ eager load | Boots cleanly as pure Community Edition (MIT) when enterprise/ is removed |

## Re-sync procedure

1. Fetch the new upstream version into a scratch location (not over the vendored directory):
   `git clone --depth 1 --branch <tag-or-branch> <upstream-url> /tmp/<name>-upstream`
2. Replace the vendored directory's contents with the new version, excluding `.git/` and `.github/` (both are deliberately not vendored). Keep the upstream `LICENSE`.
3. Re-apply every row of **Local edits** above; drop any row upstream has made unnecessary.
4. Review `git diff --stat` for the directory — anything changed that is neither upstream nor in the edits table is a mistake.
5. Bring the affected stack up per `AGENTS.md` and re-run the checks for it: HTTP status on its port, `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests`, and `python scripts/test-chatwoot-crm-sync.py`.
6. Update the **Baselines** table and commit the re-sync as one commit (`chore(vendor): sync <name> to <version>`).
