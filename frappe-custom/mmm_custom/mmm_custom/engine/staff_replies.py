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

from mmm_custom.engine.text import EMAIL_RE, PHONE_RE, fold, word_set

MAX_CANDIDATES = 12
# 1.500.000đ · 1,500,000 đồng · 1,5 triệu · 1tr5 · 1.5tr · 1500k
MONEY_RE = re.compile(r"(?<![\w.,])(?:(\d{1,3}(?:[.,]\d{3})+)\s*(?:đ|đồng|vnđ|vnd)?"
                      r"|(\d+(?:[.,]\d+)?)\s*(?:tr|triệu)(?:\s*(\d))?"
                      r"|(\d+)\s*k)(?![\w])", re.IGNORECASE)
DRAFT_PREFIXES = ("💡", "✍️")  # the bot's draft note (engine/draft.py) and the Gemini one (engine/llm_draft.py)
STAFF_PREFIXES = DRAFT_PREFIXES + ("⚠", "👤", "🤖", "⏰")  # private notes written by the bot, never staff replies


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


def similarity(wa, wb):
    """Shared words over all words (Jaccard) of two text.word_set()s."""
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


def _scored(catalog, text, course, group, drafting):
    """(score, reply) for every usable library reply that shares a word with the message. Customers only ever get
    approved replies; staff drafts may also use new ones."""
    asked = word_set(text)
    for reply in catalog.staff_replies:
        if (reply.approved or drafting) and fits(reply, course, group):
            score = max((similarity(asked, words) for words in reply.example_words), default=0.0)
            if score > 0:
                yield score, reply


def candidates(catalog, text, course=None, group="", drafting=False, limit=MAX_CANDIDATES):
    """The library replies worth showing Jev for this message, most similar first."""
    ranked = sorted(_scored(catalog, text, course, group, drafting), key=lambda p: (-p[0], p[1].name))
    return [reply for _, reply in ranked[:limit]]


def any_candidate(catalog, text, course=None, group="", drafting=False):
    """Whether staff once answered something like this (stops at the first match)."""
    return next(_scored(catalog, text, course, group, drafting), None) is not None


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
        if private and not draft and content.startswith(DRAFT_PREFIXES):
            draft, kind_of_draft = content.split("\n\n", 1)[-1], "llm" if content.startswith(DRAFT_PREFIXES[1]) else "bot"
        if kind in (0, "incoming") and content:
            texts.append(content)
    return "\n".join(reversed(texts)), draft, kind_of_draft


def capture(conversation_id, message_id, text, consultant=""):
    """RQ job (bot_api, agent_message): keep a staff reply with what it answered, as a new library entry."""
    from mmm_custom.engine.repo import FrappeRepo, chatwoot_admin
    from mmm_custom.engine.state import ConversationState
    from mmm_custom.engine.understand import understand

    if not text or text.startswith(STAFF_PREFIXES) or len(word_set(text)) < 3:
        return {"status": "ignored"}
    asked, draft, drafted_by = customer_turn(chatwoot_admin().list_messages(int(conversation_id)).get("payload") or [],
                                             int(message_id))
    if not asked:
        return {"status": "ignored", "reason": "nothing_asked"}
    repo = FrappeRepo()
    catalog = repo.catalog()
    state = repo.state_of(conversation_id) or ConversationState(str(conversation_id))
    course = catalog.course_in(state.slots)
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


# ---------------------------------------------------------------- review screen ("Tri thức khóa học" → "Câu trả lời NV")
FIELDS = ["name", "status", "course", "course_group", "topic", "customer_examples", "reply", "needs_check", "consultant",
          "source", "draft_outcome", "modified"]


def preview(reply, course, catalog, render):
    """The reply as the customer would read it with today's data, or the template error."""
    from mmm_custom.engine.context import base_context
    from mmm_custom.engine.render import RenderError, render_text
    from mmm_custom.engine.state import ConversationState

    slot = catalog.slot_for("course")
    slots = {slot.key: {"value": course.code}} if course and slot else {}
    try:
        return render_text(reply, base_context(slots, catalog, ConversationState("preview")), render), ""
    except RenderError as e:
        return "", str(e)[:300]


def outcome_stats(rows):
    """{used, edited, ignored, total} from rows counted per draft_outcome ({"draft_outcome", "n"}). Pure."""
    counts = {"used": 0, "edited": 0, "ignored": 0}
    for r in rows:
        if r.get("draft_outcome") in counts:
            counts[r["draft_outcome"]] += int(r.get("n") or 0)
    return {**counts, "total": sum(counts.values())}


@frappe.whitelist() if frappe else (lambda f: f)
def library(product=None):
    """The staff replies of one course (and of its group), newest first, with a preview; plus the review queue size."""
    from mmm_custom.engine.knowledge import ROLES
    from mmm_custom.engine.render import frappe_renderer
    from mmm_custom.engine.repo import FrappeRepo

    frappe.only_for(ROLES)
    catalog = FrappeRepo().catalog()
    course = catalog.courses.get(product) if product else None
    filters = {"status": ["!=", "rejected"]}
    or_filters = [["course", "=", course.code], ["course_group", "=", course.group]] if course else None
    rows = frappe.get_all("Staff Reply", filters=filters, or_filters=or_filters, fields=FIELDS,
                          order_by="status desc, modified desc", limit=300)
    for r in rows:
        if course and r.course_group == course.group and not r.course:
            r["scope"] = "group"
        r["preview"], r["error"] = preview(r.reply, course, catalog, frappe_renderer)
    stats = outcome_stats(frappe.get_all("Staff Reply", filters={"draft_outcome": ["is", "set"]},
                                         fields=["draft_outcome", "count(name) as n"], group_by="draft_outcome"))
    return {"replies": rows, "pending": frappe.db.count("Staff Reply", {"status": "new"}), "stats": stats}


@frappe.whitelist() if frappe else (lambda f: f)
def review(name, status, reply=None):
    """Approve or reject a staff reply, optionally with an edited template. An approved reply must render and must
    not carry amounts the course data does not explain (needs_check), unless the manager edited them."""
    from mmm_custom.engine.knowledge import ROLES
    from mmm_custom.engine.render import frappe_renderer
    from mmm_custom.engine.repo import FrappeRepo

    frappe.only_for(ROLES)
    if status not in ("approved", "rejected", "new"):
        frappe.throw("Trạng thái không hợp lệ.")
    doc = frappe.get_doc("Staff Reply", name)
    edited = reply is not None and reply.strip() != (doc.reply or "").strip()
    if edited:
        doc.reply = reply.strip()
    if status == "approved":
        catalog = FrappeRepo().catalog()
        course = catalog.courses.get(doc.course) or next(
            (c for c in catalog.courses.values() if c.group == doc.course_group), None)
        _, error = preview(doc.reply, course, catalog, frappe_renderer)
        if error:
            frappe.throw(f"Câu trả lời chưa hiển thị được: {error}")
        if doc.needs_check and not edited:
            frappe.throw(f"Kiểm tra lại số tiền {doc.needs_check} (không khớp học phí khóa) rồi sửa trước khi duyệt.")
        if edited:
            doc.needs_check = None
    doc.status = status
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status, "reply": doc.reply}


def on_change(doc, method=None):
    """doc_events: reload the bot's library when a reply is reviewed or edited, not for each newly captured one
    (those reach staff drafts at the next reload)."""
    from mmm_custom.engine.repo import clear_catalog_cache

    if not doc.flags.in_insert and (doc.has_value_changed("status") or doc.has_value_changed("reply")):
        clear_catalog_cache()

