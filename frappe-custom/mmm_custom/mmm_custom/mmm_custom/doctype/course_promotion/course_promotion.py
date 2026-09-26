import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from mmm_custom.catalog_rules import validate_promotion


class CoursePromotion(Document):
	def validate(self):
		try:
			validate_promotion(
				self.discount_type, self.discount_value,
				getdate(self.valid_from) if self.valid_from else None,
				getdate(self.valid_to) if self.valid_to else None,
			)
		except ValueError as e:
			frappe.throw(str(e))
