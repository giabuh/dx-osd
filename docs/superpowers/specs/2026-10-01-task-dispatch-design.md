# Task dispatch with a manager's approval — Design Spec

Decision D-126 (`2026-09-26-edu-lead-engine/decisions.md`). Human in the loop: the system proposes, a manager decides.

## Purpose

CRM Tasks about customers (follow-up calls, trial reminders, payment reminders) are created by `followup.py`,
the bot (trial booking, registration drafts) and staff. Each goes to the Lead's owner (`assigned_to =
lead_owner`). Nothing looks at who is available: a task stays with a person who is off duty, left the team
(an `@eduflow.vn` demo account on a live Lead), or holds twenty other tasks. Nothing on the Tasks page tells
a manager that a task sits with the wrong person.

The Chatwoot handoff already picks a person with `engine/routing.pick_consultant` (branch, course-group
specialty, hot customer → team lead, on duty, least loaded). Tasks reuse it.

## Design

### What gets a proposal (`mmm_custom/task_dispatch.py`, pure `problem`)

Only open CRM Tasks (Backlog, Todo, In Progress) that belong to a CRM Lead or CRM Deal; internal tasks and
tasks of `Administrator` are left alone.

| Case | Condition | Reason shown |
|---|---|---|
| unassigned | no `assigned_to` | "chưa có người phụ trách" |
| not a consultant | the assignee is not an active Consultant | "<user> không còn là tư vấn viên đang hoạt động" |
| off duty and urgent | assignee offline in Chatwoot and the task is due within 24 h or overdue | "<name> đang offline mà việc đã/đến hạn …" |
| overloaded | assignee holds ≥ 8 open tasks and a candidate holds at least 3 fewer | "<name> đang giữ N việc mở" |

### Who gets it

`routing.pick_consultant` over the active Consultants except the current assignee, with the Lead's branch
(`territory`), the Lead's course group (first product, else a Deal's course) and `ai_hotness == hot`. The
load is the open tasks per person and is updated as proposals are made, so one person does not receive every
task. Most urgent tasks first (overdue, then due date, then priority). The reason sentence is built from
rules, so it is checkable: "<problem> → <name>: <why the router chose them> (đang giữ N việc)".

### Manager approval (the Tasks page, `/crm/tasks`)

The panel "Đề xuất giao việc" sits at the top of the Tasks page (`components/TaskDispatchPanel.vue`, one tag in
`pages/Tasks.vue`). It shows only to managers (Sales Manager, System Manager, Administrator); the server checks the
role again on every call. The proposals and the task list below it are the same CRM Task records, and the list
reloads after every decision, so the two never disagree.

- **Phân tích & đề xuất** runs the dispatcher (also every morning at 08:15, after the follow-up rules). It
  writes only proposals, never an assignee.
- The panel lists, per task: title, the Lead, due date, priority, from → to, reason. The manager
  **Duyệt** (assign, optionally to another consultant picked from the list, which shows each person's open
  tasks), **Từ chối** (the task is not proposed again for 3 days), or **Duyệt tất cả**.
- Approving sets `assigned_to` (CRM Task then re-assigns the Frappe ToDo) and writes a Comment on the Task
  "Giao việc: A → B, lý do …, duyệt bởi …". Rejection also leaves a Comment.
- The first version was a tab in `/crm/admin`; it moved to the Tasks page so a manager decides where the tasks are.

New CRM Task custom fields (read-only): `proposed_to` (Link User), `proposal_reason`, `proposal_status`
(Pending / Rejected), `proposal_at`. 

## Out of scope

LLM-written reasons (the rule-built sentence is enough and costs no tokens), automatic assignment without
approval, internal tasks, changing due dates.

## Verification

- `tests/test_task_dispatch.py`: each case of `problem`, candidate choice (branch, specialty, on duty, load
  gap), simulated load across several proposals, ordering, rejection cool-down, internal tasks ignored.
- Bench: proposals on the live tasks in a rolled-back transaction; approve changes `assigned_to` and the
  ToDo; reject hides the proposal.
