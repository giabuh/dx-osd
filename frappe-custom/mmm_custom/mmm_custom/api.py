import hashlib
import hmac
import json
import re
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
from mmm_custom.data_quality import compute_data_quality


COURSE_KEYWORD_PATTERNS = [
    (re.compile(r"\b(tiếng anh|tieng anh|english)\b", re.IGNORECASE), "Tiếng Anh"),
    (re.compile(r"\b(bơi lội|boi loi|bơi|swimming)\b", re.IGNORECASE), "Bơi lội"),
    (re.compile(r"\b(toán tư duy|toan tu duy|toán|math)\b", re.IGNORECASE), "Toán tư duy"),
]


def detect_course_interest(text: str | None) -> str | None:
    if not text or not isinstance(text, str):
        return None
    for pattern, course_name in COURSE_KEYWORD_PATTERNS:
        if pattern.search(text):
            return course_name
    return None


def extract_message_text(conversation: dict, payload: dict) -> str:
    messages = conversation.get("messages") or payload.get("messages") or []
    texts = []
    if isinstance(messages, list):
        for msg in messages:
            if isinstance(msg, dict) and msg.get("content"):
                texts.append(str(msg.get("content")))
            elif isinstance(msg, str):
                texts.append(msg)
    if payload.get("content") and isinstance(payload.get("content"), str):
        texts.append(payload.get("content"))
    return " ".join(texts)


_PLACEHOLDER_NAME = "Khách Messenger"


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
    secret = conf.get("chatwoot_webhook_secret") if conf else None
    if not secret:
        # No built-in fallback: a default secret in a public repo would let anyone forge webhooks.
        frappe.throw("chatwoot_webhook_secret is not configured", frappe.AuthenticationError)
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
    meta = payload.get("meta") or conversation.get("meta") or {}
    meta_sender = meta.get("sender") if isinstance(meta, dict) else {}
    contact = (
        contact_inbox.get("contact")
        or meta_sender
        or conversation.get("sender")
        or payload.get("sender")
        or {}
    )
    contact_id = contact.get("id")
    raw_name = contact.get("name")
    first_name = str(raw_name).strip() if raw_name and str(raw_name).strip() else _PLACEHOLDER_NAME
    email = contact.get("email")
    phone = contact.get("phone_number") or contact.get("phone")
    custom_attrs = contact.get("custom_attributes") or {}
    crm_lead_id = custom_attrs.get("crm_lead_id")

    msg_text = extract_message_text(conversation, payload)
    course_interest = detect_course_interest(msg_text)

    # 2. Dedup & Lead Convergence — 3-tier: crm_lead_id → chatwoot_contact_id → email/phone
    if crm_lead_id and frappe.db.exists("CRM Lead", crm_lead_id):
        lead_name = crm_lead_id
        if contact_id:
            frappe.db.set_value("CRM Lead", lead_name, "chatwoot_contact_id", str(contact_id))
        if course_interest:
            frappe.db.set_value("CRM Lead", lead_name, "course_interest", course_interest)
        # Fix placeholder name if we now have the real name
        if first_name != _PLACEHOLDER_NAME:
            stored = frappe.db.get_value(
                "CRM Lead", lead_name, ["first_name", "lead_name"], as_dict=True,
            )
            if stored and stored.get("first_name") in (
                _PLACEHOLDER_NAME, "EduFlow Student", None, "",
            ):
                frappe.db.set_value("CRM Lead", lead_name, "first_name", first_name)
                frappe.db.set_value("CRM Lead", lead_name, "lead_name", first_name)
    elif contact_id and frappe.db.exists("CRM Lead", {"chatwoot_contact_id": str(contact_id)}):
        lead_name = frappe.db.get_value("CRM Lead", {"chatwoot_contact_id": str(contact_id)}, "name")
        if course_interest:
            frappe.db.set_value("CRM Lead", lead_name, "course_interest", course_interest)
        # Fix placeholder name if we now have the real name
        if first_name != _PLACEHOLDER_NAME:
            stored = frappe.db.get_value(
                "CRM Lead", lead_name, ["first_name", "lead_name"], as_dict=True,
            )
            if stored and stored.get("first_name") in (
                _PLACEHOLDER_NAME, "EduFlow Student", None, "",
            ):
                frappe.db.set_value("CRM Lead", lead_name, "first_name", first_name)
                frappe.db.set_value("CRM Lead", lead_name, "lead_name", first_name)
    else:
        matched = find_matching_lead(email, phone)
        if matched:
            lead_name = matched.name if hasattr(matched, "name") else matched.get("name")
            if contact_id:
                frappe.db.set_value("CRM Lead", lead_name, "chatwoot_contact_id", str(contact_id))
            if course_interest:
                frappe.db.set_value("CRM Lead", lead_name, "course_interest", course_interest)
            # Fix placeholder name if we now have the real name
            if first_name != _PLACEHOLDER_NAME:
                stored = frappe.db.get_value(
                    "CRM Lead", lead_name, ["first_name", "lead_name"], as_dict=True,
                )
                if stored and stored.get("first_name") in (
                    _PLACEHOLDER_NAME, "EduFlow Student", None, "",
                ):
                    frappe.db.set_value("CRM Lead", lead_name, "first_name", first_name)
                    frappe.db.set_value("CRM Lead", lead_name, "lead_name", first_name)
        else:
            lead_data = {
                "doctype": "CRM Lead",
                "first_name": first_name,
                "email": email,
                "mobile_no": normalize_phone(phone),
                "source": "Messenger",
                "chatwoot_contact_id": str(contact_id) if contact_id is not None else None,
            }
            if course_interest:
                lead_data["course_interest"] = course_interest
            lead = frappe.get_doc(lead_data).insert(ignore_permissions=True)
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
            "title": f"Chatwoot #{conv_id}",
            "content": first_msg,
            "reference_doctype": "CRM Lead",
            "reference_docname": lead_name,
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

    # 5. Compute data quality indicator
    try:
        compute_data_quality(lead_name)
    except Exception:
        pass

    return {"status": "success", "lead_id": lead_name}
