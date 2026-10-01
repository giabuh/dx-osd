"""Task dispatch with a manager's approval (D-124, spec 2026-10-01-task-dispatch-design.md): the system finds
CRM Tasks about customers that sit with the wrong person (nobody, someone who left, someone off duty with an
urgent task, someone swamped) and PROPOSES who should take them; a manager approves, changes or rejects each
proposal in /crm/admin/tasks. Nothing is assigned without that decision.

The person is picked by the same rule as the Chatwoot handoff (engine/routing.pick_consultant). Pure helpers
(in_scope, open_load, problem, build_proposals, approval_comment, rejection_comment, check_assignee) are tested
offline; the whitelisted functions below read and write CRM Tasks."""

from datetime import timedelta

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine.routing import pick_consultant

whitelist = frappe.whitelist if frappe else (lambda **kw: (lambda fn: fn))

OPEN = ("Backlog", "Todo", "In Progress")
CUSTOMER_DOCTYPES = ("CRM Lead", "CRM Deal")
PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}
CONFIG = {"max_open": 8, "overload_gap": 3, "urgent_hours": 24, "reject_days": 3, "limit": 50}
PENDING, REJECTED = "Pending", "Rejected"
FIELDS = ["name", "title", "status", "priority", "assigned_to", "due_date", "reference_doctype",
          "reference_docname", "proposed_to", "proposal_reason", "proposal_status", "proposal_at"]


def in_scope(task):
    """An open task about a customer that is somebody's job (not internal, not the administrator's own)."""
    return (task.get("status") in OPEN and task.get("reference_doctype") in CUSTOMER_DOCTYPES
            and task.get("assigned_to") != "Administrator")


def open_load(tasks):
    """{user: open tasks held}, counting every open task of the person, internal ones included."""
    load = {}
    for t in tasks:
        if t.get("status") in OPEN and t.get("assigned_to"):
            load[t["assigned_to"]] = load.get(t["assigned_to"], 0) + 1
    return load


def _label(person, user):
    return (person or {}).get("full_name") or user


def _due_text(due, now):
    hours = (due - now).total_seconds() / 3600
    if hours < 0:
        return f"đã quá hạn {max(int(-hours // 24), 0)} ngày" if hours <= -24 else "đã quá hạn"
    return f"đến hạn sau {int(hours)} giờ"


def problem(task, people, load, online, now, cfg):
    """(code, reason) when the task's holder is the wrong person for it, else None. `people`: {user: consultant};
    `online`: Chatwoot agent ids on duty, or None when presence is unknown (then nobody counts as off duty)."""
    user = task.get("assigned_to")
    if not user:
        return "unassigned", "chưa có người phụ trách"
    person = people.get(user)
    if not person or not person.get("active", 1):
        return "not_consultant", f"Người phụ trách {user} không còn là tư vấn viên đang hoạt động"
    due = task.get("due_date")
    if (online is not None and due and str(person.get("chatwoot_agent_id")) not in online
            and (due - now) <= timedelta(hours=cfg["urgent_hours"])):
        return "offline", f"{_label(person, user)} đang offline mà việc {_due_text(due, now)}"
    held = load.get(user, 0)
    if held >= cfg["max_open"]:
        return "overloaded", f"{_label(person, user)} đang giữ {held} việc mở"
    return None


def _urgency(task):
    from datetime import datetime

    return (task.get("due_date") or datetime.max, PRIORITY_RANK.get(task.get("priority"), 1), str(task["name"]))


def _skipped(task, now, cfg):
    if task.get("proposal_status") == PENDING:
        return True
    at = task.get("proposal_at")
    return bool(task.get("proposal_status") == REJECTED and at and now - at < timedelta(days=cfg["reject_days"]))


