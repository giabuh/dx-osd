"""What a customer message says, as data for decide(): filled slots, chosen parents, skills."""

from dataclasses import dataclass, field

from mmm_custom.engine.slot_types import REGISTRY, course_phrases
from mmm_custom.engine.text import content_words, find_phrases, fold


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
    folded = fold(text)
    pending = state.pending.get("slot") or ""
    slots = [(s, REGISTRY[s.type]) for s in catalog.slots if s.type in REGISTRY]
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
