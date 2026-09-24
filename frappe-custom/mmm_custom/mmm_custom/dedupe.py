import re


def normalize_phone(phone_str: str) -> str:
    """Normalize phone number to international format (+84 for Vietnam).

    Removes spaces, hyphens, and formats local 0-prefix numbers to +84.
    Returns empty string if phone_str is empty or None.
    """
    if not phone_str:
        return ""
    cleaned = re.sub(r"[^0-9+]", "", str(phone_str))
    if not cleaned:
        return ""
    if cleaned.startswith("+84"):
        return cleaned
    if cleaned.startswith("0") and len(cleaned) in [10, 11]:
        return "+84" + cleaned[1:]
    return cleaned


def build_lead_search_filters(email: str = None, phone: str = None) -> list:
    """Build OR search filters for querying CRM Lead by email or mobile_no.

    Returns a list of condition triplets, e.g.:
    [["email_id", "=", "test@example.com"], ["mobile_no", "=", "+84901234567"]]
    Returns [] if neither email nor phone is provided.
    """
    filters = []
    if email and str(email).strip():
        filters.append(["email_id", "=", str(email).strip()])
    norm_phone = normalize_phone(phone)
    if norm_phone:
        filters.append(["mobile_no", "=", norm_phone])
    return filters


def find_matching_lead(email: str = None, phone: str = None):
    """Query Frappe CRM for an existing Lead matching email OR mobile_no.

    Guarded against environments where frappe is not installed (e.g. standalone test runner).
    Returns the first matching lead dict or None.
    """
    try:
        import frappe

        if frappe is None:
            return None
    except ImportError:
        return None

    filters = build_lead_search_filters(email, phone)
    if not filters:
        return None

    leads = frappe.get_all(
        "CRM Lead",
        or_filters=filters,
        fields=["name", "first_name", "email_id", "mobile_no", "chatwoot_contact_id"],
        limit=1,
    )
    return leads[0] if leads else None
