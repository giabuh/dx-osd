"""decide(): the pure heart of a bot turn (D-025) — no I/O, offline-testable.

Given the conversation state, what the message was understood to say, and the catalog, return one
Decision: answer skill(s) (and ask the next slot), ask the next missing slot, hand off, or stay silent.
"""

import copy
from dataclasses import dataclass, field

from mmm_custom.engine.state import filled, value

HANDOFF_REASONS = {
    "button": "Khách chọn gặp tư vấn viên",
    "skill": "Câu hỏi cần tư vấn viên xử lý",
    "required_filled": "Đã đủ thông tin bắt buộc",
    "stuck": "Bot chưa hiểu khách nhiều lượt liên tiếp",
}


@dataclass
class Decision:
    type: str                                   # answer | ask_slot | handoff | silent
    slots: dict = field(default_factory=dict)   # slots after this turn
    new_slots: list = field(default_factory=list)
    skills: list = field(default_factory=list)  # skill keys to answer, in reply order
    ask: str = ""                               # slot whose question ends the reply
    greet: bool = False
    fallback: bool = False
    handoff_reason: str = ""                    # button | skill | required_filled | stuck
    pending_skill: str = ""
    stuck_turns: int = 0
    reason: str = ""


def slot_active(slot, slots):
    return not slot.depends_on or value(slots, slot.depends_on[0]) == slot.depends_on[1]


def required_filled(slots, catalog):
    return all(filled(slots, s.key) for s in catalog.slots if s.required and slot_active(s, slots))


def merge(slots, u, catalog):
    """Apply an Understanding to the slots; returns (slots, newly filled keys, other changed keys)."""
    out = copy.deepcopy(slots)
    changed = []
    for key, parent in u.parents.items():
        slot, entry = catalog.slot(key), out.setdefault(key, {})
        if slot and entry.get("parent") != parent:
            entry["parent"] = parent
            entry.pop("candidates", None)
            changed.append(key)
            if filled(out, key) and catalog.parent_of(slot, entry["value"]) != parent:
                entry.pop("value", None)  # D-029: a course outside the chosen group is dropped
    for key, candidates in u.ambiguous.items():
        if key not in u.fills:
            out.setdefault(key, {})["candidates"] = list(candidates)
            changed.append(key)
    new = []
    for key, fill in u.fills.items():
        slot, entry = catalog.slot(key), out.setdefault(key, {})
        if entry.get("value") != fill["value"]:
            entry.update(fill)
            new.append(key)
        entry.pop("candidates", None)
        parent = catalog.parent_of(slot, fill["value"]) if slot else ""
        if parent:
            entry["parent"] = parent
    for key in u.skipped:
        out.setdefault(key, {})["skipped"] = 1
        changed.append(key)
    return out, new, changed


def pick_skills(state, u, slots, catalog):
    """Skills to answer now (capped, by sort_order) and the first one still waiting for a slot."""
    keys = list(dict.fromkeys(u.skills + ([state.pending_skill] if state.pending_skill else [])))
    ready, waiting = [], ""
    for key in keys:
        skill = catalog.skills.get(key)
        if not skill:
            continue
        missing = [p for p in skill.params if catalog.slot(p) and not filled(slots, p)]
        if missing and skill.missing_policy == "ask":
            waiting = waiting or key
            continue
        ready.append(skill)
    ready.sort(key=lambda s: s.order)
    return [s.key for s in ready[: int(catalog.settings["max_skills_per_reply"])]], waiting


def next_slot(slots, catalog, first=()):
    ordered = [catalog.slot(k) for k in first if catalog.slot(k)] + list(catalog.slots)
    for slot in ordered:
        entry = slots.get(slot.key) or {}
        if filled(slots, slot.key) or not slot_active(slot, slots):
            continue
        if not slot.required and (entry.get("asked") or entry.get("skipped")):
            continue
        return slot.key
    return ""


def handoff_reason(u, skills, slots, stuck, catalog):
    if u.handoff:
        return "button"
    if any(catalog.skills[k].action == "handoff" or catalog.skills[k].handoff_after for k in skills):
        return "skill"
    if required_filled(slots, catalog):
        return "required_filled"
    if stuck >= int(catalog.settings["max_stuck_turns"]):
        return "stuck"
    return ""


def decide(state, u, catalog):
    keep = dict(slots=copy.deepcopy(state.slots), stuck_turns=state.stuck_turns, pending_skill=state.pending_skill)
    if state.status == "closed":
        return Decision("silent", **keep, reason="Hội thoại đã đóng")
    if state.consultant_replied:
        return Decision("silent", **keep, reason="Tư vấn viên đã nhắn khách, bot im lặng")

    slots, new, changed = merge(state.slots, u, catalog)
    skills, waiting = pick_skills(state, u, slots, catalog)
    greet = state.turns == 0 and not skills
    progress = bool(new or changed or skills or waiting or u.handoff or u.focus)
    stuck = 0 if progress or greet else state.stuck_turns + 1
    common = dict(slots=slots, new_slots=new, skills=skills, pending_skill=waiting, stuck_turns=stuck)
    answered = ", ".join(catalog.skills[k].title for k in skills)

    if state.status == "handed_off":
        if skills:
            return Decision("answer", **common, reason=f"Đã chuyển tư vấn viên; trả lời: {answered}")
        return Decision("silent", **common, reason="Đã chuyển tư vấn viên, chờ tư vấn viên nhắn")

    why = handoff_reason(u, skills, slots, stuck, catalog)
    if why:
        return Decision("handoff", **common, handoff_reason=why, reason=HANDOFF_REASONS[why])

    first = ([u.focus] if u.focus else []) + (list(catalog.skills[waiting].params) if waiting else [])
    ask = next_slot(slots, catalog, first)
    if ask:
        slots.setdefault(ask, {})["asked"] = 1
    label = catalog.slot(ask).label.lower() if ask else ""
    reason = f"Trả lời: {answered}" if skills else ""
    if ask:
        reason = f"{reason}; hỏi tiếp {label}" if reason else f"Hỏi {label} (còn thiếu)"
    return Decision("answer" if skills else "ask_slot", **common, ask=ask, greet=greet,
                    fallback=not progress and not greet, reason=reason)
