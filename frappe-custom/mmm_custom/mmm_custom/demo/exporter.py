"""Write the live branches, staff and course knowledge back into the demo dataset.

Run: bench --site crm.localhost execute mmm_custom.demo.exporter.export
Then commit demo/saoviet/*.json; another bench gets the same data with mmm_custom.demo.loader.load.
"""

import json

import frappe

from mmm_custom.demo.loader import DATA_DIR, KNOWLEDGE_FIELDS, PRODUCT_FIELDS

DEFAULT_WEEKDAYS = "T2, T4, T6"  # schedule hints live only in the dataset, not in the CRM
DEFAULT_SHIFTS = ["evening"]


def _number(value):
	return int(value) if isinstance(value, float) and value.is_integer() else value


def _write(name, data):
	path = DATA_DIR / f"{name}.json"
	path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _children(doctype, parent, field, parenttype):
	return frappe.get_all(doctype, filters={"parent": parent, "parenttype": parenttype, "parentfield": field},
	                      fields=["*"], order_by="idx asc")


def export_areas():
	root = frappe.get_all("CRM Territory", filters={"parent_crm_territory": ["in", ["", None]], "is_group": 1},
	                      pluck="name", order_by="creation asc")[0]
	fields = ["territory_name", "branch_code", "button_label", "branch_tier", "address", "hotline", "aliases"]
	areas = []
	for area in frappe.get_all("CRM Territory", filters={"parent_crm_territory": root, "is_group": 1},
	                           fields=["territory_name", "button_label", "aliases"], order_by="creation asc"):
		branches = frappe.get_all("CRM Territory", filters={"parent_crm_territory": area.territory_name, "is_group": 0},
		                          fields=fields, order_by="creation asc")
		areas.append({**{k: area[k] or "" for k in ("territory_name", "button_label", "aliases")}, "branches": [{
			"territory_name": b.territory_name, "branch_code": b.branch_code, "button_label": b.button_label or "",
			"tier": b.branch_tier, "address": b.address or "", "hotline": b.hotline or "", "aliases": b.aliases or ""}
			for b in branches]})
	return {"root": root, "areas": areas}


def export_course_groups():
	return frappe.get_all("Course Group", fields=["group_name", "button_label", "emoji", "sort_order", "aliases",
	                                              "description"], order_by="sort_order asc, creation asc")


def export_courses(previous):
	hints = {c["product_code"]: c for c in previous}
	courses = []
	for p in frappe.get_all("CRM Product", fields=["name", "product_code", *PRODUCT_FIELDS, *KNOWLEDGE_FIELDS[:2]],
	                        order_by="creation asc"):
		old = hints.get(p.product_code, {})
		courses.append({
			"product_code": p.product_code,
			**{k: _number(p[k]) for k in PRODUCT_FIELDS},
			"next_courses": [r.course for r in _children("Course Link", p.name, "next_courses", "CRM Product")],
			"weekdays": old.get("weekdays", DEFAULT_WEEKDAYS),
			"shifts": old.get("shifts", DEFAULT_SHIFTS),
			"description": p.description or "",
			"syllabus": p.syllabus or "",
			"faqs": [{k: r[k] or "" for k in ("question", "examples", "answer")}
			         for r in _children("Course FAQ", p.name, "faqs", "CRM Product")],
		})
	return courses


def export_consultants():
	rows = []
	for c in frappe.get_all("Consultant", fields=["name", "user", "full_name", "branch", "level", "handles_b2b", "active"],
	                        order_by="creation asc"):
		rows.append({
			"full_name": c.full_name, "email": c.user, "branch": c.branch or "", "level": c.level,
			"specialties": [r.course_group for r in _children("Course Group Link", c.name, "specialties", "Consultant")],
			"handles_b2b": c.handles_b2b, "active": c.active})
	return rows


def export():
	previous = json.loads((DATA_DIR / "courses.json").read_text(encoding="utf-8"))
	data = {"areas": export_areas(), "course_groups": export_course_groups(),
	        "courses": export_courses(previous), "consultants": export_consultants()}
	for name, rows in data.items():
		_write(name, rows)
	return {name: len(rows["areas"] if name == "areas" else rows) for name, rows in data.items()}
