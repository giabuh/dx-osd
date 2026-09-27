"""Switch into a consultant's account for demos, and back (spec 2026-09-27-one-customer-record).

A System Manager can view the CRM exactly as an active consultant sees it. It reuses Frappe's own
impersonation (`LoginManager.impersonate` keeps `impersonated_by` in the server-side session), limited
to consultant accounts, logged in the Activity Log, and off when the site config has
`disable_staff_switch`.
"""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

whitelist = frappe.whitelist if frappe else (lambda **kw: (lambda fn: fn))

SWITCHER_ROLE = "System Manager"
MANAGER_ROLES = frozenset(("System Manager", "Sales Manager", "Administrator"))


def refusal(caller_roles, switched, disabled, target_roles, target_is_consultant):
    """Why a switch is not allowed, or "" when it is. Pure."""
    if disabled:
        return "Chức năng xem như nhân viên đang tắt."
    if switched:
        return "Bạn đang xem như nhân viên. Quay lại tài khoản quản trị trước."
    if SWITCHER_ROLE not in caller_roles:
        return "Chỉ quản trị hệ thống được xem như nhân viên."
    if not target_is_consultant:
        return "Chỉ xem được như một nhân viên đang làm việc."
    if MANAGER_ROLES.intersection(target_roles):
        return "Không thể xem như một tài khoản quản lý."
    return ""


def _impersonated_by():
    return (frappe.session.data or {}).get("impersonated_by") or ""


def _log(user, subject):
    frappe.get_doc({"doctype": "Activity Log", "user": user, "status": "Success", "subject": subject,
                    "operation": "Impersonate"}).insert(ignore_permissions=True, ignore_links=True)


@whitelist()
def state():
    user = frappe.session.user
    return {"user": user, "full_name": frappe.utils.get_fullname(user), "impersonated_by": _impersonated_by(),
            "can_switch": not frappe.conf.get("disable_staff_switch") and SWITCHER_ROLE in frappe.get_roles()}


@whitelist(methods=["POST"])
def switch_to(user):
    user = (user or "").strip()
    is_consultant = bool(frappe.db.get_value("Consultant", {"name": user, "active": 1}, "name")) and bool(
        frappe.db.get_value("User", user, "enabled"))
    reason = refusal(frappe.get_roles(), bool(_impersonated_by()), bool(frappe.conf.get("disable_staff_switch")),
                     frappe.get_roles(user) if is_consultant else [], is_consultant)
    if reason:
        frappe.throw(reason, frappe.PermissionError)
    manager = frappe.session.user
    _log(user, f"{manager} xem CRM như {user} (demo)")
    frappe.local.login_manager.impersonate(user)
    return {"user": user}


@whitelist(methods=["POST"])
def switch_back():
    original = _impersonated_by()
    if not original:
        frappe.throw("Phiên này không phải phiên xem như nhân viên.", frappe.PermissionError)
    switched_user, old_sid = frappe.session.user, frappe.session.sid
    _log(switched_user, f"{original} thôi xem CRM như {switched_user}")
    frappe.local.login_manager.login_as(original)
    from frappe.sessions import delete_session

    delete_session(old_sid, user=switched_user, reason="Staff switch ended")
    return {"user": original}
