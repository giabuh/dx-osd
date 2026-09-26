import frappe


def create_custom_fields():
	if not frappe.db.exists("Custom Field", "CRM Lead-chatwoot_contact_id"):
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "CRM Lead",
			"fieldname": "chatwoot_contact_id",
			"label": "Chatwoot Contact ID",
			"fieldtype": "Data",
			"unique": 1,
			"read_only": 0,
			"insert_after": "lead_name",
		}).insert(ignore_permissions=True)
		print("Custom field chatwoot_contact_id created")
	else:
		print("Custom field chatwoot_contact_id already exists, skipping")

	if not frappe.db.exists("Custom Field", "CRM Lead-course_interest"):
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "CRM Lead",
			"fieldname": "course_interest",
			"label": "Course Interest",
			"fieldtype": "Data",
			"in_list_view": 1,
			"in_standard_filter": 1,
			"insert_after": "source",
		}).insert(ignore_permissions=True)
		print("Custom field course_interest created")
	else:
		doc = frappe.get_doc("Custom Field", "CRM Lead-course_interest")
		doc.fieldtype = "Data"
		doc.options = None
		doc.in_list_view = 1
		doc.in_standard_filter = 1
		doc.insert_after = "source"
		doc.save(ignore_permissions=True)
		print("Custom field course_interest updated to Data")

	if not frappe.db.exists("Custom Field", "CRM Lead-branch"):
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "CRM Lead",
			"fieldname": "branch",
			"label": "Branch",
			"fieldtype": "Select",
			"options": "\nCS1 Bình Thạnh\nCS2 Quận 1\nCS3 Thủ Đức",
			"in_list_view": 1,
			"in_standard_filter": 1,
			"insert_after": "course_interest",
		}).insert(ignore_permissions=True)
		print("Custom field branch created")
	else:
		doc = frappe.get_doc("Custom Field", "CRM Lead-branch")
		doc.options = "\nCS1 Bình Thạnh\nCS2 Quận 1\nCS3 Thủ Đức"
		doc.in_list_view = 1
		doc.in_standard_filter = 1
		doc.save(ignore_permissions=True)
		print("Custom field branch updated")

	if not frappe.db.exists("Custom Field", "CRM Lead-data_quality"):
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "CRM Lead",
			"fieldname": "data_quality",
			"label": "Data Quality",
			"fieldtype": "Select",
			"options": "\nĐầy đủ\nThiếu SĐT/Email\nNghi trùng",
			"in_list_view": 1,
			"in_standard_filter": 1,
			"read_only": 1,
			"insert_after": "branch",
		}).insert(ignore_permissions=True)
		print("Custom field data_quality created")
	else:
		doc = frappe.get_doc("Custom Field", "CRM Lead-data_quality")
		doc.options = "\nĐầy đủ\nThiếu SĐT/Email\nNghi trùng"
		doc.in_list_view = 1
		doc.in_standard_filter = 1
		doc.read_only = 1
		doc.save(ignore_permissions=True)
		print("Custom field data_quality updated")

	# Written by the optional [I] AI agents (intelligence.py); options must match its INTENTS / HOTNESS.
	for field in AI_FIELDS:
		if not frappe.db.exists("Custom Field", f"CRM Lead-{field['fieldname']}"):
			frappe.get_doc({"doctype": "Custom Field", "dt": "CRM Lead", **field}).insert(ignore_permissions=True)
			print(f"Custom field {field['fieldname']} created")

	frappe.db.commit()


AI_FIELDS = [
	{
		"fieldname": "ai_intent",
		"label": "AI Intent",
		"fieldtype": "Select",
		"options": "\npurchase\nprice_inquiry\nsupport\ncomplaint\nspam\nother",
		"in_standard_filter": 1,
		"read_only": 1,
		"insert_after": "data_quality",
	},
	{
		"fieldname": "ai_hotness",
		"label": "AI Hotness",
		"fieldtype": "Select",
		"options": "\ncold\nwarm\nhot",
		"in_list_view": 1,
		"in_standard_filter": 1,
		"read_only": 1,
		"insert_after": "ai_intent",
	},
]


def create_custom_field():
	create_custom_fields()


