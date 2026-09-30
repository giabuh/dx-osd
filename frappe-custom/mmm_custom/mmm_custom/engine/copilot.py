"""Staff assist (D-111): who answers a customer message.

Nobody from the staff is around → the bot answers at once (AUTO). A person watches the conversation, has
claimed it ("Nhận xử lý") or has written in it → ASSIST: the bot posts its draft as a private note for that
person, queues the message, and answers the queued messages itself when nobody has within
`assist_wait_minutes` (scheduler: `run_due` every minute). A staff message empties the queue.

`mode`, `hold`, `human_replied`, `due`, `merged_event` and `handle`/`answer` are pure given a repo and effects
(offline-testable); `process`, `run_due` and `answer_due` are the Frappe entry points."""

from datetime import datetime, timezone

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine.draft import draft_turn, note
from mmm_custom.engine.pipeline import Event, run_turn

AUTO, ASSIST = "auto", "assist"
MAX_WAITING = 10
CONTACT_KEYS = ("id", "name", "email", "phone_number", "custom_attributes")


def wait_seconds(settings):
    return 60 * float(settings["assist_wait_minutes"])


def mode(state, viewers, settings):
    """ASSIST while a person watches the conversation, has claimed it or has written in it."""
    if int(settings["assist_disabled"] or 0) or state.is_sandbox or state.status == "closed":
        return AUTO
    return ASSIST if (viewers or state.claimed_by or state.consultant_replied) else AUTO


def hold(state, event, now, settings):
    """Queue the message for a person; the first unanswered one starts the timer."""
    waiting = [w for w in state.assist.get("waiting", []) if w["id"] != event.message_id]
    state.assist = {**state.assist, "waiting": (waiting + [{"id": event.message_id, "text": event.text}])[-MAX_WAITING:]}
    if event.contact:
        state.assist["contact"] = {k: event.contact[k] for k in CONTACT_KEYS if event.contact.get(k) is not None}
    if not state.fallback_due:
        state.fallback_due = now + wait_seconds(settings)
    return state


def human_replied(assist, now):
    """A staff message answers everything that was waiting; the hold line may be sent again later."""
    return {**(assist or {}), "waiting": [], "held": False, "human_at": now}


def due(state, now):
    return bool(state.fallback_due) and now >= state.fallback_due and bool(state.assist.get("waiting"))


def merged_event(state):
    """The waiting messages as one customer message (the bot answers them together)."""
    waiting = state.assist.get("waiting") or []
    return Event("customer_message", state.conversation_id, max(int(w["id"]) for w in waiting),
                 "\n".join(w["text"] for w in waiting)[:1000], state.assist.get("contact") or {"id": state.contact_id},
                 state.inbox_id)


def status_attributes(state, assist_mode):
    """What the assist banner in Chatwoot reads from the conversation's custom attributes (D-112)."""
    due_at = datetime.fromtimestamp(state.fallback_due, timezone.utc).isoformat() if state.fallback_due else ""
    return {"bot_mode": assist_mode, "bot_fallback_at": due_at, "claimed_by": state.claimed_by or ""}


def handle(event, repo, effects, render, viewers=()):
    """One customer message: the bot answers it (AUTO), or drafts it for staff and starts the timer (ASSIST)."""
    catalog = repo.catalog()
    state = repo.load_state(event)
    if event.message_id and event.message_id <= state.last_message_id:
        return None  # redelivered webhook
    if mode(state, viewers, catalog.settings) == AUTO:
        if not state.assist.get("waiting"):
            turn = run_turn(event, repo, effects, render)
            if turn and turn.decision.type == "silent" and turn.state.status == "handed_off":
                _suggest(event, repo, effects, render, catalog)  # handed off, nobody here yet: a note for later
            return turn
        hold(state, event, repo.now(), catalog.settings)  # the person left: answer what was waiting, too
        repo.save_state(state)
        turn = run_turn(merged_event(state), repo, effects, render, fallback=True)
        effects.assist_status(state.conversation_id, status_attributes(turn.state if turn else state, AUTO))
        return turn
    turn = _suggest(event, repo, effects, render, catalog)
    hold(state, event, repo.now(), catalog.settings)
    repo.save_state(state)
    effects.assist_status(state.conversation_id, status_attributes(state, ASSIST))
    return turn


def _suggest(event, repo, effects, render, catalog):
    turn = draft_turn(event, repo, render)
    text = note(turn, catalog)
    if text:
        effects.note(event.conversation_id, text)
    return turn


def answer(conversation_id, repo, effects, render):
    """The timer ran out: the bot answers the waiting messages (None when a person answered first)."""
    state = repo.load_state(Event("customer_message", str(conversation_id)))
    if not due(state, repo.now()):
        return None
    turn = run_turn(merged_event(state), repo, effects, render, fallback=True)
    if turn:
        effects.assist_status(state.conversation_id, status_attributes(turn.state, ASSIST))
    return turn


def process(event):
    """Frappe: called by pipeline.process_event under the conversation lock."""
    from mmm_custom.engine.effects import chatwoot_effects
    from mmm_custom.engine.presence import viewers
    from mmm_custom.engine.render import frappe_renderer
    from mmm_custom.engine.repo import FrappeRepo

    return handle(event, FrappeRepo(), chatwoot_effects(frappe.conf), frappe_renderer, viewers(event.conversation_id))


def run_due():
    """Scheduler, every minute: queue the conversations whose wait is over."""
    import time

    for cid in frappe.get_all("Bot Conversation", filters={"fallback_due_at": ["between", [1, time.time()]],
                                                         "status": ["!=", "closed"], "is_sandbox": 0},
                              pluck="conversation_id"):
        frappe.enqueue("mmm_custom.engine.copilot.answer_due", queue="short", conversation_id=cid,
                       job_id=f"assist_due_{cid}", deduplicate=True)


def answer_due(conversation_id):
    from frappe.utils.synchronization import filelock

    from mmm_custom.engine.effects import chatwoot_effects
    from mmm_custom.engine.render import frappe_renderer
    from mmm_custom.engine.repo import FrappeRepo

    with filelock(f"lead_engine_conversation_{conversation_id}", timeout=60):
        answer(conversation_id, FrappeRepo(), chatwoot_effects(frappe.conf), frappe_renderer)
        frappe.db.commit()
