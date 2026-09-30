"""The "Khóa học & Lớp" page (D-120): every consultant reads the courses' open classes with the seats left; managers
add and edit classes. Access is the Course Schedule doctype's own: Sales User read, Sales Manager / System Manager
write, so the page needs no role check of its own. Courses themselves are edited in /crm/admin (bot_admin.save_course)."""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.desk import can_open_bot
from mmm_custom.lifecycle import AWAITING_CONFIRMATION, PENDING_PAYMENT

whitelist = frappe.whitelist if frappe else (lambda **kw: (lambda fn: fn))

FIELDS = ("course", "branch", "start_date", "shift", "weekdays", "seats", "status")
REQUIRED = {"course": "Chọn khóa học.", "branch": "Chọn chi nhánh.", "start_date": "Nhập ngày khai giảng.",
            "shift": "Chọn ca học."}
MAX_ROWS = 300


def row_view(row, course_names, taken, pending):
    """A class as the page shows it. `seats` 0 means no limit. Pure."""
    seats = int(row.get("seats") or 0)
    used = taken.get(row["name"], 0)
    return {**row, "course_name": course_names.get(row["course"], row["course"]), "taken": used,
            "pending": pending.get(row["name"], 0), "seats_left": max(seats - used, 0) if seats else None}


def clean_values(values, shifts, statuses, creating):
    """The values a save may carry: known fields only, a new class complete, options and seats valid. Pure."""
    out = {k: v for k, v in values.items() if k in FIELDS and v is not None}
    if creating:
        for key, message in REQUIRED.items():
            if not out.get(key):
                raise ValueError(message)
    if out.get("shift") and out["shift"] not in shifts:
        raise ValueError("Ca học không hợp lệ.")
    if out.get("status") and out["status"] not in statuses:
        raise ValueError("Trạng thái lớp không hợp lệ.")
    if "seats" in out:
        try:
            out["seats"] = int(out["seats"] or 0)
        except (TypeError, ValueError):
            raise ValueError("Sĩ số phải là số nguyên không âm.") from None
        if out["seats"] < 0:
            raise ValueError("Sĩ số phải là số nguyên không âm.")
    return out


def _options(fieldname):
    return [o for o in (frappe.get_meta("Course Schedule").get_field(fieldname).options or "").split("\n") if o]


@whitelist()
def context():
    """Filters and permissions for the page: what the user may edit, their branch, courses, branches, options."""
    frappe.has_permission("Course Schedule", "read", throw=True)
    branch = frappe.db.get_value("Consultant", frappe.session.user, "branch") \
        if frappe.db.exists("Consultant", frappe.session.user) else ""
    courses = frappe.get_all("CRM Product", filters={"disabled": 0}, fields=["name", "product_name", "course_group"],
                             order_by="product_name asc")
    return {"can_edit": frappe.has_permission("Course Schedule", "write"), "can_edit_courses": can_open_bot(),
            "my_branch": branch or "",
            "courses": [{"code": c.name, "name": c.product_name or c.name, "group": c.course_group or ""}
                        for c in courses],
            "branches": frappe.get_all("CRM Territory", filters={"is_group": 0}, pluck="name", order_by="name asc"),
            "shifts": _options("shift"), "statuses": _options("status")}


@whitelist()
def schedules(course="", branch="", status="", include_past=0):
    """Classes, soonest first, with the seats held (deposit / enrolled) and the registrations still pending."""
    frappe.has_permission("Course Schedule", "read", throw=True)
    from mmm_custom.enrolment import seats_taken

    filters = {k: v for k, v in (("course", course), ("branch", branch), ("status", status)) if v}
    if not int(include_past or 0):
        filters["start_date"] = [">=", frappe.utils.getdate()]
    rows = frappe.get_all("Course Schedule", filters=filters, fields=["name", "title", *FIELDS],
                          order_by="start_date asc", limit=MAX_ROWS)
    names = [r.name for r in rows]
    waiting = frappe.get_all("CRM Deal", filters={"course_schedule": ["in", names],
                                                  "status": ["in", [AWAITING_CONFIRMATION, PENDING_PAYMENT]]},
                             fields=["course_schedule", "count(name) as n"], group_by="course_schedule") if names else []
    course_names = {c.name: c.product_name for c in frappe.get_all("CRM Product", fields=["name", "product_name"])}
    taken = seats_taken(names)
    pending = {r.course_schedule: r.n for r in waiting}
    return [row_view(dict(r), course_names, taken, pending) for r in rows]


@whitelist(methods=["POST"])
def save_schedule(name="", course="", branch="", start_date="", shift="", weekdays="", seats=None, status=""):
    """Create a class, or edit the one `name`. Doctype permissions decide who may (no `ignore_permissions`)."""
    values = {"course": course, "branch": branch, "start_date": start_date, "shift": shift, "weekdays": weekdays,
              "seats": seats, "status": status}
    if name:
        values = {k: v for k, v in values.items() if v not in (None, "")} | \
                 ({"seats": seats} if seats not in (None, "") else {})
    try:
        clean = clean_values(values, _options("shift"), _options("status"), creating=not name)
    except ValueError as error:
        frappe.throw(str(error))
    doc = frappe.get_doc("Course Schedule", name) if name else frappe.new_doc("Course Schedule")
    doc.update(clean)
    doc.save()
    return {"name": doc.name, "title": doc.title}
