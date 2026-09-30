"""Jev questions generated from CRM data (D-028, D-039, D-075): only what is still open, criteria in
English carrying the Vietnamese names and aliases customers use. Keys:
    parent:<slot>  course group / area          slot:<slot>  course, branch, choice or number value
    skill:<key>    one noul per Bot Skill        intent · hotness · wants_human (D-032)
    course_faq     which FAQ of the known course the message asks (D-085)
    course_fact    which part of the known course's own data the message asks: content, length, audience… (D-110)
    staff_reply    which reply staff once wrote answers the message, among the most similar ones (D-114)
    level_unsure   unsure of their level, asked only while a level test can be offered (D-106)
    reply_to_bot   which of the buttons the bot just offered a typed message means (D-107)
"""

from mmm_custom.engine import staff_replies
from mmm_custom.engine.context import shown_slots
from mmm_custom.engine.decide import slot_active
from mmm_custom.engine.offers import LEVEL_UNSURE, available
from mmm_custom.engine.state import filled
from mmm_custom.intelligence import HOTNESS_CRITERIA, INTENTS

NONE = "none"
NONE_TEXT = "None of these, or not said in the chat"
MAX_HISTORY = 20  # 10 turns of customer + bot lines (D-061, D-074)
COURSE_FAQ = "course_faq"
COURSE_FACT = "course_fact"
STAFF_REPLY = "staff_reply"
REPLY_TO_BOT = "reply_to_bot"
# Parts of a course's own data the bot can answer from (D-110): key -> (Course attribute, what the customer asks).
# Fee and schedules are skills of their own (fee_quote, schedule_lookup) with promotions and open classes.
FACTS = {
    "summary": ("summary", "What the course is, what it is about overall"),
    "syllabus": ("syllabus", "The lessons, topics or programme the course teaches"),
    "duration": ("duration", "How long the course takes: weeks, months, number of sessions"),
    "audience": ("audience", "Who the course is for: level needed, beginners, age"),
    "certificate": ("certificate", "Whether a certificate or diploma is given at the end"),
    "next": ("next_courses", "What to study after this course"),
}


def _named(name, aliases=()):
    return f"{name} (customers also write: {', '.join(aliases)})" if aliases else name


def course_criterion(c):
    """How Jev reads one course among the choices of the course question."""
    return f"{_named(c.name, c.aliases)}; group: {c.group}; for: {c.audience}"


def _choice(instructions, criteria):
    return {"type": "choice", "instructions": instructions, "criteria": {**criteria, NONE: NONE_TEXT}}


def faq_course(state, u, catalog):
    """The course whose FAQs Jev reads: the one named in this message, else the one already known."""
    slot = catalog.slot_for("course")
    if not slot:
        return None
    course = catalog.courses.get((u.fills.get(slot.key) or state.slots.get(slot.key) or {}).get("value"))
    return course if course and course.faqs else None


def known_course(state, u, catalog):
    """The course named in this message, else the one already known."""
    slot = catalog.slot_for("course")
    if not slot:
        return None
    return catalog.courses.get((u.fills.get(slot.key) or state.slots.get(slot.key) or {}).get("value"))


def course_facts(course):
    """The FACTS this course has data for, in FACTS order."""
    return [key for key, (attr, _) in FACTS.items() if course and getattr(course, attr)]


def jev_state(text, state, catalog):
    pending = catalog.slot(state.pending.get("slot") or "")
    return {"latest_message": text, "recent_turns": list(state.history[-MAX_HISTORY:]),
            "known": shown_slots(state.slots, catalog), "bot_question": pending.label if pending else ""}


def _catalog_questions(slot, state, u, catalog):
    entry = state.slots.get(slot.key) or {}
    candidates = u.ambiguous.get(slot.key) or entry.get("candidates") or []
    parent = u.parents.get(slot.key) or entry.get("parent") or ""
    if slot.source == "course":
        parents = {g.name: _named(g.name, g.aliases) for g in catalog.groups.values()}
        leaves = {c.code: course_criterion(c) for c in catalog.courses.values()}
        what, parent_what = "course", "course group (field of study)"
    else:
        parents = {a.name: _named(a.name, a.aliases) for a in catalog.areas.values()}
        leaves = {b.name: f"{_named(b.name, b.aliases)}; address: {b.address}" for b in catalog.branches.values()}
        what, parent_what = "branch (campus) where the customer wants to study", "province or area"
    if candidates:
        leaves = {k: v for k, v in leaves.items() if k in candidates}
    elif parent:
        leaves = {k: v for k, v in leaves.items() if catalog.parent_of(slot, k) == parent}
    out = {}
    if not parent and not candidates:
        out[f"parent:{slot.key}"] = _choice(f"Which {parent_what} does the customer mean in this Vietnamese chat?", parents)
    out[f"slot:{slot.key}"] = _choice(f"Which {what} does the customer mean in this Vietnamese chat?", leaves)
    return out


