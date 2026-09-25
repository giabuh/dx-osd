"""[I] Intelligence layer: AI agents on TypeSafe Jev (optional).

For every incoming Chatwoot message, `analyze_conversation` asks Jev — a decision model
that returns typed choices/scores with a confidence, not generated text — about the
conversation, and applies only the decisions Jev is confident about:
intent and hotness on the CRM Lead, the customer's phone/email picked out of the chat
(never overwriting one the Lead already has, never merging Leads), conversation labels,
and a suggested reply template as a private note.

Off unless the site config has `typesafe_api_key`. Verified against the real Jev API on
hand-labelled Vietnamese chats: every wrong answer came back below the 0.7 threshold.
"""

import json
import logging
import re
import time

try:
    import requests
except ImportError:
    requests = None

try:
    import frappe
except ImportError:
    from unittest.mock import MagicMock

    frappe = MagicMock()

from mmm_custom.chatwoot_client import ChatwootClient
from mmm_custom.data_quality import compute_data_quality
from mmm_custom.dedupe import normalize_phone

logger = logging.getLogger(__name__)

JEV_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_THRESHOLD = 0.7

# Keys must match the ai_intent / ai_hotness Select options created in setup.py.
INTENTS = {
    "purchase": "The customer wants to buy, order, register, or book something now",
    "price_inquiry": "The customer asks about price, fees, promotions, or availability before deciding",
    "support": "The customer already bought or enrolled and needs help with an existing order or class",
    "complaint": "The customer is unhappy or complains about a product or service",
    "spam": "Spam, advertising, or a message that is not from a real prospective customer",
    "other": "Anything else, such as a greeting or thanks with no clear request",
}
HOTNESS = ["cold", "warm", "hot"]
HOTNESS_CRITERIA = [
    "Cold: no buying signal, just browsing or off-topic",
    "Warm: interested and asking questions, but not ready to buy yet",
    "Hot: clear intent to buy soon, asks how to order, or gives contact details to be called",
]
# Override per site with the `ai_reply_templates` site config key (a JSON object).
DEFAULT_REPLY_TEMPLATES = {
    "send_price": "Dạ em gửi anh/chị bảng giá mới nhất ạ: [link/ảnh bảng giá]. Anh/chị quan tâm mục nào để em tư vấn kỹ hơn nhé!",
    "ask_phone": "Dạ để tư vấn nhanh và chính xác hơn, anh/chị cho em xin số điện thoại, bên em gọi lại ngay ạ.",
    "confirm_order": "Dạ em xác nhận đăng ký của anh/chị. Anh/chị cho em xin tên, số điện thoại và cơ sở thuận tiện nhất ạ.",
    "book_consult": "Dạ anh/chị muốn bên em tư vấn trực tiếp vào khung giờ nào ạ? Em sắp xếp nhân viên liên hệ đúng giờ.",
    "order_support": "Dạ anh/chị cho em xin mã đăng ký hoặc số điện thoại đã đăng ký để em kiểm tra ngay ạ.",
    "apologize_complaint": "Dạ em rất xin lỗi vì trải nghiệm chưa tốt. Anh/chị mô tả giúp em vấn đề, bên em sẽ xử lý và phản hồi trong hôm nay ạ.",
    "greeting": "Dạ em chào anh/chị! Anh/chị đang quan tâm khoá học/dịch vụ nào để em hỗ trợ ạ?",
    "thanks": "Dạ em cảm ơn anh/chị đã tin tưởng. Cần hỗ trợ gì thêm anh/chị cứ nhắn em nhé!",
}
# The "Messenger to CRM" webhook creates the Lead on conversation_created, which races the
# first message; the job waits for it (4 attempts over ~28 s).
LEAD_WAIT_SECONDS = (4, 8, 16)

PHONE_RE = re.compile(r"(?:\+84|0)(?:[\s.-]?\d){9}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def ask_jev(api_key: str, state, questions: dict, model: str = "jev-latest", url: str = JEV_URL) -> dict:
    """One TypeSafe System One call: every question is evaluated against the same state."""
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "state": state, "questions": questions},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["answers"]


