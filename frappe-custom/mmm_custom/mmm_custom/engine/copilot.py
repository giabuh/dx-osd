"""Staff assist (D-111): who answers a customer message.

Nobody from the staff is around → the bot answers at once (AUTO). A person watches the conversation, has
claimed it ("Nhận xử lý") or has written in it → ASSIST: the bot posts its draft as a private note for that
person, queues the message, and answers the queued messages itself when nobody has within
`assist_wait_minutes` (scheduler: `run_due` every minute). A staff message empties the queue.

`mode`, `hold`, `human_replied`, `due`, `merged_event` and `handle`/`answer` are pure given a repo and effects
(offline-testable); `process`, `run_due` and `answer_due` are the Frappe entry points."""

from datetime import datetime, timezone
import time

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine.draft import NO_KNOWLEDGE, draft_turn, note
from mmm_custom.engine.pipeline import Event, run_turn

AUTO, ASSIST = "auto", "assist"
MAX_WAITING = 10
CONTACT_KEYS = ("id", "name", "email", "phone_number", "custom_attributes")


def wait_seconds(settings):
    return 60 * float(settings["assist_wait_minutes"])


def mode(state, viewers, settings):
    """ASSIST while a person watches the conversation, has claimed it or has written in it. `viewers` is called last,
    only when nothing else decides (it may ask Chatwoot)."""
    if int(settings["assist_disabled"] or 0) or state.is_sandbox or state.status == "closed":
        return AUTO
    return ASSIST if (state.claimed_by or state.consultant_replied or viewers()) else AUTO


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


def status_attributes(state):
    """What the assist banner in Chatwoot reads from the conversation's custom attributes (D-112)."""
    assisting = state.claimed_by or state.consultant_replied or state.fallback_due
    due_at = datetime.fromtimestamp(state.fallback_due, timezone.utc).isoformat() if state.fallback_due else ""
    return {"bot_mode": ASSIST if assisting else AUTO, "bot_fallback_at": due_at, "claimed_by": state.claimed_by or ""}


def push_status(effects, state):
    """Write the banner attributes when they changed (each write echoes back as a conversation_updated webhook).
    The last written ones live in state.assist["banner"]; the caller saves the state."""
    banner = status_attributes(state)
    if state.assist.get("banner") == banner:
        return False
    effects.assist_status(state.conversation_id, banner)
    state.assist = {**state.assist, "banner": banner}
    return True


def handle(event, repo, effects, render, viewers=lambda: ()):
    """One customer message: the bot answers it (AUTO), or drafts it for staff and starts the timer (ASSIST)."""
    catalog = repo.catalog()
    state = repo.load_state(event)
    if event.message_id and event.message_id <= state.last_message_id:
        return None  # redelivered webhook
    assisting = mode(state, viewers, catalog.settings) == ASSIST
    if not (assisting or state.assist.get("waiting")):
        turn = run_turn(event, repo, effects, render)
        if turn and turn.decision.type == "silent" and turn.state.status == "handed_off":
            _suggest(event, repo, effects, render, catalog)  # handed off, nobody here yet: a note for later
        return turn
    draft = _suggest(event, repo, effects, render, catalog, state) if assisting else None
    hold(state, event, repo.now(), catalog.settings)
    if assisting:
        push_status(effects, state)
    repo.save_state(state)
    return draft if assisting else _answer_waiting(state, repo, effects, render)  # the person left: answer it all


def _answer_waiting(state, repo, effects, render):
    turn = run_turn(merged_event(state), repo, effects, render, fallback=True)
    if turn and push_status(effects, turn.state):
        repo.save_state(turn.state)
    return turn


def _suggest(event, repo, effects, render, catalog, state=None):
    """The bot's draft as a private note; when the bot has no answer, a checked Gemini draft instead (D-115)."""
    turn = draft_turn(event, repo, render)
    text = note(turn, catalog)
    if text == NO_KNOWLEDGE and state is not None:
        text = _written(event, turn, repo, catalog, state) or text
    if text:
        effects.note(event.conversation_id, text)
    return turn


