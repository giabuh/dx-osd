"""Access and workspace setup for the bot administration surfaces."""

try:
    import frappe
    from frappe.modules.import_file import import_file_by_path
except ImportError:  # offline tests
    frappe = import_file_by_path = None

HIDDEN_WORKSPACES = ("Website", "Tools", "Integrations", "Build")
BOT_WORKSPACE = "Bot Sao Việt"  # name == title: the desk routes by slug(name) but links the sidebar by slug(title)
OLD_BOT_WORKSPACE = "Bot Sao Viet"  # first version, whose sidebar link pointed at a route that did not exist
BOT_ROLES = frozenset(("System Manager", "Sales Manager"))


def can_open_bot():
    return bool(BOT_ROLES.intersection(frappe.get_roles()))


def hide_unused_workspaces():
    for name in HIDDEN_WORKSPACES:
        if frappe.db.exists("Workspace", name) and not frappe.db.get_value("Workspace", name, "is_hidden"):
            frappe.db.set_value("Workspace", name, "is_hidden", 1)


def ensure_bot_workspace_icon():
    """Bring existing site records in line with the workspace JSON icon."""
    name = BOT_WORKSPACE
    if frappe.db.exists("Workspace", name) and frappe.db.get_value("Workspace", name, "icon") != "education":
        frappe.db.set_value("Workspace", name, "icon", "education")


def remove_old_bot_workspace():
    """Replace the first, unaccented workspace. The migrate sync skips the renamed JSON on sites that had the
    old record, so the new one is imported here when it is missing."""
    if frappe.db.exists("Workspace", OLD_BOT_WORKSPACE):
        frappe.delete_doc("Workspace", OLD_BOT_WORKSPACE, ignore_permissions=True, force=True)
    if not frappe.db.exists("Workspace", BOT_WORKSPACE):
        import_file_by_path(frappe.get_app_path("mmm_custom", "mmm_custom", "workspace", "bot_sao_viet",
                                                "bot_sao_viet.json"), force=True)


ADMIN_APP = "mmm_custom"  # add_to_apps_screen route /crm/admin
CRM_APP = "crm"


def default_app_for(roles, current):
    """Where a desk user lands after login (User.default_app): managers on /crm/admin, everyone else on /crm
    (the System Settings default). Returns the new value, or None to leave the user's choice alone."""
    manager = bool(BOT_ROLES.intersection(roles))
    if manager and not current:
        return ADMIN_APP
    if not manager and current == ADMIN_APP:
        return ""
    return None


def _set_default_app(user, roles, current):
    new = default_app_for(roles, current or "")
    if new is not None:
        frappe.db.set_value("User", user, "default_app", new, update_modified=False)


def apply_default_apps():
    """after_migrate: CRM is the site-wide landing app; each enabled desk user gets their role's home."""
    if not frappe.db.get_single_value("System Settings", "default_app"):
        frappe.db.set_single_value("System Settings", "default_app", CRM_APP)
    for user in frappe.get_all("User", filters={"enabled": 1, "user_type": "System User"},
                               fields=["name", "default_app"]):
        _set_default_app(user.name, frappe.get_roles(user.name), user.default_app)


def apply_user_default_app(doc, method=None):
    """User on_update: role changes and staff created by staff_sync get the right home."""
    if not doc.enabled or doc.user_type != "System User":
        return
    roles = BOT_ROLES if doc.name == "Administrator" else [row.role for row in doc.get("roles") or []]
    _set_default_app(doc.name, roles, frappe.db.get_value("User", doc.name, "default_app"))
