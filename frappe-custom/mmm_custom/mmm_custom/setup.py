import frappe


def create_custom_field():
	if frappe.db.exists("Custom Field", "CRM Lead-chatwoot_contact_id"):
		print("Custom field already exists, skipping")
		return

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
	frappe.db.commit()
	print("Custom field created")
