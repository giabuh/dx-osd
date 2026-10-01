# Customer page and registration page (2026-10-01)

Decisions D-122, D-123 (`2026-09-26-edu-lead-engine/decisions.md`). Builds on the customer lifecycle
(`2026-09-30-customer-lifecycle-design.md`) and registration drafts (`2026-09-30-registration-drafts-design.md`).

## Problem

- The Lead page opened on the activity timeline; the conversation, which is where a consultant works, was the
  ninth tab.
- The Data tab repeated the side panel; the Attachments tab, the website button and the attach button had no use.
- The side panel hid empty read-only fields, so staff could not see what was still missing, and it left out fields
  the bot fills (learner, age, shift) or knows only in its conversation state (goal, level).
- "Tổ chức / Doanh nghiệp" sat first in the panel although a customer is a person.
- Nothing on the Lead page showed the customer's registrations.

## Design

### Tabs (Lead.vue, MobileLead.vue, Deal.vue, MobileDeal.vue)

Tin nhắn · Email · Bình luận · Cuộc gọi · Nhiệm vụ · Ghi chú · (WhatsApp) · Hoạt động. Mobile keeps its Chi tiết
(side panel) tab first. Every Lead or Deal URL without a hash opens `#messages`; a Deal without a Lead has no
Messages tab and opens on its first tab. The Deal header gets the "Nhắn tin" button.

### Customer side panel

`setup.LEAD_SIDE_PANEL`, written by `update_lead_side_panel` (after_migrate, after_install, patch v1_3) once: a
stored panel that has the `needs_section` sentinel is left alone.

| Group | Content |
|---|---|
| Liên hệ | name, phone, email, gender, owner |
| Nhu cầu học | course interest, branch, learner, learner name, age, shift, goal, level, trial date |
| Hồ sơ đăng ký | one card per Deal: status, course, class, start date, paid / balance; "Ghi danh" when none |
| Bot và bài test | hotness, intent, data quality, level test, topics to review, voucher; card: the bot's conversation (status, consultant, turns) and each level test |
| Nguồn và giới thiệu (collapsed) | source, campaign, Facebook page, own referral code, code given, referred by; the customers this one referred |

`SidePanelLayout` gains `showEmpty` (empty read-only fields show "Chưa có", one scroll for the whole panel),
`highlight` (empty listed fields are tinted) and an `after-fields` slot; a section flagged `custom` is drawn by the
page. `components/Customer/LeadSidePanel.vue` wraps it for both Lead pages and shows "Còn thiếu: …" for an empty
course, branch or phone — the bot's required slots.

`customer_profile.profile(lead)` returns the cards' data; access is the Lead's read permission, as on the Messages
tab, because Sales Users cannot read Quiz Attempt.

### Registration page

`enrolment.SIDE_PANEL` adds Người học (learner, name, age) after Học viên; the Đăng ký học section gets a class card
(`customer_profile.class_card`: start date, shift, days, seats left) and Học phí a progress bar (paid / final fee).
The side panel layout is rewritten once (sentinel `learner_section`, patch `v1_3.registration_page`). The avatar is
the student's initials; organization loading is gone.

### Data

- CRM Lead: `learner_name`, `learning_goal`, `current_level` (`setup.CATALOG_FIELDS`). The Bot Slots `goal` and
  `level` write to the last two; the patch fills them for Leads the bot already asked, never over a value a person set.
- CRM Deal: `learner_type`, `learner_name`, `learner_age`, copied from the Lead on Ghi danh (same field names).
- `organization` is in `REMOVE_FROM_LEAD`: it leaves the Lead side panel, data and quick entry layouts.

## Verification

- `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests` (`test_customer_profile.py`,
  `test_enrolment.py`, `test_branches.py`).
- `yarn build` in `crm/frontend`.
- On a bench: `bench --site crm.localhost migrate`, `bench build --app crm`; open a Lead: Tin nhắn first, five
  groups, "Chưa có" on empty fields, no Tổ chức; Ghi danh it: the card appears and the Deal page shows the learner,
  the class card and the fee bar.
