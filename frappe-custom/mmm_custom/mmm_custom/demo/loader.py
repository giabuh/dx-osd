"""Idempotent loader for the Tin Học Sao Việt demo dataset.

Run: bench --site crm.localhost execute mmm_custom.demo.loader.load
Re-running creates nothing new and only updates values that changed.
"""

import json
import urllib.parse
import zlib
from datetime import date, timedelta
from pathlib import Path

try:
	import frappe
except ImportError:  # offline tests
	frappe = None

DATA_DIR = Path(__file__).resolve().parent / "saoviet"
WEEKDAY_INDEX = {"T2": 0, "T3": 1, "T4": 2, "T5": 3, "T6": 4, "T7": 5, "CN": 6}
SHIFT_LABELS = {"morning": "Sáng 8:30–11:00", "afternoon": "Chiều 13:30–16:30", "evening": "Tối 17:00–21:00"}
PRODUCT_FIELDS = ("product_name", "button_label", "course_group", "audience", "min_age", "max_age",
                  "standard_rate", "duration_text", "certificate", "offer", "aliases")


def load_dataset(root=DATA_DIR):
	return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(root.glob("*.json"))}


def map_url(address):
	return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(address)


def generate_schedules(courses, branches, anchor, weeks=8, cadence=4):
	"""One class per course × branch every `cadence` weeks; crc32 keeps phase/shift/seats stable across runs."""
	rows = []
	for course in courses:
		first_day = WEEKDAY_INDEX[course["weekdays"].split(",")[0].strip()]
		for branch in branches:
			if course["offer"] == "full" and branch["tier"] != "full":
				continue
			seed = zlib.crc32(f"{course['product_code']}|{branch['territory_name']}".encode())
			for i, week in enumerate(range(seed % cadence, weeks, cadence)):
				rows.append({
					"course": course["product_code"],
					"branch": branch["territory_name"],
					"start_date": anchor + timedelta(weeks=week, days=first_day),
					"shift": SHIFT_LABELS[course["shifts"][(seed + i) % len(course["shifts"])]],
					"weekdays": course["weekdays"],
					"seats": 12 + (seed + i) % 9,
					"status": "Open",
					"is_demo_data": 1,
				})
	return rows


class FrappeDb:
	"""The small slice of frappe the loader needs; tests pass a fake with the same methods."""

	def get_value(self, doctype, filters, fieldname="name"):
		return frappe.db.get_value(doctype, filters, fieldname)

	def insert(self, doctype, values):
		return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name

	def get(self, doctype, name):
		return frappe.get_doc(doctype, name).as_dict()

	def update(self, doctype, name, values):
		doc = frappe.get_doc(doctype, name)
		doc.update(values)
		doc.save(ignore_permissions=True)


def _same(current, value):
	"""Compare a stored value with a desired one; child rows compare only the fields the dataset sets."""
	if isinstance(value, list):
		current = current or []
		return len(current) == len(value) and all(
			all(row.get(k) == v for k, v in want.items()) for row, want in zip(current, value))
	if isinstance(value, date) and current is not None and not isinstance(current, date):
		return str(current) == value.isoformat()
	return current == value


def upsert(doctype, filters, values, db=None):
	db = db or FrappeDb()
	name = db.get_value(doctype, filters)
	if not name:
		return db.insert(doctype, {**filters, **values}), True
	current = db.get(doctype, name)
	changed = {k: v for k, v in values.items() if not _same(current.get(k), v)}
	if changed:
		db.update(doctype, name, changed)
	return name, False


def _anchor_monday(anchor):
	day = date.fromisoformat(anchor) if anchor else frappe.utils.getdate()
	return day - timedelta(days=day.weekday())


