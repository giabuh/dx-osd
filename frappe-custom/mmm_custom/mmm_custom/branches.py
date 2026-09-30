"""One branch field (D-116): the standard `territory` is the Lead's branch everywhere (engine, list, scope,
routing). The legacy `branch` select (CS1 Bình Thạnh…) is hidden; a value still written to it — old sites,
scripts/comment-reply.py — fills `territory` when that is empty."""

import re

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine.text import fold


def _key(name):
    return fold(re.sub(r"^\s*(cs|cn)\s*\d*\s+", "", fold(name or "")))


def territory_for_branch(branch, territories):
    """The branch territory a legacy value names: "CS1 Bình Thạnh" → "CN Bình Thạnh" (by name or alias).
    `territories`: [{name, aliases}] of branch (non-group) territories. None when nothing matches."""
    key = _key(branch)
    if not key:
        return None
    for t in territories:
        names = [_key(t["name"])] + [fold(a) for a in (t.get("aliases") or "").split(",") if a.strip()]
        if key in names:
            return t["name"]
    return None


def _branches():
    return frappe.get_all("CRM Territory", filters={"is_group": 0}, fields=["name", "aliases"])


def fill_territory(doc, method=None):
    """doc_events CRM Lead validate."""
    if doc.get("branch") and not doc.get("territory"):
        doc.territory = territory_for_branch(doc.branch, _branches())


def migrate():
    """after_migrate: hide the legacy field and give Leads that only have it their territory (`modified` stays)."""
    name = "CRM Lead-branch"
    if not frappe.db.exists("Custom Field", name):
        return
    frappe.db.set_value("Custom Field", name, {"hidden": 1, "in_list_view": 0, "in_standard_filter": 0})
    frappe.clear_cache(doctype="CRM Lead")
    territories = _branches()
    for row in frappe.get_all("CRM Lead", filters={"branch": ["is", "set"], "territory": ["is", "not set"]},
                              fields=["name", "branch"], limit_page_length=0):
        territory = territory_for_branch(row.branch, territories)
        if territory:
            frappe.db.set_value("CRM Lead", row.name, "territory", territory, update_modified=False)
    frappe.db.commit()
