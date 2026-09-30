"""Automatic lead qualification (D-083, statuses D-116) — pure. The bot's target status for its Lead:
Qualified (đủ thông tin) once it has a course and a phone, or Jev reads the customer as hot;
Unqualified (không phù hợp) when Jev reads an existing student's support request, Junk when it reads spam.
The bot never downgrades a Lead it qualified; whether the Lead may move at all is lifecycle.can_auto_move
(repo), so a status a person set or a later step (handoff, trial) is never undone."""

from mmm_custom.engine.state import filled
from mmm_custom.lifecycle import JUNK, LABELS, NEW, QUALIFIED, UNQUALIFIED

NOT_A_BUYER = {"support": UNQUALIFIED, "spam": JUNK}

__all__ = ["JUNK", "LABELS", "NEW", "QUALIFIED", "UNQUALIFIED", "lead_status"]


def lead_status(slots, ai, catalog, previous=""):
    """`ai` holds the confident `ai_intent`/`ai_hotness` values known for the conversation."""
    if previous == QUALIFIED:
        return QUALIFIED
    course = catalog.slot_for("course")
    phone = next((s for s in catalog.slots if s.type == "phone"), None)
    has_contact = bool(course and phone and filled(slots, course.key) and filled(slots, phone.key))
    if has_contact or ai.get("ai_hotness") == "hot":  # a purchase intent alone proved too noisy
        return QUALIFIED
    if ai.get("ai_intent") in NOT_A_BUYER:
        return NOT_A_BUYER[ai["ai_intent"]]
    return previous or NEW
