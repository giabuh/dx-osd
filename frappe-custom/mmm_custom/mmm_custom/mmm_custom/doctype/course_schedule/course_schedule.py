import frappe
from frappe.model.document import Document

from mmm_custom.catalog_rules import assert_leaf_branch
from mmm_custom.mmm_custom.doctype.consultant.consultant import territory_is_group


class CourseSchedule(Document):
	def validate(self):
		try:
			assert_leaf_branch(self.branch, territory_is_group)
		except ValueError as e:
			frappe.throw(str(e))
