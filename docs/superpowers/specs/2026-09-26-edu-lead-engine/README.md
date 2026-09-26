# Edu Lead Engine — Agent Briefing

Start here if you are an AI agent (or a new human) picking up this work. It tells you what to read,
in what order, and how to turn the spec into a correct plan without loading everything.

**The spec:** [`../2026-09-26-edu-lead-engine-design.md`](../2026-09-26-edu-lead-engine-design.md).
This folder holds its companions. **Current position:** C1, C2 and C3 designed (spec §7.1–§7.2);
waiting for the user's review of the written spec, then the C1 implementation plan. C4+ not designed.
Layer IDs are `Cn.m` (D-047); old numbers 1–39 in early decisions map via spec §6.3.

## Read order (stop as soon as you have what you need)

1. **This file.**
2. **`decisions.md`** — whole file; it is short and binding.
3. **Spec §6.2** — find the layer/cluster you are working on and its status.
4. **Spec §7.x** for that cluster only. If the cluster has no §7 section, it is **not designed**: do
   not plan it — run a design (brainstorming) session first.
5. **`current-state.md`** — only the rows for files you will touch. Re-check line numbers with `grep -n`.
6. `glossary.md` / `open-questions.md` — when a term or gap comes up.

Do not read the whole spec or every companion by default.

## Authority when files disagree

`decisions.md` > spec §7 (cluster design) > spec §1–6 > `current-state.md` > conversation memory.
If you find a conflict, say so, fix the lower-authority file, and continue from the higher one.

## Rules

- Build only what an approved decision or §7 design says. Anything new → propose it, record it in
  `decisions.md` once approved, then act.
- A decision marked **assumed** must be confirmed with the user before code depends on it.
- Follow the repo rules in `AGENTS.md` (area checks, vendored-edit log, no secrets, commit style).
- Jev never generates text; every customer-facing sentence comes from a template + CRM data (D-003).
- Everything must still work with no Jev key (spec §5.3).

## Writing a plan

- **One plan per cluster**; each layer is one phase and one commit (the `/gate` cadence).
  Save to `docs/superpowers/plans/YYYY-MM-DD-edu-lead-engine-cNN-<name>.md`.
- Each phase states: the layer row it implements, the decision IDs it relies on, files to create or
  modify, tests to write first, and the exact verification command with the expected result (from
  spec §7.x "verification" and the area table in `AGENTS.md`).
- Stay inside the layer. Work that belongs to a later layer is listed as out of scope, not done early.

## When a layer is done

1. Update its status in spec §6.2 (⬜ → 🔨 → ✅ only after verification on running stacks).
2. Update the affected rows in `current-state.md`.
3. Record any decision made during the work in `decisions.md`; remove answered items from `open-questions.md`.
