"""Webhook endpoint for the Chatwoot Agent Bot.

Receives Agent Bot webhook events from Chatwoot, runs the state machine,
sends Quick Reply responses via Chatwoot API, and on completion creates/
updates the CRM Lead and hands off to a human agent.
"""

import hashlib
import hmac
import json
import logging
import time

try:
    import requests
except ImportError:
    requests = None

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

from mmm_custom.bot_engine import BRANCHES, COURSES, transition
from mmm_custom.chatwoot_client import ChatwootClient
from mmm_custom.dedupe import find_matching_lead, normalize_phone
from mmm_custom.data_quality import compute_data_quality

logger = logging.getLogger(__name__)


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


def _find_best_agent(branch_key: str, client: ChatwootClient) -> int | None:
    """Find the best-match agent by branch, round-robin by fewest open convos."""
    try:
        agents = client.list_agents()
    except Exception:
        logger.exception("Failed to list agents")
        return None

    # Filter by branch
    branch_agents = [
        a for a in agents
        if (a.get("custom_attributes") or {}).get("branch") == branch_key
    ]
    candidates = branch_agents if branch_agents else agents

    if not candidates:
        return None

    # Find agent with fewest open conversations
    best_agent_id = None
    min_convos = float("inf")
    for agent in candidates:
        try:
            convos = client.list_agent_conversations(agent["id"], status="open")
            count = len(convos)
        except Exception:
            count = 0
        if count < min_convos:
            min_convos = count
            best_agent_id = agent["id"]

    return best_agent_id


_PLACEHOLDER_NAME = "Khách Messenger"


def _create_or_update_lead(contact: dict, courses: list[str],
                           branch_key: str, contact_id: int | None,
                           phone_override: str | None = None):
    """Create or update a CRM Lead with bot-collected data."""
    email = contact.get("email")
    phone = phone_override or contact.get("phone_number") or contact.get("phone")
    raw_name = contact.get("name")
    first_name = (
        str(raw_name).strip() if raw_name and str(raw_name).strip()
        else _PLACEHOLDER_NAME
    )

    # Map course keys to display names
    course_display = ", ".join(
        COURSES.get(k, k) for k in courses
    )
    # Map branch key to display name (without emoji for CRM Select option) and branch owner consultant
    raw_branch = BRANCHES.get(branch_key, branch_key) or ""
    branch_display = raw_branch.replace("📍 ", "").strip()
    branch_owners = {
        "binh_thanh": "mai.binhthanh@eduflow.vn",
        "quan_1": "nam.quan1@eduflow.vn",
        "thu_duc": "phuc.thuduc@eduflow.vn",
    }
    lead_owner = branch_owners.get(branch_key)

    custom_attrs = contact.get("custom_attributes") or {}
    crm_lead_id = custom_attrs.get("crm_lead_id")

    lead_name = None
    if crm_lead_id and frappe.db.exists("CRM Lead", crm_lead_id):
        lead_name = crm_lead_id
    elif contact_id and frappe.db.exists("CRM Lead", {"chatwoot_contact_id": str(contact_id)}):
        lead_name = frappe.db.get_value("CRM Lead", {"chatwoot_contact_id": str(contact_id)}, "name")
    else:
        matched = find_matching_lead(email, phone)
        if matched:
            lead_name = matched.name if hasattr(matched, "name") else matched.get("name")

    if lead_name:
        frappe.db.set_value("CRM Lead", lead_name, "course_interest", course_display)
        frappe.db.set_value("CRM Lead", lead_name, "branch", branch_display)
        if lead_owner:
            frappe.db.set_value("CRM Lead", lead_name, "lead_owner", lead_owner)
        if contact_id:
            frappe.db.set_value("CRM Lead", lead_name, "chatwoot_contact_id", str(contact_id))
        if phone:
            frappe.db.set_value("CRM Lead", lead_name, "mobile_no", normalize_phone(phone))
        # Fix placeholder name if we now have the real name from Chatwoot
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
        lead = frappe.get_doc({
            "doctype": "CRM Lead",
            "first_name": first_name,
            "email": email,
            "mobile_no": normalize_phone(phone),
            "source": "Messenger Bot",
            "course_interest": course_display,
            "branch": branch_display,
            "lead_owner": lead_owner,
            "chatwoot_contact_id": str(contact_id) if contact_id else None,
        }).insert(ignore_permissions=True)
        lead_name = lead.name

    return lead_name


