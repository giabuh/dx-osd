import frappe
from frappe.model.document import Document

from mmm_custom.catalog_rules import assert_leaf_branch


def territory_is_group(name):
	return frappe.db.get_value("CRM Territory", name, "is_group")


class Consultant(Document):
	def validate(self):
		try:
			assert_leaf_branch(self.branch, territory_is_group)
		except ValueError as e:
			frappe.throw(str(e))
