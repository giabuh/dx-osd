"""The registration record (D-117; spec 2026-09-30-customer-lifecycle-design.md): a CRM Deal is created when a
customer agrees to register ("Ghi danh"). It carries the course, the class, the fee after the promotion and what
has been paid; `compute` and `next_status` are pure, the doc_events hooks below fill and check the Deal.

- before_insert: the course and its listed fee from the Lead's first course, the best active promotion.
- validate: the class belongs to the course (its start date is copied), discount / final fee / balance, `deal_value`
  = final fee (upstream dashboards sum it), a deposit moves Pending Payment → Deposit Paid.
- on_update: a registration cancelled as Postponed sends the Lead back to Nurture, so nurturing picks it up again.
"""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.lifecycle import DEPOSIT_PAID, LOST, NURTURE, PENDING_PAYMENT, POSTPONED


def compute(fee, discount=0, deposit=0, paid=0):
    """Money fields of a registration: the discount never exceeds the fee; `paid` is everything received so far
    and includes the deposit (a deposit alone counts as paid)."""
    fee = max(float(fee or 0), 0.0)
    discount = min(max(float(discount or 0), 0.0), fee)
    final = fee - discount
    received = max(float(paid or 0), float(deposit or 0), 0.0)
    return {"discount_amount": discount, "final_fee": final, "balance_due": max(final - received, 0.0)}


def next_status(status, deposit=0, paid=0):
    """Money received moves a registration waiting for the fee to Deposit Paid; enrolment (Won) stays a person's."""
    if status == PENDING_PAYMENT and max(float(deposit or 0), float(paid or 0)) > 0:
        return DEPOSIT_PAID
    return status


def schedule_title(course_name, branch, start_date, shift):
    """"Excel cơ bản · CN Quận 7 · 04/10/2026 · Tối": what staff pick a class by (Course Schedule names are random)."""
    day = start_date.strftime("%d/%m/%Y") if hasattr(start_date, "strftime") else str(start_date or "")
    return " · ".join(p for p in (course_name, branch, day, (shift or "").split(" ")[0]) if p)[:140]


# The Deal page of a registration (D-117): student, registration, fee, source; no B2B organization section.
SIDE_PANEL = [
    {"label": "Student", "name": "contacts_section", "opened": True, "editable": False, "contacts": []},
    {"label": "Registration", "name": "enrolment_section", "opened": True, "columns": [
        {"name": "column_enrol", "fields": ["enrol_course", "course_schedule", "class_start_date", "territory",
                                            "deal_owner"]}]},
    {"label": "Fee", "name": "fee_section", "opened": True, "columns": [
        {"name": "column_fee", "fields": ["tuition_fee", "promotion", "discount_amount", "final_fee", "deposit_amount",
                                          "deposit_date", "paid_amount", "balance_due", "payment_due_date"]}]},
    {"label": "Source", "name": "source_section", "opened": False, "columns": [
        {"name": "column_source", "fields": ["source", "lead", "course_interest", "placement_result", "voucher_code",
                                             "trial_date"]}]},
]
DATA_FIELDS = [{"name": "first_tab", "sections": [
    {"label": "Registration", "name": "enrolment_section", "opened": True, "columns": [
        {"name": "column_e1", "fields": ["enrol_course", "course_schedule", "class_start_date"]},
        {"name": "column_e2", "fields": ["territory", "deal_owner", "source"]}]},
    {"label": "Fee", "name": "fee_section", "opened": True, "columns": [
        {"name": "column_f1", "fields": ["tuition_fee", "promotion", "discount_amount", "final_fee"]},
        {"name": "column_f2", "fields": ["deposit_amount", "deposit_date", "paid_amount", "balance_due",
                                         "payment_due_date"]}]},
    {"label": "Details", "name": "details_section", "opened": False, "columns": [
        {"name": "column_d1", "fields": ["organization", "next_step"]},
        {"name": "column_d2", "fields": ["course_interest", "placement_result", "voucher_code"]}]},
]}]
REQUIRED_FIELDS = [{"name": "first_tab", "sections": [
    {"label": "Registration", "name": "enrolment_section", "columns": [
        {"name": "column_r1", "fields": ["enrol_course", "course_schedule"]},
        {"name": "column_r2", "fields": ["deposit_amount", "payment_due_date"]}]},
]}]


def promotion_discount(promo, fee):
    """Amount off `fee` for a Course Promotion row (discount_type Percent / Amount)."""
    from mmm_custom.engine.actions import discount

    return min(discount(promo, float(fee or 0)), float(fee or 0)) if promo else 0.0


# ---------------------------------------------------------------- Frappe side

def _course(code):
    return frappe.db.get_value("CRM Product", code, ["name", "standard_rate", "course_group"], as_dict=True)