def find_candidates(texts: list[str]) -> dict:
    """Regex finds phone/email candidates; Jev only decides which one (if any) is the customer's."""
    joined = "\n".join(texts)
    phones = list(dict.fromkeys(normalize_phone(p.replace(".", "")) for p in PHONE_RE.findall(joined)))
    emails = list(dict.fromkeys(e.lower() for e in EMAIL_RE.findall(joined)))
    return {"phones": phones, "emails": emails}


def build_questions(candidates: dict, templates: dict) -> dict:
    questions = {
        "intent": {
            "type": "choice",
            "instructions": "What does the customer want in this Vietnamese chat with a business?",
            "criteria": INTENTS,
        },
        "hotness": {
            "type": "score",
            "instructions": "How close is the customer to buying, based on the whole chat?",
            "criteria": HOTNESS_CRITERIA,
        },
    }

    def pick(values, what):
        return {
            "type": "choice",
            "instructions": f'Which of these {what} did the customer give as their own contact? Answer "none" if it belongs to someone else or is not a contact.',
            "criteria": {**{v: None for v in values}, "none": "None of these is the customer’s own contact"},
        }

    if candidates["phones"]:
        questions["phone"] = pick(candidates["phones"], "phone numbers")
    if candidates["emails"]:
        questions["email"] = pick(candidates["emails"], "email addresses")
    if templates:
        questions["reply"] = {
            "type": "choice",
            "instructions": "Which reply template best answers the customer’s latest message?",
            "criteria": {**templates, "none": "No template fits the latest message"},
        }
    return questions


def decide_actions(answers: dict, templates: dict, threshold: float, lead: dict) -> dict:
    """Pure decision step: turn Jev's answers into the changes to apply, gated on confidence."""

    def sure(answer):
        return bool(answer) and (answer.get("confidence") or 0) >= threshold

    plan = {"lead_update": {}, "labels": [], "reply_note": None, "skipped": []}

    if sure(answers.get("intent")):
        plan["lead_update"]["ai_intent"] = answers["intent"]["choice"]
        plan["labels"].append("ai-" + answers["intent"]["choice"])
    else:
        plan["skipped"].append("intent")

    if sure(answers.get("hotness")):
        hotness = HOTNESS[round(answers["hotness"]["score"])]
        plan["lead_update"]["ai_hotness"] = hotness
        if hotness == "hot":
            plan["labels"].append("hot")
    else:
        plan["skipped"].append("hotness")

    is_spam = plan["lead_update"].get("ai_intent") == "spam"
    for key, field in (("phone", "mobile_no"), ("email", "email")):
        answer = answers.get(key)
        # Spam ads carry their own phone numbers; never copy those onto the Lead.
        if not answer or answer.get("choice") == "none" or lead.get(field) or is_spam:
            continue
        if sure(answer):
            plan["lead_update"][field] = answer["choice"]
        else:
            plan["skipped"].append(key)

    reply = answers.get("reply")
    if reply and reply.get("choice") != "none" and not is_spam:
        if sure(reply):
            plan["reply_note"] = f"Gợi ý trả lời (AI, độ tin cậy {reply['confidence']:.2f}):\n\n{templates[reply['choice']]}"
        else:
            plan["skipped"].append("reply")
    return plan


def _conf():
    return getattr(frappe, "conf", None) or {}


def _chatwoot_client(conf) -> ChatwootClient:
    return ChatwootClient(
        conf.get("chatwoot_api_url") or "http://127.0.0.1:3000",
        conf.get("chatwoot_api_token") or "",
        int(conf.get("chatwoot_account_id") or 1),
    )


def _find_lead(contact: dict) -> str | None:
    lead_id = (contact.get("custom_attributes") or {}).get("crm_lead_id")
    if lead_id and frappe.db.exists("CRM Lead", lead_id):
        return lead_id
    if contact.get("id") is not None:
        return frappe.db.get_value("CRM Lead", {"chatwoot_contact_id": str(contact["id"])}, "name")
    return None


