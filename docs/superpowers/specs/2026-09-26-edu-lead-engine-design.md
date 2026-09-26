# Edu Lead Engine — Design Spec

_Started: 2026-09-26 · Status: **design in progress** — C1 approved, C2+ not yet designed · Pilot: Tin Học Sao Việt (demo data)_

## 1. Purpose

Turn DX-OSD from "Messenger messages become CRM Leads" into an education lead engine: every inbound
customer is understood by an AI decision model (TypeSafe Jev), answered from real CRM data, routed to
the right branch and consultant, and followed through to enrolment — with every automated decision
visible to managers and consultants.

This spec is also the roadmap for that work: **10 clusters, 39 layers**, built one layer at a time. It
refines `ROADMAP.md` Phases 4–5 (sales automation, AI assistance) for the education vertical.
Production/ops and multi-tenancy stay in `ROADMAP.md` Phases 1–2 (D-011).

## 2. How this spec is organised

This file is **the spec**. Companion files in
[`2026-09-26-edu-lead-engine/`](2026-09-26-edu-lead-engine/) hold the context it relies on, so design
conversations and implementation read files instead of relying on memory (D-017):

| Companion | Role | Authority |
|---|---|---|
| [`README.md`](2026-09-26-edu-lead-engine/README.md) | Agent briefing: read order, authority, how to write a plan | Entry point |
| [`decisions.md`](2026-09-26-edu-lead-engine/decisions.md) | Every decision, numbered `D-NNN`, with rationale | **Binding.** If this spec and the log disagree, the log wins and this spec is fixed |
| [`current-state.md`](2026-09-26-edu-lead-engine/current-state.md) | Map of today's code (file:line), what is on/off, which layer changes it | Facts; re-verify line numbers |
| [`glossary.md`](2026-09-26-edu-lead-engine/glossary.md) | Terms EN ↔ VI | Reference |
| [`open-questions.md`](2026-09-26-edu-lead-engine/open-questions.md) | Undecided items and unconfirmed assumptions | Working list |

Workflow: a new decision goes into `decisions.md` first, then this spec is updated. A cluster's detailed
design is added to §7 only after it is presented and approved; the layer then moves to 📝.

## 3. Success criteria (program level)

1. A customer writing free text on Messenger ("Robotics cho con 8 tuổi ở Dĩ An, học phí sao?") gets a
   correct, data-backed answer within seconds, or a clean handoff — never an invented fee or schedule.
2. Every lead lands on the right consultant by rule D (branch + specialty + hotness), and the reason is
   recorded.
3. Courses, fees, schedules, branches, consultants and answer wording are changed in the CRM UI with no
   code change or deploy.
4. Managers see the funnel and every automated decision in the CRM; consultants see, beside each
   Chatwoot conversation, what the AI understood and why the conversation is theirs.
5. With no Jev key, or Jev failing, customers are still served (buttons only) and no lead is lost.

## 4. Constraints

- **Stand on giants / extend first.** Reuse Frappe CRM DocTypes (Territory, Product, Lead `territory`
  and `products`, SLA, Task, Deal) and Chatwoot features (Agent Bot, Teams, Dashboard Apps). No edits
  to vendored `crm/` or `chatwoot/` unless no extension point fits — and then recorded in
  `docs/vendored-upstreams.md`.
- **One source of truth.** CRM owns all business data, including consultants (D-015). Chatwoot holds
  conversation state and ids only.
- **Jev is optional.** It is a proprietary hosted API (listed in `THIRD_PARTY_LICENSES.md`); nothing
  may depend on it being available (success criterion 5).
- **Jev never writes text** (D-003). All bot wording comes from Jinja templates filled with CRM data.
- **Security unchanged:** HMAC-verified webhooks with anti-replay, ports on `127.0.0.1`, no secrets in git.
- **Messenger limits:** ≤13 quick replies per message, ≤20 chars per title; outbound messages outside
  the 24h window need a message tag.
- Code, identifiers, docs in English; bot copy in Vietnamese.

## 5. Architecture

### 5.1 System context

