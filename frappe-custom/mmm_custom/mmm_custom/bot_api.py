"""Webhook endpoint for the Chatwoot Agent Bot (spec 2026-09-26-edu-lead-engine §7.2).

Verifies the HMAC signature and anti-replay timestamp, then hands each customer message to the lead
engine as a background job (job_id = message id, deduplicated) so Chatwoot gets its answer well
inside its 5 s timeout and a retried delivery never produces a second reply (D-025).
"""

import hashlib
import hmac
import json
import time

try:
    import frappe
except ImportError:
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

from mmm_custom.engine.pipeline import parse_event
from mmm_custom.engine.repo import close_conversation, mark_consultant_replied


def _verify_hmac(raw_body: bytes, secret: str, timestamp: str, signature: str):
    """Validate HMAC-SHA256 signature and anti-replay timestamp."""
    if not timestamp:
        frappe.throw("Timestamp expired or missing", frappe.AuthenticationError)

    try:
        ts_val = float(timestamp)
    except (ValueError, TypeError):
        frappe.throw("Timestamp expired or missing", frappe.AuthenticationError)

    if abs(time.time() - ts_val) > 300:
        frappe.throw("Timestamp expired or missing", frappe.AuthenticationError)

    hex_digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + raw_body,
        hashlib.sha256,
    ).hexdigest()
    expected = "sha256=" + hex_digest

    if not signature or not (
        hmac.compare_digest(expected, signature)
        or hmac.compare_digest(hex_digest, signature)
    ):
        frappe.throw("Invalid HMAC signature", frappe.AuthenticationError)


def _raw_body(req) -> bytes:
    if hasattr(req, "get_data") and callable(req.get_data):
        raw = req.get_data()
    else:
        raw = getattr(req, "data", b"")
    if isinstance(raw, str):
        return raw.encode("utf-8")
    return raw if isinstance(raw, bytes) else bytes(raw or b"")


@frappe.whitelist(allow_guest=True)
def agent_bot_webhook():
    """Receive Agent Bot webhook events from Chatwoot."""
    req = frappe.request
    headers = getattr(req, "headers", {}) or {}
    raw_body = _raw_body(req)

    conf = getattr(frappe, "conf", None)
    secret = conf.get("chatwoot_bot_webhook_secret") if conf else None
    if not secret:
        # No built-in fallback: a default secret in a public repo would let anyone forge webhooks.
        frappe.throw("chatwoot_bot_webhook_secret is not configured", frappe.AuthenticationError)

    _verify_hmac(raw_body, secret, headers.get("X-Chatwoot-Timestamp"), headers.get("X-Chatwoot-Signature", ""))

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {"status": "error", "message": "Invalid JSON body"}
    if not isinstance(payload, dict):
        return {"status": "error", "message": "Invalid JSON body"}

    event = parse_event(payload)
    if event.kind == "customer_message" and event.conversation_id:
        frappe.enqueue("mmm_custom.engine.pipeline.process_event", queue="short",
                       job_id=f"lead_engine_msg_{event.message_id}", deduplicate=True, payload=payload)
        return {"status": "queued"}
    if event.kind == "agent_message" and event.conversation_id:
        mark_consultant_replied(event.conversation_id)  # D-059: never talk over a person
        return {"status": "consultant_replied"}
    if event.kind == "resolved" and event.conversation_id:
        close_conversation(event.conversation_id)
        return {"status": "closed"}
    return {"status": "ignored", "event": payload.get("event")}
