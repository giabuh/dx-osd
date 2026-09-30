"""A Lead's Chatwoot conversation on the Lead page (spec 2026-09-27-one-customer-record, B3/B4).

Consultants read and answer their branch's customers without the Chatwoot inbox. Access is the CRM's:
whoever may read the Lead (branch scope, mmm_custom.scope) may read its conversation. Answers go out
under the consultant's own Chatwoot identity (their access token, stored by staff_sync), so Chatwoot
shows who answered and the bot stops talking, as when answering inside Chatwoot.
"""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.chatwoot_client import ChatwootClient
from mmm_custom.crm_links import chatwoot_base
from mmm_custom.desk import can_open_bot
from mmm_custom.engine import presence

whitelist = frappe.whitelist if frappe else (lambda **kw: (lambda fn: fn))

MAX_REPLY = 2000
# Chatwoot message_type: 0 incoming, 1 outgoing, 2 activity, 3 template
INCOMING, OUTGOING, ACTIVITY = 0, 1, 2


def message_kind(message):
    """customer | staff | bot | note | activity. Pure."""
    mtype = message.get("message_type")
    if mtype == ACTIVITY:
        return "activity"
    if message.get("private"):
        return "note"
    if mtype == INCOMING:
        return "customer"
    sender = message.get("sender") or {}
    return "staff" if mtype == OUTGOING and sender.get("type") == "user" else "bot"


def to_message(message):
    """A Chatwoot message payload → what the Lead page shows. Pure."""
    items = (message.get("content_attributes") or {}).get("items") or []
    sender = message.get("sender") or {}
    return {"id": message.get("id"), "kind": message_kind(message), "text": message.get("content") or "",
            "sender": sender.get("available_name") or sender.get("name") or "", "at": message.get("created_at"),
            "buttons": [i.get("title") for i in items if isinstance(i, dict) and i.get("title")],
            "attachments": len(message.get("attachments") or [])}


def newest_conversation(conversations):
    """Id of the most recently active conversation, or None. Pure."""
    rows = [c for c in conversations or [] if c.get("id")]
    if not rows:
        return None
    return max(rows, key=lambda c: (c.get("last_activity_at") or 0, c["id"]))["id"]


def admin_client():
    conf = frappe.conf
    if not conf.get("chatwoot_api_token"):
        frappe.throw("Chưa cấu hình kết nối Chatwoot (chatwoot_api_token).")
    return ChatwootClient(conf.get("chatwoot_api_url") or "http://chatwoot-rails:3000", conf.get("chatwoot_api_token"),
                          int(conf.get("chatwoot_account_id") or 1))


def _require_read(lead):
    if not frappe.has_permission("CRM Lead", "read", lead):
        frappe.throw("Bạn không có quyền xem khách này.", frappe.PermissionError)


def conversation_of(lead, client):
    """The Lead's conversation: the one the bot linked to it, else the newest of its Chatwoot contact."""
    linked = frappe.get_all("Bot Conversation", filters={"lead": lead, "is_sandbox": 0}, pluck="conversation_id",
                            order_by="modified desc", limit=1)
    if linked and str(linked[0]).isdigit():
        return int(linked[0])
    contact_id = str(frappe.db.get_value("CRM Lead", lead, "chatwoot_contact_id") or "").strip()
    if not contact_id.isdigit():
        return None
    return newest_conversation(client.list_contact_conversations(int(contact_id)))


def own_token(user):
    """The user's own Chatwoot token (Consultant.chatwoot_access_token), or ""."""
    if not frappe.db.exists("Consultant", user):
        return ""
    from frappe.utils.password import get_decrypted_password

    return get_decrypted_password("Consultant", user, "chatwoot_access_token", raise_exception=False) or ""


def sender_client(user):
    """Who an answer goes out as: the consultant's own Chatwoot account; a manager without one uses the
    admin account. None when the user cannot answer yet."""
    token = own_token(user)
    if token:
        conf = frappe.conf
        return ChatwootClient(conf.get("chatwoot_api_url") or "http://chatwoot-rails:3000", token,
                              int(conf.get("chatwoot_account_id") or 1))
    return admin_client() if can_open_bot() else None


def _conversation_url(conversation):
    conf = frappe.conf
    return f"{chatwoot_base(conf)}/app/accounts/{int(conf.get('chatwoot_account_id') or 1)}/conversations/{conversation}"


@whitelist()
def chat(lead):
    _require_read(lead)
    client = admin_client()
    conversation = conversation_of(lead, client)
    if not conversation:
        return {"conversation": None, "messages": [], "can_reply": False, "chatwoot_url": None}
    presence.seen(conversation, frappe.session.user)  # the Lead page chat is open: the bot drafts, not answers (D-112)
    payload = client.list_messages(conversation).get("payload") or []
    return {"conversation": conversation, "messages": [to_message(m) for m in payload],
            "can_reply": bool(own_token(frappe.session.user) or can_open_bot()),
            "chatwoot_url": _conversation_url(conversation)}


@whitelist(methods=["POST"])
def send(lead, text):
    _require_read(lead)
    text = (text or "").strip()
    if not text:
        frappe.throw("Nhập nội dung tin nhắn.")
    if len(text) > MAX_REPLY:
        frappe.throw(f"Tin nhắn dài quá {MAX_REPLY} ký tự.")
    conversation = conversation_of(lead, admin_client())
    if not conversation:
        frappe.throw("Khách này chưa có cuộc chat trên Chatwoot.")
    client = sender_client(frappe.session.user)
    if not client:
        frappe.throw("Tài khoản Chatwoot của bạn chưa sẵn sàng. Nhờ quản trị chạy đồng bộ nhân viên.")
    try:
        sent = client.send_message(conversation, text)
    except Exception as error:
        status = getattr(getattr(error, "response", None), "status_code", None)
        if status in (401, 403, 404):  # Chatwoot: the conversation is not assigned to this agent's team yet
            frappe.throw("Cuộc chat này chưa được giao cho nhóm của bạn trên Chatwoot (bot chưa chuyển khách).")
        raise
    return to_message(sent)
