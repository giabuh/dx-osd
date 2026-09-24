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
			"fieldtype": "Select",
			"options": "\nTiếng Anh\nBơi lội\nToán tư duy\nChưa xác định",
			"insert_after": "source",
		}).insert(ignore_permissions=True)
		print("Custom field course_interest created")
	else:
		doc = frappe.get_doc("Custom Field", "CRM Lead-course_interest")
		doc.options = "\nTiếng Anh\nBơi lội\nToán tư duy\nChưa xác định"
		doc.insert_after = "source"
		doc.save(ignore_permissions=True)
		print("Custom field course_interest updated")

	frappe.db.commit()


def create_custom_field():
	create_custom_fields()


def create_lead_sources():
	for source_name in ("Messenger", "Instagram"):
		frappe.get_doc({"doctype": "CRM Lead Source", "source_name": source_name}).insert(ignore_if_duplicate=True)
	frappe.db.commit()
	print("Lead sources created")


def setup():
	create_custom_fields()
	create_lead_sources()


def create_custom_field_and_lead_sources():
	setup()
