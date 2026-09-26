"""What a customer message says, as data for decide(): filled slots, chosen parents, skills."""

from dataclasses import dataclass, field


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


def understand(text, state, catalog):
    return Understanding()
