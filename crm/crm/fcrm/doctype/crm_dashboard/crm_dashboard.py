# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CRMDashboard(Document):
	pass


def default_manager_dashboard_layout():
	"""
	Returns the default layout for the CRM Manager Dashboard.
	"""
	return '[{"name":"total_leads","type":"number_chart","tooltip":"Total number of leads","layout":{"x":0,"y":0,"w":5,"h":3,"i":"total_leads"}},{"name":"messenger_bot_leads","type":"number_chart","tooltip":"Leads from Messenger Bot","layout":{"x":5,"y":0,"w":5,"h":3,"i":"messenger_bot_leads"}},{"name":"facebook_ads_leads","type":"number_chart","tooltip":"Leads from Facebook Ads","layout":{"x":10,"y":0,"w":5,"h":3,"i":"facebook_ads_leads"}},{"name":"leads_with_phone","type":"number_chart","tooltip":"Leads with phone number","layout":{"x":15,"y":0,"w":5,"h":3,"i":"leads_with_phone"}},{"name":"lead_trend_by_source","type":"axis_chart","layout":{"x":0,"y":3,"w":12,"h":9,"i":"lead_trend_by_source"}},{"name":"leads_by_course_interest","type":"donut_chart","layout":{"x":12,"y":3,"w":8,"h":9,"i":"leads_by_course_interest"}},{"name":"leads_by_branch","type":"axis_chart","layout":{"x":0,"y":12,"w":10,"h":9,"i":"leads_by_branch"}},{"name":"leads_by_source","type":"donut_chart","layout":{"x":10,"y":12,"w":10,"h":9,"i":"leads_by_source"}},{"name":"sales_trend","type":"axis_chart","layout":{"x":0,"y":21,"w":10,"h":9,"i":"sales_trend"}},{"name":"funnel_conversion","type":"axis_chart","layout":{"x":10,"y":21,"w":10,"h":9,"i":"funnel_conversion"}}]'


def create_default_manager_dashboard(force=False):
	"""
	Creates the default CRM Manager Dashboard if it does not exist.
	"""
	if not frappe.db.exists("CRM Dashboard", "Manager Dashboard"):
		doc = frappe.new_doc("CRM Dashboard")
		doc.title = "Manager Dashboard"
		doc.layout = default_manager_dashboard_layout()
		doc.insert(ignore_permissions=True)
	else:
		doc = frappe.get_doc("CRM Dashboard", "Manager Dashboard")
		if force:
			doc.layout = default_manager_dashboard_layout()
			doc.save(ignore_permissions=True)
	return doc.layout
