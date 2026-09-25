# Contributing to DX-OSD

Thanks for helping. By contributing you agree your contribution is licensed under the project's [AGPL-3.0](LICENSE) (or, inside a vendored directory, that directory's own license).

## Reporting bugs and requesting features

Use [GitHub Issues](https://github.com/giabuh/dx-osd/issues) with the **Bug report** or **Feature request** template. For a bug, include the steps to reproduce, what you expected, what happened, and which stack (Chatwoot / CRM / Activepieces) is involved. Never paste `.env` contents or API keys.

## Making a change

1. Fork, then branch from `main` (`feat/<topic>` or `fix/<topic>`).
2. Build and run the stacks from source as described in [`README.md`](README.md).
3. Make the change. New work should trace to a phase in [`ROADMAP.md`](ROADMAP.md).
4. Run the checks for the area you touched:

   | Area | Check |
   |---|---|
   | Sync/dedup and AI agent logic (`activepieces/logic/`) | `node --test activepieces/logic/*.test.mjs` |
   | Flows (`activepieces/flows/`) | Re-import into Activepieces and exercise the changed flow |
   | Chatwoot (`chatwoot/`, `docker/chatwoot/`) | Rebuild; `http://127.0.0.1:3000` answers 200/302 |
   | CRM (`crm/`, `frappe-custom/mmm_custom/`) | `bench --site crm.localhost list-apps` shows `mmm_custom`; `http://127.0.0.1:8000` answers 200 |

5. If you edited anything inside `chatwoot/` or `crm/`, add a row to [`docs/vendored-upstreams.md`](docs/vendored-upstreams.md).
6. Add a line under **Unreleased** in [`CHANGELOG.md`](CHANGELOG.md).
7. Open a pull request describing what changed and how you verified it.

## Conventions

- Code, comments, commit messages, and docs in English.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/): `feat(scope): ...`, `fix(scope): ...`, `docs: ...`.
- Never commit `.env` files or `scripts/seed-shared-accounts/credentials.local.json`.
- Every new dependency must have an OSI-approved license compatible with AGPL-3.0; list it in [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).
