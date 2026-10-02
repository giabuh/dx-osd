"""Compute data quality indicators for CRM Leads.

Classifies each lead into data quality tiers:
- "Nghi trùng"       (red)    — same contact (phone or email) and a shared course at the same branch: one person
                                 entered twice
- "Trùng chi nhánh"  (amber)  — same contact and a shared course at a DIFFERENT branch: two branches are working
                                 the same customer for the same course
- "Thiếu SĐT/Email"  (orange) — no email AND no phone number
- "Đầy đủ"           (green)  — has contact info, no conflict (the same person learning another course is fine)

`classify` and `course_keys` are pure; `compute_data_quality` reads and writes the database. The Lead that caused
the flag is kept in `duplicate_of` so staff can open it.
"""

try:
    import frappe
except ImportError:
    frappe = None

from mmm_custom.dedupe import normalize_phone

COMPLETE, NO_CONTACT, DUPLICATE, CROSS_BRANCH = "Đầy đủ", "Thiếu SĐT/Email", "Nghi trùng", "Trùng chi nhánh"
QUALITIES = (COMPLETE, NO_CONTACT, DUPLICATE, CROSS_BRANCH)
SELECT_OPTIONS = "\n" + "\n".join(QUALITIES)  # the options of the CRM Lead `data_quality` Select (setup.py)

_PLACEHOLDER_NAMES = ("Khách Messenger", "EduFlow Student", "")


def _norm(val):
    return (str(val) if val is not None else "").strip().lower()


def course_keys(products=(), course_interest=""):
    """Everything that names a lead's courses: product codes and names, and the readable `course_interest`
    summary ("Tin học cơ bản, Photoshop"). Two leads share a course when these sets intersect. Pure."""
    keys = set()
    for p in products or ():
        keys.update(_norm(p.get(k)) for k in ("product_code", "product_name"))
    keys.update(_norm(x) for x in str(course_interest or "").split(","))
    keys.discard("")
    return frozenset(keys)


def phone_variants(phone):
    """The forms one Vietnamese number is stored in: +84901234567 and 0901234567. Pure."""
    norm = normalize_phone(phone)
    if not norm:
        return []
    out = [norm]
    if norm.startswith("+84"):
        out.append("0" + norm[3:])
    if str(phone).strip() not in out:
        out.append(str(phone).strip())
    return out


def classify(lead, others):
    """(quality, conflicting lead) for a lead with contact info. `lead` / `others`: {name, territory, courses}.

    A match that shares no course (both sides name their courses and they differ) is the same person learning
    another course, not a duplicate. A match with no course on either side counts as a conflict: nothing says it
    is another course. Same branch wins over another branch: two records of one person is the worse problem. Pure."""
    same, cross = [], []
    mine = lead.get("courses") or frozenset()
    for other in others:
        theirs = other.get("courses") or frozenset()
        if mine and theirs and not (mine & theirs):
            continue
        a, b = _norm(lead.get("territory")), _norm(other.get("territory"))
        (cross if a and b and a != b else same).append(other["name"])
    if same:
        return DUPLICATE, same[0]
    if cross:
        return CROSS_BRANCH, cross[0]
    return COMPLETE, ""


# ── Bench side ─────────────────────────────────────────────────────────────────────────────────────


def _matches(lead_name, email, phone):
    """Other Leads with the same email or the same phone (in any stored form)."""
    found = {}
    fields = ["name", "territory", "course_interest"]
    if email:
        for r in frappe.get_all("CRM Lead", filters={"email": email, "name": ["!=", lead_name]}, fields=fields):
            found[r["name"]] = r
    variants = phone_variants(phone)
    if variants:
        for r in frappe.get_all("CRM Lead", filters={"mobile_no": ["in", variants], "name": ["!=", lead_name]},
                                fields=fields):
            found.setdefault(r["name"], r)
    return list(found.values())


def _products(names):
    rows = frappe.get_all("CRM Products", filters={"parenttype": "CRM Lead", "parent": ["in", list(names)]},
                          fields=["parent", "product_code", "product_name"])
    out = {}
    for r in rows:
        out.setdefault(r["parent"], []).append(r)
    return out


def _save(lead_name, quality, duplicate_of):
    values = {"data_quality": quality}
    if frappe.get_meta("CRM Lead").has_field("duplicate_of"):
        values["duplicate_of"] = duplicate_of or None
    frappe.db.set_value("CRM Lead", lead_name, values, update_modified=False)


def compute_data_quality(lead_name: str, sync_matching: bool = True) -> str | None:
    """Compute and persist the *data_quality* field (and `duplicate_of`) for a single CRM Lead; with
    `sync_matching` the Leads it matches are recomputed too, so both sides of a pair show the flag.

    Returns the quality string, or ``None`` if the lead does not exist.
    """
    lead = frappe.db.get_value("CRM Lead", lead_name, ["email", "mobile_no", "territory", "course_interest"],
                               as_dict=True)
    if not lead:
        return None
    others = []
    if not lead.get("email") and not lead.get("mobile_no"):
        quality, duplicate_of = NO_CONTACT, ""
    else:
        others = _matches(lead_name, lead.get("email"), lead.get("mobile_no"))
        products = _products([lead_name] + [o["name"] for o in others]) if others else {}
        me = {"name": lead_name, "territory": lead.get("territory"),
              "courses": course_keys(products.get(lead_name), lead.get("course_interest"))}
        them = [{"name": o["name"], "territory": o.get("territory"),
                 "courses": course_keys(products.get(o["name"]), o.get("course_interest"))} for o in others]
        quality, duplicate_of = classify(me, them)
    _save(lead_name, quality, duplicate_of)
    if sync_matching:
        for other in others:
            compute_data_quality(other["name"], sync_matching=False)
    return quality


def on_lead_update(doc, method=None):
    """doc_events hook for CRM Lead on_update."""
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
