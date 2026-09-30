"""What a conversation's slots mean for the CRM Lead, both ways (D-014, D-022, D-070) — pure.

Each Bot Slot names its Lead field in `lead_field`: `products` appends the course to the Lead's
standard products table, `territory` stores the branch, anything else is set as is (choice slots
store the option label, which is what a person reads in the CRM)."""

from mmm_custom.engine.state import filled, value

PLACEHOLDER_NAMES = ("Khách Messenger", "EduFlow Student", "")


def lead_updates(slots, catalog):
    fields, courses = {}, []
    for slot in catalog.slots:
        if not slot.lead_field or not filled(slots, slot.key):
            continue
        raw = value(slots, slot.key)
        if slot.lead_field == "products":
            if raw in catalog.courses:
                courses.append(catalog.courses[raw])
        elif slot.type == "choice":
            option = slot.option(raw)
            fields[slot.lead_field] = option.label if option else raw
        else:
            fields[slot.lead_field] = raw
    return fields, courses


def _entry(val, source):
    return {"value": val, "source": source, "confidence": 1.0}


def prefill_slots(lead_values, catalog):
    """Known facts from an existing Lead (source "lead"); never `products` — every conversation asks
    what the customer wants now (D-070). Values the catalog does not know are left for the bot to ask."""
    out = {}
    for slot in catalog.slots:
        if not slot.lead_field or slot.lead_field == "products":
            continue
        raw = lead_values.get(slot.lead_field)
        if raw in (None, "", 0):
            continue
        if slot.type == "catalog":
            known = catalog.branches if slot.source == "branch" else catalog.courses
            if raw not in known:
                continue
        elif slot.type == "choice":
            option = next((o for o in slot.options if raw in (o.label, o.value)), None)
            if not option:
                continue
            raw = option.value
        elif slot.lead_field == "first_name" and raw in PLACEHOLDER_NAMES:
            continue
        out[slot.key] = _entry(raw, "lead")
    return out


def contact_prefill(contact, catalog):
    """The name Facebook/Chatwoot already knows fills the name slot, so the bot never asks it."""
    name = " ".join(str(contact.get("name") or "").split())
    slot = next((s for s in catalog.slots if s.lead_field == "first_name"), None)
    if not slot or name in PLACEHOLDER_NAMES:
        return {}
    return {slot.key: _entry(name, "contact")}


def contact_update(fields, courses, lead, crm_url=""):
    """What the bot learned, for the Chatwoot contact: consultants read it in the inbox without the CRM.
    Only values known in this write; Chatwoot merges custom_attributes, so earlier values stay. The Lead status
    (`trang_thai_lead`) is not here: it follows the Lead's real status on every save (lifecycle.on_lead_update).
    With `crm_url` (the CRM's public base URL) the contact also links back to the Lead (ho_so_crm)."""
    from mmm_custom.crm_links import lead_url

    attrs = {"crm_lead_id": lead, "khoa_hoc_quan_tam": ", ".join(c.name for c in courses),
             "chi_nhanh": fields.get("territory") or "",
             "ho_so_crm": lead_url(crm_url, lead) if crm_url and lead else ""}
    out = {"custom_attributes": {k: v for k, v in attrs.items() if v}}
    if fields.get("mobile_no"):
        out["phone_number"] = fields["mobile_no"]
    return out
