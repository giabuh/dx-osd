"""What the bot would answer, for staff (D-110): the reply suggestion is the bot's own answer from the course's
data (FAQ, facts, fee, schedules, promotions), never a canned template. Runs `run_turn(draft=True)` on a repo
that reads everything and writes nothing, with effects that only record."""

import copy

from mmm_custom.engine.decide import faq_question, fact_label
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import run_turn

NOTE_HEADER = "💡 Jev gợi ý"
NO_KNOWLEDGE = "⚠ Jev chưa có tri thức để trả lời câu này. Bạn trả lời giúp nhé."
FOR_STAFF = "👤 Khách cần tư vấn viên ({why}). Bạn trả lời giúp nhé."


class DraftRepo:
    """Reads through `repo`, writes nothing. The bot drafts as if it still led the conversation: no person has
    written and nothing was handed off (D-059 and D-026 are about what it sends, not what it suggests). Jev
    tokens still count against the daily budget."""

    def __init__(self, repo):
        self.repo = repo

    def __getattr__(self, name):
        return getattr(self.repo, name)

    def load_state(self, event):
        state = copy.deepcopy(self.repo.load_state(event))
        state.consultant_replied, state.drafting = False, True
        if state.status == "handed_off":
            state.status = "active"
        return state

    def save_state(self, state):
        pass

    def write_log(self, row):
        pass

    def write_signal(self, row):
        pass

    def save_quiz_attempt(self, state, change):
        pass


def draft_turn(event, repo, render):
    return run_turn(event, DraftRepo(repo), RecordingEffects(), render, draft=True)


def sources(turn, catalog):
    """What the draft is built from, as staff read it."""
    d = turn.decision
    out = [f'FAQ "{faq_question(d.faq, catalog)}"'] if d.faq else []
    out += [fact_label(d.fact, catalog)] if d.fact else []
    if d.staff_reply:
        out.append("câu trả lời NV" + ("" if catalog.staff_reply(d.staff_reply["name"]).approved else " (chưa duyệt)"))
    out += [catalog.skills[k].title for k in d.skills if k in catalog.skills]
    if d.greet:
        out.append("chào hỏi")
    if d.ask and catalog.slot(d.ask):
        out.append(f"hỏi {catalog.slot(d.ask).label.lower()}")
    return out


def note(turn, catalog):
    """The private note for staff, or None when the bot has nothing to add."""
    if turn is None:
        return None
    d = turn.decision
    if turn.needs_staff and not d.answered:
        return FOR_STAFF.format(why=turn.needs_staff)
    if turn.no_answer:
        return NO_KNOWLEDGE
    if not turn.reply.messages:
        return None
    course = catalog.course_in(d.slots)
    head = [f"khóa {course.name}"] if course else []
    used = sources(turn, catalog)
    head += [f"dựa trên: {', '.join(used)}"] if used else []
    title = f"{NOTE_HEADER} ({'; '.join(head)})" if head else NOTE_HEADER
    body = "\n\n".join(turn.reply.messages)
    buttons = [b["title"] for b in turn.reply.buttons]
    if buttons:
        body += "\n\nNút gợi ý: " + " · ".join(buttons)
    return f"{title}:\n\n{body}"


def suggest(event):
    """Frappe entry point: the note for the conversation's latest customer message (or None)."""
    from mmm_custom.engine.render import frappe_renderer
    from mmm_custom.engine.repo import FrappeRepo

    repo = FrappeRepo()
    return note(draft_turn(event, repo, frappe_renderer), repo.catalog())
