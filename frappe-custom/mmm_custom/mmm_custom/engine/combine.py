"""Keyword tier + Jev answers → one Understanding (D-029, D-030, D-063). Pure, no I/O.

Rules: a button tap is final; a unique keyword match wins unless Jev confidently picks another value
(→ confirm, never a silent swap); Jev picks among ambiguous candidates; a child outside a confident
parent is dropped; per slot type, act ≥ act threshold, confirm ≥ confirm threshold, else nothing.
At most one confirmation per turn, in slot order."""

import copy

from mmm_custom.engine.context import display
from mmm_custom.engine.jev_questions import (COURSE_FACT, COURSE_FAQ, FACTS, NONE, REPLY_TO_BOT, STAFF_REPLY, faq_course,
                                             known_course)
from mmm_custom.engine.offers import LEVEL_UNSURE
from mmm_custom.intelligence import HOTNESS


def slot_limits(slot, settings):
    if slot.type == "catalog":
        return float(settings["catalog_act"]), float(settings["catalog_confirm"])
    return float(settings["choice_act"]), float(settings["choice_confirm"])


def ask_confirm(u, confirm):
    if not u.confirm:
        u.confirm = confirm


def _choice(answers, questions, key):
    """(choice, confidence) when Jev answered `key` with one of the question's own options, else (None, 0)."""
    answer = answers.get(key)
    if not isinstance(answer, dict) or key not in questions:
        return None, 0.0
    choice = answer.get("choice")
    if choice in (None, "", NONE) or str(choice) not in (questions[key].get("criteria") or {}):
        return None, 0.0
    try:
        return str(choice), float(answer.get("confidence") or 0)
    except (TypeError, ValueError):
        return None, 0.0


def _noul(answers, questions, key):
    answer = answers.get(key)
    if key not in questions or not isinstance(answer, dict) or "noul" not in answer:
        return None
    try:
        return float(answer["noul"])
    except (TypeError, ValueError):
        return None


def _skills(u, answers, questions, catalog):
    """Apply one Jev noul per skill; a keyword hit receives at least confirmation."""
    act, confirm = float(catalog.settings["skill_act"]), float(catalog.settings["skill_confirm"])

    def candidate(key):
        return {"kind": "skill", "skill": key, "label": catalog.skills[key].title}

    kept = []
    for key in u.skills:  # the customer typed the alias: it lifts Jev's score one band (D-063)
        n = _noul(answers, questions, f"skill:{key}")
        if n is None or n >= confirm:
            kept.append(key)
        else:
            ask_confirm(u, candidate(key))
    for key in catalog.skills:
        if key in u.skills:
            continue
        n = _noul(answers, questions, f"skill:{key}")
        if n is None:
            continue
        if n >= act:
            kept.append(key)
            u.matches.append({"skill": key, "kind": "jev", "confidence": round(n, 3)})
        elif n >= confirm:
            ask_confirm(u, candidate(key))
    u.skills = kept


def _signals(u, answers, questions, catalog):
    intent, p = _choice(answers, questions, "intent")
    if intent:
        u.intent = {"value": intent, "confidence": round(p, 3)}
        if intent == "spam" and p >= float(catalog.settings["spam_threshold"]):
            u.spam = round(p, 3)
    hot = answers.get("hotness")
    if "hotness" in questions and isinstance(hot, dict):
        try:
            score = float(hot.get("score"))
            u.hotness = {"value": HOTNESS[min(max(round(score), 0), len(HOTNESS) - 1)], "score": round(score, 3),
                         "confidence": round(float(hot.get("confidence") or 0), 3)}
        except (TypeError, ValueError):
            pass
    n = _noul(answers, questions, "wants_human")
    if n is not None:
        u.wants_human = round(n, 3)
    n = _noul(answers, questions, LEVEL_UNSURE)
    if n is not None:
        u.level_unsure = round(n, 3)


def _slots(u, answers, questions, catalog, state):
    for slot in catalog.slots:
        choice, p = _choice(answers, questions, f"slot:{slot.key}")
        if choice is None:
            continue
        value = int(choice) if slot.type == "number" else choice
        if slot.depends_on:
            dep = (u.fills.get(slot.depends_on[0]) or state.slots.get(slot.depends_on[0]) or {}).get("value")
            if dep != slot.depends_on[1]:
                continue  # e.g. an age only counts once the learner is a child
        act, confirm = slot_limits(slot, catalog.settings)
        candidate = {"kind": "slot", "slot": slot.key, "value": value, "label": display(slot, value, catalog)}
        keyword = u.fills.get(slot.key)
        if keyword:
            if keyword["value"] != value and p >= act:  # D-029: confident disagreement → confirm
                del u.fills[slot.key]
                ask_confirm(u, candidate)
            continue
        if p >= act:
            u.fills[slot.key] = {"value": value, "source": "jev", "confidence": round(p, 3)}
            u.ambiguous.pop(slot.key, None)
            u.matches.append({"slot": slot.key, "kind": "jev", "value": value, "confidence": round(p, 3)})
        elif p >= confirm:
            ask_confirm(u, candidate)


