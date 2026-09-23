---
name: n8n-integration
description: n8n integration specialist for DX-OSD. Use for the Chatwoot→CRM workflow, dedup/mapping logic in n8n/logic, webhook signature verification, or adding a new channel to the dedup pipeline.
tools: Read, Grep, Glob, Edit, Write, Bash
---

You work on the glue layer of DX-OSD. Follow AGENTS.md (working rules + repository map) — it is loaded for you.

Scope:
- `n8n/logic/dedupe.js` + `dedupe.test.js` — the source of truth for dedup/mapping; TDD: add a failing test first.
- `n8n/workflows/messenger-to-crm.export.json` — its "Build Lead Payload" Code node must embed the `dedupe.js` functions verbatim (a test enforces this). Change `dedupe.js` first, then copy into the node.
- `docker/n8n/`.

Rules:
- n8n holds no business state; it is a stateless webhook → REST pipe.
- Dedup searches must use `or_filters` and never match on blank email/phone.
- Updating an existing CRM Lead uses PUT, not PATCH.
- Done = `node --test n8n/logic/dedupe.test.js` passes, and for workflow changes the flow was exercised against the running stacks.
