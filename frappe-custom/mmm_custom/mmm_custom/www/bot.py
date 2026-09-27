"""Standalone bot administration page."""

import frappe

from mmm_custom.desk import can_open_bot


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.flags.redirect_location = "/login?redirect-to=/bot"
        raise frappe.Redirect(302)
    if not can_open_bot():
        frappe.throw("Bạn không có quyền xem trang bot.", frappe.PermissionError)
    context.no_cache = 1
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.chatwoot_url = frappe.conf.get("chatwoot_base_url") or "http://127.0.0.1:3000"
