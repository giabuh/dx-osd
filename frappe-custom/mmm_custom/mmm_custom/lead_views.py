"""The CRM Leads list shows the same context as the admin customer dashboard (spec
2026-09-27-one-customer-record, B1): branch, course and hotness are quick filters next to the ones the
site already has."""

import json

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

LEAD_QUICK_FILTERS = ("territory", "ai_hotness", "course_interest")


def merge_filters(current, wanted=LEAD_QUICK_FILTERS):
    """Keep the site's quick filters and their order; append the missing wanted ones. Pure."""
    return list(current) + [f for f in wanted if f not in current]


def ensure_lead_quick_filters():
    """after_migrate. Without a saved setting the CRM uses the fields marked in_standard_filter, so that is
    the starting list."""
    name = frappe.db.exists("CRM Global Settings", {"dt": "CRM Lead", "type": "Quick Filters"})
    if name:
        current = json.loads(frappe.db.get_value("CRM Global Settings", name, "json") or "[]")
    else:
        current = [f.fieldname for f in frappe.get_meta("CRM Lead").fields if f.in_standard_filter]
    fields = {f.fieldname for f in frappe.get_meta("CRM Lead").fields}
    merged = merge_filters(current, [f for f in LEAD_QUICK_FILTERS if f in fields])
    if merged == current:
        return
    if name:
        frappe.db.set_value("CRM Global Settings", name, "json", json.dumps(merged))
    else:
        frappe.get_doc({"doctype": "CRM Global Settings", "dt": "CRM Lead", "type": "Quick Filters",
                        "json": json.dumps(merged)}).insert(ignore_permissions=True)
