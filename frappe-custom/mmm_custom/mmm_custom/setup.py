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


def create_lead_sources():
	# Same pattern as upstream's own crm/patches/v1_0/add_fb_lead_source.py.
	# "Facebook" already exists upstream but doesn't distinguish Messenger from
	# Instagram DMs, which the Activepieces Chatwoot-CRM sync flow needs to set as
	# CRM Lead.source.
	for source_name in ("Messenger", "Instagram"):
		frappe.get_doc({"doctype": "CRM Lead Source", "source_name": source_name}).insert(ignore_if_duplicate=True)
	frappe.db.commit()
	print("Lead sources created")


# Written by the Activepieces "Lead intelligence" flow (activepieces/logic/intelligence.mjs);
# options must match its INTENTS / HOTNESS keys.
AI_FIELDS = [
	{
		"fieldname": "ai_intent",
		"label": "AI Intent",
		"fieldtype": "Select",
		"options": "\npurchase\nprice_inquiry\nsupport\ncomplaint\nspam\nother",
		"insert_after": "chatwoot_contact_id",
	},
	{
		"fieldname": "ai_hotness",
		"label": "AI Hotness",
		"fieldtype": "Select",
		"options": "\ncold\nwarm\nhot",
		"insert_after": "ai_intent",
	},
]


def create_ai_fields():
	for field in AI_FIELDS:
		if frappe.db.exists("Custom Field", f"CRM Lead-{field['fieldname']}"):
			continue
		frappe.get_doc({"doctype": "Custom Field", "dt": "CRM Lead", **field}).insert(ignore_permissions=True)
	frappe.db.commit()
	print("AI fields ready")


def create_custom_field_and_lead_sources():
	create_custom_field()
	create_lead_sources()
	create_ai_fields()
