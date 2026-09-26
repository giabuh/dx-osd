"""Chatwoot conversation custom-attribute definitions for the bot's slots (D-027), so the values the bot
mirrors onto a conversation at handoff show in Chatwoot's sidebar. Idempotent; run after adding slots:

    bench --site crm.localhost execute mmm_custom.engine.chatwoot_setup.ensure_conversation_attributes
"""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.chatwoot_client import ChatwootClient


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
    return {"created": created}
