"""Daily nurturing (D-116, roadmap C6.4): every open Lead gets the next step its status calls for, as a CRM
Task for the Lead owner, at 08:00 so consultants find it when their day starts.

| Status        | When                                         | Task                                              |
| Qualified     | no Task, quiet `qualified_call_hours` (24 h)  | Gọi tư vấn khách đủ thông tin (High)              |
| New/Contacted | no Task, quiet `stale_days` (3)               | [I] Jev picks call / message / review close;      |
|               |                                              | without an AI key: Nhắn tin chăm sóc lại (Medium) |
| Trial Booked  | the trial date has passed                     | Sau học thử: chốt đăng ký / hẹn lại (High)        |
| Nurture       | no Task, every `nurture_every_days` (14)      | Chăm sóc định kỳ with the next class, up to       |
|               |                                              | `nurture_max_touches` (4); then Xem xét đóng      |
| Deal: Pending | no Task, quiet `payment_stale_days` (3) or    | Nhắc đóng phí (High), on the registration (D-117) |
|  Payment      | past its `payment_due_date`                   |                                                   |

The rules are pure (`rule_task`); a Lead with an open Task is left alone, except the after-trial check (the trial
Task itself is usually still open). It never changes a Lead: moving it on stays a person's decision. Settings:
`lead_nurture` in the site config; `ai_followup_stale_days` / `ai_followup_statuses` still work.
"""

import logging
from datetime import datetime, timedelta

try:
    import frappe
except ImportError:
    from unittest.mock import MagicMock

    frappe = MagicMock()

from mmm_custom.intelligence import DEFAULT_THRESHOLD, JEV_URL, ask_jev
from mmm_custom.lifecycle import CONTACTED, NEW, NURTURE, PENDING_PAYMENT, QUALIFIED, TRIAL_BOOKED

logger = logging.getLogger(__name__)

NEXT_ACTIONS = {
    "call": "Call the customer: they showed buying interest or left a phone number",
    "message": "Send a follow-up message: they were interested but went quiet in chat",
    "review_close": "The Lead looks dead, spam, or not a real customer; a salesperson should review closing it",
    "wait": "Too early or nothing useful to do yet",
}
TASKS = {
    "call": {"title": "Gọi lại khách", "priority": "High"},
    "message": {"title": "Nhắn tin chăm sóc lại khách", "priority": "Medium"},
    "review_close": {"title": "Xem xét đóng Lead", "priority": "Low"},
    "qualified_call": {"title": "Gọi tư vấn khách đủ thông tin", "priority": "High"},
    "after_trial": {"title": "Sau học thử: chốt đăng ký / hẹn lại", "priority": "High"},
    "nurture": {"title": "Chăm sóc định kỳ", "priority": "Medium"},
    "nurture_done": {"title": "Xem xét đóng khách nuôi dưỡng", "priority": "Low"},
    "payment": {"title": "Nhắc đóng phí", "priority": "High"},
}
DEFAULTS = {"qualified_call_hours": 24, "stale_days": 3, "nurture_every_days": 14, "nurture_max_touches": 4,
            "payment_stale_days": 3, "max_leads": 200}
OPEN_TASK_STATUSES = ["Backlog", "Todo", "In Progress"]
RULE_STATUSES = [NEW, QUALIFIED, CONTACTED, TRIAL_BOOKED, NURTURE]
LEAD_FIELDS = ["name", "lead_name", "status", "source", "lead_owner", "modified", "mobile_no", "email",
               "course_interest", "territory", "ai_intent", "ai_hotness", "trial_date", "preferred_shift"]


def settings(conf):
    cfg = {**DEFAULTS, **(conf.get("lead_nurture") or {})}
    if conf.get("ai_followup_stale_days") is not None:  # 0 is valid: every open Lead
        cfg["stale_days"] = conf["ai_followup_stale_days"]
    cfg["stale_statuses"] = conf.get("ai_followup_statuses") or [NEW, CONTACTED]
    return cfg


def _date(value):
    return value.date() if isinstance(value, datetime) else value