def _written(event, turn, repo, catalog, state):
    """A Gemini draft checked by Jev, from the course this turn knows; the call counts against state's budget."""
    from mmm_custom import llm
    from mmm_custom.engine import llm_draft
    from mmm_custom.engine.actions import applicable
    from mmm_custom.engine.context import course_context

    if not llm.api_key():
        return None
    course, today = catalog.course_in(turn.state.slots), repo.today()
    schedules = repo.open_schedules(course.code, None, None, today, 3) if course else []
    promotions = [p for p in repo.active_promotions(today) if course and applicable(p, course_context(course, catalog), "")]
    written, _, calls = llm_draft.make(event.text, turn.state, catalog, repo.jev_client(), llm.generate, schedules,
                                       promotions, repo.now(), state.assist.get("llm_calls", []))
    state.assist = {**state.assist, "llm_calls": calls}
    return written


def answer(conversation_id, repo, effects, render):
    """The timer ran out: the bot answers the waiting messages (None when a person answered first)."""
    state = repo.state_of(conversation_id)
    if not state or not due(state, repo.now()):
        return None
    return _answer_waiting(state, repo, effects, render)


TYPING_GRACE = 60  # a staff member typing pushes the bot's answer back this far (D-112)


def banner_changes(payload):
    """conversation_updated → what a staff member changed on the assist banner (D-112), pure:
    {"claimed_by": agent id or ""} for "Nhận xử lý" / "Trả lại cho Jev", {"reply_at": epoch} for "Để Jev trả lời ngay"."""
    from mmm_custom.intelligence import changed_attributes

    change = changed_attributes(payload).get("custom_attributes")
    if not isinstance(change, dict):
        return {}
    before, after = change.get("previous_value") or {}, change.get("current_value") or {}
    out = {}
    if str(after.get("claimed_by") or "") != str(before.get("claimed_by") or ""):
        out["claimed_by"] = str(after.get("claimed_by") or "")
    if after.get("bot_fallback_at") and after.get("bot_fallback_at") != before.get("bot_fallback_at"):
        try:
            out["reply_at"] = datetime.fromisoformat(str(after["bot_fallback_at"]).replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return out


def apply_banner(state, changes, now):
    """Claim → the bot only suggests; hand back → the bot answers again, now; "reply now" → the timer ends now.
    Only a time earlier than the current deadline counts: the bot's own writes echo back through this webhook."""
    if "claimed_by" in changes:
        state.claimed_by = changes["claimed_by"]
        if not state.claimed_by:  # handed back to the bot: it leads again and answers what is waiting
            state.consultant_replied = False
            if state.assist.get("waiting"):
                state.fallback_due = now
    reply_at = changes.get("reply_at")
    if reply_at and state.fallback_due and reply_at < state.fallback_due - 1:
        state.fallback_due = max(reply_at, 1.0)
    return state


def typing(state, now):
    """A staff member is typing a public reply: do not answer over them for another TYPING_GRACE seconds."""
    if state.fallback_due and state.fallback_due < now + TYPING_GRACE:
        state.fallback_due = now + TYPING_GRACE
    return state


def process(event):
    """Frappe: called by pipeline.process_event under the conversation lock."""
    from mmm_custom.engine.effects import chatwoot_effects
    from mmm_custom.engine.presence import viewers
    from mmm_custom.engine.render import frappe_renderer
    from mmm_custom.engine.repo import FrappeRepo

    return handle(event, FrappeRepo(), chatwoot_effects(frappe.conf), frappe_renderer,
                  lambda: viewers(event.conversation_id))


def run_due():
    """Scheduler, every minute: queue the conversations whose wait is over."""
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


def _update(conversation_id, change=None):
    """Apply a banner / typing change to a conversation's state and refresh the banner; without `change`, only the
    refresh (after a staff message)."""
    from mmm_custom.engine.effects import chatwoot_effects
    from mmm_custom.engine.repo import FrappeRepo

    repo = FrappeRepo()
    state = repo.state_of(conversation_id)
    if not state:
        return {"status": "ignored", "reason": "no_bot_conversation"}
    if change:
        before = (state.claimed_by, state.fallback_due, state.consultant_replied)
        change(state, time.time())
        if (state.claimed_by, state.fallback_due, state.consultant_replied) == before:
            return {"status": "unchanged"}
    if push_status(chatwoot_effects(frappe.conf), state) or change:
        repo.save_state(state)
    return {"status": "updated"}


def on_conversation_updated(payload):
    """Account webhook conversation_updated: the assist banner's buttons (D-112)."""
    changes = banner_changes(payload)
    if not changes or not payload.get("id"):
        return None
    return _update(payload["id"], lambda state, now: apply_banner(state, changes, now))


def on_typing(payload):
    """Account webhook conversation_typing_on: a public reply is being typed (private notes do not count)."""
    conversation = payload.get("conversation") or {}
    if payload.get("is_private") or not conversation.get("id"):
        return {"status": "ignored"}
    return _update(conversation["id"], typing)


def refresh_status(conversation_id):
    """After a staff message: the banner stops counting down (queued by bot_api)."""
    return _update(conversation_id)


def replacement(state, consultants, load, online, assignee_id, catalog):
    """The customer waited too long (D-113): someone on duty from the same branch (else the central team) when the
    assignee is not on duty; None when the assignee is on duty or nobody else is. Pure."""
    from mmm_custom.engine.routing import pick_consultant
    from mmm_custom.engine.state import value

    if not online or (assignee_id and str(assignee_id) in online):
        return None
    branch_slot = catalog.slot_for("branch")
    branch = value(state.slots, branch_slot.key) if branch_slot else ""
    others = [c for c in consultants if str(c.get("chatwoot_agent_id")) != str(assignee_id or "")]
    consultant, why = pick_consultant(branch or "", others, load, online=online)
    if not consultant or str(consultant.get("chatwoot_agent_id")) not in online:
        return None
    return consultant, why


def on_timeout(event):
    """lead_engine_events handler for assist_timeout: re-route in a job, never inside the bot's turn."""
    if event.get("is_sandbox") or not event.get("conversation_id"):
        return
    frappe.enqueue("mmm_custom.engine.copilot.escalate", queue="short", conversation_id=event["conversation_id"],
                   job_id=f"assist_escalate_{event['conversation_id']}", deduplicate=True, enqueue_after_commit=True)


def escalate(conversation_id):
    from mmm_custom.engine.repo import FrappeRepo, chatwoot_admin

    repo, client = FrappeRepo(), chatwoot_admin()
    state = repo.state_of(conversation_id)
    if not state:
        return {"status": "kept"}
    assignee = ((client.list_messages(int(conversation_id)).get("meta") or {}).get("assignee") or {}).get("id")
    picked = replacement(state, repo.consultants(), repo.consultant_load(), repo.online_agents(), assignee, repo.catalog())
    if not picked:
        return {"status": "kept"}
    consultant, why = picked
    client.assign_conversation(int(conversation_id), int(consultant["chatwoot_agent_id"]))
    wait = int(float(repo.catalog().settings["assist_wait_minutes"]))
    client.send_private_note(int(conversation_id), f"⏰ Khách chờ quá {wait} phút mà chưa ai trả lời: Jev chuyển cho "
                                                   f"{consultant.get('full_name') or consultant['name']} ({why}).")
    frappe.db.set_value("Bot Conversation", {"conversation_id": str(conversation_id)}, "consultant", consultant["name"])
    frappe.db.commit()
    return {"status": "reassigned", "consultant": consultant["name"]}

