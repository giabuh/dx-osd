"""Branches, staff and courses for the manager screens (/crm/admin, crm/frontend pages/Admin.vue). CRM is where both live; saving a Consultant
triggers the Chatwoot staff sync (mmm_custom.staff_sync)."""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

import html
import re

from mmm_custom.desk import can_open_bot

whitelist = frappe.whitelist if frappe else (lambda **kw: (lambda fn: fn))

LEVELS = ("Consultant", "Team Lead")
STAFF_ROLE = "Sales User"
BRANCH_FIELDS = ("button_label", "branch_code", "address", "hotline", "map_url", "aliases")
AUDIENCES = ("Trẻ em", "Học sinh – Sinh viên", "Người đi làm", "Doanh nghiệp")  # CRM Product.audience options
OFFERS = ("all", "full")


def _require_access():
    if not can_open_bot():
        frappe.throw("Bạn không có quyền quản trị bot.", frappe.PermissionError)


@whitelist()
def app_links():
    """Links the admin header opens in a new tab."""
    _require_access()
    return {"chatwoot_url": (frappe.conf.get("chatwoot_base_url") or "http://127.0.0.1:3000").rstrip("/")}


def split_tree(rows):
    """CRM Territory rows → (root, areas, branches). The root has no parent, areas are its group children,
    branches are the leaves under an area."""
    root = next((r["name"] for r in rows if r["is_group"] and not r.get("parent_crm_territory")), "")
    areas = sorted(r["name"] for r in rows if r["is_group"] and r.get("parent_crm_territory"))
    branches = [r for r in rows if not r["is_group"] and r.get("parent_crm_territory") in areas]
    return root, areas, sorted(branches, key=lambda r: (r["parent_crm_territory"], r["name"]))


def _tree():
    return split_tree(frappe.get_all("CRM Territory", fields=["name", "parent_crm_territory", "is_group",
                                                              *BRANCH_FIELDS]))


@whitelist()
def branches():
    _require_access()
    _, areas, rows = _tree()
    counts = {r.branch: r.n for r in frappe.get_all("Consultant", filters={"active": 1}, fields=[
        "branch", "count(name) as n"], group_by="branch")}
    return {"areas": areas,
            "branches": [{**r, "area": r["parent_crm_territory"], "staff": counts.get(r["name"], 0)} for r in rows]}


@whitelist(methods=["POST"])
def save_branch(name="", territory_name="", area="", new_area="", **fields):
    """Create a branch (under an existing or a new area) or edit one; the name is fixed once created."""
    _require_access()
    root, areas, _ = _tree()
    new_area = (new_area or "").strip()
    if new_area and new_area not in areas:
        frappe.get_doc({"doctype": "CRM Territory", "territory_name": new_area, "is_group": 1,
                        "parent_crm_territory": root}).insert()
    if not new_area and area not in areas:
        frappe.throw("Chọn khu vực cho chi nhánh.")
    area = new_area or area
    values = {k: (fields.get(k) or "").strip() for k in BRANCH_FIELDS}
    if name:
        doc = frappe.get_doc("CRM Territory", name)
        doc.update({**values, "parent_crm_territory": area})
        doc.save()
    else:
        territory_name = (territory_name or "").strip()
        if not territory_name:
            frappe.throw("Nhập tên chi nhánh.")
        doc = frappe.get_doc({"doctype": "CRM Territory", "territory_name": territory_name, "is_group": 0,
                              "parent_crm_territory": area, **values}).insert()
    return doc.name


def _text(value):
    return str(value if value is not None else "").strip()


def _lines(value):
    items = value if isinstance(value, list) else _text(value).splitlines()
    return "\n".join(line for line in (_text(i) for i in items) if line)


def _int(value, label):
    digits = re.sub(r"[^\d]", "", _text(value))  # "2.500.000đ" → 2500000
    if _text(value) and not digits:
        raise ValueError(f"{label} phải là số.")
    return int(digits or 0)


def _paragraphs(text):
    """The overview as the CRM stores it (HTML); plain text becomes escaped paragraphs."""
    if text.startswith("<"):
        return text
    return "".join(f"<p>{html.escape(p.strip(), quote=False)}</p>" for p in re.split(r"\n\s*\n", text) if p.strip())


