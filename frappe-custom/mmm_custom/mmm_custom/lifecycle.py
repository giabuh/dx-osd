"""The customer journey of a training centre (D-116, D-117; spec 2026-09-30-customer-lifecycle-design.md).

Lead statuses keep upstream English keys (record names, code, the EN/VI switch); `crm/crm/locale/vi.po` gives
the Vietnamese label and `LABELS` repeats it for text mmm_custom writes itself (Chatwoot attribute, dashboards).
`can_auto_move` is the one rule for every status change a machine makes. The Frappe part at the bottom creates
the statuses and lost reasons and moves existing records to them (patch v1_1, after_install, after_migrate)."""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

NEW, QUALIFIED, CONTACTED, TRIAL_BOOKED = "New", "Qualified", "Contacted", "Trial Booked"
NURTURE, CONVERTED, UNQUALIFIED, JUNK = "Nurture", "Converted", "Unqualified", "Junk"
PENDING_PAYMENT, DEPOSIT_PAID, WON, LOST = "Pending Payment", "Deposit Paid", "Won", "Lost"

# (key, Vietnamese label, type, colour[, probability]); position is the row order
LEAD_STATUSES = (
    (NEW, "Mới", "Open", "gray"),
    (QUALIFIED, "Đủ thông tin", "Ongoing", "amber"),
    (CONTACTED, "Đang tư vấn", "Ongoing", "orange"),
    (TRIAL_BOOKED, "Hẹn học thử / test", "Ongoing", "violet"),
    (NURTURE, "Nuôi dưỡng", "On Hold", "blue"),
    (CONVERTED, "Đã đăng ký", "Won", "green"),
    (UNQUALIFIED, "Không phù hợp", "Lost", "red"),
    (JUNK, "Rác / Spam", "Lost", "purple"),
)
DEAL_STATUSES = (
    (PENDING_PAYMENT, "Chờ đóng phí", "Open", "orange", 50),
    (DEPOSIT_PAID, "Đã đặt cọc", "Ongoing", "blue", 80),
    (WON, "Đã nhập học", "Won", "green", 100),
    (LOST, "Hủy đăng ký", "Lost", "red", 0),
)
# Upstream B2B sales stages: their Deals move to Pending Payment, then the unused status is removed
OLD_DEAL_STATUSES = ("Qualification", "Demo/Making", "Proposal/Quotation", "Negotiation", "Ready to Close")

LABELS = {s[0]: s[1] for s in LEAD_STATUSES}
DEAL_LABELS = {s[0]: s[1] for s in DEAL_STATUSES}
OPEN_LEAD = (NEW, QUALIFIED, CONTACTED, TRIAL_BOOKED, NURTURE)  # still in play: not registered, not lost
LOST_LEAD = (UNQUALIFIED, JUNK)

EXISTING_STUDENT, SPAM, OTHER = "Existing Student", "Spam", "Other"
POSTPONED = "Postponed"
# (reason, Vietnamese description); upstream reasons are kept and translated in vi.po
LOST_REASONS = (
    (EXISTING_STUDENT, "Học viên cũ nhắn để được hỗ trợ, không phải khách mới"),
    (SPAM, "Tin rác, quảng cáo, không phải khách thật"),
    ("Schedule Mismatch", "Lịch học không phù hợp với khách"),
    ("Location Too Far", "Chi nhánh quá xa nơi khách ở / làm việc"),
    (POSTPONED, "Khách hoãn sang khóa sau"),
)
BOT_REASON = {UNQUALIFIED: EXISTING_STUDENT, JUNK: SPAM}  # a Lost status the bot sets always carries its reason

# target → statuses a machine may move it from (D-116); anything else is a person's decision
AUTO_FROM = {
    QUALIFIED: (NEW,),
    UNQUALIFIED: (NEW,),
    JUNK: (NEW,),
    CONTACTED: (NEW, QUALIFIED, NURTURE),
    TRIAL_BOOKED: (NEW, QUALIFIED, CONTACTED, NURTURE),
    CONVERTED: OPEN_LEAD,
}


def can_auto_move(current, target, lost_reason=""):
    """May the bot / an event move a Lead from `current` to `target`? Never backwards, never over a person:
    a Lost status is left only when the bot set it (its own reason) and the customer turned out to be real."""
    current = current or NEW
    if not target or current == target:
        return False
    if target == QUALIFIED and current in LOST_LEAD:
        return lost_reason in BOT_REASON.values()
    return current in AUTO_FROM.get(target, ())


def auto_update(current, target, lost_reason=""):
    """The Lead fields for an automatic move, or {} when the move is not allowed."""
    if not can_auto_move(current, target, lost_reason):
        return {}
    out = {"status": target}
    if target in BOT_REASON:
        out["lost_reason"] = BOT_REASON[target]
    elif current in LOST_LEAD:
        out["lost_reason"] = ""  # the bot's own reason goes with the Lost status it set
    return out


def reason_for_lost(ai_intent, status):
    """Backfill for a Lost Lead saved before reasons were required of the bot."""
    if ai_intent == "support":
        return EXISTING_STUDENT
    if ai_intent == "spam" or status == JUNK:
        return SPAM
    return OTHER


