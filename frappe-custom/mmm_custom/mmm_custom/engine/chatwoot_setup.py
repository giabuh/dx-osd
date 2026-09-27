"""Chatwoot conversation custom-attribute definitions for the bot's slots (D-027), so the values the bot
mirrors onto a conversation at handoff show in Chatwoot's sidebar. Idempotent; run after adding slots:

    bench --site crm.localhost execute mmm_custom.engine.chatwoot_setup.ensure_conversation_attributes
"""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.chatwoot_client import ChatwootClient


# (key, display name, Chatwoot attribute_display_type)
CONTACT_ATTRIBUTES = [("crm_lead_id", "Mã Lead CRM", "text"), ("khoa_hoc_quan_tam", "Khóa học quan tâm", "text"),
                      ("chi_nhanh", "Chi nhánh", "text"), ("trang_thai_lead", "Trạng thái khách", "text"),
                      ("ho_so_crm", "Hồ sơ CRM", "link")]


def plan_contact_attributes(existing_keys):
    return [attr for attr in CONTACT_ATTRIBUTES if attr[0] not in existing_keys]


def plan_attributes(slots, existing_keys):
    return [(f"bot_{s.key}", f"Bot · {s.label}") for s in slots if f"bot_{s.key}" not in existing_keys]


def ensure_conversation_attributes():
    from mmm_custom.engine.repo import load_catalog

    conf = frappe.conf
    client = ChatwootClient(conf.get("chatwoot_api_url") or "http://chatwoot-rails:3000", conf.get("chatwoot_api_token"),
                            int(conf.get("chatwoot_account_id") or 1))
    existing = {a.get("attribute_key") for a in client.list_custom_attributes()}
    created = []
    for key, name in plan_attributes(load_catalog().slots, existing):
        client.create_custom_attribute(key, name)
        created.append(key)
    existing = {a.get("attribute_key") for a in client.list_custom_attributes("contact_attribute")}
    for key, name, display_type in plan_contact_attributes(existing):  # what the bot writes on the contact
        client.create_custom_attribute(key, name, model="contact_attribute", display_type=display_type)
        created.append(key)
    return {"created": created}
