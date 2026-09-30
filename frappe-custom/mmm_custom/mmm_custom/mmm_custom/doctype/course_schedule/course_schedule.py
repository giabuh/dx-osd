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
		from mmm_custom.enrolment import schedule_title

		name = frappe.db.get_value("CRM Product", self.course, "product_name") or self.course
		self.title = schedule_title(name, self.branch, frappe.utils.getdate(self.start_date), self.shift)