```mermaid
flowchart LR
    C[Customer<br/>Messenger / later Zalo, web] --> CW[Chatwoot<br/>inbox + Agent Bot]
    CW -- "webhooks (HMAC)" --> MC
    subgraph CRM[Frappe CRM bench]
        MC[mmm_custom<br/>P: bot, routing, sync]
        D[(D: CRM data<br/>Territory, Product, Consultant,<br/>Schedule, Promotion, FAQ Topic,<br/>Lead, Decision Log)]
        MC <--> D
    end
    MC -- "typed questions" --> JEV[I: TypeSafe Jev<br/>choice / score / noul]
    JEV -- "answers + confidence" --> MC
    MC -- "REST: reply, assign, note, labels" --> CW
    CW --> H[Consultants<br/>Chatwoot + Dashboard App]
    D --> M[Managers<br/>CRM dashboard]
```

### 5.2 Target message flow (detailed in C2/C3)

```mermaid
sequenceDiagram
    participant K as Customer
    participant CW as Chatwoot
    participant B as mmm_custom bot
    participant J as Jev
    participant D as CRM data
    K->>CW: free-text message
    CW->>B: Agent Bot webhook (message_created)
    B->>J: tiered questions: group→course, area→branch, FAQ topic, intent, hotness
    J-->>B: choices/scores + confidence
    B->>D: look up course, branch, schedules, promotions
    alt confident FAQ answer
        B->>CW: reply rendered from template + data
    else slots missing
        B->>CW: ask only the missing slot (quick replies)
    else all slots filled, hot, or unsure
        B->>D: rule D picks consultant
        B->>CW: open + assign + summary private note
    end
    B->>D: write AI Decision Log entry
```

### 5.3 Degraded mode

No `typesafe_api_key`, Jev timeout or error → the same slot-filling engine runs with buttons only
(tiered: area → branch, group → course), and the decision log records `jev_unavailable`.

### 5.4 H-P-D-I mapping

| Layer | In this program |
|---|---|
| H (Human) | Consultants in Chatwoot, managers in CRM |
| P (Process) | Slot-filling bot, handoff, routing, SLA, follow-ups (`mmm_custom`) |
| D (Data) | CRM DocTypes of C1 + Lead + AI Decision Log |
| I (Intelligence) | Jev: understanding, FAQ choice, hotness/intent, confidence gate |

## 6. Roadmap

### 6.1 Layer-splitting rules (D-009)

1. Each layer delivers a result checkable on the running system, not just "code written".
2. Each layer is size S (≤1 day) or M (2–3 days); bigger is split.
3. Dependencies point one way: a layer only uses earlier layers, so the system works at every stop.
4. External dependencies (Jev, Meta, Zalo) are isolated from internal work.
5. Each cluster ends at a demoable business milestone.

Customer-journey spine: **Attract → Understand → Route → See → Nurture → Close → Widen → Measure → Retain.**
Order rationale: finish the whole journey on one channel (Messenger) before adding channels; data
before AI (Jev can only answer what the data holds); measure only once real data flows.

Status: ⬜ not started · 📝 designed · 🔨 in progress · ✅ done (verified on running stacks)

### 6.2 Clusters and layers

**C1 — Data foundation [D]** · milestone: open CRM and see all of Sao Việt · design §7.1
| # | Layer | Size | Status |
|---|---|---|---|
| 1 | Areas → branches on CRM Territory | S | 📝 |
| 2 | Course groups → courses on CRM Product (custom fields) | M | 📝 |
| 3 | Consultants: branch, specialties, level, B2B flag | M | 📝 |
| 4 | Course schedules + promotions | M | 📝 |
| 5 | FAQ topics + Jinja answer templates | M | 📝 |
| 6 | Sao Việt demo dataset + idempotent loader + Chatwoot agents/teams | M | 📝 |

**C2 — Conversation bot, no Jev yet** · milestone: a Messenger customer is fully served with buttons only
| 7 | Slot-filling engine replaces `bot_engine.py`; tiered buttons from data; Lead writes `territory`/`products` | M | ⬜ |
| 8 | Answer composer: template + data | M | ⬜ |
| 9 | AI Decision Log | M | ⬜ |
| 10 | Handoff + summary private note | S | ⬜ |

**C3 — Jev understanding [I]** · milestone: free-text messages are understood and answered correctly
| 11 | Labelled Vietnamese utterance set (~100) + evaluation tool (the ruler before the AI) | M | ⬜ |
| 12 | Jev slot extraction, tiered (group→course, area→branch) | M | ⬜ |
| 13 | Jev FAQ topic choice → direct answer behind the confidence gate | M | ⬜ |
| 14 | Hotness + intent → early handoff (reuse `intelligence.py`) | S | ⬜ |

