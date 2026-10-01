# Demo seed: one command for a full demo CRM

Date: 2026-10-01. Goal: anyone who clones the repo runs one command and gets the same demo CRM: catalog, staff,
bot knowledge, level tests, **52 sample Leads, 15 registrations, notes, tasks, level-test attempts and Facebook posts
with comments**, and (opt-in) a wipe of the test data a developer piled up. The developers' own test Leads
("Bảo Gia", "Hoàng Thành") are never part of the sample.

## Command

```bash
scripts/seed-demo.sh            # catalog + staff + sample customers; idempotent, safe to re-run
scripts/seed-demo.sh --reset    # first delete ALL customer/test data (CRM and Chatwoot), then seed
```

Steps of `scripts/seed-demo.sh` (bash, `set -euo pipefail`, runs `bench` inside `crm-frappe-1` the way
`scripts/quickstart.sh` does; site `crm.localhost`):

1. `--reset` only: `bench execute mmm_custom.demo.customers.reset` (CRM) and the Chatwoot wipe (below).
2. `bench execute mmm_custom.demo.loader.load` (existing: territories, groups, courses, schedules, promotions,
   consultants, bot slots/skills/settings, staff replies).
3. `bench execute mmm_custom.staff_sync.sync_now`, then `python3 scripts/seed-demo-logins.py` (existing).
4. `bench execute mmm_custom.demo.customers.seed` (new), which also runs `seed_demo.seed_tasks`.
5. Print the counts returned by each step.

`scripts/quickstart.sh --demo` calls the same new step 4 after its existing demo steps.

## Branch addresses (`demo/saoviet/areas.json`)

Take the 13 addresses from tinhocsaoviet.com (post-2025 ward names). Keep `territory_name`, `branch_code`,
`hotline`, `aliases` unchanged:

| branch_code | address |
|---|---|
| HCM-BT | 21/8 Lê Trực, Phường Gia Định, TP.HCM |
| HCM-Q7 | 515 B2/12 Lê Văn Lương, Phường Tân Hưng, TP.HCM |
| HCM-Q6 | Phòng TM-0.39, 510 Kinh Dương Vương, Phường An Lạc, TP.HCM |
| HCM-Q12 | A23 Lê Thị Riêng, KDC Thới An, Phường Thới An, TP.HCM |
| HCM-TD | 133/2 Đỗ Xuân Hợp, Phường Phước Long, TP.HCM |
| HCM-TB | 180 Phạm Văn Bạch, Phường Tân Bình, TP.HCM |
| BD-TDM | Số 107, D5, KDC Phú Hòa 1, Thủ Dầu Một, Bình Dương |
| BD-TA | 8 Đường NA8, KDC Việt Sing, Phường Thuận Giao, Bình Dương |
| BD-DA | 184/19/11 Đặng Văn Mây, KP Đông Chiêu, Phường Dĩ An, Bình Dương |
| BD-TU | 30 Tổ 3, KP Tân Hóa, Phường Tân Khánh, Bình Dương |
| DN-BH | 91 Đoàn Văn Cự, Phường Tam Hiệp, Biên Hòa, Đồng Nai |
| DN-LT | 72 Đinh Bộ Lĩnh, Xã Long Thành, Đồng Nai |
| VT-VT | 293 Bình Giã, Phường Tam Thắng, Vũng Tàu |

## Sample customers (`demo/saoviet/customers.json` + `mmm_custom/demo/customers.py`)

Data is hand-written JSON (realistic Vietnamese names, messages and notes; no real people). Dates are **day
offsets from the run day** (like `seed_demo.TASKS`), so a demo on any day looks current. Course codes, branch names,
consultant emails, promotion titles and quiz skill keys must exist in the other `demo/saoviet/*.json` files.

### Leads: 52, 4 per branch

- Identity: `first_name`/`last_name`, unique `mobile_no` (`09xx xxx xxx`, distinct from every other demo phone),
  `email` = `<slug>@demo.saoviet.invalid` (the idempotency key and the marker of sample data).
- `territory` = the branch, `lead_owner` = a consultant of that branch (`consultants.json`), `products` = 1–2
  courses that the branch offers (an `offer: "full"` course only at a `tier: "full"` branch), `course_interest`
  their readable names, `ai_hotness`, `ai_intent`, `preferred_shift`; about half also `learner_type`,
  `learner_name`, `learner_age`, `learning_goal`, `current_level`.
- `creation` spread over the last 30 days (day offset 0 … -30, some today, ~12 in the last 7 days).
- Status (final, after registrations): New 9, Qualified 9, Contacted 7, Trial Booked 5 (with `trial_date` in the
  coming days), Nurture 4, Converted 12, Unqualified 3 (`lost_reason` Existing Student), Junk 3 (Spam).
