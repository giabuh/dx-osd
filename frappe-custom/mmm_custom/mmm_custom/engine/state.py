"""Per-conversation bot state (the `Bot Conversation` DocType, D-024) as a plain object.

`slots` maps slot_key → entry dict: `value` (when filled), `source` (button / keyword / jev / lead /
contact), `confidence`, and bookkeeping keys `parent` (chosen course group / area), `candidates`
(ambiguous values), `asked`, `skipped`. `pending` holds the question being asked and the offered
buttons as title → action (D-034).
"""

from dataclasses import dataclass, field


@dataclass
class ConversationState:
    conversation_id: str
    contact_id: str = ""
    inbox_id: str = ""
    lead: str = ""
    status: str = "active"  # active | handed_off | closed
    slots: dict = field(default_factory=dict)
    pending: dict = field(default_factory=dict)
    pending_skill: str = ""
    stuck_turns: int = 0
    last_message_id: int = 0
    consultant_replied: bool = False
    consultant: str = ""
    is_sandbox: bool = False
    is_returning: bool = False
    turns: int = 0
    answered: list = field(default_factory=list)  # skill keys answered so far
    history: list = field(default_factory=list)  # last turns for Jev's state
    jev_calls: list = field(default_factory=list)  # epoch seconds of Jev calls in the last hour
    ai: dict = field(default_factory=dict)  # last intent/hotness values written to the Lead


def value(slots, key):
    return (slots.get(key) or {}).get("value")


def filled(slots, key):
    return value(slots, key) not in (None, "")