**C4 — Route to the right person** · milestone: every lead reaches the right consultant, with a reason
| 15 | Routing rule D, configurable in CRM | M | ⬜ |
| 16 | Working hours, holidays, away status | S | ⬜ |
| 17 | Reassign when a consultant misses the response deadline | M | ⬜ |
| 18 | B2B lead detection → B2B team (D-012, assumed) | M | ⬜ |

**C5 — Visibility** · milestone: managers and consultants see the automation
| 19 | CRM dashboard: funnel + charts by course/branch/consultant | M | ⬜ |
| 20 | Decision log browser page | S | ⬜ |
| 21 | Chatwoot Dashboard App, read-only: what AI understood, why assigned | M | ⬜ |
| 22 | Chatwoot Dashboard App, actions: matching schedules/fees, insert into reply | M | ⬜ |

**C6 — No lead left behind** · milestone: no lead goes overdue unnoticed
| 23 | Lead statuses for a training centre + lost reasons | S | ⬜ |
| 24 | First-response SLA + manager alert (CRM SLA) | S | ⬜ |
| 25 | Consultation/trial appointments + reminders (CRM Task) | S | ⬜ |
| 26 | Course-aware re-engagement, 24h-window aware (upgrade `followup.py`) | M | ⬜ |
| 27 | Unified lead score | M | ⬜ |

**C7 — Close the enrolment** · milestone: from chat to enrolment with fee
| 28 | Lead → Deal: enrol course, fee, promotion | M | ⬜ |
| 29 | Duplicate merge proposals, human-approved (never auto-merge) | M | ⬜ |

**C8 — More lead sources**
| 30 | Facebook Lead Ads per-course forms into the same pipeline | M | ⬜ |
| 31 | Website chat widget + form | S | ⬜ |
| 32 | Zalo OA (depends on Zalo approval) | M | ⬜ |

**C9 — Measure & improve**
| 33 | Consultant/branch performance | M | ⬜ |
| 34 | AI quality: bot resolution rate, handoff rate, human corrections → template tuning | M | ⬜ |
| 35 | Ad → enrolment attribution, cost per lead (Meta Marketing API) | M | ⬜ |

**C10 — After enrolment** (direction only; designed when reached)
| 36 | Class schedule reminders | — | ⬜ |
| 37 | Satisfaction survey | — | ⬜ |
| 38 | Referrals | — | ⬜ |
| 39 | Next-course suggestion along learning paths | — | ⬜ |

## 7. Cluster designs

### 7.1 C1 — Data foundation (approved 2026-09-26, D-013…D-016)

#### Data model

```mermaid
erDiagram
    CRM_TERRITORY ||--o{ CRM_TERRITORY : "area contains branch"
    CRM_TERRITORY ||--o{ CONSULTANT : "branch employs"
    CRM_TERRITORY ||--o{ COURSE_SCHEDULE : "held at"
    COURSE_GROUP ||--o{ CRM_PRODUCT : "groups"
    COURSE_GROUP }o--o{ CONSULTANT : "specialty of"
    CRM_PRODUCT ||--o{ COURSE_SCHEDULE : "scheduled as"
    CRM_PRODUCT }o--o{ CRM_PRODUCT : "next course"
    COURSE_PROMOTION }o--o{ CRM_PRODUCT : "applies to"
    CRM_LEAD }o--|| CRM_TERRITORY : "territory"
    CRM_LEAD ||--o{ CRM_PRODUCT : "products (interest)"
    FAQ_TOPIC
```

