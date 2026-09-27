"""`consultant_corrected` learning signals (D-057): a person changed a Lead's branch or course away from
what the bot set. Hooked on CRM Lead on_update; the engine's own saves carry doc.flags.lead_engine."""

import json

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

LEAD_FIELDS = (("branch", "territory"), ("course", "products"))


def corrections(before, after, bot_slots, catalog):
    out = []
    for source, field in LEAD_FIELDS:
        slot = catalog.slot_for(source)
        entry = (bot_slots.get(slot.key) or {}) if slot else {}
        bot_value = entry.get("value")
        if not bot_value or entry.get("source") == "lead":
            continue
        was, now = before.get(field), after.get(field)
        if field == "products":
            if bot_value in (was or []) and bot_value not in (now or []):
                out.append({"field": field, "bot_value": bot_value, "new_value": ", ".join(now or [])})
        elif was == bot_value and now != bot_value:
            out.append({"field": field, "bot_value": bot_value, "new_value": now or ""})
    return out


def _snapshot(doc):
    return {"territory": doc.get("territory"), "products": [p.product_code for p in doc.get("products") or []]}


def on_lead_update(doc, method=None):
    if doc.flags.get("lead_engine"):
        return
    before = doc.get_doc_before_save()
    if not before:
        return
    conv = frappe.get_all("Bot Conversation", filters={"lead": doc.name, "is_sandbox": 0}, fields=["name", "slots"],
                          order_by="modified desc", limit=1)
    if not conv:
        return
    from mmm_custom.engine.repo import load_catalog

    for change in corrections(_snapshot(before), _snapshot(doc), json.loads(conv[0].slots or "{}"), load_catalog()):
        frappe.get_doc({"doctype": "Bot Learning Signal", "signal_type": "consultant_corrected", "status": "new",
                        "bot_conversation": conv[0].name, "lead": doc.name,
                        "details": json.dumps(change, ensure_ascii=False)}).insert(ignore_permissions=True)
