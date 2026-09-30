import frappe

from mmm_custom.enrolment import rewrite_layouts
from mmm_custom.lifecycle import ensure_statuses
from mmm_custom.setup import create_catalog_fields


def execute():
	# D-118 / D-120: the draft status takes its place in the order, the Deal layouts lose the payment date, and the
	# field itself goes (its column stays in the table: no data is dropped).
	ensure_statuses(create_only=False)
	rewrite_layouts()
	frappe.delete_doc("Custom Field", "CRM Deal-payment_due_date", ignore_missing=True, force=True)
	create_catalog_fields()
