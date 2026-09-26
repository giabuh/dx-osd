"""[I] Intelligence layer: daily cold-lead follow-up agent (optional, TypeSafe Jev).

For open Leads with no change in `ai_followup_stale_days` (default 3), Jev picks the next
action and a CRM Task is created for the Lead owner. Leads that already have an open Task
are skipped, so it never piles up duplicates. It never changes a Lead itself — closing a
Lead stays a human decision. Off unless the site config has `typesafe_api_key`.
"""

import logging
from datetime import datetime, timedelta

try:
    import frappe
except ImportError:
    from unittest.mock import MagicMock

    frappe = MagicMock()

from mmm_custom.intelligence import DEFAULT_THRESHOLD, JEV_URL, ask_jev

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
}
OPEN_TASK_STATUSES = ["Backlog", "Todo", "In Progress"]
LEAD_FIELDS = ["name", "lead_name", "status", "source", "lead_owner", "modified", "mobile_no", "email",
               "course_interest", "branch", "ai_intent", "ai_hotness"]


def plan_followups(now: datetime | None = None) -> dict:
    conf = getattr(frappe, "conf", None) or {}
    api_key = conf.get("typesafe_api_key")
    if not api_key:
        return {"status": "ai_disabled"}
    # Frappe stores datetimes in the site timezone; now_datetime() is in the same zone.
    now = now or frappe.utils.now_datetime()
    stale_days = int(conf.get("ai_followup_stale_days", 3))  # 0 is valid: every open Lead
    threshold = float(conf.get("typesafe_confidence_threshold") or DEFAULT_THRESHOLD)
    open_statuses = conf.get("ai_followup_statuses") or ["New", "Contacted", "Nurture"]

    leads = frappe.get_all(
        "CRM Lead",
        filters={"status": ["in", open_statuses], "modified": ["<", now - timedelta(days=stale_days)]},
        fields=LEAD_FIELDS,
        order_by="modified asc",
        limit=int(conf.get("ai_followup_max_leads", 20)),
    )
    results = []
    for lead in leads:
        if frappe.get_all(
            "CRM Task",
            filters={"reference_doctype": "CRM Lead", "reference_docname": lead["name"], "status": ["in", OPEN_TASK_STATUSES]},
            pluck="name",
        ):
            results.append({"lead": lead["name"], "action": "skipped", "reason": "open task exists"})
            continue
        notes = frappe.get_all(
            "FCRM Note",
            filters={"reference_doctype": "CRM Lead", "reference_docname": lead["name"]},
            fields=["title", "content"],
            order_by="creation desc",
            limit=5,
        )
        # Date math stays in code; Jev is weak at arithmetic.
        days_since_update = (now - lead["modified"]).days
        state = {"lead": {**{k: str(v) for k, v in lead.items() if v is not None}, "days_since_update": days_since_update}, "recent_notes": notes}
        answer = ask_jev(api_key, state, {
            "next_action": {"type": "choice", "instructions": "What should the salesperson do next with this quiet sales lead?", "criteria": NEXT_ACTIONS},
        }, model=conf.get("typesafe_model") or "jev-latest", url=conf.get("typesafe_api_url") or JEV_URL)["next_action"]
        choice, confidence = answer["choice"], answer.get("confidence") or 0
        if confidence < threshold or choice == "wait":
            results.append({"lead": lead["name"], "action": "none", "choice": choice, "confidence": confidence})
            continue
        task = TASKS[choice]
        frappe.get_doc({
            "doctype": "CRM Task",
            "title": f"{task['title']}: {lead.get('lead_name') or lead['name']}",
            "description": f"AI (độ tin cậy {confidence:.2f}): Lead không có cập nhật {days_since_update} ngày. {NEXT_ACTIONS[choice]}.",
            "priority": task["priority"],
            "status": "Todo",
            "assigned_to": lead.get("lead_owner"),
            "reference_doctype": "CRM Lead",
            "reference_docname": lead["name"],
            "due_date": now + timedelta(days=1),
        }).insert(ignore_permissions=True)
        results.append({"lead": lead["name"], "action": "task_created", "choice": choice, "confidence": confidence})
    frappe.db.commit()
    return {"status": "done", "checked": len(leads), "results": results}


def run_daily():
    """Scheduler entry point (hooks.py scheduler_events)."""
    result = plan_followups()
    logger.info("AI follow-up: %s", result)
    return result
