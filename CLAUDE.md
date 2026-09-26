# CLAUDE.md

@AGENTS.md

## Claude Code specifics

- Project settings (`.claude/settings.json`) auto-allow read-only and test commands and deny the destructive/secret-reading ones listed in AGENTS.md's working rules. Personal overrides go in `.claude/settings.local.json` (gitignored).
- Subagents in `.claude/agents/` map one-to-one to the areas in AGENTS.md's repository map: `crm-dev`, `chatwoot-dev`, `automation-integration`, `devops`. Delegate area-scoped work to the matching one; `automation-integration` covers only the non-default Activepieces alternative.