def _first_lead_course(lead):
    if not lead:
        return None
    return frappe.db.get_value("CRM Products", {"parenttype": "CRM Lead", "parent": lead}, "product_code",
                               order_by="idx asc")


def _best_promotion(course, branch):
    from mmm_custom.engine import actions, voucher
    from mmm_custom.engine.repo import FrappeRepo

    ctx = {"code": course.name, "group": course.course_group, "fee": float(course.standard_rate or 0)}
    promo, _off = voucher.best_promotion(FrappeRepo().active_promotions(frappe.utils.getdate()), ctx, branch or "",
                                         actions.applicable, actions.discount)
    return promo["title"] if promo else None  # Course Promotion is named by its title


def before_insert(doc, method=None):
    if not doc.get("enrol_course"):
        doc.enrol_course = _first_lead_course(doc.get("lead"))
    course = _course(doc.enrol_course) if doc.get("enrol_course") else None
    if course and not doc.get("tuition_fee"):
        doc.tuition_fee = course.standard_rate or 0
    if course and not doc.get("promotion"):
        doc.promotion = _best_promotion(course, doc.get("territory"))


def validate(doc, method=None):
    if doc.get("course_schedule"):
        cls = frappe.db.get_value("Course Schedule", doc.course_schedule, ["course", "start_date", "branch"], as_dict=True)
        if cls:
            if doc.get("enrol_course") and cls.course != doc.enrol_course:
                frappe.throw(f"Lớp khai giảng {doc.course_schedule} không thuộc khóa {doc.enrol_course}.")
            doc.enrol_course = doc.get("enrol_course") or cls.course
            doc.class_start_date = cls.start_date
            doc.territory = doc.get("territory") or cls.branch
    promo = None
    if doc.get("promotion"):
        promo = frappe.db.get_value("Course Promotion", doc.promotion, ["discount_type", "discount_value"], as_dict=True)
    if doc.get("tuition_fee"):
        doc.update(compute(doc.tuition_fee, promotion_discount(promo, doc.tuition_fee), doc.get("deposit_amount"),
                           doc.get("paid_amount")))
        doc.deal_value = doc.final_fee
    doc.status = next_status(doc.status, doc.get("deposit_amount"), doc.get("paid_amount"))


def after_insert(doc, method=None):
    """convert_to_deal marks the Lead Converted with db_set (no Lead hooks): the Chatwoot contact learns it here."""
    if doc.get("lead"):
        frappe.enqueue("mmm_custom.lifecycle.push_status", queue="short", enqueue_after_commit=True,
                       job_id=f"lead_status_{doc.lead}", deduplicate=True, lead=doc.lead)


def on_update(doc, method=None):
    """Cancelled as Postponed: the customer is not lost, the Lead goes back to nurturing (D-117)."""
    if not doc.get("lead") or not doc.has_value_changed("status"):
        return
    if doc.status == LOST and doc.get("lost_reason") == POSTPONED:
        lead = frappe.get_doc("CRM Lead", doc.lead)
        lead.update({"status": NURTURE, "converted": 0})
        lead.flags.lead_engine = True
        lead.save(ignore_permissions=True)


def update_deal_layouts():
    """after_migrate: the registration layouts, once; a layout that already has the registration section (or a
    manager's own edit of it) is left alone."""
    import json

    for name, type_, layout in (("CRM Deal-Side Panel", "Side Panel", SIDE_PANEL),
                                ("CRM Deal-Data Fields", "Data Fields", DATA_FIELDS),
                                ("CRM Deal-Required Fields", "Required Fields", REQUIRED_FIELDS)):
        if frappe.db.exists("CRM Fields Layout", name):
            doc = frappe.get_doc("CRM Fields Layout", name)
            if "enrolment_section" in (doc.layout or ""):
                continue
        else:
            doc = frappe.new_doc("CRM Fields Layout")
            doc.update({"dt": "CRM Deal", "type": type_})
        doc.layout = json.dumps(layout, ensure_ascii=False)
        if doc.is_new():
            doc.insert(ignore_permissions=True)
        else:
            doc.save(ignore_permissions=True)
    for row in frappe.get_all("Course Schedule", filters={"title": ["is", "not set"]}, pluck="name"):
        frappe.get_doc("Course Schedule", row).save(ignore_permissions=True)  # validate sets the title
    frappe.db.commit()


def seats_taken(schedules):
    """{Course Schedule: registrations holding a seat (Deposit Paid or Won)}."""
    if not schedules or not frappe.get_meta("CRM Deal").has_field("course_schedule"):
        return {}
    rows = frappe.get_all("CRM Deal", filters={"course_schedule": ["in", list(schedules)],
                                               "status": ["in", [DEPOSIT_PAID, "Won"]]},
                          fields=["course_schedule", "count(name) as n"], group_by="course_schedule")
    return {r.course_schedule: r.n for r in rows}