def build_questions(state, u, catalog, skills=True, text=""):
    q = {}
    for slot in catalog.slots:
        if slot.on_demand and state.pending.get("slot") != slot.key:
            continue
        known = {**state.slots, **u.fills}
        # a number said together with a still-unknown dependency ("con mình 8 tuổi"): ask now, combine checks it
        early = (slot.type == "number" and slot.depends_on and not filled(known, slot.depends_on[0])
                 and u.has_number)
        if not (slot_active(slot, known) or early) or (filled(state.slots, slot.key) and u.focus != slot.key):
            continue  # D-075: open before this message; this turn's keyword matches are still cross-checked
        if slot.type == "catalog":
            q.update(_catalog_questions(slot, state, u, catalog))
        elif slot.type == "choice":
            q[f"slot:{slot.key}"] = _choice(f"What does the customer answer for '{slot.label}' in this Vietnamese chat?",
                                            {o.value: _named(o.label, o.aliases) for o in slot.options})
        elif slot.type == "number":
            q[f"slot:{slot.key}"] = _choice(f"Which number does the customer give for '{slot.label}'?",
                                            {str(n): str(n) for n in range(1, 100)})
    if skills:
        for key, skill in catalog.skills.items():
            question = {"type": "noul", "instructions": f"Does the customer's latest message ask about this: {skill.description or skill.title}?"}
            if skill.examples:
                question["criteria"] = {"true": "Messages like: " + " | ".join(skill.examples),
                                        "false": "The latest message is about something else"}
            q[f"skill:{key}"] = question
        course = faq_course(state, u, catalog)
        if course:
            q[COURSE_FAQ] = _choice(f"Which of these questions about the course '{course.name}' does the customer's latest message ask?",
                                    {str(i): _named(f.question, f.examples) for i, f in enumerate(course.faqs)})
        known = known_course(state, u, catalog)
        facts = course_facts(known)
        if facts:
            q[COURSE_FACT] = _choice(f"What does the customer's latest message ask about the course '{known.name}'?",
                                     {key: FACTS[key][1] for key in facts})
        group = u.parents.get("course") or (state.slots.get("course") or {}).get("parent", "")
        library = staff_replies.candidates(catalog, text, known, group, state.drafting) if text else []
        if library:
            q[STAFF_REPLY] = _choice("Which of these replies that staff once wrote answers the customer's latest "
                                     "message in this Vietnamese chat? Choose none unless it fits the question.",
                                     {r.name: staff_replies.criterion(r) for r in library})
    options = list((state.pending.get("options") or {}))
    if options and not u.tapped:  # a typed answer the keyword tier could not tie to a button (D-107)
        q[REPLY_TO_BOT] = _choice("The bot's last message offered these buttons. Which one does the customer's latest "
                                  "message choose, in their own words (agreeing, refusing, a date, an answer)? "
                                  "Choose none when they ask or say something else.",
                                  {str(i): title for i, title in enumerate(options)})
    q["intent"] = {"type": "choice", "instructions": "What does the customer want in this Vietnamese chat with a training centre?",
                   "criteria": INTENTS}
    q["hotness"] = {"type": "score", "instructions": "How close is the customer to enrolling, based on the whole chat?",
                    "criteria": HOTNESS_CRITERIA}
    q["wants_human"] = {"type": "noul", "instructions": "Does the customer ask to talk to a real person or consultant, or to be called back?"}
    if available(state, {**state.slots, **u.fills}, catalog):  # only when a level test could be offered (D-106)
        q[LEVEL_UNSURE] = {"type": "noul", "instructions": "Is the customer unsure of their current level, or of "
                                                          "whether a basic or an advanced course fits them?"}
    return q