def load(anchor=None):
	data = load_dataset()
	monday = _anchor_monday(anchor)
	created = {}

	def put(doctype, filters, values):
		name, new = upsert(doctype, filters, values)
		created[doctype] = created.get(doctype, 0) + int(new)
		return name

	areas = data["areas"]
	put("CRM Territory", {"territory_name": areas["root"]}, {"is_group": 1})
	branches = []
	for area in areas["areas"]:
		put("CRM Territory", {"territory_name": area["territory_name"]}, {
			"is_group": 1, "parent_crm_territory": areas["root"],
			"button_label": area["button_label"], "aliases": area["aliases"]})
		for b in area["branches"]:
			put("CRM Territory", {"territory_name": b["territory_name"]}, {
				"is_group": 0, "parent_crm_territory": area["territory_name"], "branch_code": b["branch_code"],
				"button_label": b["button_label"], "branch_tier": b["tier"], "address": b["address"],
				"hotline": b["hotline"], "map_url": map_url(b["address"]), "aliases": b["aliases"]})
			branches.append(b)

	for g in data["course_groups"]:
		put("Course Group", {"group_name": g["group_name"]},
		    {k: g[k] for k in ("button_label", "emoji", "sort_order", "aliases", "description")})

	for c in data["courses"]:
		put("CRM Product", {"product_code": c["product_code"]},
		    {**{k: c[k] for k in PRODUCT_FIELDS}, "is_demo_data": 1})
	for c in data["courses"]:  # second pass: every linked course now exists
		put("CRM Product", {"product_code": c["product_code"]},
		    {"next_courses": [{"course": n} for n in c["next_courses"]]})

	for p in data["consultants"]:
		put("User", {"email": p["email"]}, {"first_name": p["full_name"], "enabled": 1, "send_welcome_email": 0})
		user = frappe.get_doc("User", p["email"])
		if "Sales User" not in [r.role for r in user.roles]:
			user.add_roles("Sales User")
		put("Consultant", {"user": p["email"]}, {
			"branch": p["branch"] or None, "level": p["level"], "handles_b2b": p["handles_b2b"], "active": 1,
			"specialties": [{"course_group": g} for g in p["specialties"]]})

	for row in generate_schedules(data["courses"], branches, monday):
		key = {k: row[k] for k in ("course", "branch", "start_date", "shift")}
		put("Course Schedule", key, {k: v for k, v in row.items() if k not in key})

	for pr in data["promotions"]:
		put("Course Promotion", {"title": pr["title"]}, {
			"discount_type": pr["discount_type"], "discount_value": pr["discount_value"],
			"valid_from": monday, "valid_to": monday + timedelta(days=pr["days"]), "active": 1, "is_demo_data": 1,
			"courses": [{"course": c} for c in pr["courses"]],
			"course_groups": [{"course_group": g} for g in pr["course_groups"]],
			"branches": [{"branch": b} for b in pr["branches"]]})

	slot_fields = ("label", "slot_type", "catalog_source", "required", "sort_order", "ask_template", "lead_field")
	for s in data["bot_slots"]:
		put("Bot Slot", {"slot_key": s["slot_key"]}, {**{k: s[k] for k in slot_fields}, "active": 1,
		                                             "ask_on_demand": s.get("ask_on_demand", 0), "options": s["options"]})
	for s in data["bot_slots"]:  # second pass: dependencies point at slots that now exist
		put("Bot Slot", {"slot_key": s["slot_key"]},
		    {"depends_on_slot": s["depends_on_slot"] or None, "depends_on_value": s["depends_on_value"] or None})

	skill_fields = ("title", "jev_description", "examples", "aliases", "missing_policy", "action_type",
	                "creates_lead", "handoff_after", "sort_order")
	for s in data["bot_skills"]:
		put("Bot Skill", {"skill_key": s["skill_key"]}, {
			**{k: s[k] for k in skill_fields}, "active": 1,
			"action_config": json.dumps(s["action_config"], ensure_ascii=False) if s["action_config"] else None,
			"parameters": [{"bot_slot": p} for p in s["parameters"]],
			"templates": s["templates"], "follow_ups": s["follow_ups"]})

	settings = frappe.get_single("Lead Engine Settings")
	settings.update(data["settings"])
	settings.save(ignore_permissions=True)

	frappe.db.commit()
	return created


def purge_demo():
	"""Delete demo-only rows (schedules, promotions, demo courses); territories, groups and bot data stay."""
	counts = {}
	for doctype in ("Course Schedule", "Course Promotion", "CRM Product"):
		names = frappe.get_all(doctype, filters={"is_demo_data": 1}, pluck="name")
		for name in names:
			frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
		counts[doctype] = len(names)
	frappe.db.commit()
	return counts
