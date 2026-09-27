"""Standalone administration page (/admin; /bot redirects here)."""

from pathlib import Path

import frappe

from mmm_custom.desk import can_open_bot

SCRIPT = Path(__file__).resolve().parent.parent / "public" / "js" / "bot_page.js"


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.flags.redirect_location = "/login?redirect-to=/admin"
        raise frappe.Redirect(302)
    if not can_open_bot():
        frappe.throw("Bạn không có quyền xem trang quản trị.", frappe.PermissionError)
    context.no_cache = 1
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.chatwoot_url = frappe.conf.get("chatwoot_base_url") or "http://127.0.0.1:3000"
    context.asset_version = int(SCRIPT.stat().st_mtime)  # assets are cached 12 h; a changed file gets a new URL