def course_values(data):
    """A course from the admin course form or an imported file → CRM Product values; ValueError names what is wrong."""
    values = {k: _text(data.get(k)) for k in ("product_name", "product_code", "course_group", "button_label",
                                               "audience", "duration_text", "certificate", "offer")}
    values["product_code"] = values["product_code"].upper()
    for key, label in (("product_name", "tên khóa học"), ("product_code", "mã khóa học"),
                       ("course_group", "nhóm khóa học")):
        if not values[key]:
            raise ValueError(f"Nhập {label}.")
    if values["audience"] and values["audience"] not in AUDIENCES:
        raise ValueError(f"Đối tượng phải là một trong: {', '.join(AUDIENCES)}.")
    values["offer"] = values["offer"] or "all"
    if values["offer"] not in OFFERS:
        raise ValueError("Nơi mở lớp phải là all hoặc full.")
    values["button_label"] = (values["button_label"] or values["product_name"])[:20].strip()
    values["standard_rate"] = _int(data.get("standard_rate"), "Học phí")
    values["min_age"], values["max_age"] = _int(data.get("min_age"), "Tuổi"), _int(data.get("max_age"), "Tuổi")
    if values["min_age"] and values["max_age"] and values["min_age"] > values["max_age"]:
        raise ValueError("Tuổi tối thiểu lớn hơn tuổi tối đa.")
    aliases = data.get("aliases")
    values["aliases"] = ", ".join(aliases) if isinstance(aliases, list) else _text(aliases)
    values["description"] = _paragraphs(_text(data.get("description")))
    values["syllabus"] = _lines(data.get("syllabus"))
    faqs = []
    for i, f in enumerate(data.get("faqs") or [], 1):
        question, answer = _text(f.get("question")), _text(f.get("answer"))
        if not question and not answer:
            continue
        if not question or not answer:
            raise ValueError(f"Câu hỏi thường gặp {i} cần cả câu hỏi và câu trả lời.")
        faqs.append({"question": question, "examples": _lines(f.get("examples")), "answer": answer})
    values["faqs"] = faqs
    return values


@whitelist()
def course_groups():
    _require_access()
    return frappe.get_all("Course Group", pluck="name", order_by="sort_order asc")


@whitelist(methods=["POST"])
def save_course(course=None):
    """Create a course the bot can answer about right away (knowledge.overview lists it)."""
    _require_access()
    data = frappe.parse_json(course) if isinstance(course, str) else (course or {})
    try:
        values = course_values(data)
    except ValueError as e:
        frappe.throw(str(e))
    if not frappe.db.exists("Course Group", values["course_group"]):
        frappe.throw(f"Không có nhóm khóa học “{values['course_group']}”.")
    if frappe.db.exists("CRM Product", values["product_code"]):
        frappe.throw(f"Mã khóa học {values['product_code']} đã có.")
    nexts = [n for n in (data.get("next_courses") or []) if frappe.db.exists("CRM Product", n)]
    doc = frappe.get_doc({"doctype": "CRM Product", **values, "next_courses": [{"course": n} for n in nexts]})
    return doc.insert().name


@whitelist()
def staff():
    _require_access()
    rows = frappe.get_all("Consultant", fields=["name", "full_name", "branch", "level", "handles_b2b", "active",
                                                "chatwoot_agent_id"], order_by="branch asc, full_name asc")
    specialties = {}
    for s in frappe.get_all("Course Group Link", filters={"parenttype": "Consultant"}, fields=["parent", "course_group"],
                            order_by="idx asc"):
        specialties.setdefault(s.parent, []).append(s.course_group)
    _, _, branch_rows = _tree()
    return {"staff": [{**r, "specialties": specialties.get(r.name, [])} for r in rows],
            "branches": [b["name"] for b in branch_rows], "levels": list(LEVELS),
            "groups": frappe.get_all("Course Group", pluck="name", order_by="sort_order asc")}


def _ensure_user(email, full_name):
    """A login for a new staff member: enabled, Sales User only."""
    if frappe.db.exists("User", email):
        return
    frappe.get_doc({"doctype": "User", "email": email, "first_name": full_name, "enabled": 1,
                    "send_welcome_email": 0, "roles": [{"role": STAFF_ROLE}]}).insert(ignore_permissions=True)


@whitelist(methods=["POST"])
def save_staff(email="", full_name="", branch="", level="Consultant", specialties=None, handles_b2b=0, active=1,
               is_new=0):
    _require_access()
    email, full_name = (email or "").strip().lower(), (full_name or "").strip()
    if not email or not full_name:
        frappe.throw("Nhập họ tên và email.")
    if level not in LEVELS:
        frappe.throw("Cấp bậc không hợp lệ.")
    specialties = frappe.parse_json(specialties) if isinstance(specialties, str) else (specialties or [])
    values = {"full_name": full_name, "branch": branch or None, "level": level,
              "handles_b2b": int(bool(int(handles_b2b))), "active": int(bool(int(active))),
              "specialties": [{"course_group": g} for g in specialties]}
    if int(is_new):
        if frappe.db.exists("Consultant", email):
            frappe.throw("Nhân viên này đã có.")
        _ensure_user(email, full_name)
        doc = frappe.get_doc({"doctype": "Consultant", "user": email, **values}).insert()
    else:
        doc = frappe.get_doc("Consultant", email)
        doc.update(values)
        doc.save()
    return doc.name
