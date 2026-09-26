# Decision Log

Binding record of every decision for the Edu Lead Engine. Newest at the bottom. A decision is changed
only by adding a new entry that supersedes it (never by editing the old one).

Status: **approved** = the user chose it · **assumed** = proposed, not explicitly confirmed yet.

| ID | Date | Decision | Rationale | Status |
|---|---|---|---|---|
| D-001 | 2026-09-26 | Hybrid conversation model (option C): buttons collect certain facts (course, branch, phone); common questions answered directly by the bot; hard questions or hot leads handed to a consultant with an AI summary | Fast answers for FAQs without letting AI handle what it cannot | approved |
| D-002 | 2026-09-26 | Use **TypeSafe Jev only** as the AI (the user holds a Jev key); no generative LLM | User choice | approved |
| D-003 | 2026-09-26 | Jev understands and decides; **reply text is composed from CRM data + templates**, never generated | Jev has no text generation (docs.typesafe.ai: choice / score / noul only). Side benefit: the bot cannot invent fees or schedules | approved |
| D-004 | 2026-09-26 | Emphasis on the **[D] Data** layer: courses, branches, consultants, schedules, FAQs are CRM data editable in the UI, not code constants | Changing a fee or opening a branch must not need a deploy | approved |
| D-005 | 2026-09-26 | Start with a **large demo dataset** modelled on tinhocsaoviet.com; real data replaces it later | No real fee/schedule data available yet; the site publishes no fees | approved |
| D-006 | 2026-09-26 | Routing rule **D = branch + specialty + hotness**: prefer same-branch consultant with the lead's course-group specialty; hot leads go to a team lead; fall back to least-loaded same-branch consultant, then central team. Data split into fine-grained, extensible groups | User choice | approved |
| D-007 | 2026-09-26 | Visibility **C = both**: CRM dashboard for managers + Chatwoot Dashboard App beside each conversation for consultants, both reading one AI Decision Log | User choice | approved |
| D-008 | 2026-09-26 | Conversation engine **approach 1**: Jev-led slot filling with buttons as fallback (ask only for missing slots; tiered Jev questions group→course, area→branch). Without a Jev key or on Jev error, the bot degrades to buttons only | Natural for free text ("Robotics cho con ở Dĩ An" fills two slots at once); approach 2 (keep the rigid button flow) rejected as too rigid for ~45 courses | approved |
| D-009 | 2026-09-26 | One program spec used as a roadmap; layers follow the 5 splitting rules in spec §6.1; layers 1–10 get detailed design first, later layers get detail when reached | Detailing 39 layers now would go stale before they are built | approved |
| D-010 | 2026-09-26 | Structure: **10 clusters / 39 layers** as listed in spec §6.2 | User approved | approved |
| D-011 | 2026-09-26 | Ops (production, backups, monitoring) and multi-tenancy are referenced from `ROADMAP.md` Phases 1–2, not duplicated here | Single place per concern | approved |
| D-012 | 2026-09-26 | Add **B2B lead detection → B2B team** as layer 18 in C4 | Sao Việt claims 15,000+ partner enterprises; a company training 20 staff is a different sale from one learner | **assumed** (user approved the structure without answering this explicitly) |
| D-013 | 2026-09-26 | Cluster 1 data design as in spec §7.1: branches on CRM Territory, courses on CRM Product (custom fields), new DocTypes Course Group / Consultant / Course Schedule / Course Promotion / FAQ Topic in `mmm_custom`; no edits to vendored `crm/` | Extend upstream first (ROADMAP principle 4) | approved |
| D-014 | 2026-09-26 | Lead stores branch in the standard `territory` field and courses in the standard `products` table (lead value = sum of fees, carried to Deal); `course_interest` stays as a readable summary; the hardcoded `branch` Select is retired when layer 7 switches writers | `branch` Select holds only 3 hardcoded branches; standard fields are what CRM reports and Deal conversion already use | approved |
| D-015 | 2026-09-26 | Consultants are a CRM DocType (source of truth), replacing Chatwoot agent `custom_attributes.branch`; Chatwoot keeps only the agent id | CRM is the only source of truth (ROADMAP principle 2) | approved |
| D-016 | 2026-09-26 | Answer templates use **Jinja** via `frappe.render_template`; only administrators edit them | Native to Frappe; supports loops (e.g. list the next 3 schedules) | approved |
| D-017 | 2026-09-26 | One main spec file (`2026-09-26-edu-lead-engine-design.md`) plus companion files in this folder (agent briefing README, this log, code map, glossary, open questions); agents consult them instead of conversation memory | Avoid context drift / hallucination across long design conversations | approved |
| D-018 | 2026-09-26 | Spec files are written in English (repo rule, `AGENTS.md`); Vietnamese bot copy stays Vietnamese; diagrams in Mermaid | Repo convention; Mermaid renders on GitHub and diffs as text | assumed |
