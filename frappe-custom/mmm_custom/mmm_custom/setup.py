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
		{"fieldname": "map_url", "label": "Map URL", "fieldtype": "Data", "options": "URL", "length": 500, "insert_after": "hotline"},
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
		# Course knowledge the bot answers from (D-084, D-085); the overview is the standard `description`.
		{"fieldname": "knowledge_section", "label": "Bot Knowledge", "fieldtype": "Section Break", "insert_after": "description"},
		{"fieldname": "syllabus", "label": "Syllabus", "fieldtype": "Small Text", "description": "One module per line", "insert_after": "knowledge_section"},
		{"fieldname": "faqs", "label": "Course FAQs", "fieldtype": "Table", "options": "Course FAQ", "description": "Questions customers ask about this course; Jev picks the matching one and the bot sends its answer", "insert_after": "syllabus"},
	],
	# Bot Slot lead_field targets that are not standard CRM Lead fields.
	"CRM Lead": [
		{"fieldname": "learner_type", "label": "Learner", "fieldtype": "Data", "insert_after": "course_interest"},
		{"fieldname": "learner_age", "label": "Learner Age", "fieldtype": "Int", "insert_after": "learner_type"},
		{"fieldname": "preferred_shift", "label": "Preferred Shift", "fieldtype": "Data", "insert_after": "learner_age"},
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


def setup_workspaces():
	import json

	# 1. Add shortcut in Frappe CRM workspace
	if frappe.db.exists("Workspace", "Frappe CRM"):
		try:
			crm_ws = frappe.get_doc("Workspace", "Frappe CRM")
			has_fb = any(s.label == "Facebook Posts" or s.link_to == "Facebook Post" for s in crm_ws.shortcuts)
			if not has_fb:
				crm_ws.append("shortcuts", {
					"type": "DocType",
					"link_to": "Facebook Post",
					"label": "Facebook Posts",
					"doc_view": "List",
					"color": "Blue",
					"idx": 3,
				})
				if crm_ws.content:
					content = json.loads(crm_ws.content)
					content.insert(5, {
						"id": "fb_post_sc_crm",
						"type": "shortcut",
						"data": {"shortcut_name": "Facebook Posts", "col": 3},
					})
					crm_ws.content = json.dumps(content)
				crm_ws.save(ignore_permissions=True)
				print("Facebook Posts shortcut added to Frappe CRM workspace")
		except Exception as e:
			print("Failed to add shortcut to Frappe CRM workspace:", e)

	# 2. Create or ensure Facebook Marketing workspace
	ws_name = "Facebook Marketing"
	content_fb = [
		{"id": "hdr_fb", "type": "header", "data": {"text": "<b>FACEBOOK MARKETING</b>", "col": 12}},
		{"id": "sc_fb_post", "type": "shortcut", "data": {"shortcut_name": "Facebook Posts", "col": 4}},
		{"id": "sc_fb_leads", "type": "shortcut", "data": {"shortcut_name": "Leads", "col": 4}},
		{"id": "sc_fb_sources", "type": "shortcut", "data": {"shortcut_name": "Lead Sources", "col": 4}},
		{"id": "spc_fb", "type": "spacer", "data": {"col": 12}},
		{"id": "card_posts", "type": "card", "data": {"card_name": "Quản lý Bài đăng & Fanpage", "col": 6}},
		{"id": "card_leads", "type": "card", "data": {"card_name": "Khách hàng & Chiến dịch", "col": 6}},
	]

	if not frappe.db.exists("Workspace", ws_name):
		try:
			ws = frappe.get_doc({
				"doctype": "Workspace",
				"name": ws_name,
				"label": ws_name,
				"title": "Facebook Marketing",
				"icon": "share-2",
				"module": "MMM Custom",
				"sequence_id": 2.0,
				"public": 1,
				"is_hidden": 0,
				"content": json.dumps(content_fb),
				"shortcuts": [
					{"type": "DocType", "link_to": "Facebook Post", "label": "Facebook Posts", "doc_view": "List", "color": "Blue"},
					{"type": "DocType", "link_to": "CRM Lead", "label": "Leads", "doc_view": "List", "color": "Green"},
					{"type": "DocType", "link_to": "CRM Lead Source", "label": "Lead Sources", "doc_view": "List", "color": "Orange"},
				],
				"links": [
					{"type": "Card Break", "label": "Quản lý Bài đăng & Fanpage"},
					{"type": "Link", "label": "Danh sách bài đăng Facebook", "link_type": "DocType", "link_to": "Facebook Post"},
					{"type": "Card Break", "label": "Khách hàng & Chiến dịch"},
					{"type": "Link", "label": "Khách hàng tiềm năng (Leads)", "link_type": "DocType", "link_to": "CRM Lead"},
					{"type": "Link", "label": "Nguồn chiến dịch Facebook/Messenger", "link_type": "DocType", "link_to": "CRM Lead Source"},
				],
			})
			ws.insert(ignore_permissions=True)
			print("Created Facebook Marketing workspace")
		except Exception as e:
			print("Failed to create Facebook Marketing workspace:", e)
	else:
		try:
			ws = frappe.get_doc("Workspace", ws_name)
			ws.is_hidden = 0
			ws.public = 1
			ws.sequence_id = 2.0
			ws.save(ignore_permissions=True)
			print("Facebook Marketing workspace updated")
		except Exception as e:
			print("Failed to update Facebook Marketing workspace:", e)

	frappe.db.commit()


def setup():
	create_custom_fields()
	update_crm_fields_layout()
	create_lead_sources()
	create_catalog_fields()
	setup_workspaces()


def create_custom_field_and_lead_sources():
	setup()