def rule_task(lead, now, cfg, tasks, next_class=""):
    """The Task a Lead's status calls for today, or None. `tasks`: the Lead's CRM Tasks (title, status, creation).
    New/Contacted return {"kind": "stale"}: Jev (or the default message) decides what it becomes."""
    status, quiet = lead.get("status"), now - lead["modified"]
    open_task = any(t["status"] in OPEN_TASK_STATUSES for t in tasks)
    titled = lambda kind: [t for t in tasks if (t.get("title") or "").startswith(TASKS[kind]["title"])]
    if status == TRIAL_BOOKED:
        trial = _date(lead.get("trial_date"))
        if trial and trial < now.date() and not [t for t in titled("after_trial") if _date(t["creation"]) >= trial]:
            return {"kind": "after_trial",
                    "why": f"Buổi học thử / test ngày {trial:%d/%m} đã qua: hỏi cảm nhận, chốt đăng ký hoặc hẹn buổi khác."}
        return None
    if open_task:
        return None
    if status == QUALIFIED and quiet >= timedelta(hours=int(cfg["qualified_call_hours"])):
        return {"kind": "qualified_call", "why": "Khách đã có khóa quan tâm và số điện thoại nhưng chưa ai gọi tư vấn."}
    if status in cfg["stale_statuses"] and quiet >= timedelta(days=int(cfg["stale_days"])):
        return {"kind": "stale"}
    if status == NURTURE:
        touches = titled("nurture")
        last = max([t["creation"] for t in touches], default=lead["modified"])
        if now - last < timedelta(days=int(cfg["nurture_every_days"])):
            return None
        if len(touches) >= int(cfg["nurture_max_touches"]):
            if titled("nurture_done"):
                return None
            return {"kind": "nurture_done",
                    "why": f"Đã chăm sóc {len(touches)} lần mà khách chưa quay lại: xem xét đóng (Không phù hợp + lý do)."}
        why = f"Lần {len(touches) + 1}/{cfg['nurture_max_touches']}: gửi thông tin mới, hỏi thăm nhu cầu."
        return {"kind": "nurture", "why": f"{why} {next_class}".strip(), "n": len(touches) + 1}
    return None


def payment_task(deal, now, cfg, tasks):
    """A registration waiting for the fee (D-117): remind when it has been quiet or its payment date passed."""
    if deal.get("status") != PENDING_PAYMENT or any(t["status"] in OPEN_TASK_STATUSES for t in tasks):
        return None
    due = _date(deal.get("payment_due_date"))
    if due and due < now.date():
        return {"kind": "payment", "why": f"Hạn đóng phí {due:%d/%m} đã qua, khách chưa đóng / đặt cọc."}
    if now - deal["modified"] >= timedelta(days=int(cfg["payment_stale_days"])):
        return {"kind": "payment", "why": "Khách đã đăng ký nhưng chưa đóng phí / đặt cọc: gọi nhắc, giữ chỗ lớp."}
    return None


def _tasks(lead, doctype="CRM Lead"):
    return frappe.get_all("CRM Task", filters={"reference_doctype": doctype, "reference_docname": lead},
                          fields=["title", "status", "creation"], order_by="creation asc")


def _next_class(lead, today):
    """"Lớp gần nhất: Thứ 7 04/10 · Tối · CN Q7" for the Lead's first course, or ""."""
    from mmm_custom.engine.repo import FrappeRepo

    course = frappe.db.get_value("CRM Products", {"parenttype": "CRM Lead", "parent": lead["name"]}, "product_code",
                                 order_by="idx asc")
    if not course:
        return ""
    rows = FrappeRepo().open_schedules(course, lead.get("territory") or "", "", today, 1)
    if not rows:
        return ""
    r = rows[0]
    return f"Lớp {course} gần nhất: {r['weekday']} {r['date']:%d/%m} · {r['shift'] or ''} · {r['branch'] or ''}."


