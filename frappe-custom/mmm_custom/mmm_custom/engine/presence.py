"""Who is looking at a conversation right now (D-112). A staff member counts as watching for VIEWER_TTL seconds
after the last sign: the Lead page chat polling it (lead_chat.chat → `seen`), or the Chatwoot dashboard's
presence ping from the open conversation (our Chatwoot fork: RoomChannel#update_presence → GET …/viewers)."""

import time

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

VIEWER_TTL = 45


def _key(conversation_id):
    return f"mmm_custom:viewers:{conversation_id}"


def fresh(seen, now, ttl=VIEWER_TTL):
    """{viewer: epoch seconds} → the viewers seen within `ttl`. Pure."""
    out = []
    for viewer, at in (seen or {}).items():
        try:
            if now - float(at) < ttl:
                out.append(viewer.decode() if isinstance(viewer, bytes) else str(viewer))
        except (TypeError, ValueError):
            continue
    return sorted(out)


def seen(conversation_id, viewer, now=None):
    """Record that `viewer` (a CRM user or a Chatwoot agent id) is looking at the conversation now."""
    if not (conversation_id and viewer):
        return
    try:
        frappe.cache().hset(_key(conversation_id), str(viewer), time.time() if now is None else now)
    except Exception:  # a hint only: reading the chat must never fail on it
        pass


def viewers(conversation_id, now=None):
    """The staff members looking at the conversation now (CRM users and Chatwoot agent ids); [] when unknown."""
    from mmm_custom.engine.repo import chatwoot_admin

    out = []
    try:
        out += fresh(frappe.cache().hgetall(_key(conversation_id)), time.time() if now is None else now)
    except Exception:  # presence is a hint: never block a customer's answer on it
        pass
    try:
        out += [f"agent:{a}" for a in chatwoot_admin().conversation_viewers(int(conversation_id))]
    except Exception:
        pass
    return out