- Source: Messenger Bot 20, Facebook Messenger 12, Zalo OA 5, Hotline 5, Giới thiệu 4, Đến trực tiếp 3, TikTok 3.
- No `chatwoot_contact_id` (sample Leads have no Chatwoot conversation).

### Registrations (CRM Deal): 15

Each on a real `Course Schedule` of the Lead's course and branch, starting within the generated 8 weeks (pick the
first open class by `course`/`branch` at seed time; do not hard-code schedule names). Fee and promotion come from
the existing `enrolment` hooks. Final status: Awaiting Confirmation 2 (Lead stays Qualified/Contacted), Pending
Payment 3, Deposit Paid 4 (`deposit_amount`, `deposit_date`), Won 5 (`paid_amount` = final fee), Lost 1 (lost reason
Postponed → the Lead goes back to Nurture). The 12 confirmed ones are exactly the 12 Converted Leads.

**Go through the real hooks** — create the Deal from the Lead's values as the Ghi danh flow does and let
`mmm_custom.enrolment` / `mmm_custom.lifecycle` move the Lead; never write `Converted` on a Lead directly
(`lifecycle.guard_converted` forbids it).

### Notes (FCRM Note): about 40

1–2 per Lead in progress (Qualified … Converted), consultant-style Vietnamese, `owner` = the Lead owner. Key: Lead +
title.

### Tasks: 14

- `seed_demo.TASKS` (6): no "Hoàng Thành" anywhere; every `reference_docname` and `assigned_to` must point at
  sample records / demo consultants (`@demo.saoviet.invalid`; `@eduflow.vn` staff do not exist). Resolve
  references at seed time by sample Lead email (store the email in the task data, not a `CRM-LEAD-…` name).
- 8 new follow-up tasks on sample Leads; 3 of them unassigned or assigned to a consultant of another branch, so the
  task dispatch panel (D-126) has proposals to show. Key: title.

### Level-test attempts: 10

Quiz Attempt (needs a Bot Conversation: create one per Lead with a clear sample name/marker, `is_sandbox` 0 on the
attempt): excel_quiz 4, word_quiz 2, design_quiz 2, kids_quiz 2; mix of `done` (score/total/level, half with
`phone_after` and a `voucher_code` also written on the Lead) and `started`/`offered`. Key: Lead + quiz.

### Facebook posts: 8, with comments

- 5 `Posted` (past week; `fb_post_id` = `demo-<n>`, no `fb_post_url`), 2 `Pending Approval` and 1 `Draft` for the
  coming days. **Never `Scheduled`** — the 5-minute publisher would post it to the real page.
- Posted ones carry plausible likes/comments/shares/reach, and `comments` rows (2–4 each, all sentiments).
- 8 `Facebook Comment Reply` rows (intents quiz/price/interest/praise/other, status Replied or Skipped,
  `public_reply`), 3 linked to sample Leads, which also get `facebook_post` set.
- The hourly `sync_all_posted_analytics` and `comment_funnel` must skip posts whose `fb_post_id` starts with
  `demo-` (small guard in their code if they would otherwise call the Graph API with it).

## `customers.seed()`

Idempotent: re-running creates nothing new, updates changed values, and moves dates to the new run day. Returns
`{doctype: {"created": n, "updated": n}}`. Commits once at the end. Pure helpers (date offsets, picking a class,
choosing a branch consultant, validating the JSON against the catalog) are unit-tested offline like
`tests/test_seed_demo.py`.

## `customers.reset()` (opt-in, destructive, dev/demo only)

Deletes every row of: CRM Lead, CRM Deal, FCRM Note, CRM Task, CRM Call Log, CRM Notification, ToDo (reference to a
Lead/Deal/Task), Comment/Version/Communication referencing a Lead or Deal, Bot Conversation, Quiz Attempt, AI
Decision Log, Bot Learning Signal, Facebook Post, Facebook Comment Reply; Contacts not linked to a User; Course
Schedule with `is_demo_data` (the loader recreates the current 8 weeks). Keeps: users, consultants, catalog,
promotions, bot slots/skills/settings, staff replies, course FAQs, channel connections, site config.

Chatwoot wipe (in the shell script, `docker exec chatwoot-rails-1 bundle exec rails runner`): destroy all
conversations (and their messages) and all contacts of the account. Keep agents, teams, inboxes, the agent bot,
webhooks.

## Checks

- `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests` passes (the existing dotenv import
  error of `test_comment_reply` aside).
- `scripts/seed-demo.sh --reset` on the dev stack, then the counts: 52 Leads (status/source split above), 15 Deals,
  ~40 notes, 14 tasks, 10 quiz attempts, 8 posts; no Lead named Bảo Gia / Hoàng Thành; Chatwoot 0 conversations.
- Running `scripts/seed-demo.sh` a second time creates nothing new.
- CRM answers 200 on `:8000`.