def update_crm_fields_layout():
	"""Ensure course_interest and branch are visible in Frappe CRM UI layouts."""
	import json

	layouts_to_update = {
		"CRM Lead-Data Fields": "details_section",
		"CRM Lead-Side Panel": "details_section",
		"CRM Lead-Quick Entry": "lead_section",
	}

	for layout_name, target_section in layouts_to_update.items():
		if not frappe.db.exists("CRM Fields Layout", layout_name):
			continue
		doc = frappe.get_doc("CRM Fields Layout", layout_name)
		try:
			layout = json.loads(doc.layout)
			for section in layout:
				if section.get("name") == target_section:
					columns = section.get("columns", [])
					if columns:
						col_fields = columns[-1].setdefault("fields", [])
						fields = ["course_interest", "branch", "data_quality"]
						if layout_name != "CRM Lead-Quick Entry":
							fields += [f["fieldname"] for f in AI_FIELDS]  # read-only, filled by the AI agents
						for f in fields:
							if f not in col_fields:
								col_fields.append(f)
			doc.layout = json.dumps(layout)
			doc.save(ignore_permissions=True)
			print(f"{layout_name} layout updated")
		except Exception as e:
			print(f"Failed to update {layout_name}:", e)

	frappe.db.commit()


def create_lead_sources():
	for source_name in ("Messenger", "Instagram", "Messenger Bot"):
		frappe.get_doc({"doctype": "CRM Lead Source", "source_name": source_name}).insert(ignore_if_duplicate=True)
	frappe.db.commit()
	print("Lead sources created")


# Lead engine catalog (spec 2026-09-26-edu-lead-engine §7.1): fields on standard CRM DocTypes.
CATALOG_FIELDS = {
	"CRM Territory": [
		{"fieldname": "branch_code", "label": "Branch Code", "fieldtype": "Data", "unique": 1, "insert_after": "territory_name"},
		{"fieldname": "button_label", "label": "Button Label", "fieldtype": "Data", "length": 20, "insert_after": "branch_code"},
		{"fieldname": "branch_tier", "label": "Branch Tier", "fieldtype": "Select", "options": "\nfull\nstandard", "insert_after": "button_label"},
		{"fieldname": "address", "label": "Address", "fieldtype": "Small Text", "insert_after": "branch_tier"},
		{"fieldname": "hotline", "label": "Hotline", "fieldtype": "Data", "insert_after": "address"},
		{"fieldname": "map_url", "label": "Map URL", "fieldtype": "Data", "insert_after": "hotline"},
		{"fieldname": "aliases", "label": "Aliases", "fieldtype": "Small Text", "description": "Comma-separated names customers use, e.g. Dĩ An, Di An", "insert_after": "map_url"},
	],
	"CRM Product": [
		{"fieldname": "course_group", "label": "Course Group", "fieldtype": "Link", "options": "Course Group", "in_standard_filter": 1, "insert_after": "product_name"},
		{"fieldname": "button_label", "label": "Button Label", "fieldtype": "Data", "length": 20, "insert_after": "course_group"},
		{"fieldname": "audience", "label": "Audience", "fieldtype": "Select", "options": "\nTrẻ em\nHọc sinh – Sinh viên\nNgười đi làm\nDoanh nghiệp", "insert_after": "button_label"},
		{"fieldname": "min_age", "label": "Min Age", "fieldtype": "Int", "insert_after": "audience"},
		{"fieldname": "max_age", "label": "Max Age", "fieldtype": "Int", "insert_after": "min_age"},
		{"fieldname": "duration_text", "label": "Duration", "fieldtype": "Data", "insert_after": "max_age"},
		{"fieldname": "certificate", "label": "Certificate", "fieldtype": "Data", "insert_after": "duration_text"},
		{"fieldname": "offer", "label": "Offered At", "fieldtype": "Select", "options": "all\nfull", "default": "all", "insert_after": "certificate"},
		{"fieldname": "aliases", "label": "Aliases", "fieldtype": "Small Text", "insert_after": "offer"},
		{"fieldname": "next_courses", "label": "Next Courses", "fieldtype": "Table MultiSelect", "options": "Course Link", "insert_after": "aliases"},
		{"fieldname": "is_demo_data", "label": "Demo Data", "fieldtype": "Check", "insert_after": "next_courses"},
	],
}


def ensure_custom_field(dt, field):
	"""Create the Custom Field, or bring an existing one in line with `field`."""
	name = f"{dt}-{field['fieldname']}"
	if frappe.db.exists("Custom Field", name):
		doc = frappe.get_doc("Custom Field", name)
		changed = {k: v for k, v in field.items() if getattr(doc, k, None) != v}
		if changed:
			for key, value in changed.items():
				setattr(doc, key, value)
			doc.save(ignore_permissions=True)
	else:
		frappe.get_doc({"doctype": "Custom Field", "dt": dt, **field}).insert(ignore_permissions=True)


def create_catalog_fields():
	for dt, fields in CATALOG_FIELDS.items():
		for field in fields:
			ensure_custom_field(dt, field)
	frappe.db.commit()


def setup():
	create_custom_fields()
	update_crm_fields_layout()
	create_lead_sources()
	create_catalog_fields()


def create_custom_field_and_lead_sources():
	setup()
