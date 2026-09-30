"""[I] Intelligence layer: AI agents on TypeSafe Jev (optional).

For every incoming Chatwoot message, `analyze_conversation` asks Jev — a decision model
that returns typed choices/scores with a confidence, not generated text — about the
conversation, and applies only the decisions Jev is confident about:
intent and hotness on the CRM Lead, the customer's phone/email picked out of the chat
(never overwriting one the Lead already has, never merging Leads), conversation labels,
and, for the staff member who owns the conversation, the bot's own answer to the latest
message as a private note (engine/draft.py, D-110: from the course's data, never a canned template).

Off unless the site config has `typesafe_api_key`. Verified against the real Jev API on
hand-labelled Vietnamese chats: every wrong answer came back below the 0.7 threshold.
"""

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
from mmm_custom.engine.text import EMAIL_RE
from mmm_custom.lifecycle import LIVE_DEAL

logger = logging.getLogger(__name__)

JEV_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_THRESHOLD = 0.7
DEFAULT_ENROL_FLOOR = 0.85  # a draft registration is a bigger step than a label: Jev must be surer
ENROL_CRITERIA = {
    "enrol": "The customer clearly says they want to register / sign up (and pay) for a course now",
    "not_yet": "Asking, comparing, booking a free trial or level test, or still undecided",
}

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
# The "Messenger to CRM" webhook creates the Lead on conversation_created, which races the
# first message; the job waits for it (4 attempts over ~28 s).
LEAD_WAIT_SECONDS = (4, 8, 16)

PHONE_RE = re.compile(r"(?:\+84|0)(?:[\s.-]?\d){9}")


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


def enrol_eligible(status, phone, course, has_live_deal, enabled=True) -> bool:
    """Is a draft registration possible for this Lead (D-118)? Only then is Jev asked, so no tokens go on chats that
    could not become one: an open (or already registered) Lead with a course and a phone and no live registration."""
    from mmm_custom.lifecycle import CONVERTED, OPEN_LEAD

    return bool(enabled and phone and course and not has_live_deal and status in (*OPEN_LEAD, CONVERTED))


def build_questions(candidates: dict, ask_enrol: bool = False) -> dict:
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
    if ask_enrol:
        questions["enrol"] = {"type": "choice", "instructions": "Has the customer decided to register for a course?",
                              "criteria": ENROL_CRITERIA}
    return questions


def decide_actions(answers: dict, threshold: float, lead: dict, enrol_floor: float = DEFAULT_ENROL_FLOOR) -> dict:
    """Pure decision step: turn Jev's answers into the changes to apply, gated on confidence."""

    def sure(answer):
        return bool(answer) and (answer.get("confidence") or 0) >= threshold

    plan = {"lead_update": {}, "labels": [], "skipped": [], "enrol": False}

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
    enrol = answers.get("enrol")
    if enrol and enrol.get("choice") == "enrol" and not is_spam:
        plan["enrol"] = (enrol.get("confidence") or 0) >= max(threshold, enrol_floor)
    for key, field in (("phone", "mobile_no"), ("email", "email")):
        answer = answers.get(key)
        # Spam ads carry their own phone numbers; never copy those onto the Lead.
        if not answer or answer.get("choice") == "none" or lead.get(field) or is_spam:
            continue
        if sure(answer):
            plan["lead_update"][field] = answer["choice"]
        else:
            plan["skipped"].append(key)

    return plan


def draft_note(conversation_id, convo: dict):
    """The bot's own answer to the conversation's latest customer message, for staff (D-110), or None."""
    from mmm_custom.engine import draft
    from mmm_custom.engine.pipeline import Event

    last = next((m for m in reversed(convo["payload"])
                 if m.get("message_type") in (0, "incoming") and not m.get("private") and m.get("content")), None)
    if not last:
        return None
    contact = (convo.get("meta") or {}).get("contact") or {}
    event = Event("customer_message", str(conversation_id), int(last.get("id") or 0), last["content"][:1000], contact,
                  str(last.get("inbox_id") or ""))
    try:
        return draft.suggest(event)
    except Exception:  # a suggestion must never break the Lead update
        logger.exception("AI: draft for conversation %s failed", conversation_id)
        return None


