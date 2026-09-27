"""Automatic lead qualification (D-083) — pure. The bot sorts its Leads into the standard CRM statuses:
Qualified (tiềm năng) once it has a course and a phone, or the customer is hot / wants to buy;
Unqualified (không tiềm năng) when Jev reads an existing student's support request or spam. A Lead the
bot marked Qualified is never downgraded by the bot, and a status a person set is left alone (repo)."""

from mmm_custom.engine.state import filled

NEW, QUALIFIED, UNQUALIFIED = "New", "Qualified", "Unqualified"
AUTO_STATUSES = (NEW, QUALIFIED, UNQUALIFIED)  # any other status was set by a person
NOT_A_BUYER = ("support", "spam")
LABELS = {QUALIFIED: "tiềm năng", UNQUALIFIED: "không tiềm năng", NEW: "mới"}


def lead_status(slots, ai, catalog, previous=""):
    """`ai` holds the confident `ai_intent`/`ai_hotness` values known for the conversation."""
    if previous == QUALIFIED:
        return QUALIFIED
    course = catalog.slot_for("course")
    phone = next((s for s in catalog.slots if s.type == "phone"), None)
    has_contact = bool(course and phone and filled(slots, course.key) and filled(slots, phone.key))
    if has_contact or ai.get("ai_hotness") == "hot" or ai.get("ai_intent") == "purchase":
        return QUALIFIED
    if ai.get("ai_intent") in NOT_A_BUYER:
        return UNQUALIFIED
    return previous or NEW
