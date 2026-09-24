import hashlib
import hmac
import json
import time

try:
    import requests
except ImportError:
    requests = None

try:
    import frappe
except ImportError:
    # Standalone environment support (for unit tests outside Frappe bench)
    from unittest.mock import MagicMock

    class AuthenticationError(Exception):
        pass

    frappe = MagicMock()

    def _whitelist(*args, **kwargs):
        def decorator(f):
            return f

        return decorator

    def _throw(msg, exc=Exception, *args, **kwargs):
        if isinstance(exc, type) and issubclass(exc, BaseException):
            raise exc(msg)
        raise Exception(msg)

    frappe.whitelist = _whitelist
    frappe.AuthenticationError = AuthenticationError
    frappe.throw = _throw

from mmm_custom.dedupe import find_matching_lead, normalize_phone


@frappe.whitelist(allow_guest=True)
def chatwoot_sync():
    req = frappe.request
    ts = req.headers.get("X-Chatwoot-Timestamp") if hasattr(req, "headers") else None
    sig = req.headers.get("X-Chatwoot-Signature", "") if hasattr(req, "headers") else ""

    if hasattr(req, "get_data") and callable(req.get_data):
        raw_body = req.get_data()
    elif hasattr(req, "data"):
        raw_body = req.data
    else:
        raw_body = b""

    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")
    elif not isinstance(raw_body, bytes):
        raw_body = bytes(raw_body or b"")

    conf = getattr(frappe, "conf", None)
    secret = (conf.get("chatwoot_webhook_secret") if conf else None) or "dx_osd_shared_webhook_secret_2026"
    secret_bytes = secret.encode("utf-8") if isinstance(secret, str) else secret

    # 1. Anti Replay Attack & Verify HMAC Signature
    if not ts:
        frappe.throw("Timestamp expired or missing", frappe.AuthenticationError)

    try:
        ts_val = float(ts)
    except (ValueError, TypeError):
        frappe.throw("Timestamp expired or missing", frappe.AuthenticationError)

    if abs(time.time() - ts_val) > 300:
        frappe.throw("Timestamp expired or missing", frappe.AuthenticationError)

    hex_digest = hmac.new(
        secret_bytes,
        f"{ts}.".encode("utf-8") + raw_body,
        hashlib.sha256,
    ).hexdigest()
    expected = "sha256=" + hex_digest

    if not sig or not (
        hmac.compare_digest(expected, sig) or hmac.compare_digest(hex_digest, sig)
    ):
        frappe.throw("Invalid HMAC signature", frappe.AuthenticationError)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {"status": "error", "message": "Invalid JSON body"}

    if not isinstance(payload, dict):
        return {"status": "error", "message": "Invalid JSON body"}

    if payload.get("event") != "conversation_created":
        return {"status": "ignored", "event": payload.get("event")}

    conversation = payload.get("conversation") or payload
    contact_inbox = conversation.get("contact_inbox") or payload.get("contact_inbox") or {}
    contact = contact_inbox.get("contact") or conversation.get("sender") or payload.get("sender") or {}
    contact_id = contact.get("id")
    raw_name = contact.get("name")
    first_name = str(raw_name).strip() if raw_name and str(raw_name).strip() else "EduFlow Student"
    email = contact.get("email")
    phone = contact.get("phone_number") or contact.get("phone")
    custom_attrs = contact.get("custom_attributes") or {}
    crm_lead_id = custom_attrs.get("crm_lead_id")

    # 2. Dedup & Lead Convergence
    if crm_lead_id and frappe.db.exists("CRM Lead", crm_lead_id):
        lead_name = crm_lead_id
        if contact_id:
            frappe.db.set_value("CRM Lead", lead_name, "chatwoot_contact_id", str(contact_id))
    else:
        matched = find_matching_lead(email, phone)
        if matched:
            lead_name = matched.name if hasattr(matched, "name") else matched.get("name")
            if contact_id:
                frappe.db.set_value("CRM Lead", lead_name, "chatwoot_contact_id", str(contact_id))
        else:
            lead = frappe.get_doc({
                "doctype": "CRM Lead",
                "first_name": first_name,
                "email_id": email,
                "mobile_no": normalize_phone(phone),
                "lead_source": "Messenger",
                "chatwoot_contact_id": str(contact_id) if contact_id is not None else None,
            }).insert(ignore_permissions=True)
            lead_name = lead.name

    # 3. Log conversation to FCRM Note
    try:
        messages = conversation.get("messages") or payload.get("messages") or []
        first_msg = (
            messages[0].get("content")
            if messages and isinstance(messages[0], dict) and messages[0].get("content")
            else "New conversation via Messenger"
        )
        conv_id = conversation.get("id") or payload.get("id") or ""
        frappe.get_doc({
            "doctype": "FCRM Note",
            "parent": lead_name,
            "parenttype": "CRM Lead",
            "parentfield": "notes",
            "content": f"[Chatwoot #{conv_id}]: {first_msg}",
        }).insert(ignore_permissions=True)
    except Exception as e:
        if hasattr(frappe, "log_error"):
            frappe.log_error(f"Failed to create FCRM Note: {str(e)}")

    # 4. Write back crm_lead_id to Chatwoot Contact
    chatwoot_url = (conf.get("chatwoot_api_url") if conf else None) or "http://127.0.0.1:3000"
    chatwoot_token = conf.get("chatwoot_api_token") if conf else None
    if chatwoot_token and contact_id and requests:
        try:
            requests.put(
                f"{chatwoot_url}/api/v1/accounts/1/contacts/{contact_id}",
                headers={"api_access_token": chatwoot_token},
                json={"custom_attributes": {"crm_lead_id": lead_name}},
                timeout=5,
            )
        except Exception as e:
            if hasattr(frappe, "log_error"):
                frappe.log_error(f"Failed to update Chatwoot contact: {str(e)}")

    return {"status": "success", "lead_id": lead_name}