@frappe.whitelist(allow_guest=True)
def agent_bot_webhook():
    """Receive Agent Bot webhook events from Chatwoot."""
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
    secret = conf.get("chatwoot_bot_webhook_secret") if conf else None
    if not secret:
        # No built-in fallback: a default secret in a public repo would let anyone forge webhooks.
        frappe.throw("chatwoot_bot_webhook_secret is not configured", frappe.AuthenticationError)

    _verify_hmac(raw_body, secret, ts, sig)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {"status": "error", "message": "Invalid JSON body"}

    if not isinstance(payload, dict):
        return {"status": "error", "message": "Invalid JSON body"}

    # Only process message_created events
    if payload.get("event") != "message_created":
        return {"status": "ignored", "event": payload.get("event")}

    # Only process incoming messages (from customer, not bot/agent)
    message_type = payload.get("message_type", -1)
    if message_type not in (0, "incoming"):
        return {"status": "ignored", "reason": "outgoing_message"}

    # Extract conversation and contact data
    conversation = payload.get("conversation") or {}
    # In Agent Bot webhooks, contact_inbox may be a GlobalID string, not a dict.
    # Extract contact from meta.sender, top-level sender, or contact_inbox.contact
    contact_inbox = conversation.get("contact_inbox") or {}
    meta = conversation.get("meta") or {}
    meta_sender = meta.get("sender") if isinstance(meta, dict) else {}
    contact = (
        (contact_inbox.get("contact") if isinstance(contact_inbox, dict) else None)
        or (meta_sender if isinstance(meta_sender, dict) else None)
        or payload.get("sender")
        or {}
    )
    contact_id = contact.get("id")
    custom_attrs = contact.get("custom_attributes") or {}
    conversation_id = conversation.get("id") or payload.get("conversation", {}).get("id")

    if not conversation_id:
        return {"status": "error", "message": "Missing conversation_id"}

    # Read bot state from contact custom_attributes
    bot_state = custom_attrs.get("bot_state")
    bot_courses = custom_attrs.get("bot_courses") or []

    # Get user input — Quick Reply value or plain text content
    user_input = payload.get("content") or ""

    # Run state machine
    result = transition(bot_state, user_input, bot_courses)

    if result is None:
        return {"status": "ignored", "reason": "completed"}

    # Recover branch from contact custom_attrs if not set in result
    # (await_phone state doesn't know the branch — it was saved earlier)
    effective_branch = result.branch or custom_attrs.get("bot_branch")

    # Initialize Chatwoot client
    bot_token = (conf.get("chatwoot_bot_api_token") if conf else None) or ""
    account_id = (conf.get("chatwoot_bot_account_id") if conf else None) or 1
    base_url = (conf.get("chatwoot_base_url") if conf else None) or "http://chatwoot-rails:3000"

    client = ChatwootClient(base_url, bot_token, int(account_id))
    # Chatwoot rejects Agent Bot tokens on /contacts and /agents (401), so contact updates and agent
    # lookup need a user token; messages, labels, assignment and status stay on the bot token.
    user_client = ChatwootClient(base_url, (conf.get("chatwoot_api_token") if conf else None) or bot_token, int(account_id))

    # Send the bot's response message
    try:
        if result.quick_replies:
            client.send_quick_replies(conversation_id, result.message, result.quick_replies)
        else:
            client.send_message(conversation_id, result.message)
    except Exception:
        logger.exception("Failed to send bot message")

    # Update contact custom_attributes with new state
    new_attrs = {
        "bot_state": result.next_state,
        "bot_courses": result.selected_courses,
    }
    if result.branch:
        new_attrs["bot_branch"] = result.branch

    try:
        if contact_id:
            user_client.update_contact(contact_id, new_attrs)
    except Exception:
        logger.exception("Failed to update contact attributes")

    # Execute actions if any
    if "update_lead" in result.actions:
        try:
            lead_name = _create_or_update_lead(
                contact, result.selected_courses, effective_branch, contact_id,
                phone_override=result.phone,
            )
            # Write back crm_lead_id to Chatwoot
            if contact_id and lead_name:
                try:
                    user_client.update_contact(contact_id, {"crm_lead_id": lead_name})
                except Exception:
                    logger.exception("Failed to write crm_lead_id back to Chatwoot")
            # Compute data quality indicator
            if lead_name:
                try:
                    compute_data_quality(lead_name)
                except Exception:
                    logger.exception("Failed to compute data quality")
        except Exception:
            logger.exception("Failed to create/update CRM Lead")

    if "assign_agent" in result.actions:
        try:
            agent_id = _find_best_agent(effective_branch, user_client)
            if agent_id:
                client.assign_conversation(conversation_id, agent_id)
        except Exception:
            logger.exception("Failed to assign agent")

    if "bot_handoff" in result.actions:
        try:
            client.toggle_status(conversation_id, "open")
        except Exception:
            logger.exception("Failed to toggle conversation status")

        # Add visual badges/labels to conversation in Chatwoot
        try:
            labels = []
            if result.branch:
                labels.append(BRANCHES.get(result.branch, result.branch).replace("📍 ", ""))
            for c_key in result.selected_courses:
                labels.append(COURSES.get(c_key, c_key).split(" ", 1)[-1])
            if labels and conversation_id:
                client.add_labels(conversation_id, labels)
        except Exception:
            logger.exception("Failed to add conversation labels")

    return {"status": "ok", "next_state": result.next_state}
