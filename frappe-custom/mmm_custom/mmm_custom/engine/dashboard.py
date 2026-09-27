"""Daily bot administration summary from CRM and bot records."""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.desk import can_open_bot
from mmm_custom.engine.qualify import QUALIFIED, UNQUALIFIED

BOT_SOURCE = "Messenger Bot"


def summarize(leads, handoffs, coverages, today):
    """Build display metrics from plain rows; dates are in the site's local timezone."""
    day = str(today)[:10]
    bot_leads = [row for row in leads if row.get("source") == BOT_SOURCE]
    is_today = lambda value: str(value or "")[:10] == day
    qualified = [row for row in bot_leads if row.get("status") == QUALIFIED]
    latest = sorted(qualified, key=lambda row: str(row.get("creation") or ""), reverse=True)[:10]
    return {
        "new_today": sum(is_today(row.get("creation")) for row in bot_leads),
        "qualified_today": sum(is_today(row.get("status_since")) for row in qualified),
        "unqualified_today": sum(is_today(row.get("status_since")) for row in bot_leads if row.get("status") == UNQUALIFIED),
        "handed_off_today": len({row.get("bot_conversation") for row in handoffs
                                 if row.get("bot_conversation") and not row.get("is_sandbox")}),  # Playground chats are not customers
        "coverage": round(sum(coverages) / len(coverages)) if coverages else 0,
        "latest_leads": latest,
    }


@frappe.whitelist() if frappe else (lambda fn: fn)
def summary():
    if not can_open_bot():
        frappe.throw("Bạn không có quyền xem trang bot.", frappe.PermissionError)

    from mmm_custom.engine.knowledge import overview

    today = frappe.utils.today()
    leads = frappe.get_all("CRM Lead", filters={"source": BOT_SOURCE},
                           fields=["name", "lead_name", "first_name", "mobile_no", "course_interest", "territory",
                                   "lead_owner", "source", "status", "creation"], limit_page_length=0)
    rows = [dict(row) for row in leads]
    names = [row["name"] for row in rows]
    if names:
        changes = frappe.get_all("CRM Status Change Log",
                                 filters={"parenttype": "CRM Lead", "parent": ["in", names], "to": ["in", ["", None]]},
                                 fields=["parent", "from", "from_date"], order_by="from_date desc", limit_page_length=0)
        latest_change = {}
        for change in changes:
            latest_change.setdefault(change.parent, change)
        for row in rows:
            change = latest_change.get(row["name"])
            row["status_since"] = change.from_date if change and change["from"] == row["status"] else row["creation"]
    handoffs = frappe.get_all("AI Decision Log",
                              filters={"decision_type": "handoff", "is_sandbox": 0, "creation": [">=", f"{today} 00:00:00"]},
                              fields=["bot_conversation", "is_sandbox"], limit_page_length=0)
    coverage = [row["coverage"] for row in overview()]
    return summarize(rows, handoffs, coverage, today)
