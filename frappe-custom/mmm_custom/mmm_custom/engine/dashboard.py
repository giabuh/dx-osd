"""Daily bot administration summary from CRM and bot records, and the manager overview for a period (D-101)."""

from datetime import date, timedelta

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.desk import can_open_bot
from mmm_custom.lifecycle import CONFIRMED_DEAL, PENDING_PAYMENT, QUALIFIED, UNQUALIFIED, reached

BOT_SOURCE = "Messenger Bot"
PERIODS = {"today": 1, "7": 7, "30": 30, "90": 90}  # the overview's period buttons → days, today included
DEFAULT_PERIOD = "30"  # a week is often empty for a small centre (the demo data looked like "0 registrations")


def summarize(leads, handoffs, coverages, today, bot_leads=frozenset()):
    """Build display metrics from plain rows; dates are in the site's local timezone. A bot Lead is one the
    bot created (source "Messenger Bot") or one a real Bot Conversation is linked to (`bot_leads`): the
    Chatwoot sync often creates the Lead first with source "Messenger"."""
    day = str(today)[:10]
    bot_leads = [row for row in leads if row.get("source") == BOT_SOURCE or row.get("name") in bot_leads]
    is_today = lambda value: str(value or "")[:10] == day
    qualified = [row for row in bot_leads if reached(row.get("status"), QUALIFIED)]  # or a later step (D-116)
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
    linked = set(frappe.get_all("Bot Conversation", filters={"is_sandbox": 0, "lead": ["is", "set"]}, pluck="lead"))
    or_filters = {"source": BOT_SOURCE, "name": ["in", list(linked)]} if linked else None
    leads = frappe.get_all("CRM Lead", filters=None if linked else {"source": BOT_SOURCE}, or_filters=or_filters,
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
    result = summarize(rows, handoffs, coverage, today, linked)
    if frappe.db.table_exists("Facebook Post"):
        result["latest_posts"] = frappe.get_all(
            "Facebook Post",
            fields=["name", "title", "course", "status", "day_of_week", "scheduled_time", "creation"],
            order_by="creation desc",
            limit_page_length=5
        )
    else:
        result["latest_posts"] = []
    return result


def period_since(period, today):
    """First day of the period as "YYYY-MM-DD"; an unknown period is the default one."""
    days = PERIODS.get(str(period), PERIODS[DEFAULT_PERIOD])
    return (date.fromisoformat(str(today)[:10]) - timedelta(days=days - 1)).isoformat()


def fees(deals):
    """Tuition of the registrations a person confirmed (not drafts, not cancelled): received so far — the deposit
    alone counts as received, as in `enrolment.compute` — and still due."""
    confirmed = [d for d in deals if d.get("status") in CONFIRMED_DEAL]
    received = lambda d: max(float(d.get("paid_amount") or 0), float(d.get("deposit_amount") or 0), 0.0)
    return {"paid": sum(received(d) for d in confirmed), "due": sum(float(d.get("balance_due") or 0) for d in confirmed),
            "registrations": len(confirmed), "pending_payment": sum(1 for d in confirmed if d.get("status") == PENDING_PAYMENT)}


@frappe.whitelist() if frappe else (lambda fn: fn)
def overview(period=DEFAULT_PERIOD):
    """/crm/admin/overview: the customer journey, tuition and the latest Leads of a period."""
    if not can_open_bot():
        frappe.throw("Bạn không có quyền xem trang bot.", frappe.PermissionError)

    from mmm_custom.engine.customers import report
    from mmm_custom.engine.knowledge import overview as knowledge

    period = str(period) if str(period) in PERIODS else DEFAULT_PERIOD
    since = period_since(period, frappe.utils.today())
    data = report(since)
    deals = frappe.get_all("CRM Deal", filters={"creation": [">=", f"{since} 00:00:00"]}, limit_page_length=0,
                           fields=["status", "deposit_amount", "paid_amount", "balance_due"])
    coverage = [row["coverage"] for row in knowledge()]
    return {"period": period, "since": since, "totals": data["totals"], "funnel": data["funnel"],
            "latest": data["latest"][:10], "fees": fees(deals),
            "coverage": round(sum(coverage) / len(coverage)) if coverage else 0}
