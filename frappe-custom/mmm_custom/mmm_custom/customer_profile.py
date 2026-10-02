"""What the customer page shows beside a Lead's own fields (D-122; spec 2026-10-01-customer-page-design.md).

The Lead page's side panel draws three cards no field layout can: the customer's registrations (CRM Deal), the bot's
conversation with its level tests, and the people this customer referred. The registration page draws its class.
Access is the CRM's: whoever may read the Lead (branch scope, mmm_custom.scope) reads its card, as on the Messages
tab (lead_chat), because Sales Users cannot read Quiz Attempt themselves."""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.lifecycle import DEAL_STATUSES, LABELS, LIVE_DEAL

whitelist = frappe.whitelist if frappe else (lambda **kw: (lambda fn: fn))

DEAL_COLOURS = {s[0]: s[3] for s in DEAL_STATUSES}
DEAL_LABELS = {s[0]: s[1] for s in DEAL_STATUSES}
BOT_STATUS = {"active": "Bot đang tư vấn", "handed_off": "Đã chuyển tư vấn viên", "closed": "Đã đóng"}
QUIZ_STATUS = {"offered": "Đã mời", "declined": "Khách để sau", "started": "Đang làm", "done": "Đã làm xong",
               "reminded": "Đã nhắc"}
DEAL_FIELDS = ("name", "status", "enrol_course", "course_schedule", "class_start_date", "final_fee", "deposit_amount",
               "paid_amount", "balance_due", "creation")
SCHEDULE_FIELDS = ("name", "title", "course", "branch", "start_date", "shift", "weekdays", "seats", "status")


def registration_view(deal, course_names, class_titles):
    """A registration (CRM Deal) as a card. Pure."""
    status = deal.get("status") or ""
    return {"name": deal["name"], "status": status, "label": DEAL_LABELS.get(status, status),
            "colour": DEAL_COLOURS.get(status, "gray"), "live": status in LIVE_DEAL,
            "course": course_names.get(deal.get("enrol_course"), deal.get("enrol_course") or ""),
            "class_title": class_titles.get(deal.get("course_schedule"), ""),
            "start_date": deal.get("class_start_date"), "final_fee": deal.get("final_fee") or 0,
            "paid": deal.get("paid_amount") or 0, "balance": deal.get("balance_due") or 0}


def bot_view(conversation, consultant_name=""):
    """The bot's conversation with the customer: where it stands and the level tests it offered. Pure."""
    if not conversation:
        return None
    status = conversation.get("status") or ""
    offers = conversation.get("quiz_offers") or {}
    if isinstance(offers, str):
        import json

        try:
            offers = json.loads(offers)
        except ValueError:
            offers = {}
    return {"status": status, "label": BOT_STATUS.get(status, status), "consultant": consultant_name,
            "turns": int(conversation.get("turns") or 0), "returning": bool(conversation.get("is_returning")),
            "quiz_offers": len(offers) if isinstance(offers, dict) else 0}


def quiz_view(attempt, quiz_names):
    """A level test the customer was offered or took. Pure."""
    status = attempt.get("status") or ""
    total = int(attempt.get("total") or 0)
    return {"quiz": quiz_names.get(attempt.get("quiz"), attempt.get("quiz") or ""), "status": status,
            "label": QUIZ_STATUS.get(status, status),
            "score": f"{int(attempt.get('score') or 0)}/{total}" if status == "done" and total else "",
            "level": attempt.get("level") or "", "voucher": attempt.get("voucher_code") or ""}


def referral_view(lead):
    """A customer this Lead referred. Pure."""
    return {"name": lead["name"], "lead_name": lead.get("lead_name") or lead["name"],
            "status": LABELS.get(lead.get("status"), lead.get("status") or "")}


def class_view(schedule, course_name, taken):
    """A class (Course Schedule) on the registration page; `seats` 0 means no limit. Pure."""
    seats = int(schedule.get("seats") or 0)
    return {**schedule, "course_name": course_name, "taken": taken,
            "seats_left": max(seats - taken, 0) if seats else None}


def _require_read(lead):
    if not frappe.has_permission("CRM Lead", "read", lead):
        frappe.throw("Bạn không có quyền xem khách này.", frappe.PermissionError)


def _names(doctype, names, field):
    names = [n for n in set(names) if n]
    if not names:
        return {}
    return {r.name: r.get(field) or r.name for r in frappe.get_all(doctype, filters={"name": ["in", names]},
                                                                    fields=["name", field])}


@whitelist()
def profile(lead):
    """The Lead page cards: registrations, the bot's conversation, level tests and referrals."""
    _require_read(lead)
    deals = frappe.get_all("CRM Deal", filters={"lead": lead}, fields=list(DEAL_FIELDS), order_by="creation desc")
    course_names = _names("CRM Product", [d.enrol_course for d in deals], "product_name")
    class_titles = _names("Course Schedule", [d.course_schedule for d in deals], "title")
    conversation = frappe.get_all("Bot Conversation", filters={"lead": lead, "is_sandbox": 0},
                                  fields=["status", "consultant", "turns", "is_returning", "quiz_offers"],
                                  order_by="modified desc", limit=1)
    consultant = ""
    if conversation and conversation[0].consultant:
        consultant = frappe.db.get_value("User", conversation[0].consultant, "full_name") or conversation[0].consultant
    attempts = frappe.get_all("Quiz Attempt", filters={"lead": lead, "is_sandbox": 0},
                              fields=["quiz", "status", "score", "total", "level", "voucher_code"],
                              order_by="creation desc", limit=10)
    quiz_names = _names("Bot Skill", [a.quiz for a in attempts], "title")
    referred = frappe.get_all("CRM Lead", filters={"referred_by": lead}, fields=["name", "lead_name", "status"],
                              order_by="creation desc", limit=20) \
        if frappe.get_meta("CRM Lead").has_field("referred_by") else []
    return {"registrations": [registration_view(d, course_names, class_titles) for d in deals],
            "bot": bot_view(conversation[0] if conversation else None, consultant),
            "quizzes": [quiz_view(a, quiz_names) for a in attempts],
            "referrals": [referral_view(r) for r in referred]}


@whitelist()
def class_card(schedule):
    """The registration page's class card: dates, shift, days and the seats left."""
    frappe.has_permission("Course Schedule", "read", throw=True)
    from mmm_custom.enrolment import seats_taken

    row = frappe.db.get_value("Course Schedule", schedule, list(SCHEDULE_FIELDS), as_dict=True)
    if not row:
        return None
    course_name = frappe.db.get_value("CRM Product", row.course, "product_name") or row.course
    return class_view(dict(row), course_name, seats_taken([schedule]).get(schedule, 0))
