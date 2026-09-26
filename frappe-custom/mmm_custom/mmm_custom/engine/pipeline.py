"""A bot turn (D-025): webhook payload → Event → per-conversation lock → load → understand →
decide (pure) → act through Effects. `process_event` is the RQ job the webhook enqueues."""

import copy
from dataclasses import dataclass, field

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine.decide import decide
from mmm_custom.engine.lead import lead_updates
from mmm_custom.engine.log import log_row, signals
from mmm_custom.engine.reply import compose
from mmm_custom.engine.understand import understand

MAX_TEXT = 1000  # D-061 input cap


@dataclass
class Event:
    kind: str  # customer_message | agent_message | resolved | ignore
    conversation_id: str = ""
    message_id: int = 0
    text: str = ""
    contact: dict = field(default_factory=dict)
    inbox_id: str = ""


@dataclass
class Turn:
    event: Event
    state: object
    understanding: object
    decision: object
    reply: object
    slots_before: dict = field(default_factory=dict)
    pending_before: dict = field(default_factory=dict)
    status_before: str = "active"
    turns_before: int = 0
    stuck_before: int = 0
    reason: str = ""


def _dict(value):
    return value if isinstance(value, dict) else {}


def parse_event(payload):
    """Classify an Agent Bot webhook payload (shapes from chatwoot/app/listeners/agent_bot_listener.rb)."""
    name = payload.get("event")
    if name in ("conversation_resolved", "conversation_status_changed"):
        resolved = name == "conversation_resolved" or payload.get("status") == "resolved"
        return Event("resolved" if resolved else "ignore", conversation_id=str(payload.get("id") or ""))
    if name != "message_created" or payload.get("private"):
        return Event("ignore")
    conv, sender = _dict(payload.get("conversation")), _dict(payload.get("sender"))
    cid, mtype = str(conv.get("id") or ""), payload.get("message_type")
    if mtype in (0, "incoming"):
        contact = _dict(_dict(conv.get("meta")).get("sender")) or sender
        inbox = conv.get("inbox_id") or _dict(payload.get("inbox")).get("id") or ""
        return Event("customer_message", cid, int(payload.get("id") or 0), (payload.get("content") or "")[:MAX_TEXT],
                     contact, str(inbox))
    if mtype in (1, "outgoing") and sender.get("type") == "user":
        return Event("agent_message", cid, int(payload.get("id") or 0))
    return Event("ignore", cid)


def apply_decision(state, decision, reply, event):
    state.slots = decision.slots
    state.stuck_turns = decision.stuck_turns
    state.pending_skill = decision.pending_skill
    if decision.type != "silent":
        state.pending = {"slot": decision.ask, "options": reply.options()}
    if decision.type == "handoff":
        state.status = "handed_off"
    state.last_message_id = max(state.last_message_id, event.message_id)
    state.turns += 1


def emit_events(effects, state, decision):
    base = {"conversation_id": state.conversation_id, "lead": state.lead, "is_sandbox": state.is_sandbox}
    for key in decision.new_slots:
        effects.emit("slot_filled", {**base, "slot": key, "value": decision.slots[key]["value"]})
    for key in decision.skills:
        effects.emit("skill_done", {**base, "skill": key})
    if decision.type == "handoff":
        effects.emit("handed_off", {**base, "reason": decision.handoff_reason, "consultant": state.consultant})


def write_lead(turn, effects, catalog):
    """C2.4: write what the conversation learned to the CRM Lead (D-014, D-022)."""
    state, decision = turn.state, turn.decision
    lead_slots = [k for k in decision.new_slots if catalog.slot(k) and catalog.slot(k).lead_field]
    wanted = not state.lead and any(catalog.skills[k].creates_lead for k in decision.skills)
    if not (lead_slots or wanted):
        return
    fields, courses = lead_updates(state.slots, catalog)
    try:
        state.lead = effects.save_lead(state, fields, courses, turn.event.contact) or state.lead
    except Exception as e:
        turn.reply.errors.append({"type": "lead_failed", "detail": str(e)[:300]})
        return
    effects.emit("lead_updated", {"conversation_id": state.conversation_id, "lead": state.lead,
                                  "is_sandbox": state.is_sandbox, "fields": sorted(fields),
                                  "courses": [c.code for c in courses]})


def run_turn(event, repo, effects, render):
    catalog = repo.catalog()
    state = repo.load_state(event)
    if event.message_id and event.message_id <= state.last_message_id:
        return None  # redelivered webhook: this message was already answered
    turn = Turn(event, state, None, None, None, copy.deepcopy(state.slots), copy.deepcopy(state.pending),
                state.status, state.turns, state.stuck_turns)
    turn.understanding = understand(event.text, state, catalog)
    turn.decision = decide(state, turn.understanding, catalog)
    turn.reason = turn.decision.reason
    turn.reply = compose(turn.decision, state, catalog, render, repo, repo.today())
    if turn.reply.messages:
        try:
            effects.send(state.conversation_id, turn.reply)
        except Exception as e:  # never raise into RQ: a retry would answer twice
            turn.reply.errors.append({"type": "send_failed", "detail": str(e)[:300]})
    apply_decision(state, turn.decision, turn.reply, event)
    write_lead(turn, effects, catalog)
    repo.save_state(state)
    emit_events(effects, state, turn.decision)
    try:
        repo.write_log(log_row(turn))
        for row in signals(turn):
            repo.write_signal(row)
    except Exception as e:  # the log must never break a customer's turn
        turn.reply.errors.append({"type": "log_failed", "detail": str(e)[:300]})
    return turn


def process_event(payload):
    """RQ job (enqueued by bot_api.agent_bot_webhook with job_id = message id, deduplicated)."""
    from frappe.utils.synchronization import filelock

    from mmm_custom.engine.effects import chatwoot_effects
    from mmm_custom.engine.render import frappe_renderer
    from mmm_custom.engine.repo import FrappeRepo

    event = parse_event(payload)
    if event.kind != "customer_message" or not event.conversation_id:
        return
    with filelock(f"lead_engine_conversation_{event.conversation_id}", timeout=60):
        run_turn(event, FrappeRepo(), chatwoot_effects(frappe.conf), frappe_renderer)
        frappe.db.commit()