def plan_statuses(existing, wanted, create_only=False):
    """[(action, row)]: create what is missing; with `create_only` False also bring type/colour/position (and
    probability) in line. `existing`: {name: {type, color, position, probability?}}; `wanted`: rows as dicts."""
    out = []
    for row in wanted:
        have = existing.get(row["name"])
        if have is None:
            out.append(("create", row))
        elif not create_only and any(have.get(k) != v for k, v in row.items() if k != "name"):
            out.append(("update", row))
    return out


def lead_rows():
    return [{"name": k, "type": t, "color": c, "position": i} for i, (k, _l, t, c) in enumerate(LEAD_STATUSES, 1)]


def deal_rows():
    return [{"name": k, "type": t, "color": c, "position": i, "probability": p}
            for i, (k, _l, t, c, p) in enumerate(DEAL_STATUSES, 1)]


# ---------------------------------------------------------------- Frappe side

def on_lead_update(doc, method=None):
    """doc_events CRM Lead on_update: the Chatwoot contact shows the Lead's real status (`trang_thai_lead`),
    whoever changed it — the bot, a handoff, a consultant in the CRM."""
    if not doc.get("chatwoot_contact_id") or not doc.status or not doc.has_value_changed("status"):
        return
    frappe.enqueue("mmm_custom.lifecycle.push_status", queue="short", enqueue_after_commit=True,
                   job_id=f"lead_status_{doc.name}", deduplicate=True, lead=doc.name)


def push_status(lead):
    from mmm_custom.lead_chat import admin_client

    row = frappe.db.get_value("CRM Lead", lead, ["chatwoot_contact_id", "status"], as_dict=True)
    if not row or not row.chatwoot_contact_id:
        return
    try:
        admin_client().update_contact(int(row.chatwoot_contact_id), {"trang_thai_lead": LABELS.get(row.status, row.status)})
    except Exception:
        frappe.log_error(title="Lead status not written to Chatwoot", message=f"CRM Lead {lead}")


def _existing(doctype, fields):
    return {r.name: dict(r) for r in frappe.get_all(doctype, fields=["name", *fields])}


def _apply(doctype, keyfield, actions):
    for action, row in actions:
        values = {k: v for k, v in row.items() if k != "name"}
        if action == "create":
            frappe.get_doc({"doctype": doctype, keyfield: row["name"], **values}).insert(ignore_permissions=True)
        else:
            frappe.db.set_value(doctype, row["name"], values)


def ensure_statuses(create_only=True):
    """Lead/Deal statuses and lost reasons. after_migrate runs it create-only, so a manager's later colour or
    order edits stay; the migration patch runs it in full once."""
    _apply("CRM Lead Status", "lead_status",
           plan_statuses(_existing("CRM Lead Status", ["type", "color", "position"]), lead_rows(), create_only))
    _apply("CRM Deal Status", "deal_status",
           plan_statuses(_existing("CRM Deal Status", ["type", "color", "position", "probability"]), deal_rows(),
                         create_only))
    for reason, description in LOST_REASONS:
        if not frappe.db.exists("CRM Lost Reason", reason):
            frappe.get_doc({"doctype": "CRM Lost Reason", "lost_reason": reason,
                            "description": description}).insert(ignore_permissions=True)
    frappe.clear_cache(doctype="CRM Lead Status")
    frappe.clear_cache(doctype="CRM Deal Status")


def ensure_statuses_hook():
    ensure_statuses(create_only=True)
    frappe.db.commit()


def migrate():
    """Move existing records to the new statuses (idempotent; never deletes customer data). `modified` is left
    untouched: follow-up measures how long a Lead has been quiet by it."""
    ensure_statuses(create_only=False)
    lead = frappe.qb.DocType("CRM Lead")
    frappe.qb.update(lead).set(lead.status, CONVERTED).where(
        (lead.converted == 1) & (lead.status == QUALIFIED)).run()
    for row in frappe.get_all("CRM Lead", filters={"status": ["in", LOST_LEAD], "lost_reason": ["is", "not set"]},
                              fields=["name", "status", "ai_intent"]):
        reason = reason_for_lost(row.get("ai_intent"), row.status)
        values = {"lost_reason": reason}
        if reason == OTHER:
            values["lost_notes"] = "Bổ sung khi chuẩn hoá trạng thái (D-116)"
        frappe.db.set_value("CRM Lead", row.name, values, update_modified=False)
    deal = frappe.qb.DocType("CRM Deal")
    old = [s for s in OLD_DEAL_STATUSES if frappe.db.exists("CRM Deal Status", s)]
    if old:
        frappe.qb.update(deal).set(deal.status, PENDING_PAYMENT).where(deal.status.isin(old)).run()
    for status in old:
        if frappe.db.count("CRM Deal", {"status": status}):
            continue
        try:
            frappe.delete_doc("CRM Deal Status", status, ignore_permissions=True)
        except frappe.LinkExistsError:
            pass  # still referenced somewhere: harmless, it is simply not offered as a stage
    frappe.clear_cache(doctype="CRM Lead")
    frappe.clear_cache(doctype="CRM Deal")
    frappe.db.commit()
