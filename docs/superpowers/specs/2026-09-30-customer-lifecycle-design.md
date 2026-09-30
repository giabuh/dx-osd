# Customer Lifecycle: from first message to enrolment — Design Spec

Decisions: D-116 (Lead journey and statuses), D-117 (Deal = registration record). Roadmap items C6.1, C6.4, C7.1.

## Purpose

The Leads page ("Khách hàng tiềm năng"), the Deals page ("Học viên đăng ký") and the Chatwoot handoff did not
describe one journey:

- Lead statuses were still upstream Frappe CRM's (New, Contacted, Nurture, Qualified, Converted, Unqualified,
  Junk). The bot used three of them; nothing set Contacted, Nurture or Converted, and `convert_to_deal` set the
  Lead back to Qualified.
- The bot could not save Unqualified: CRM requires a lost reason for a Lost status and the bot never gave one.
- A handoff changed only `lead_owner`; a trial booking only created a Task. The Chatwoot contact attribute
  `trang_thai_lead` showed the status the bot wanted, not the one the Lead has.
- Deal statuses were a B2B sales pipeline (Demo/Making, Proposal/Quotation, Negotiation…); the Deal page had
  Organization, Annual Revenue and no course, class, fee or deposit.
- Vietnamese was patchy: "Lead" translated as "Chì", "Deal", "Lãnh thổ", untranslated statuses and custom fields,
  list columns mixing both languages.
- `followup.py` selected Leads by statuses nobody set and did nothing without an AI key.

## Confirmed decisions (owner, 2026-09-30)

1. The Lead carries the whole journey: consulting, trial/level test and nurturing. A Lead becomes a Deal
   ("Học viên đăng ký") only when the customer agrees to register.
2. Status keys stay in English (record names, code, the EN/VI switch); the Vietnamese label comes from
   `crm/crm/locale/vi.po` (both status doctypes are `translated_doctype`).
3. Full scope: statuses, Vietnamese, handoff/trial moves, status-aware nurturing, the registration record.

## The journey

```
Messenger/IG ─► Chatwoot ─► Bot Jev ─────────────► CRM Lead
  [Mới] ── course + phone / hot ──► [Đủ thông tin]
    │                                    │ handoff / first consultant reply
    │                                    ▼
    │                             [Đang tư vấn] ── trial / level test booked ──► [Hẹn học thử]
    │                                    │ ▲                                        │
    │           not ready (consultant)   ▼ │ customer comes back                    │
    │                             [Nuôi dưỡng]  (a touch every 14 days, 4 times)    │
    ├─ existing student asking for support ─► [Không phù hợp] + lost reason         │
    └─ spam ─► [Rác / Spam]                                                         │
                               customer agrees to register ── "Ghi danh" ◄──────────┘
                                          ▼
               Lead [Đã đăng ký]  +  Deal (Học viên đăng ký):
               [Chờ đóng phí] ─ deposit ─► [Đã đặt cọc] ─► [Đã nhập học]  /  [Hủy đăng ký]
```

### Lead statuses (`mmm_custom/lifecycle.py` LEAD_STATUSES)

| # | Key | Label (vi.po) | Type | Colour | Set by |
|---|---|---|---|---|---|
| 1 | New | Mới | Open | gray | default on insert |
| 2 | Qualified | Đủ thông tin | Ongoing | amber | bot: course + phone, or Jev reads hot |
| 3 | Contacted | Đang tư vấn | Ongoing | orange | handoff with an owner; first consultant reply |
| 4 | Trial Booked | Hẹn học thử / test | Ongoing | violet | `book_trial` skill |
| 5 | Nurture | Nuôi dưỡng | On Hold | blue | a consultant |
| 6 | Converted | Đã đăng ký | Won | green | `convert_to_deal` |
| 7 | Unqualified | Không phù hợp | Lost | red | bot (support request) or a consultant, with a reason |
| 8 | Junk | Rác / Spam | Lost | purple | bot (spam) or a consultant |

"Tiềm năng" is not used as a status label: the whole Leads page is "Khách hàng tiềm năng".

Lost reasons added (upstream ones kept and translated): Existing Student (Học viên cũ cần hỗ trợ), Spam,
Schedule Mismatch (Lịch học không phù hợp), Location Too Far (Chi nhánh xa).

### Automatic moves

One pure function, `lifecycle.can_auto_move(current, target, lost_reason="")`, decides every automatic change.
Anything outside this table is a person's decision (moving into Nurture, marking Lost once a Lead is past New,
every Deal status).

