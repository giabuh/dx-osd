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

from mmm_custom.data_quality import compute_data_quality
from mmm_custom.engine.repo import ensure_lead, load_catalog
from mmm_custom.engine.understand import match_courses
from mmm_custom.intelligence import enqueue_analysis, enqueue_on_assignment
from mmm_custom.sources import channel_key, source_name


def detect_courses(text, catalog=None):
    """Courses named in the text, matched against the CRM catalog aliases (C2.4 replaces 3 hardcoded courses)."""
    if not text or not isinstance(text, str):
        return []
    try:
        catalog = catalog or load_catalog()
    except Exception:
        return []
    return match_courses(text, catalog)


def detect_course_interest(text, catalog=None):
    return ", ".join(c.name for c in detect_courses(text, catalog)) or None


def _lead_source(conversation):
    """The channel's CRM Lead Source (D-100); "Messenger" until migrate has created the channel sources."""
    source = source_name(channel_key(conversation))
    return source if source and frappe.db.exists("CRM Lead Source", source) else "Messenger"


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

    if payload.get("event") == "message_created":
        return enqueue_analysis(payload)  # [I] layer; ignores everything unless an API key is set
    if payload.get("event") == "conversation_updated":
        from mmm_custom.engine.copilot import on_conversation_updated

        assist = on_conversation_updated(payload)  # the assist banner's buttons (D-112)
        result = enqueue_on_assignment(payload)  # a staff member took the conversation: suggest a reply
        return {**result, "assist": assist} if assist else result
    if payload.get("event") == "conversation_typing_on":
        from mmm_custom.engine.copilot import on_typing

        return on_typing(payload)  # a staff member is typing: the bot waits a little longer (D-112)

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

    msg_text = extract_message_text(conversation, payload)
    courses = detect_courses(msg_text)
    course_interest = ", ".join(c.name for c in courses) or None

    # 2. Dedup & Lead convergence (crm_lead_id → chatwoot_contact_id → email/phone), shared with the bot engine:
    # a contact becomes one Lead whichever event arrives first (repo.ensure_lead).
    lead_name, created = ensure_lead(contact, _lead_source(conversation), courses)
    if created:
        try:
            from crm.fcrm.doctype.crm_notification.crm_notification import notify_crm_users
            lead_src = _lead_source(conversation)
            course_text = f" quan tâm khóa học {course_interest}" if course_interest else ""
            notify_crm_users(
                title="Khách hàng tiềm năng mới",
                message=f"Học viên {first_name} vừa liên hệ qua {lead_src}{course_text}.",
                notification_type="Assignment",
                reference_doctype="CRM Lead",
                reference_name=lead_name,
            )
        except Exception:
            pass

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
            frappe.log_error(title="Failed to create FCRM Note", message=str(e))

    # 4. Write back crm_lead_id to Chatwoot Contact
    chatwoot_url = (conf.get("chatwoot_api_url") if conf else None) or "http://chatwoot-rails:3000"
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
                frappe.log_error(title="Failed to update Chatwoot contact", message=str(e))

    # 5. Compute data quality indicator
    try:
        compute_data_quality(lead_name)
    except Exception:
        pass

    return {"status": "success", "lead_id": lead_name}


@frappe.whitelist()
def switch_language(lang):
    """Switch user interface language between Vietnamese ('vi') and English ('en')."""
    if lang not in ["vi", "en"]:
        frappe.throw(_("Ngôn ngữ không hợp lệ / Invalid language"))

    user = getattr(frappe.session, "user", None) or "Administrator"
    frappe.db.set_value("User", user, "language", lang)
    if user == "Administrator":
        frappe.db.set_single_value("System Settings", "language", lang)
    if hasattr(frappe.db, "commit"):
        frappe.db.commit()

    if hasattr(frappe, "local") and hasattr(frappe.local, "cookie_manager"):
        frappe.local.cookie_manager.set_cookie("user_lang", lang)

    return {"status": "success", "language": lang}

