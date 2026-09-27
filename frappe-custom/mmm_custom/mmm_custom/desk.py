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
