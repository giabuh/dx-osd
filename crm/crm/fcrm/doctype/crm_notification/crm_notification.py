# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CRMNotification(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		comment: DF.Link | None
		from_user: DF.Link | None
		message: DF.HTMLEditor | None
		notification_text: DF.Text | None
		notification_type_doc: DF.DynamicLink | None
		notification_type_doctype: DF.Link | None
		read: DF.Check
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		to_user: DF.Link
		type: DF.Literal["Mention", "Task", "Assignment", "WhatsApp", "Marketing", "System"]
	# end: auto-generated types

	def on_update(self):
		if self.to_user:
			frappe.publish_realtime(
				"crm_notification",
				{
					"title": getattr(self, "reference_name", None) or "Thông báo mới",
					"message": self.message,
					"type": self.type,
					"name": self.name,
					"reference_doctype": self.reference_doctype,
					"reference_name": self.reference_name,
				},
				user=self.to_user,
			)


def get_permission_query_conditions(user=None):
	if not user:
		user = frappe.session.user

	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return ""

	return f"`tabCRM Notification`.`to_user` = {frappe.db.escape(user)}"


def has_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user

	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True

	if ptype == "create":
		return False

	if not doc.to_user:
		return True

	return doc.to_user == user


def notify_user(notification):
	"""
	Notify the assigned user
	"""
	notification = frappe._dict(notification)
	if notification.owner == notification.assigned_to:
		return

	values = frappe._dict(
		doctype="CRM Notification",
		from_user=notification.owner,
		to_user=notification.assigned_to,
		type=notification.notification_type,
		message=notification.message,
		notification_text=notification.notification_text,
		notification_type_doctype=notification.reference_doctype,
		notification_type_doc=notification.reference_docname,
		reference_doctype=notification.redirect_to_doctype,
		reference_name=notification.redirect_to_docname,
	)

	if frappe.db.exists("CRM Notification", values):
		return
	frappe.get_doc(values).insert(ignore_permissions=True)



def notify_crm_users(
	title: str,
	message: str,
	to_users: list | str | None = None,
	notification_type: str = "Marketing",
	reference_doctype: str | None = None,
	reference_name: str | None = None,
	from_user: str | None = None,
):
	"""
	Send CRM Notification to one or multiple users.
	Defaults to Administrator and active System / Sales Managers.
	Triggers real-time socket events so sidebar badge and toasts update immediately.
	"""
	if not from_user:
		from_user = (
			frappe.session.user
			if getattr(frappe, "session", None) and getattr(frappe.session, "user", None)
			else "Administrator"
		)

	if not to_users:
		managers = []
		if hasattr(frappe, "get_all"):
			try:
				managers = frappe.get_all(
					"Has Role",
					filters={
						"role": ["in", ["System Manager", "Sales Manager"]],
						"parenttype": "User",
					},
					pluck="parent",
				)
			except Exception:
				pass
		to_users = list(set(managers + ["Administrator"]))
	elif isinstance(to_users, str):
		to_users = [to_users]

	to_users = list(dict.fromkeys(to_users))

	escaped_title = frappe.utils.escape_html(title) if hasattr(frappe, "utils") and hasattr(frappe.utils, "escape_html") else title
	escaped_msg = frappe.utils.escape_html(message) if hasattr(frappe, "utils") and hasattr(frappe.utils, "escape_html") else message

	notification_text = f"""
		<div class="mb-1 leading-5">
			<div class="font-medium text-ink-gray-9">{escaped_title}</div>
			<div class="text-sm text-ink-gray-6 mt-0.5">{escaped_msg}</div>
		</div>
	"""

	for u in to_users:
		if hasattr(frappe, "db") and hasattr(frappe.db, "exists"):
			if not frappe.db.exists("User", u):
				continue

		values = frappe._dict(
			doctype="CRM Notification",
			from_user=from_user,
			to_user=u,
			type=notification_type,
			message=message,
			notification_text=notification_text,
			notification_type_doctype=reference_doctype,
			notification_type_doc=reference_name,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			read=0,
		)

		try:
			doc = frappe.get_doc(values)
			doc.insert(ignore_permissions=True)
			if hasattr(frappe, "publish_realtime"):
				frappe.publish_realtime(
					"crm_notification",
					{
						"title": title,
						"message": message,
						"type": notification_type,
						"name": doc.name,
						"reference_doctype": reference_doctype,
						"reference_name": reference_name,
					},
					user=u,
				)
		except Exception as e:
			if hasattr(frappe, "log_error"):
				frappe.log_error(f"Error notifying {u}: {e}", "CRM Notification")

	if hasattr(frappe, "db") and hasattr(frappe.db, "commit"):
		frappe.db.commit()
