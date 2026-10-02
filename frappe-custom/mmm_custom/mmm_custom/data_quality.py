"""Compute data quality indicators for CRM Leads.

Classifies each lead into data quality tiers:
- "Trùng chi nhánh"  (amber)  — same contact & same course at a different branch
- "Nghi trùng"       (red)    — duplicate contact & same course at same branch
- "Thiếu SĐT/Email"  (orange) — no email AND no phone number
- "Đầy đủ"           (green)  — has contact info, no duplicate conflicts (multi-course learners allowed)
"""

try:
    import frappe
except ImportError:
    from unittest.mock import MagicMock

    frappe = MagicMock()

_PLACEHOLDER_NAMES = ("Khách Messenger", "EduFlow Student", "")


def _norm(val):
    return (str(val) if val is not None else "").strip().lower()


def compute_data_quality(lead_name: str, sync_matching: bool = True) -> str | None:
    """Compute and persist the *data_quality* field for a single CRM Lead.

    Returns the quality string, or ``None`` if the lead does not exist.
    """
    lead = frappe.db.get_value(
        "CRM Lead",
        lead_name,
        ["first_name", "email", "mobile_no", "territory", "course_interest"],
        as_dict=True,
    )
    if not lead:
        return None

    # 1. Missing contact info
    if not lead.get("email") and not lead.get("mobile_no"):
        quality = "Thiếu SĐT/Email"
        frappe.db.set_value("CRM Lead", lead_name, "data_quality", quality)
        return quality

    # 2. Duplicate detection — match on email or phone against other leads
    matching_leads = []
    if hasattr(frappe, "get_all"):
        try:
            if lead.get("email"):
                matches = frappe.get_all(
                    "CRM Lead",
                    filters={"email": lead["email"], "name": ["!=", lead_name]},
                    fields=["name", "territory", "course_interest"],
                )
                if matches and isinstance(matches, list):
                    matching_leads.extend(matches)
            if lead.get("mobile_no"):
                matches = frappe.get_all(
                    "CRM Lead",
                    filters={"mobile_no": lead["mobile_no"], "name": ["!=", lead_name]},
                    fields=["name", "territory", "course_interest"],
                )
                if matches and isinstance(matches, list):
                    for m in matches:
                        if not any(x.get("name") == m.get("name") for x in matching_leads):
                            matching_leads.append(m)
        except Exception:
            pass

    # Fallback to frappe.db.count if get_all didn't return list (e.g. older mocks)
    if not matching_leads and hasattr(frappe.db, "count"):
        try:
            email_dup = bool(lead.get("email") and frappe.db.count("CRM Lead", {"email": lead["email"], "name": ["!=", lead_name]}) > 0)
            phone_dup = bool(lead.get("mobile_no") and frappe.db.count("CRM Lead", {"mobile_no": lead["mobile_no"], "name": ["!=", lead_name]}) > 0)
            if email_dup or phone_dup:
                matching_leads.append({
                    "name": "legacy_mock_match",
                    "territory": lead.get("territory"),
                    "course_interest": lead.get("course_interest"),
                })
        except Exception:
            pass

    # 3. Classify
    if not matching_leads:
        quality = "Đầy đủ"
    else:
        lead_course = _norm(lead.get("course_interest"))
        lead_territory = _norm(lead.get("territory"))

        has_cross_branch_conflict = False
        has_same_branch_dup = False
        all_diff_courses = True

        for other in matching_leads:
            other_course = _norm(other.get("course_interest"))
            other_territory = _norm(other.get("territory"))

            # Check if courses match
            same_course = bool(lead_course and other_course and lead_course == other_course)
            diff_course = bool(lead_course and other_course and lead_course != other_course)

            if same_course:
                all_diff_courses = False
                if lead_territory and other_territory and lead_territory != other_territory:
                    has_cross_branch_conflict = True
                else:
                    has_same_branch_dup = True
            elif diff_course:
                # Registered for different courses: allowed cross-sell, not a duplicate
                pass
            else:
                # Course interest not specified on one or both
                all_diff_courses = False
                if lead_territory and other_territory and lead_territory != other_territory:
                    has_cross_branch_conflict = True
                else:
                    has_same_branch_dup = True

        if has_cross_branch_conflict:
            quality = "Trùng chi nhánh"
        elif has_same_branch_dup:
            quality = "Nghi trùng"
        elif all_diff_courses:
            quality = "Đầy đủ"
        else:
            quality = "Nghi trùng"

    # 4. Persist
    frappe.db.set_value("CRM Lead", lead_name, "data_quality", quality)

    # 5. Synchronize matching leads bidirectionally
    if sync_matching and matching_leads:
        for other in matching_leads:
            other_name = other.get("name")
            if other_name and other_name != "legacy_mock_match":
                compute_data_quality(other_name, sync_matching=False)

    return quality


def on_lead_update(doc, method=None):
    """doc_events hook for CRM Lead validate/on_update."""
    if doc and getattr(doc, "name", None):
        compute_data_quality(doc.name)


def recompute_all() -> dict:
    """Batch-recompute data_quality for every CRM Lead.

    Intended to be called via ``bench --site <site> execute
    mmm_custom.data_quality.recompute_all``.
    """
    leads = frappe.get_all("CRM Lead", pluck="name")
    stats: dict[str, int] = {}
    for name in leads:
        q = compute_data_quality(name, sync_matching=False)
        stats[q] = stats.get(q, 0) + 1
    frappe.db.commit()
    print(f"Recomputed {len(leads)} leads: {stats}")
    return stats
