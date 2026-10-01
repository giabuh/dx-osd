# Weekly plan from CRM data — Design Spec

Decision D-123 (`2026-09-26-edu-lead-engine/decisions.md`). Builds on the comment funnel (D-122).

## Purpose

What the weekly autopilot (`autopilot.py`, spec `2026-09-27-autonomous-marketing-agent-design.md`) does today:

- `WEEKLY_MATRIX` hard-codes four courses (Tiếng Anh, Toán tư duy, Bơi lội, Chung) that are not in the catalog.
  `Facebook Post.course` links to `CRM Product`, so on the live site the first insert fails with
  `LinkValidationError: Could not find Khóa học: Tiếng Anh` and no batch is created. The tests use a mocked
  `frappe` and do not see it.
- The planner reads no data: no class dates, promotions, or the Leads each post brought.
- The caption prompt and the banner footer hard-code a brand, three branches and a hotline
  ("EduFlow Academy", "CS1 Bình Thạnh / CS2 Quận 1 / CS3 Thủ Đức", "0901.888.666"). The CRM says
  "Tin Học Sao Việt", 13 branches, 0931 144 858.
- Captions ask to "inbox the page"; nothing invites the comment keyword that starts the level test (D-106),
  so the comment funnel (D-122) is not opened by the post itself.

## Design

### Choosing the week's courses (`mmm_custom/marketing_plan.py`)

Pure `score(candidate, today)` → (points, reasons), over every course the bot offers (catalog courses):

| Signal | Points | Reason shown |
|---|---|---|
| An open class starts within 30 days with seats left | +3 (+1 within 14 days) | "lớp khai giảng 12/10 còn 6 chỗ" |
| An active Course Promotion applies | +2 | "đang có ưu đãi “Excel nâng cao giảm 10%”" |
| Leads from its posts in the last 28 days | +1 each, max 3 | "bài gần đây ra 2 khách tiềm năng" |
| Registrations from those posts | +2 each, max 4 | "1 học viên đăng ký từ bài gần đây" |
| Not posted (or planned) in the last 28 days | +1 | "lâu chưa đăng" |
| Posted or planned in the last 7 days | −4 | — |

`pick(candidates, today, n=4)`: highest score first, at most one course per course group, then fill;
ties by course code (deterministic). Slot order keeps the matrix days, times and angles; a picked course
with a promotion goes to the Sunday "FOMO offer" slot. Each post stores its `plan_reason`.

`autopilot.generate_weekly_batch` takes the courses from `marketing_plan.plan_week(today)`; the matrix keeps
day, time and angle only. The pipeline card names the chosen courses and why.

### Facts instead of hard-coded text

`marketing_plan.post_facts(course)` gathers, from CRM data: brand name, hotline, website, branch names,
the course's name and fee, the best active promotion and the price after it, the next open class, and the
level-test keyword (`comment_funnel.post_context`). `facts_lines(facts)` turns them into lines.

- Caption prompt: the facts block replaces the hard-coded brand, branches and hotline, with the rule "only
  numbers, offers and addresses from this data". After generation `ensure_cta` appends
  "Bình luận "test photoshop" để nhận bài test trình độ miễn phí" when the course has a level test and the
  caption does not already say it. If the caption carries a number that is not in the facts
  (`engine/llm_draft.numbers_ok`, D-115), the post gets `content_warning` for the person who approves it.
- Banner: footer = hotline · website (or branch count); the CTA reads "INBOX NHẬN ƯU ĐÃI NGAY" when a
  promotion applies. No data → a neutral footer, never invented contact details.

New `Facebook Post` fields: `plan_reason`, `content_warning` (Small Text, read-only).

## Out of scope

Changing slot days/times from engagement data, A/B variants, the admin pages (giabuh's area).

## Verification

- `tests/test_marketing_plan.py`: scoring, group diversity, Sunday promo slot, facts lines, CTA, footer.
- `tests/test_autopilot.py`: the batch uses the planned courses and stores the reason.
- Bench: `plan_week` on live data returns real course codes with reasons; inserting a planned post passes
  link validation (in a rolled-back transaction, no AI calls).