def enqueue_analysis(payload: dict) -> dict:
    """Called by the Chatwoot webhook for message_created: queue analysis of incoming messages."""
    if not _conf().get("typesafe_api_key"):
        return {"status": "ignored", "reason": "ai_disabled"}
    if payload.get("message_type") not in ("incoming", 0) or payload.get("private"):
        return {"status": "ignored", "reason": "not_incoming"}
    conversation_id = (payload.get("conversation") or {}).get("id")
    if not conversation_id:
        return {"status": "error", "message": "Missing conversation id"}
    frappe.enqueue("mmm_custom.intelligence.analyze_conversation", queue="long", conversation_id=conversation_id)
    return {"status": "queued", "conversation_id": conversation_id}


def analyze_conversation(conversation_id: int, sleep=time.sleep) -> dict:
    """Background job: read the conversation, ask Jev, apply the confident decisions."""
    conf = _conf()
    api_key = conf.get("typesafe_api_key")
    if not api_key:
        return {"status": "ai_disabled"}
    client = _chatwoot_client(conf)

    for wait in (*LEAD_WAIT_SECONDS, None):
        convo = client.list_messages(conversation_id)
        lead_id = _find_lead(convo["meta"]["contact"])
        if lead_id or wait is None:
            break
        sleep(wait)
    if not lead_id:
        logger.warning("AI: conversation %s has no CRM Lead after waiting, skipped", conversation_id)
        return {"status": "no_lead"}

    chat = [
        {"from": "customer" if m["message_type"] == 0 else "business", "text": m["content"]}
        for m in convo["payload"]
        if not m.get("private") and m.get("message_type") in (0, 1) and m.get("content")
    ][-20:]
    templates = conf.get("ai_reply_templates") or DEFAULT_REPLY_TEMPLATES
    if isinstance(templates, str):
        templates = json.loads(templates)
    candidates = find_candidates([m["text"] for m in chat if m["from"] == "customer"])
    lead = frappe.db.get_value("CRM Lead", lead_id, ["mobile_no", "email"], as_dict=True) or {}

    answers = ask_jev(api_key, {"chat": chat}, build_questions(candidates, templates), model=conf.get("typesafe_model") or "jev-latest")
    threshold = float(conf.get("typesafe_confidence_threshold") or DEFAULT_THRESHOLD)
    plan = decide_actions(answers, templates, threshold, lead)

    applied = []
    if plan["lead_update"]:
        frappe.db.set_value("CRM Lead", lead_id, plan["lead_update"])
        applied.append("lead_updated")
        new_contact = {k: v for k, v in plan["lead_update"].items() if k in ("mobile_no", "email")}
        if new_contact:
            # A newly found contact may belong to another Lead (e.g. from Lead Ads): flag it, never merge.
            others = frappe.get_all(
                "CRM Lead",
                filters={"name": ["!=", lead_id]},
                or_filters=[[k, "=", v] for k, v in new_contact.items()],
                pluck="name",
            )
            if others:
                frappe.get_doc({
                    "doctype": "FCRM Note",
                    "title": "Possible duplicate",
                    "content": f"AI: số điện thoại/email khách vừa cung cấp trùng với {', '.join(others)} — có thể là cùng một khách, cần kiểm tra và gộp.",
                    "reference_doctype": "CRM Lead",
                    "reference_docname": lead_id,
                }).insert(ignore_permissions=True)
                applied.append("duplicate_flagged")
            compute_data_quality(lead_id)
    frappe.db.commit()

    if plan["labels"]:
        client.add_labels(conversation_id, plan["labels"])
        applied.append("labels_added")
    if plan["reply_note"]:
        client.send_private_note(conversation_id, plan["reply_note"])
        applied.append("reply_suggested")
    return {"status": "analyzed", "lead_id": lead_id, "decisions": plan["lead_update"], "skipped": plan["skipped"], "applied": applied}