def _parents(u, answers, questions, catalog):
    for slot in catalog.slots:
        parent, p = _choice(answers, questions, f"parent:{slot.key}")
        if parent is None or p < float(catalog.settings["catalog_act"]):
            continue
        fill = u.fills.get(slot.key)
        if fill and catalog.parent_of(slot, fill["value"]) != parent:
            del u.fills[slot.key]  # D-029: drop the child, keep the confident parent
        if u.confirm.get("slot") == slot.key and catalog.parent_of(slot, u.confirm["value"]) != parent:
            u.confirm = {}
        if slot.key not in u.fills:
            u.parents.setdefault(slot.key, parent)


def _course_faq(u, answers, questions, course, catalog):
    choice, p = _choice(answers, questions, COURSE_FAQ)
    if course and choice is not None and p >= float(catalog.settings["skill_act"]):
        u.faq = {"course": course.code, "index": int(choice), "confidence": round(p, 3)}
        u.matches.append({"faq": course.code, "index": int(choice), "kind": "jev", "confidence": round(p, 3)})


def _course_fact(u, answers, questions, course, catalog):
    """Jev tied the message to a part of the course's own data (D-110); the course's FAQ, when one fits, wins."""
    choice, p = _choice(answers, questions, COURSE_FACT)
    if u.faq or not course or choice not in FACTS or p < float(catalog.settings["skill_act"]):
        return
    u.fact = {"course": course.code, "fact": choice, "confidence": round(p, 3)}
    u.matches.append({"fact": choice, "course": course.code, "kind": "jev", "confidence": round(p, 3)})


def _staff_reply(u, answers, questions, catalog):
    """Jev picked a reply staff once wrote (D-114); only replies the question offered can be picked."""
    choice, p = _choice(answers, questions, STAFF_REPLY)
    reply = next((r for r in catalog.staff_replies if r.name == choice), None)
    if not reply or p < float(catalog.settings["skill_act"]):
        return
    u.staff_reply = {"name": reply.name, "topic": reply.topic, "approved": reply.approved, "confidence": round(p, 3)}
    u.matches.append({"staff_reply": reply.name, "kind": "jev", "confidence": round(p, 3)})


def _reply_to_bot(u, answers, questions, state, catalog):
    """Jev tied a typed message to one of the offered buttons: act as if it was tapped."""
    from mmm_custom.engine.understand import apply_action

    choice, p = _choice(answers, questions, REPLY_TO_BOT)
    actions = list((state.pending.get("options") or {}).values())
    if choice is None or p < float(catalog.settings["choice_act"]) or int(choice) >= len(actions):
        return
    action = actions[int(choice)]
    skill = catalog.skills.get(action.get("skill")) if action.get("type") == "skill" else None
    if skill and (skill.action == "handoff" or skill.handoff_after):
        # a typed reply never hands off on its own: "Đăng ký giữ chỗ" is asked back first (D-109)
        ask_confirm(u, {"kind": "skill", "skill": skill.key, "label": skill.title})
        return
    apply_action(u, action)
    u.matches.append({"button": int(choice), "kind": "jev", "confidence": round(p, 3)})


def combine(u, answers, questions, state, catalog):
    if u.tapped:
        return u  # buttons (and typed answers to a confirmation) are never overridden
    course = faq_course(state, u, catalog)  # the course the FAQ question was built for
    out = copy.deepcopy(u)
    answers = answers if isinstance(answers, dict) else {}
    if u.greeting:  # "hihi" is small talk: no button, skill or slot, whatever Jev reads into it (D-109)
        _signals(out, answers, questions, catalog)
        return out
    _slots(out, answers, questions, catalog, state)
    _parents(out, answers, questions, catalog)
    _skills(out, answers, questions, catalog)
    _course_faq(out, answers, questions, course, catalog)
    _course_fact(out, answers, questions, known_course(state, u, catalog), catalog)
    _staff_reply(out, answers, questions, catalog)
    _reply_to_bot(out, answers, questions, state, catalog)
    _signals(out, answers, questions, catalog)
    return out
