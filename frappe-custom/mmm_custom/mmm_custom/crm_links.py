"""Links between a Chatwoot contact and its CRM Lead: the `ho_so_crm` contact attribute points at the Lead.
The Lead page reads and answers the conversation itself (mmm_custom.lead_chat, "Tin nhắn" tab); the first
version's "Mở cuộc chat" form script is switched off on migrate."""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

import logging
from urllib.parse import quote

whitelist = frappe.whitelist if frappe else (lambda **kw: (lambda fn: fn))
logger = logging.getLogger(__name__)

DEFAULT_CRM_URL = "http://127.0.0.1:8000"
DEFAULT_CHATWOOT_URL = "http://127.0.0.1:3000"
FORM_SCRIPT = "Mở cuộc chat (mmm_custom)"  # replaced by the Lead page's "Tin nhắn" tab


def crm_base(conf):
    return (conf.get("crm_public_url") or DEFAULT_CRM_URL).rstrip("/")


def chatwoot_base(conf):
    return (conf.get("chatwoot_base_url") or DEFAULT_CHATWOOT_URL).rstrip("/")


def lead_url(base, lead):
    return f"{base.rstrip('/')}/crm/leads/{quote(str(lead), safe='')}"


def chatwoot_contact_url(base, account_id, contact_id):
    return f"{base.rstrip('/')}/app/accounts/{int(account_id)}/contacts/{int(contact_id)}"


@whitelist()
def open_chat_url(lead):
    """The Chatwoot contact page for a Lead, or None when the Lead never chatted."""
    if not frappe.has_permission("CRM Lead", "read", lead):
        frappe.throw("Bạn không có quyền xem Lead này.", frappe.PermissionError)
    contact_id = frappe.db.get_value("CRM Lead", lead, "chatwoot_contact_id")
    if not str(contact_id or "").strip().isdigit():
        return None
    conf = frappe.conf
    return chatwoot_contact_url(chatwoot_base(conf), conf.get("chatwoot_account_id") or 1, contact_id)


def retire_lead_form_script():
    """after_migrate: switch off the "Mở cuộc chat" form script sites got from the first version."""
    if frappe.db.get_value("CRM Form Script", FORM_SCRIPT, "enabled"):
        frappe.db.set_value("CRM Form Script", FORM_SCRIPT, "enabled", 0)


def backfill_contact_links():
    """Write ho_so_crm on every Chatwoot contact a Lead links to. Run by hand:

        bench --site crm.localhost execute mmm_custom.crm_links.backfill_contact_links
    """
    from mmm_custom.chatwoot_client import ChatwootClient

    conf = frappe.conf
    client = ChatwootClient(conf.get("chatwoot_api_url") or "http://chatwoot-rails:3000", conf.get("chatwoot_api_token"),
                            int(conf.get("chatwoot_account_id") or 1))
    base = crm_base(conf)
    updated = failed = 0
    for lead in frappe.get_all("CRM Lead", filters={"chatwoot_contact_id": ["is", "set"]},
                               fields=["name", "chatwoot_contact_id"]):
        try:
            client.update_contact(int(lead.chatwoot_contact_id), {"ho_so_crm": lead_url(base, lead.name)})
            updated += 1
        except Exception:
            logger.exception("ho_so_crm backfill failed for %s", lead.name)
            failed += 1
    return {"updated": updated, "failed": failed}