Standard DocTypes extended with Custom Fields (created in `setup.py` + a patch, like today's fields):

| DocType | Custom fields |
|---|---|
| CRM Territory | `branch_code` (Data, unique), `address` (Small Text), `hotline` (Data), `map_url` (Data), `aliases` (Small Text, comma-separated: "Dĩ An, Di An") |
| CRM Product (= course) | `course_group` (Link Course Group), `audience` (Select: Trẻ em / Học sinh – Sinh viên / Người đi làm / Doanh nghiệp), `min_age`, `max_age` (Int), `duration_text` (Data, "1–2 tháng"), `certificate` (Data), `aliases` (Small Text), `next_courses` (Table MultiSelect → course), `is_demo_data` (Check). `standard_rate` = listed fee |

New DocTypes in `mmm_custom` (module *Mmm Custom*), editable at `/app/<doctype>`:

| DocType | Fields |
|---|---|
| **Course Group** | `group_name` (name), `emoji`, `sort_order`, `aliases`, `description` |
| **Consultant** | `user` (Link User, unique), `full_name` (fetched), `chatwoot_agent_id` (Int), `branch` (Link CRM Territory, leaf only; empty = central team), `level` (Select: Team Lead / Consultant), `specialties` (Table MultiSelect → Course Group), `handles_b2b` (Check), `active` (Check) |
| **Course Schedule** | `course` (Link CRM Product), `branch` (Link CRM Territory), `start_date` (Date), `shift` (Select: Sáng 8:30–11:00 / Chiều 13:30–16:30 / Tối 17:00–21:00), `weekdays` (Data, "T2, T4, T6"), `seats` (Int), `status` (Select: Open / Full / Started), `is_demo_data` |
| **Course Promotion** | `title`, `discount_type` (Percent / Amount), `discount_value`, `valid_from`, `valid_to`, `courses`, `course_groups`, `branches` (Table MultiSelect each; empty = all), `active`, `is_demo_data` |
| **FAQ Topic** | `topic_key` (name), `title`, `jev_description` (Small Text — the criterion text Jev reads), `answer_template` (Code, Jinja), `needs_course`, `needs_branch` (Check), `action` (Select: answer / handoff / link), `creates_lead` (Check; off for e.g. certificate lookup), `active`, `sort_order` |

Rules:
- Aliases on branches, groups and courses are read by both button matching and Jev criteria.
- Templates render with `frappe.render_template`; the context contract (course, branch, next open
  schedules, active promotions) is fixed in layer 8. Only System Manager may edit FAQ Topics.
- C1 **adds only**. `api.py`, `bot_api.py` and Activepieces keep writing `branch`/`course_interest`
  until layer 7 switches to `territory`/`products` (D-014); existing dev leads are mapped where a
  branch matches, otherwise left as is.

#### Demo dataset (layer 6, D-005)

| Data | Count | Source |
|---|---|---|
| Areas / branches | 4 / 13 | **Real** (tinhocsaoviet.com, with addresses) |
| Course groups / courses | 8 / ~45 | **Real names**: Tin học văn phòng, Đồ họa, Vẽ kỹ thuật, Kế toán, Lập trình, Tin học trẻ em (+ Robotics), Digital Marketing, AI & Automation |
| Fees, durations | ~45 | Invented, `is_demo_data = 1` |
| Consultants | ~45 (3 per branch + B2B team + central team) | Invented, non-routable demo email domain |
| Schedules | ~400 (next 8 weeks) | Generated deterministically from per-course branch offerings |
| Promotions / FAQ topics | ~10 / ~30 | Invented; copy built on real selling points ("học không giới hạn buổi đến khi thành thạo", certificate lookup at `chungnhan.tinhocsaoviet.com`) |

Loader: JSON files under `mmm_custom/demo/saoviet/`, run with
`bench --site crm.localhost execute mmm_custom.demo.loader.load`. It upserts by natural key
(`territory_name`, `group_name`, `product_code`, consultant `user`, schedule
course+branch+date+shift, promotion `title`, `topic_key`), so re-running changes nothing, and it can
purge rows with `is_demo_data`. A companion script creates the Chatwoot side: one agent per consultant,
one Team per branch plus B2B and central teams, inbox membership, and writes `chatwoot_agent_id` back to
the Consultant. It supersedes `scripts/seed-branch-agents.py`.

#### C1 verification

- Unit tests for the loader's upsert/idempotency and the deterministic schedule generator.
- On a fresh `-p crmverify` bench: `bench migrate` succeeds; loader run twice gives identical counts
  (4 areas, 13 branches, 8 groups, ~45 courses, ~45 consultants, ~400 schedules); Chatwoot shows the
  15 teams with their agents.
- Existing suites still pass: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests`
  and `scripts/test-chatwoot-crm-sync.py` (5/5).

### 7.2 C2 onwards

Not designed yet. See [`open-questions.md`](2026-09-26-edu-lead-engine/open-questions.md).