def _create_task(lead, kind, why, now, title_suffix="", doctype="CRM Lead"):
    task = TASKS[kind]
    frappe.get_doc({
        "doctype": "CRM Task",
        "title": f"{task['title']}{title_suffix}: {lead.get('lead_name') or lead['name']}"[:140],
        "description": why,
        "priority": task["priority"],
        "status": "Todo",
        "assigned_to": lead.get("lead_owner") or lead.get("deal_owner"),
        "reference_doctype": doctype,
        "reference_docname": lead["name"],
        "due_date": now + timedelta(days=1),
    }).insert(ignore_permissions=True)


def _ask_jev(conf, lead, now):
    notes = frappe.get_all("FCRM Note", filters={"reference_doctype": "CRM Lead", "reference_docname": lead["name"]},
                           fields=["title", "content"], order_by="creation desc", limit=5)
    days = (now - lead["modified"]).days  # date math stays in code; Jev is weak at arithmetic
    state = {"lead": {**{k: str(v) for k, v in lead.items() if v is not None}, "days_since_update": days},
             "recent_notes": notes}
    return ask_jev(conf["typesafe_api_key"], state, {
        "next_action": {"type": "choice", "instructions": "What should the salesperson do next with this quiet sales lead?",
                        "criteria": NEXT_ACTIONS},
    }, model=conf.get("typesafe_model") or "jev-latest", url=conf.get("typesafe_api_url") or JEV_URL)["next_action"]


def plan_followups(now: datetime | None = None) -> dict:
    conf = getattr(frappe, "conf", None) or {}
    now = now or frappe.utils.now_datetime()  # site timezone, like the stored datetimes
    cfg = settings(conf)
    threshold = float(conf.get("typesafe_confidence_threshold") or DEFAULT_THRESHOLD)
    jev_left = int(conf.get("ai_followup_max_leads", 20)) if conf.get("typesafe_api_key") else 0
    leads = frappe.get_all("CRM Lead", filters={"status": ["in", RULE_STATUSES], "converted": 0},
                           fields=LEAD_FIELDS, order_by="modified asc", limit=int(cfg["max_leads"]))
    results = []
    for lead in leads:
        tasks = _tasks(lead["name"])
        nurture = lead.get("status") == NURTURE
        rule = rule_task(lead, now, cfg, tasks, _next_class(lead, now.date()) if nurture and not any(
            t["status"] in OPEN_TASK_STATUSES for t in tasks) else "")
        if not rule:
            continue
        kind, why = rule["kind"], rule.get("why", "")
        if kind == "stale":
            days = (now - lead["modified"]).days
            if jev_left:
                jev_left -= 1
                answer = _ask_jev(conf, lead, now)
                choice, confidence = answer["choice"], answer.get("confidence") or 0
                if confidence < threshold or choice == "wait":
                    results.append({"lead": lead["name"], "action": "none", "choice": choice, "confidence": confidence})
                    continue
                kind, why = choice, f"AI (độ tin cậy {confidence:.2f}): Lead không có cập nhật {days} ngày. {NEXT_ACTIONS[choice]}."
            else:
                kind, why = "message", f"Khách không có cập nhật {days} ngày: nhắn hỏi thăm, gửi thông tin khóa học."
        suffix = f" (lần {rule['n']})" if kind == "nurture" else ""
        _create_task(lead, kind, why, now, suffix)
        results.append({"lead": lead["name"], "action": "task_created", "choice": kind})
    for deal in frappe.get_all("CRM Deal", filters={"status": PENDING_PAYMENT}, order_by="modified asc",
                               fields=["name", "lead_name", "deal_owner", "status", "modified", "payment_due_date"],
                               limit=int(cfg["max_leads"])):
        rule = payment_task(deal, now, cfg, _tasks(deal["name"], "CRM Deal"))
        if rule:
            _create_task(deal, rule["kind"], rule["why"], now, doctype="CRM Deal")
            results.append({"deal": deal["name"], "action": "task_created", "choice": rule["kind"]})
    frappe.db.commit()
    return {"status": "done", "checked": len(leads), "results": results}


def run_daily():
    """Scheduler entry point (hooks.py scheduler_events)."""
    result = plan_followups()
    logger.info("Follow-up: %s", result)
    return result
