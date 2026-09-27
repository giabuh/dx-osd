"""Access and workspace setup for the bot administration surfaces."""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

HIDDEN_WORKSPACES = ("Website", "Tools", "Integrations", "Build")
BOT_ROLES = frozenset(("System Manager", "Sales Manager"))


def can_open_bot():
    return bool(BOT_ROLES.intersection(frappe.get_roles()))


def hide_unused_workspaces():
    for name in HIDDEN_WORKSPACES:
        if frappe.db.exists("Workspace", name) and not frappe.db.get_value("Workspace", name, "is_hidden"):
            frappe.db.set_value("Workspace", name, "is_hidden", 1)


def ensure_bot_workspace_icon():
    """Bring existing site records in line with the workspace JSON icon."""
    name = "Bot Sao Viet"
    if frappe.db.exists("Workspace", name) and frappe.db.get_value("Workspace", name, "icon") != "education":
        frappe.db.set_value("Workspace", name, "icon", "education")
