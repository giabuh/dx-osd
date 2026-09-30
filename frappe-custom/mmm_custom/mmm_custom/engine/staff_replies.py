"""The staff reply library (D-114): what staff answered customers, kept as templates the bot can reuse.

Jev writes no text, so the bot sounds like staff by choosing among replies staff actually wrote: every staff
message in Chatwoot is captured with the customer messages it answered (`capture`), personal data masked and the
course's fee, name and duration turned into placeholders (`templatize`), so a reused reply always carries today's
data. Managers approve replies in the CRM ("Tri thức khóa học" → "Câu trả lời NV"); the bot sends approved ones to
customers and may suggest new ones to staff. `candidates` picks the few worth showing Jev for one message."""

import difflib
import re

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine.text import fold

MAX_CANDIDATES = 12
PHONE_RE = re.compile(r"(?:\+?84|0)(?:[\s.\-]?\d){8,10}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# 1.500.000đ · 1,500,000 đồng · 1,5 triệu · 1tr5 · 1.5tr · 1500k
MONEY_RE = re.compile(r"(?<![\w.,])(?:(\d{1,3}(?:[.,]\d{3})+)\s*(?:đ|đồng|vnđ|vnd)?"
                      r"|(\d+(?:[.,]\d+)?)\s*(?:tr|triệu)(?:\s*(\d))?"
                      r"|(\d+)\s*k)(?![\w])", re.IGNORECASE)
STAFF_PREFIXES = ("💡", "✍️", "⚠", "👤", "🤖", "⏰")  # private notes written by the bot, never staff replies


def mask(text):
    """Personal data out of anything stored or shown to Jev: phone numbers and e-mail addresses."""
    return EMAIL_RE.sub("[email]", PHONE_RE.sub("[SĐT]", text or ""))


def money_value(match):
    """The amount in đồng a MONEY_RE match stands for."""
    dotted, millions, hundred_k, thousands = match.groups()
    if dotted:
        return int(re.sub(r"[.,]", "", dotted))
    if millions:
        return int(round(float(millions.replace(",", ".")) * 1_000_000 + int(hundred_k or 0) * 100_000))
    return int(thousands) * 1000


def templatize(text, course=None):
    """(template, numbers that match no course data). The course's fee, name and duration become placeholders so
    a reused reply always shows today's data; any other amount is flagged for a manager to check."""
    out, unknown = mask(text), []
    fee = int(course.fee) if course and course.fee else 0

    def money(m):
        if fee and money_value(m) == fee:
            return "{{ course.fee | vnd }}"
        unknown.append(m.group(0).strip())
        return m.group(0)

    out = MONEY_RE.sub(money, out)
    if course:
        for value, placeholder in ((course.name, "{{ course.name }}"), (course.duration, "{{ course.duration }}")):
            if value:
                out = re.sub(re.escape(value), placeholder, out, flags=re.IGNORECASE)
    return out.strip(), unknown


def words(text):
    return {w for w in fold(text).split() if len(w) > 1}


def similarity(a, b):
    """Shared words over all words (Jaccard) of two messages, diacritics ignored."""
    wa, wb = words(a), words(b)
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def outcome(draft, sent):
    """How the staff member used the bot's draft: used (as is), edited, or ignored."""
    if not draft:
        return ""
    ratio = difflib.SequenceMatcher(None, fold(draft), fold(sent)).ratio()
    return "used" if ratio >= 0.9 else "edited" if ratio >= 0.5 else "ignored"


def fits(reply, course, group):
    """A reply for this course, for its group, or for any customer; one naming course data needs a course."""
    if reply.course:
        return bool(course) and reply.course == course.code
    if reply.group and reply.group != (course.group if course else group):
        return False
    return bool(course) or "course." not in reply.reply


def candidates(catalog, text, course=None, group="", drafting=False, limit=MAX_CANDIDATES):
    """The library replies worth showing Jev for this message, most similar first. Customers only ever get
    approved replies; staff drafts may also use new ones."""
    scored = []
    for reply in catalog.staff_replies:
        if not (reply.approved or drafting) or not fits(reply, course, group):
            continue
        score = max((similarity(text, e) for e in reply.examples), default=0.0)
        if score > 0:
            scored.append((score, reply.name, reply))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [r for _, _, r in scored[:limit]]


def criterion(reply):
    """How Jev reads one library reply: what customers asked, and the answer (placeholders as words)."""
    answer = re.sub(r"\{\{\s*course\.(\w+)[^}]*\}\}", r"<course \1>", reply.reply)
    return f"Customers asked: {' | '.join(reply.examples[:3])} → staff answered: {answer[:300]}"


def customer_turn(messages, message_id):
    """(customer text, bot draft, "bot" | "llm") a staff message answered: the customer messages since the previous
    public outgoing message, and the last draft note among them. `messages` as Chatwoot lists them."""
    ordered = sorted(messages, key=lambda m: m.get("id") or 0)
    at = next((i for i, m in enumerate(ordered) if m.get("id") == message_id), len(ordered))
    texts, draft, kind_of_draft = [], "", ""
    for m in reversed(ordered[:at]):
        kind, private, content = m.get("message_type"), m.get("private"), m.get("content") or ""
        if kind in (1, "outgoing") and not private:
            break
        if private and not draft and content.startswith(("💡", "✍️")):
            draft, kind_of_draft = content.split("\n\n", 1)[-1], "llm" if content.startswith("✍️") else "bot"
        if kind in (0, "incoming") and content:
            texts.append(content)
    return "\n".join(reversed(texts)), draft, kind_of_draft


def capture(conversation_id, message_id, text, consultant=""):
    """RQ job (bot_api, agent_message): keep a staff reply with what it answered, as a new library entry."""
    from mmm_custom.engine.pipeline import Event
    from mmm_custom.engine.repo import FrappeRepo, chatwoot_admin
    from mmm_custom.engine.state import value
    from mmm_custom.engine.understand import understand

    if not text or text.startswith(STAFF_PREFIXES) or len(words(text)) < 3:
        return {"status": "ignored"}
    asked, draft, drafted_by = customer_turn(chatwoot_admin().list_messages(int(conversation_id)).get("payload") or [],
                                             int(message_id))
    if not asked:
        return {"status": "ignored", "reason": "nothing_asked"}
    repo = FrappeRepo()
    catalog = repo.catalog()
    state = repo.load_state(Event("customer_message", str(conversation_id)))
    course_slot = catalog.slot_for("course")
    course = catalog.courses.get(value(state.slots, course_slot.key)) if course_slot else None
    template, unknown = templatize(text, course)
    understood = understand(asked, state, catalog)
    doc = frappe.get_doc({
        "doctype": "Staff Reply", "status": "new", "source": "llm" if drafted_by == "llm" and outcome(draft, text) == "used" else "staff",
        "course": course.code if course else None, "course_group": course.group if course else None,
        "topic": (understood.skills or [""])[0], "customer_examples": mask(asked), "reply": template,
        "needs_check": ", ".join(unknown) or None, "consultant": consultant or None,
        "conversation_id": str(conversation_id), "lead": state.lead or None, "bot_draft": draft or None,
        "draft_outcome": outcome(draft, text) or None})
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "captured", "name": doc.name}
