"""The channels tab (/crm/admin/channels): providers, connections and the branch each page belongs to."""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.channels import PROVIDERS
from mmm_custom.desk import can_open_bot

whitelist = frappe.whitelist if frappe else (lambda **kw: (lambda fn: fn))

FIELDS = ["name", "provider", "external_id", "display_name", "picture", "status", "branch", "chatwoot_inbox_id",
          "lead_forms", "connected_by", "connected_at", "last_checked_at", "token_expires_at", "last_error"]


def _require_access():
    if not can_open_bot():
        frappe.throw("Bạn không có quyền kết nối kênh.", frappe.PermissionError)


def inbox_url(chatwoot_url, account_id, inbox_id):
    """The Chatwoot page of one inbox, or "" before the page has an inbox."""
    if not inbox_id:
        return ""
    return f"{chatwoot_url.rstrip('/')}/app/accounts/{account_id}/inbox/{inbox_id}"


def provider_cards(providers, connections):
    """Providers with how many of their accounts are connected. Pure."""
    counts = {}
    for c in connections:
        if c.get("status") != "Disconnected":
            counts[c.get("provider")] = counts.get(c.get("provider"), 0) + 1
    return [{**p, "connected": counts.get(p["provider"], 0)} for p in providers]


@whitelist()
def overview():
    _require_access()
    conf = frappe.conf
    chatwoot_url = (conf.get("chatwoot_base_url") or "http://127.0.0.1:3000").rstrip("/")
    account_id = conf.get("chatwoot_account_id") or 1
    rows = frappe.get_all("Channel Connection", fields=FIELDS, order_by="provider asc, display_name asc")
    for row in rows:
        row["chatwoot_url"] = inbox_url(chatwoot_url, account_id, row.chatwoot_inbox_id)
    from mmm_custom.channels.facebook import callback_url

    return {
        "providers": provider_cards(PROVIDERS, rows),
        "connections": rows,
        "branches": frappe.get_all("CRM Territory", filters={"is_group": 0}, pluck="name", order_by="name asc"),
        "facebook": {"configured": bool(conf.get("facebook_app_id") and conf.get("facebook_app_secret")),
                     "redirect_uri": callback_url(conf, frappe.utils.get_url()),
                     "chatwoot_configured": bool(conf.get("chatwoot_api_token"))},
    }


@whitelist(methods=["POST"])
def set_branch(name, branch=""):
    """Which branch's staff see every conversation of this page; empty = the bot hands off one by one."""
    _require_access()
    branch = (branch or "").strip()
    if branch and not frappe.db.exists("CRM Territory", {"name": branch, "is_group": 0}):
        frappe.throw(f"Chi nhánh không tồn tại: {branch}")
    frappe.db.set_value("Channel Connection", name, "branch", branch or None)
    from mmm_custom.staff_sync import enqueue_sync

    enqueue_sync()
    return branch
