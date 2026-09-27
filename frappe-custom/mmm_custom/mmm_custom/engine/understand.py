"""What a customer message says, as data for decide(): filled slots, chosen parents, skills."""

from dataclasses import dataclass, field

from mmm_custom.engine.slot_types import REGISTRY, course_phrases
from mmm_custom.engine.text import content_words, find_phrases, fold

YES = frozenset({"dung", "dung roi", "dung a", "dung roi a", "phai", "phai a", "vang", "da", "da dung", "da phai",
                 "ok", "oke", "uh", "u", "chuan", "chinh xac"})
NO = frozenset({"khong", "khong phai", "khong a", "khong phai a", "ko", "k", "sai", "sai roi", "khong dung"})


@dataclass
class Understanding:
    fills: dict = field(default_factory=dict)      # slot_key -> {"value", "source", "confidence"}
    parents: dict = field(default_factory=dict)    # slot_key -> chosen course group / area
    ambiguous: dict = field(default_factory=dict)  # slot_key -> [candidate values]
    skipped: list = field(default_factory=list)    # optional slots the customer skipped
    skills: list = field(default_factory=list)     # skill keys, in the order they appeared
    handoff: bool = False                          # a "talk to a person" button was tapped
    focus: str = ""                                # a follow-up button asked for this slot
    tapped: bool = False                           # the message was a quick-reply tap
    matches: list = field(default_factory=list)    # what matched, for the decision log
    spans: list = field(default_factory=list)      # (start, end) of matched phrases in the folded text
    unmatched: list = field(default_factory=list)  # content words that matched nothing
    confirm: dict = field(default_factory=dict)
    rejected: dict = field(default_factory=dict)
    intent: dict = field(default_factory=dict)
    hotness: dict = field(default_factory=dict)
    wants_human: float = 0.0
    spam: float = 0.0


def apply_action(u, action):
    """A quick-reply tap: the stored action decides exactly what the customer chose (D-034)."""
    kind = action.get("type")
    if kind == "slot":
        u.fills[action["slot"]] = {"value": action["value"], "source": "button", "confidence": 1.0}
    elif kind == "parent":
        u.parents[action["slot"]] = action["value"]
    elif kind == "skip":
        u.skipped.append(action["slot"])
    elif kind == "skill":
        u.skills.append(action["skill"])
    elif kind == "ask":
        u.focus = action["slot"]
    elif kind == "confirm_yes":
        if action.get("slot"):
            u.fills[action["slot"]] = {"value": action["value"], "source": "confirmed", "confidence": 1.0}
        elif action.get("skill"):
            u.skills.append(action["skill"])
    elif kind == "confirm_no":
        u.rejected = {k: v for k, v in action.items() if k != "type"}
        if action.get("slot"):
            u.focus = action["slot"]
    elif kind == "handoff":
        u.handoff = True


def _match_skills(folded, catalog, u):
    hits = find_phrases(folded, {k: s.aliases for k, s in catalog.skills.items()})
    for key, span in sorted(hits.items(), key=lambda kv: kv[1][0]):
        u.skills.append(key)
        u.spans.append(span)
        u.matches.append({"skill": key, "kind": "skill"})


def understand(text, state, catalog):
    """Keyword tier (D-028): exact button taps first, then folded aliases/regexes per slot type and skill."""
    u = Understanding()
    action = (state.pending.get("options") or {}).get((text or "").strip())
    if action:
        u.tapped = True
        apply_action(u, action)
        return u
    confirm = state.pending.get("confirm")
    if confirm and fold(text) in YES | NO:
        u.tapped = True
        apply_action(u, {"type": "confirm_yes" if fold(text) in YES else "confirm_no", **confirm})
        return u
    folded = fold(text)
    pending = state.pending.get("slot") or ""
    slots = [(s, REGISTRY[s.type]) for s in catalog.slots
             if s.type in REGISTRY and (not s.on_demand or pending == s.key)]
    for slot, handler in slots:
        if not handler.late:
            handler.understand(slot, text or "", folded, pending == slot.key, catalog, u)
    _match_skills(folded, catalog, u)
    for slot, handler in slots:
        if handler.late:
            handler.understand(slot, text or "", folded, pending == slot.key, catalog, u)
    u.unmatched = content_words(folded, u.spans)
    return u


def match_courses(text, catalog):
    """Courses mentioned in free text, in order of appearance (used by the sync webhook, api.py)."""
    hits = find_phrases(fold(text), course_phrases(catalog))
    return [catalog.courses[code] for code, _ in sorted(hits.items(), key=lambda kv: kv[1][0])]
