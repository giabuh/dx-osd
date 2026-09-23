# Vendored upstreams

`chatwoot/`, `crm/`, and `messenger-platform-samples/` are vendored copies of upstream repos (nested `.git` removed in `3a0e4ef`). There is no upstream remote — this file is the record of where each copy came from, what we changed inside it, and how to re-sync.

## Baselines

| Directory | Upstream | Baseline | Vendored on |
|---|---|---|---|
| `chatwoot/` | https://github.com/chatwoot/chatwoot | `4.18.0` (`chatwoot/VERSION`) | 2026-09-22 |
| `crm/` | https://github.com/frappe/crm | `main` branch, `2.0.0-dev` (`crm/crm/__init__.py`) | 2026-09-22 |
| `messenger-platform-samples/` | https://github.com/fbsamples/messenger-platform-samples | default branch | 2026-09-22 |

Update this table on every re-sync.

## What actually runs (known gap)

Neither stack currently runs the vendored source:

- **Chatwoot** runs the prebuilt image `chatwoot/chatwoot:latest` (`chatwoot/docker-compose.production.yaml`).
- **Frappe CRM** clones the app from GitHub at startup: `bench get-app crm --branch main` (`crm/docker/init.sh`).

Observed 2026-09-23 on a fresh bench: running `crm` is `1.84.0` while the vendored copy says `2.0.0-dev`.

So edits to Chatwoot/CRM application code in this repo have **no runtime effect** yet, and the running version can differ from the vendored baseline (both track moving `latest`/`main`). Edits to the Docker files below do take effect. Closing this gap (build/install from the vendored source, pinned) is required before relying on any application-code edit.

## Local edits inside vendored directories

Every change we make inside a vendored directory is listed here, so it can be re-applied after a re-sync. Customizations that live outside vendored directories (`frappe-custom/mmm_custom/`, `n8n/`, `docker/`, `scripts/`) do not belong here.

| File | Change | Why |
|---|---|---|
| `crm/docker/docker-compose.override.yml` | New file (ours): `127.0.0.1` port binds, `dns:` + DNS wait loop, bench volume at `/home/frappe`, bind-mount `frappe-custom/mmm_custom` at `/home/frappe/mmm_custom` | Upstream quickstart does not persist the bench and can fail first-run network calls; see plan Task 3 |
| `crm/docker/init.sh` | Symlink `mmm_custom` into `apps/`, `pip install -e` it, add it to `sites/apps.txt`, `install-app mmm_custom` | Fresh bench comes up with our custom app installed, no manual steps |

## Re-sync procedure

1. Fetch the new upstream version into a scratch location (not over the vendored directory):
   `git clone --depth 1 --branch <tag-or-branch> <upstream-url> /tmp/<name>-upstream`
2. Replace the vendored directory's contents with the new version, excluding `.git/` and `.github/` (both are deliberately not vendored). Keep the upstream `LICENSE`.
3. Re-apply every row of **Local edits** above; drop any row upstream has made unnecessary.
4. Review `git diff --stat` for the directory — anything changed that is neither upstream nor in the edits table is a mistake.
5. Bring the affected stack up per `CLAUDE.md` and re-run the checks for it: HTTP status on its port, `node --test n8n/logic/dedupe.test.js`, and the Messenger → CRM flow from the plan's Task 9/10.
6. Update the **Baselines** table and commit the re-sync as one commit (`chore(vendor): sync <name> to <version>`).
