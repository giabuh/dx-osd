"""Branch scope for consultants (spec 2026-09-27-one-customer-record, B2), plugged into Frappe CRM's
record permissions through the `crm_record_scope` hook (crm/permissions/org_hierarchy.py).

On top of what the CRM already shows a Sales User (own and assigned records), a consultant sees:
- with a branch: every Lead/Deal whose territory is that branch;
- B2B: every Lead/Deal owned by a B2B consultant;
- central team (no branch, not B2B): every Lead/Deal without a territory.
Managers are not affected: the CRM already shows them everything.
"""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

OWNER_FIELD = {"CRM Lead": "lead_owner", "CRM Deal": "deal_owner"}


def rule(consultant):
    """Consultant row (branch, handles_b2b) → ("branch", name) | ("b2b", None) | ("central", None);
    None when the user is not an active consultant. Pure."""
    if not consultant:
        return None
    if consultant.get("branch"):
        return ("branch", consultant["branch"])
    if consultant.get("handles_b2b"):
        return ("b2b", None)
    return ("central", None)


def record_scope(user, doctype, DT):
    if doctype not in OWNER_FIELD:
        return None
    consultant = frappe.db.get_value("Consultant", {"name": user, "active": 1}, ["branch", "handles_b2b"],
                                     as_dict=True)
    kind, branch = rule(consultant) or (None, None)
    if kind == "branch":
        return DT.territory == branch
    if kind == "b2b":
        b2b = frappe.get_all("Consultant", filters={"handles_b2b": 1, "active": 1}, pluck="name")
        return DT[OWNER_FIELD[doctype]].isin(b2b or [user])
    if kind == "central":
        return DT.territory.isnull() | (DT.territory == "")
    return None