| Trigger | Target | Allowed from |
|---|---|---|
| Bot qualifies | Qualified | New; Unqualified/Junk when the lost reason is one the bot set |
| Bot reads a support request | Unqualified (reason Existing Student) | New |
| Bot reads spam | Junk (reason Spam) | New |
| Handoff with an owner, first consultant reply | Contacted | New, Qualified, Nurture |
| Trial booked | Trial Booked | New, Qualified, Contacted, Nurture |
| `convert_to_deal` | Converted | anything not Lost |

The bot never moves a Lead backwards. The Chatwoot contact attribute `trang_thai_lead` follows the Lead's real
status on every save (`lifecycle.on_lead_update`).

### Deal = registration record (D-117)

| # | Key | Label | Type | Probability |
|---|---|---|---|---|
| 1 | Pending Payment | Chờ đóng phí | Open | 50 |
| 2 | Deposit Paid | Đã đặt cọc | Ongoing | 80 |
| 3 | Won | Đã nhập học | Won | 100 |
| 4 | Lost | Hủy đăng ký | Lost | 0 |

Deal custom fields: `enrol_course` (CRM Product), `course_schedule` (Course Schedule of that course), 
`class_start_date` (from the schedule), `tuition_fee`, `promotion` (Course Promotion), `discount_amount`,
`final_fee`, `deposit_amount`, `deposit_date`, `paid_amount`, `balance_due`, `payment_due_date`; plus
`course_interest`, `placement_result`, `voucher_code`, which `create_deal` copies from the Lead because the
field names match.

`mmm_custom/enrolment.py`:
- `before_insert`: course and fee from the Lead's first product row; the best active promotion for that course
  and branch (`voucher.best_promotion`).
- `validate`: pure `compute(fee, discount, deposit, paid)` → discount, final fee, balance; `deal_value =
  final_fee` so upstream dashboards keep summing; a deposit moves Pending Payment → Deposit Paid; the class must
  be of the enrolled course.

Deal page: side panel sections Học viên (contacts), Đăng ký học, Học phí, Nguồn; no Organization section. The
student's name heads the page; a Messages tab shows the Lead's Chatwoot conversation.

## Nurturing (`followup.py`)

Rules run every morning without an AI key; Jev only chooses call vs. message for quiet New/Contacted Leads, as
before. A Lead with an open Task is skipped, except the after-trial check.

| Status | When | Task |
|---|---|---|
| Qualified | no Task within 24 h | Gọi tư vấn khách đủ thông tin (High) |
| New / Contacted | no change for 3 days | Jev's call/message; without AI "Nhắn tin chăm sóc lại khách" |
| Trial Booked | trial date passed | Sau học thử: chốt đăng ký / hẹn lại (High) |
| Nurture | every 14 days, 4 touches | Chăm sóc định kỳ, with the next class of the course; then "Xem xét đóng" |
| Deal Pending Payment | 3 days quiet or `payment_due_date` passed | Nhắc đóng phí |

Settings: `lead_nurture` in site config (`qualified_call_hours`, `stale_days`, `nurture_every_days`,
`nurture_max_touches`, `payment_stale_days`); `ai_followup_statuses` still overrides the New/Contacted list.

## Migration

`lifecycle.migrate()` runs from the patch `mmm_custom.patches.v1_1.education_lifecycle` and from `after_install`
(patches do not run on a fresh install); `after_migrate` only creates missing records. It never deletes customer
data:

- creates/updates the statuses and lost reasons;
- converted Leads in Qualified → Converted; Unqualified/Junk without a reason get one from `ai_intent`;
- Deals in Qualification/Demo/Proposal/Negotiation/Ready to Close → Pending Payment;
- deletes an old Deal status only when no Deal uses it.

## One Lead writer

`api.chatwoot_sync` and the engine both created Leads. Both now go through `engine/repo.ensure_lead` (same lookup,
placeholder-name fix and products append) so a Lead has one shape whichever event arrives first.

## Vietnamese

`vi.po` carries every status, lost reason and custom-field label; "Lead" → "Khách hàng tiềm năng", "Deal" →
"Hồ sơ đăng ký", "Convert to Deal" → "Ghi danh", "Territory" → "Chi nhánh". Lead list columns use English labels
that go through the translation. The Lead forms drop the B2B fields (website, annual revenue, employees, industry,
job title) and the legacy `branch` select; `territory` is the one branch field.
