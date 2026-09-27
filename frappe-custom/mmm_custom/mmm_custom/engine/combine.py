"""Keyword tier + Jev answers → one Understanding (D-029, D-030, D-063). Pure, no I/O.

Rules: a button tap is final; a unique keyword match wins unless Jev confidently picks another value
(→ confirm, never a silent swap); Jev picks among ambiguous candidates; a child outside a confident
parent is dropped; per slot type, act ≥ act threshold, confirm ≥ confirm threshold, else nothing.
At most one confirmation per turn, in slot order."""

import copy

from mmm_custom.engine.context import display
from mmm_custom.engine.jev_questions import NONE


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


def _slots(u, answers, questions, catalog):
    for slot in catalog.slots:
        choice, p = _choice(answers, questions, f"slot:{slot.key}")
        if choice is None:
            continue
        value = int(choice) if slot.type == "number" else choice
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


def combine(u, answers, questions, state, catalog):
    if u.tapped:
        return u  # buttons (and typed answers to a confirmation) are never overridden
    out = copy.deepcopy(u)
    answers = answers if isinstance(answers, dict) else {}
    _slots(out, answers, questions, catalog)
    _parents(out, answers, questions, catalog)
    return out
