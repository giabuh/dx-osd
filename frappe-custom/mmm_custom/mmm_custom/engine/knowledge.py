"""What the bot knows about each course (D-086): an overview per course — the data templates use, the
FAQ replies as the customer would read them, what Jev reads to recognise the course — and a coverage
table of every course listing the gaps that make the bot answer less. Shown on the Bot Knowledge page."""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine.actions import applicable, discount
from mmm_custom.engine.context import base_context, course_context
from mmm_custom.engine.jev_questions import course_criterion
from mmm_custom.engine.render import RenderError, render_text
from mmm_custom.engine.state import ConversationState

ROLES = ("System Manager", "Sales Manager")
CHECKS = (  # what a course needs for the bot to answer well, and the gap shown when it is missing
    ("fee", "Chưa có học phí (Standard Selling Rate)"),
    ("summary", "Chưa có mô tả tổng quan (Description)"),
    ("syllabus", "Chưa có nội dung học (Syllabus)"),
    ("faqs", "Chưa có câu hỏi thường gặp (Course FAQs)"),
    ("aliases", "Chưa có tên gọi khách hay gõ (Aliases)"),
    ("schedules", "Chưa có lịch khai giảng sắp tới (Course Schedule)"),
)


def gaps(course, schedule_count):
    have = {"fee": course.fee, "summary": course.summary, "syllabus": course.syllabus, "faqs": course.faqs,
            "aliases": course.aliases, "schedules": schedule_count}
    return [text for key, text in CHECKS if not have[key]]


def coverage(missing):
    return round(100 * (len(CHECKS) - len(missing)) / len(CHECKS))


def course_overview(course, catalog, schedules, promotions, render):
    course_slot = catalog.slot_for("course")
    slots = {course_slot.key: {"value": course.code}} if course_slot else {}
    ctx = base_context(slots, catalog, ConversationState(""))
    ctx["course"] = course_context(course, catalog)
    missing = gaps(course, len(schedules))
    faqs = []
    for i, f in enumerate(course.faqs, 1):
        try:
            reply, error = render_text(f.answer, ctx, render), ""
        except RenderError as e:
            reply, error = "", str(e)[:200]
            missing.append(f"Mẫu câu trả lời {i} bị lỗi, bot sẽ không gửi được")
        faqs.append({"question": f.question, "examples": list(f.examples), "answer": f.answer, "reply": reply,
                     "error": error})
    promos = [p for p in promotions if applicable(p, ctx["course"], None)]  # what a customer anywhere is offered
    best = max((discount(p, course.fee) for p in promos), default=0)
    return {**ctx["course"], "button": course.button, "offer": course.offer, "aliases": list(course.aliases),
            "final_fee": max(course.fee - best, 0), "promotions": [p["title"] for p in promos], "faqs": faqs,
            "schedules": schedules, "jev_reads": course_criterion(course), "gaps": missing,
            "coverage": coverage(gaps(course, len(schedules)))}


def knowledge_table(catalog, schedule_counts):
    rows = []
    for c in catalog.courses.values():
        missing = gaps(c, schedule_counts.get(c.code, 0))
        rows.append({"code": c.code, "name": c.name, "group": c.group, "fee": c.fee, "faqs": len(c.faqs),
                     "syllabus": len(c.syllabus), "schedules": schedule_counts.get(c.code, 0),
                     "coverage": coverage(missing), "gaps": missing})
    return sorted(rows, key=lambda r: (r["coverage"], r["group"], r["name"]))


def _open_counts(today):
    rows = frappe.get_all("Course Schedule", filters={"status": "Open", "start_date": [">=", today]},
                          fields=["course", "count(name) as n"], group_by="course")
    return {r.course: r.n for r in rows}


@frappe.whitelist() if frappe else (lambda f: f)
def overview():
    """Every course the bot knows, least covered first."""
    import json

    from mmm_custom.engine.repo import FrappeRepo

    frappe.only_for(ROLES)
    repo = FrappeRepo()
    return json.loads(json.dumps(knowledge_table(repo.catalog(), _open_counts(repo.today())), default=str))


@frappe.whitelist() if frappe else (lambda f: f)
def course(product):
    import json

    from mmm_custom.engine.render import frappe_renderer
    from mmm_custom.engine.repo import FrappeRepo

    frappe.only_for(ROLES)
    repo, code = FrappeRepo(), frappe.db.get_value("CRM Product", product, "product_code") or product
    catalog, today = repo.catalog(), repo.today()
    if code not in catalog.courses:
        frappe.throw("Khóa này chưa có trong kho tri thức của bot: cần chọn Course Group và không để Disabled.")
    out = course_overview(catalog.courses[code], catalog, repo.open_schedules(code, None, None, today, 5),
                          repo.active_promotions(today), frappe_renderer)
    out["schedule_count"] = _open_counts(today).get(code, 0)
    return json.loads(json.dumps(out, default=str))
