# Registration drafts, one way to "Đã đăng ký", VND and a classes page (2026-09-30)

Decisions D-118, D-119, D-120 (`2026-09-26-edu-lead-engine/decisions.md`). Builds on the customer lifecycle
(`2026-09-30-customer-lifecycle-design.md`).

## Problem

- "Đã đăng ký" could be picked in the Lead status dropdown: no registration was created and the Lead stayed in the
  Leads list, uncounted. The Ghi danh button did it right; the two disagreed.
- The Ghi danh modal showed a Contact block nobody understood, a payment due date nobody wanted, a required status
  the server already defaults, money in "$", and course / class pickers that gave no way to manage classes.
- Classes (Course Schedule) could only be edited in Desk.
- "Mình muốn đăng ký" in chat only handed the customer to a consultant: nothing recorded what they wanted.

## Design

### One way to register (D-119)

- `lifecycle.guard_converted` (CRM Lead `validate`) refuses Converted without a confirmed registration (Deal in
  Pending Payment, Deposit Paid or Won). Skipped during import / migrate / install and for the registration hook.
- The Lead page dropdown (desktop and mobile) opens the Ghi danh modal for a Won-type status; the modal shows a
  live registration instead of offering a second one. Kanban drops and bulk edits show the server's refusal.
- The Lead follows its registrations (`enrolment.lead_after_deal_change`, on_update of the Deal):

| Deal change | Lead |
|---|---|
| Awaiting Confirmation → Pending Payment / Deposit Paid / Won | Converted, `converted = 1` |
| → Lost, reason Postponed | Nurture, `converted = 0` |
| Pending Payment / Deposit Paid → Lost, other reason | Contacted, `converted = 0` |
| Awaiting Confirmation → Lost, other reason | unchanged (the draft never moved it) |
| → Lost while another live or Won registration exists | unchanged |

### A simpler modal (D-120)

Course, class, branch and deposit. The branch is filled from the Lead and narrows the classes (clear it to see other
branches). The contact is linked by phone / email or created by the server. `payment_due_date` is removed (Custom
Field, layouts, reminder). Status and currency come from Property Setter defaults (Pending Payment, VND).
VND: `setup.ensure_vnd`. Patch `v1_2/simplify_registration` fixes the stored layouts, the status order and the field.

### Drafts by the bot and Jev (D-118)

1. Bot turn: skill `register` (action `enrol`, needs only the course) starts the registration dialogue (D-121,
   `engine/enrol_flow.py`): the next open classes as buttons filling `enrol_class`, plus "Nhờ tư vấn chọn lớp"
   (skip); then the phone; then the handoff (reason `enrol_ready`). While it runs, neither a hot reading nor the
   required slots hand off. A message that leaves the dialogue is read by Jev (`enrol_step`): a side question is
   answered and the class buttons come back (twice, then the consultant picks the class); `later` / `cancel` end it
   without a handoff or a draft; `no_phone` / `any_class` skip that step; asking for a person hands off at once.
   The draft is made when the dialogue ends in a handoff (`pipeline.enrol_drafts` → `effects.enrol` →
   `enrolment.create_draft`), with the class and phone it asked; after a handoff, `register` drafts at once.
2. After a consultant has replied: `intelligence.analyze_conversation` asks Jev `enrol / not_yet` (only when a draft
   is possible) and drafts at confidence ≥ 0.85, with a private note in the conversation.
3. `create_draft`: Deal "Awaiting Confirmation" (course, class if chosen, fee and promotion from `before_insert`), the
   contact linked, a High-priority Task "Xác nhận ghi danh" for the Lead owner. The Lead keeps its status. No second
   draft while a live registration exists.
4. A consultant confirms (moves the Deal to Chờ đóng phí, or enters a deposit) → the Lead becomes Converted; or
   cancels the draft (Hủy đăng ký) → nothing changes for the Lead.

### Classes page

Sidebar "Khóa học & Lớp" (`/crm/classes`): classes by course / branch / status with seats held, seats left and
registrations waiting. Consultants read (default filter: their branch); managers add and edit classes and see the
courses tab. Permissions are the Course Schedule doctype's.

## Out of scope

Editing promotions in the CRM; a class calendar view; bot booking of free-text dates (C6.3).

## Verification

Unit tests for every pure rule (`test_lifecycle`, `test_enrolment`, `test_engine_enrol`, `test_intelligence`,
`test_classes`, `test_currency`); `bench migrate` on the dev site; the guard and the draft → confirm → cancel cycle
exercised on the dev site with a rollback.