def _conf():
    return getattr(frappe, "conf", None) or {}


def _chatwoot_client(conf) -> ChatwootClient:
    return ChatwootClient(
        conf.get("chatwoot_api_url") or "http://chatwoot-rails:3000",
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


def _bot_conversation(conversation_id, status) -> bool:
    return bool(frappe.db.exists("Bot Conversation",
                                 {"conversation_id": str(conversation_id), "status": status, "is_sandbox": 0}))


def bot_active(conversation_id) -> bool:
    """An active bot conversation supplies its own Jev intent and hotness signals."""
    return _bot_conversation(conversation_id, "active")


def bot_handles(conversation_id) -> bool:
    """The lead engine owns this conversation (D-111): it drafts the staff suggestions itself, per message."""
    return _bot_conversation(conversation_id, ["!=", "closed"])


def has_human_assignee(conversation: dict) -> bool:
    """A staff member owns the conversation (assigned by a person, by themselves, or by the bot's handoff)."""
    assignee = ((conversation or {}).get("meta") or {}).get("assignee") or {}
    return bool(assignee.get("id")) and assignee.get("type", "user") == "user"


def customer_waiting(conversation: dict) -> bool:
    """The last message of the conversation came from the customer or the bot, not from a staff member."""
    messages = (conversation or {}).get("messages") or []
    if not messages:
        return False
    last = messages[-1]
    return last.get("message_type") in (0, "incoming") or (last.get("sender") or {}).get("type") == "agent_bot"


def changed_attributes(payload: dict) -> dict:
    """conversation_updated → {attribute: {"previous_value", "current_value"}}. Pure."""
    changed = {}
    for item in payload.get("changed_attributes") or []:
        if isinstance(item, dict):
            changed.update(item)
    return changed


def assignment_trigger(payload: dict):
    """conversation_updated → the conversation id when it was just assigned to a staff member while the
    customer waits for an answer (D-108); otherwise None. Pure."""
    change = changed_attributes(payload).get("assignee_id")
    if not isinstance(change, dict):
        return None
    current = change.get("current_value")
    if not current or current == change.get("previous_value"):
        return None
    if not has_human_assignee(payload) or not customer_waiting(payload):
        return None
    return payload.get("id")


def _enqueue_suggestion(conversation_id, **kwargs):
    frappe.enqueue("mmm_custom.intelligence.analyze_conversation", queue="long", conversation_id=conversation_id,
                   suggest_reply=True, job_id=f"ai_suggest_{conversation_id}", deduplicate=True, **kwargs)


def enqueue_on_assignment(payload: dict) -> dict:
    """Called by the Chatwoot webhook for conversation_updated: a staff member took the conversation
    (assigned it to themselves, or a manager did), so they get a reply suggestion right away."""
    if not _conf().get("typesafe_api_key"):
        return {"status": "ignored", "reason": "ai_disabled"}
    conversation_id = assignment_trigger(payload)
    if not conversation_id:
        return {"status": "ignored", "reason": "not_assigned"}
    if bot_active(conversation_id):
        return {"status": "ignored", "reason": "bot_active"}
    _enqueue_suggestion(conversation_id)
    return {"status": "queued", "conversation_id": conversation_id}


def on_handed_off(event: dict):
    """lead_engine_events handler: the bot handed the conversation to a consultant, who gets a reply
    suggestion as they open it. Runs after the turn commits, when the conversation is no longer active."""
    if event.get("is_sandbox") or not event.get("conversation_id") or not _conf().get("typesafe_api_key"):
        return
    _enqueue_suggestion(int(event["conversation_id"]), enqueue_after_commit=True)


def enqueue_analysis(payload: dict) -> dict:
    """Called by the Chatwoot webhook for message_created: queue analysis of incoming messages.
    A reply suggestion is added only when a staff member owns the conversation (D-108)."""
    if not _conf().get("typesafe_api_key"):
        return {"status": "ignored", "reason": "ai_disabled"}
    if payload.get("message_type") not in ("incoming", 0) or payload.get("private"):
        return {"status": "ignored", "reason": "not_incoming"}
    conversation = payload.get("conversation") or {}
    if not conversation.get("id"):
        return {"status": "error", "message": "Missing conversation id"}
    if bot_active(conversation["id"]):
        return {"status": "ignored", "reason": "bot_active"}
    frappe.enqueue(
        "mmm_custom.intelligence.analyze_conversation", queue="long", conversation_id=conversation["id"],
        # Pending = the agent bot is still qualifying the lead; a suggestion per Quick Reply click is noise.
        # Nobody assigned yet: the suggestion comes when someone takes the conversation (enqueue_on_assignment).
        suggest_reply=(conversation.get("status") != "pending" and has_human_assignee(conversation)
                       and not bot_handles(conversation["id"])),
    )
    return {"status": "queued", "conversation_id": conversation["id"]}


def _draft_registration(lead_id, course):
    """The draft registration and its Task (D-118), or "" when it failed: the analysis never breaks on it."""
    from mmm_custom import enrolment

    try:
        deal = enrolment.create_draft(lead_id, course, source="jev")
        frappe.db.commit()
        return deal
    except Exception:
        logger.exception("AI: draft registration for %s failed", lead_id)
        return ""


def analyze_conversation(conversation_id: int, suggest_reply: bool = True, sleep=time.sleep) -> dict:
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
    candidates = find_candidates([m["text"] for m in chat if m["from"] == "customer"])
    lead = frappe.db.get_value("CRM Lead", lead_id, ["mobile_no", "email", "status"], as_dict=True) or {}
    course = frappe.db.get_value("CRM Products", {"parenttype": "CRM Lead", "parent": lead_id}, "product_code",
                                 order_by="idx asc")
    ask_enrol = enrol_eligible(
        lead.get("status"), lead.get("mobile_no") or candidates["phones"], course,
        frappe.db.exists("CRM Deal", {"lead": lead_id, "status": ["in", list(LIVE_DEAL)]}),
        int(conf.get("ai_enrol_drafts", 1)) != 0)

    answers = ask_jev(
        api_key, {"chat": chat}, build_questions(candidates, ask_enrol),
        model=conf.get("typesafe_model") or "jev-latest", url=conf.get("typesafe_api_url") or JEV_URL,
    )
    threshold = float(conf.get("typesafe_confidence_threshold") or DEFAULT_THRESHOLD)
    plan = decide_actions(answers, threshold, lead, float(conf.get("ai_enrol_floor") or DEFAULT_ENROL_FLOOR))

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

    draft_deal = _draft_registration(lead_id, course) if plan["enrol"] else ""
    if draft_deal:
        applied.append("draft_registration")
        client.send_private_note(
            conversation_id, f"📝 Jev: khách muốn đăng ký khóa {course} — đã tạo hồ sơ đăng ký nháp {draft_deal}. "
                             "Gọi xác nhận lớp và học phí trên CRM.")

    if plan["labels"]:
        client.add_labels(conversation_id, plan["labels"])
        applied.append("labels_added")
    note = draft_note(conversation_id, convo) if suggest_reply else None
    last_note = next((m.get("content") for m in reversed(convo["payload"]) if m.get("private")), None)
    if note and note != last_note:
        client.send_private_note(conversation_id, note)
        applied.append("reply_suggested")
    return {"status": "analyzed", "lead_id": lead_id, "decisions": plan["lead_update"], "skipped": plan["skipped"], "applied": applied}
