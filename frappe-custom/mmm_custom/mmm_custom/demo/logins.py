"""Demo logins shared with Chatwoot: the same email and password sign in to both apps.

Chatwoot CE has no SSO, so for the demo every active consultant gets one known password here and in
Chatwoot (scripts/seed-demo-logins.py sets the Chatwoot side), and the Chatwoot admin
`admin@eduflow.vn` also exists as a CRM System Manager. Dev/demo only: never run on real staff.

Run: bench --site crm.localhost execute mmm_custom.demo.logins.apply --kwargs '{"staff_password": "..."}'
"""

try:
	import frappe
except ImportError:  # offline tests
	frappe = None

ADMIN_EMAIL = "admin@eduflow.vn"
ADMIN_PASSWORD = "admin123"
ADMIN_ROLES = ("System Manager", "Sales Manager")


def staff_emails(consultants):
	"""Emails of the active consultants, in a stable order. Pure."""
	return sorted(c["user"] for c in consultants if c.get("active", 1) and c.get("user"))


def apply(staff_password):
	from frappe.utils.password import update_password

	if not frappe.db.exists("User", ADMIN_EMAIL):
		frappe.get_doc({"doctype": "User", "email": ADMIN_EMAIL, "first_name": "EduFlow Admin",
		                "send_welcome_email": 0}).insert(ignore_permissions=True)
	admin = frappe.get_doc("User", ADMIN_EMAIL)
	admin.enabled = 1
	admin.save(ignore_permissions=True)
	admin.add_roles(*[r for r in ADMIN_ROLES if r not in [x.role for x in admin.roles]])
	update_password(ADMIN_EMAIL, ADMIN_PASSWORD, logout_all_sessions=False)

	emails = staff_emails(frappe.get_all("Consultant", fields=["user", "active"]))
	for email in emails:
		frappe.db.set_value("User", email, "enabled", 1, update_modified=False)
		update_password(email, staff_password, logout_all_sessions=False)
	frappe.db.commit()
	return {"admin": ADMIN_EMAIL, "admin_password": ADMIN_PASSWORD, "staff": emails}