def build_proposals(tasks, ctx, people, online, now, cfg=None, limit=None):
    """[{task, title, from, from_name, to, to_name, reason, code, due, priority}], most urgent first. `ctx`: {task:
    {branch, group, hot}} or a function of a task; `people`: consultants (dicts with name = user)."""
    cfg = {**CONFIG, **(cfg or {})}
    limit = cfg["limit"] if limit is None else limit
    by_user = {p["name"]: p for p in people}
    load = open_load(tasks)
    out = []
    for t in sorted((t for t in tasks if in_scope(t) and not _skipped(t, now, cfg)), key=_urgency):
        if len(out) >= limit:
            break
        found = problem(t, by_user, load, online, now, cfg)
        if not found:
            continue
        code, why_problem = found
        where = ctx(t) if callable(ctx) else ctx.get(t["name"], {})
        candidates = [p for p in people if p["name"] != t.get("assigned_to")]
        ask = dict(branch=where.get("branch") or "", load=load, group=where.get("group") or "",
                   hot=bool(where.get("hot")), online=online)
        # nobody swamped gets more work while someone with room can take it; only then everyone is considered
        room = [p for p in candidates if load.get(p["name"], 0) < cfg["max_open"]]
        chosen, why = pick_consultant(consultants=room, **ask) if room else (None, "")
        if not chosen:
            chosen, why = pick_consultant(consultants=candidates, **ask)
        if not chosen:
            continue
        held = t.get("assigned_to")
        if code == "overloaded" and load.get(chosen["name"], 0) > load.get(held, 0) - cfg["overload_gap"]:
            continue  # nobody is clearly lighter: moving the task would only shuffle the load
        name = chosen.get("full_name") or chosen["name"]
        out.append({"task": t["name"], "title": t.get("title") or "", "from": held or None,
                    "from_name": _label(by_user.get(held), held) if held else "", "to": chosen["name"],
                    "to_name": name, "code": code, "due": t.get("due_date"), "priority": t.get("priority"),
                    "reason": f"{why_problem[:1].upper()}{why_problem[1:]} → giao {name}: {why} "
                              f"(đang giữ {load.get(chosen['name'], 0)} việc)"})
        load[chosen["name"]] = load.get(chosen["name"], 0) + 1  # one person does not receive every task
        if held in load and code != "unassigned":
            load[held] -= 1
    return out


def approval_comment(old, new, reason, by):
    return f"Giao việc: {old or '(chưa có)'} → {new}. Lý do: {reason}. Duyệt bởi {by}."


def rejection_comment(proposed, by):
    return f"Từ chối đề xuất giao cho {proposed}. Duyệt bởi {by}."


def check_assignee(user, people):
    """"" when `user` is an active consultant, else the sentence to show the manager."""
    person = people.get(user or "")
    return "" if person and person.get("active", 1) else f"{user or '(trống)'} không phải tư vấn viên đang hoạt động."


# ── Bench side ─────────────────────────────────────────────────────────────────────────────────────


def _require_manager():
    from mmm_custom.desk import can_open_bot

    if not can_open_bot():
        frappe.throw("Chỉ quản lý được giao việc.", frappe.PermissionError)


def _people():
    from mmm_custom.engine.repo import FrappeRepo

    return {c["name"]: c for c in FrappeRepo().consultants()}


def _online():
    try:
        from mmm_custom.engine.repo import FrappeRepo

        return FrappeRepo().online_agents()
    except Exception:
        return None


def _context(task):
    """Branch, course group and hotness of the customer a task is about."""
    doctype, name = task.get("reference_doctype"), task.get("reference_docname")
    if not (doctype and name and frappe.db.exists(doctype, name)):
        return {}
    meta = frappe.get_meta(doctype)
    fields = [f for f in ("territory", "ai_hotness", "enrol_course") if meta.has_field(f)]
    row = frappe.db.get_value(doctype, name, fields, as_dict=True) or {}
    code = row.get("enrol_course") or ""
    if not code and doctype == "CRM Lead":
        code = frappe.db.get_value("CRM Products", {"parenttype": doctype, "parent": name}, "product_code") or ""
    group = ""
    if code:
        group = (frappe.db.get_value("CRM Product", {"product_code": code}, "course_group")
                 or frappe.db.get_value("CRM Product", code, "course_group") or "")
    return {"branch": row.get("territory") or "", "group": group, "hot": row.get("ai_hotness") == "hot"}


def _reset(name, **values):
    frappe.db.set_value("CRM Task", name, {"proposed_to": None, "proposal_reason": None, "proposal_status": None,
                                           "proposal_at": None, **values}, update_modified=False)


