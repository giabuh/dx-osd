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

	frappe.db.commit()


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
						for f in ("course_interest", "branch", "data_quality"):
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


def setup():
	create_custom_fields()
	update_crm_fields_layout()
	create_lead_sources()


def create_custom_field_and_lead_sources():
	setup()
