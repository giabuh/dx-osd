import frappe
from frappe.model.document import Document

from mmm_custom.catalog_rules import validate_slot_dependency


class BotSlot(Document):
	def validate(self):
		try:
			validate_slot_dependency(self.slot_type, self.catalog_source, self.depends_on_slot, self.depends_on_value)
		except ValueError as e:
			frappe.throw(str(e))
