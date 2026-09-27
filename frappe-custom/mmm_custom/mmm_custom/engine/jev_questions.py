"""Jev questions generated from CRM data (D-028, D-039, D-075): only what is still open, criteria in
English carrying the Vietnamese names and aliases customers use. Keys:
    parent:<slot>  course group / area          slot:<slot>  course, branch, choice or number value
    skill:<key>    one noul per Bot Skill        intent · hotness · wants_human (D-032)
"""

from mmm_custom.engine.context import shown_slots
from mmm_custom.engine.decide import slot_active
from mmm_custom.engine.state import filled
from mmm_custom.intelligence import HOTNESS_CRITERIA, INTENTS

NONE = "none"
NONE_TEXT = "None of these, or not said in the chat"
MAX_HISTORY = 20  # 10 turns of customer + bot lines (D-061, D-074)


def _named(name, aliases=()):
    return f"{name} (customers also write: {', '.join(aliases)})" if aliases else name


def _choice(instructions, criteria):
    return {"type": "choice", "instructions": instructions, "criteria": {**criteria, NONE: NONE_TEXT}}


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
        leaves = {c.code: f"{_named(c.name, c.aliases)}; group: {c.group}; for: {c.audience}" for c in catalog.courses.values()}
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


def build_questions(state, u, catalog, skills=True):
    q = {}
    for slot in catalog.slots:
        if not slot_active(slot, state.slots) or filled(state.slots, slot.key):
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
    q["intent"] = {"type": "choice", "instructions": "What does the customer want in this Vietnamese chat with a training centre?",
                   "criteria": INTENTS}
    q["hotness"] = {"type": "score", "instructions": "How close is the customer to enrolling, based on the whole chat?",
                    "criteria": HOTNESS_CRITERIA}
    q["wants_human"] = {"type": "noul", "instructions": "Does the customer ask to talk to a real person or consultant, or to be called back?"}
    return q
