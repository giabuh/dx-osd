"""Compute data quality indicators for CRM Leads.

Classifies each lead into one of three quality tiers:
- "Nghi trùng"      (red)    — duplicate email or phone found in another lead
- "Thiếu SĐT/Email" (orange) — no email AND no phone number
- "Đầy đủ"          (green)  — has contact info, no duplicates detected
"""

try:
    import frappe
except ImportError:
    from unittest.mock import MagicMock

    frappe = MagicMock()

_PLACEHOLDER_NAMES = ("Khách Messenger", "EduFlow Student", "")


def compute_data_quality(lead_name: str) -> str | None:
    """Compute and persist the *data_quality* field for a single CRM Lead.

    Returns the quality string, or ``None`` if the lead does not exist.
    """
    lead = frappe.db.get_value(
        "CRM Lead",
        lead_name,
        ["first_name", "email", "mobile_no"],
        as_dict=True,
    )
    if not lead:
        return None

    # 1. Duplicate detection — match on email or phone against other leads
    is_duplicate = False
    if lead.get("email"):
        dup_count = frappe.db.count(
            "CRM Lead",
            {"email": lead["email"], "name": ["!=", lead_name]},
        )
        if dup_count > 0:
            is_duplicate = True

    if not is_duplicate and lead.get("mobile_no"):
        dup_count = frappe.db.count(
            "CRM Lead",
            {"mobile_no": lead["mobile_no"], "name": ["!=", lead_name]},
        )
        if dup_count > 0:
            is_duplicate = True

    # 2. Classify
    if is_duplicate:
        quality = "Nghi trùng"
    elif not lead.get("email") and not lead.get("mobile_no"):
        quality = "Thiếu SĐT/Email"
    else:
        quality = "Đầy đủ"

    # 3. Persist
    frappe.db.set_value("CRM Lead", lead_name, "data_quality", quality)
    return quality


def recompute_all() -> dict:
    """Batch-recompute data_quality for every CRM Lead.

    Intended to be called via ``bench --site <site> execute
    mmm_custom.data_quality.recompute_all``.
    """
    leads = frappe.get_all("CRM Lead", pluck="name")
    stats: dict[str, int] = {}
    for name in leads:
        q = compute_data_quality(name)
        stats[q] = stats.get(q, 0) + 1
    frappe.db.commit()
    print(f"Recomputed {len(leads)} leads: {stats}")
    return stats