def _run(dry_run):
    now = frappe.utils.now_datetime()
    if not dry_run:  # a fresh look: a proposal whose reason no longer holds goes away
        for name in frappe.get_all("CRM Task", filters={"proposal_status": PENDING}, pluck="name"):
            _reset(name)
    tasks = frappe.get_all("CRM Task", filters={"status": ["in", OPEN]}, fields=FIELDS)
    people = list(_people().values())
    found = build_proposals(tasks, _context, people, _online(), now)
    if not dry_run:
        for p in found:
            _reset(p["task"], proposed_to=p["to"], proposal_reason=p["reason"], proposal_status=PENDING,
                   proposal_at=now)
    return found


@whitelist()
def propose(dry_run=0):
    """Manager: analyse the open tasks and write proposals (dry_run: only list them)."""
    _require_manager()
    found = _run(bool(int(dry_run or 0)))
    return {"status": "ok", "count": len(found), "proposals": found}


def run_scheduled():
    """08:15 every day, after the follow-up rules: proposals only, never an assignment."""
    return {"count": len(_run(False))}


@whitelist()
def overview():
    """Manager: pending proposals and what each consultant holds."""
    _require_manager()
    people = _people()
    rows = frappe.get_all("CRM Task", filters={"proposal_status": PENDING}, fields=FIELDS, order_by="due_date asc")
    load = open_load(frappe.get_all("CRM Task", filters={"status": ["in", OPEN]}, fields=["status", "assigned_to"]))
    proposals = []
    for r in rows:
        lead = ""
        if r.reference_doctype == "CRM Lead" and r.reference_docname:
            lead = frappe.db.get_value("CRM Lead", r.reference_docname, "lead_name") or ""
        proposals.append({"task": r.name, "title": r.title, "priority": r.priority, "due": r.due_date,
                          "reference_doctype": r.reference_doctype, "reference_docname": r.reference_docname,
                          "customer": lead, "from": r.assigned_to or None,
                          "from_name": _label(people.get(r.assigned_to), r.assigned_to or ""), "to": r.proposed_to,
                          "to_name": _label(people.get(r.proposed_to), r.proposed_to), "reason": r.proposal_reason})
    team = [{"user": u, "name": _label(p, u), "branch": p.get("branch") or "", "level": p.get("level") or "",
             "open": load.get(u, 0)} for u, p in people.items() if p.get("active", 1)]
    team.sort(key=lambda p: (p["branch"] == "", p["branch"], p["name"]))
    return {"proposals": proposals, "team": team, "max_open": CONFIG["max_open"]}


def _approve_one(name, assignee, by, people):
    doc = frappe.get_doc("CRM Task", name)
    if doc.get("proposal_status") != PENDING:
        frappe.throw(f"Việc #{name} không còn đề xuất nào đang chờ.")
    target = assignee or doc.get("proposed_to")
    wrong = check_assignee(target, people)
    if wrong:
        frappe.throw(wrong)
    old, reason = doc.assigned_to, doc.get("proposal_reason") or ""
    doc.assigned_to = target
    doc.proposed_to = doc.proposal_reason = doc.proposal_status = doc.proposal_at = None
    doc.flags.ignore_permissions = True
    doc.save()
    doc.add_comment("Comment", approval_comment(old, target, reason, by))
    return target


@whitelist()
def approve(task, assignee=None):
    """Manager: give the task to the proposed person, or to `assignee` when the manager picks someone else."""
    _require_manager()
    to = _approve_one(task, assignee, frappe.session.user, _people())
    return {"status": "ok", "task": task, "assigned_to": to}


@whitelist()
def approve_all():
    """Manager: approve every pending proposal as proposed."""
    _require_manager()
    people, done = _people(), 0
    for name in frappe.get_all("CRM Task", filters={"proposal_status": PENDING}, pluck="name"):
        _approve_one(name, None, frappe.session.user, people)
        done += 1
    return {"status": "ok", "count": done}


@whitelist()
def reject(task):
    """Manager: keep the task where it is; the same task is not proposed again for a few days."""
    _require_manager()
    doc = frappe.get_doc("CRM Task", task)
    if doc.get("proposal_status") != PENDING:
        frappe.throw(f"Việc #{task} không còn đề xuất nào đang chờ.")
    proposed = doc.get("proposed_to") or ""
    _reset(task, proposal_status=REJECTED, proposal_at=frappe.utils.now_datetime())
    doc.add_comment("Comment", rejection_comment(proposed, frappe.session.user))
    return {"status": "ok", "task": task}
