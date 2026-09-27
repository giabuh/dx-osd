"""A bot turn (D-025): webhook payload → Event → per-conversation lock → load → understand →
decide (pure) → act through Effects. `process_event` is the RQ job the webhook enqueues."""

import copy
from dataclasses import dataclass, field

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine.combine import combine
from mmm_custom.engine.context import shown_slots
from mmm_custom.engine.cost_guard import allow_jev, recent_calls
from mmm_custom.engine.decide import decide
from mmm_custom.engine.handoff import plan_handoff
from mmm_custom.engine.jev import JevResult
from mmm_custom.engine.jev_questions import MAX_HISTORY, build_questions, jev_state
from mmm_custom.engine.lead import lead_updates
from mmm_custom.engine.log import log_row, signals
from mmm_custom.engine.qualify import LABELS, NEW, lead_status
from mmm_custom.engine.reply import compose
from mmm_custom.engine.state import value
from mmm_custom.engine.understand import understand
from mmm_custom.sources import campaign_of, channel_key, source_name

MAX_TEXT = 1000  # D-061 input cap


@dataclass
class Event:
    kind: str  # customer_message | agent_message | resolved | ignore
    conversation_id: str = ""
    message_id: int = 0
    text: str = ""
    contact: dict = field(default_factory=dict)
    inbox_id: str = ""
    channel: str = ""  # sources.CHANNELS key (D-100)
    campaign: str = ""


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
    jev: object = None


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
                     contact, str(inbox), channel_key(conv), campaign_of(conv))
    if mtype in (1, "outgoing") and sender.get("type") == "user":
        return Event("agent_message", cid, int(payload.get("id") or 0))
    return Event("ignore", cid)


def understand_turn(text, state, catalog, jev, now=0.0, tokens_today=0, budget=0):
    """Always run keywords; call Jev only when available and within the cost guard."""
    u = understand(text, state, catalog)
    if jev is None:
        return u, JevResult("disabled")
    allowed, why = allow_jev(u, state, catalog, now, tokens_today, budget)
    if not allowed:
        return u, JevResult("skipped_cost_guard", error=why)
    state.jev_calls = recent_calls(state.jev_calls, now) + [now]
    questions = build_questions(state, u, catalog)
    result = jev.ask(jev_state(text, state, catalog), questions)
    if result.status != "ok":
        return u, result
    return combine(u, result.answers, questions, state, catalog), result


def apply_decision(state, decision, reply, event):
    state.slots = decision.slots
    state.stuck_turns = decision.stuck_turns
    state.pending_skill = reply.pending_skill or decision.pending_skill
    state.answered = list(dict.fromkeys(state.answered + [k for k in decision.skills if k != reply.pending_skill]))
    if decision.type != "silent":
        state.pending = {"slot": reply.ask or ("" if reply.hold else decision.ask), "options": reply.options()}
        if decision.confirm:
            state.pending["confirm"] = decision.confirm
    if reply.ask:
        state.slots.setdefault(reply.ask, {})["asked"] = 1
    if reply.hold and decision.ask and decision.ask != reply.ask:
        state.slots.get(decision.ask, {}).pop("asked", None)  # not asked after all: ask it once the quiz ends
    lines = [{"from": "customer", "text": event.text[:300]}]
    if reply.messages:
        lines.append({"from": "bot", "text": " ".join(reply.messages)[:300]})
    state.history = (state.history + lines)[-MAX_HISTORY:]
    if decision.type == "handoff":
        state.status = "handed_off"
    if decision.close:
        state.status = "closed"
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


def ai_fields(u, settings):
    """Return confident intent and hotness values for the CRM Lead."""
    floor, out = float(settings["handoff_noul"]), {}
    if u.intent.get("confidence", 0) >= floor:
        out["ai_intent"] = u.intent["value"]
    if u.hotness.get("confidence", 0) >= floor:
        out["ai_hotness"] = u.hotness["value"]
    return out


def write_lead(turn, effects, catalog):
    """Write what the conversation learned, including confident Jev signals, to the CRM Lead."""
    state, decision = turn.state, turn.decision
    lead_slots = [k for k in decision.new_slots if catalog.slot(k) and catalog.slot(k).lead_field]
    wanted = not state.lead and any(catalog.skills[k].creates_lead for k in decision.skills)
    ai = {k: v for k, v in ai_fields(turn.understanding, catalog.settings).items() if state.ai.get(k) != v}
    previous = state.ai.get("status", "")
    status = lead_status(state.slots, {**state.ai, **ai}, catalog, previous)
    if status != (previous or NEW):
        ai["status"] = status
    if not (lead_slots or wanted or (ai and state.lead)):
        return
    fields, courses = lead_updates(state.slots, catalog)
    fields.update(ai)
    if not state.lead and source_name(state.channel):  # first touch: a new Lead records where it came from
        fields["source"] = source_name(state.channel)
        if state.campaign:
            fields["source_campaign"] = state.campaign
    try:
        state.lead = effects.save_lead(state, fields, courses, turn.event.contact) or state.lead
    except Exception as e:
        turn.reply.errors.append({"type": "lead_failed", "detail": str(e)[:300]})
        return
    state.ai.update(ai)
    if "status" in ai:
        turn.reason = f"{turn.reason} · Lead: {LABELS[status]}"
    effects.emit("lead_updated", {"conversation_id": state.conversation_id, "lead": state.lead,
                                  "is_sandbox": state.is_sandbox, "fields": sorted(fields),
                                  "courses": [c.code for c in courses]})


def apply_quiz_results(decision, catalog):
    """A finished level quiz (D-104) fills `level`, the `placement` summary for the Lead and, when the
    customer has not chosen one yet, the recommended course."""
    from mmm_custom.engine import quiz

    for key in decision.skills:
        skill = catalog.skills.get(key)
        if not skill or skill.action != "level_quiz":
            continue
        res = quiz.result(skill.config, quiz.progress(value(decision.slots, skill.config.get("slot", "quiz_progress")), key))
        if res is None:
            continue
        level = catalog.slot("level")
        option = level.option(res["level"]) if level else None
        fills = {"level": res["level"] if option else None,
                 "placement": quiz.summary(skill.config, res, option.label if option else "")}
        course_slot = catalog.slot_for("course")
        chosen = catalog.courses.get(value(decision.slots, course_slot.key)) if course_slot else None
        best = catalog.courses.get(res["course"])
        if course_slot and best and (not chosen or chosen.group == best.group):
            fills[course_slot.key] = best.code  # the test knows which course of that group fits
        for slot_key, val in fills.items():
            if val and catalog.slot(slot_key):
                decision.slots[slot_key] = {**(decision.slots.get(slot_key) or {}), "value": val, "source": "quiz",
                                            "confidence": 1.0}
                if slot_key not in decision.new_slots:
                    decision.new_slots.append(slot_key)


def book_trials(turn, effects, catalog, plan=None):
    """A `book_trial` skill answered this turn (D-102): a CRM Task for whoever serves the Lead."""
    state = turn.state
    for key in turn.decision.skills:
        skill = catalog.skills.get(key)
        booking = value(state.slots, skill.config.get("slot", "trial_class")) if skill and skill.action == "book_trial" else ""
        if not booking:
            continue
        try:
            effects.book_trial(state, booking, plan.owner if plan else "")
        except Exception as e:
            turn.reply.errors.append({"type": "trial_failed", "detail": str(e)[:300]})


def run_turn(event, repo, effects, render):
    catalog = repo.catalog()
    state = repo.load_state(event)
    state.channel, state.campaign = event.channel or state.channel, event.campaign or state.campaign
    if event.message_id and event.message_id <= state.last_message_id:
        return None  # redelivered webhook: this message was already answered
    turn = Turn(event, state, None, None, None, copy.deepcopy(state.slots), copy.deepcopy(state.pending),
                state.status, state.turns, state.stuck_turns)
    jev = repo.jev_client()
    tokens, budget = repo.jev_budget() if jev else (0, 0)
    turn.understanding, turn.jev = understand_turn(event.text, state, catalog, jev, repo.now(), tokens, budget)
    if turn.jev.input_tokens:
        repo.add_jev_tokens(turn.jev.input_tokens)
    if turn.jev.error == "daily_budget":
        repo.warn_budget()
    turn.decision = decide(state, turn.understanding, catalog)
    apply_quiz_results(turn.decision, catalog)
    turn.reason = turn.decision.reason

    plan, errors = None, []
    if turn.decision.type == "handoff":
        try:
            plan = plan_handoff(state, turn.decision, catalog, repo, render)
            turn.reason = f"{turn.reason} · {plan.why}"
            errors += plan.errors
        except Exception as e:
            errors.append({"type": "handoff_failed", "detail": str(e)[:300]})
    extra = {"consultant": plan.consultant_ctx} if plan else None
    advisor_jev = jev if turn.jev.status == "ok" else None
    advisor_state = {**jev_state(event.text, state, catalog), "known": shown_slots(turn.decision.slots, catalog)}
    turn.reply = compose(turn.decision, state, catalog, render, repo, repo.today(), extra, advisor_jev, advisor_state)
    for call in turn.reply.jev_extra:
        state.jev_calls.append(repo.now())
        if call.get("input_tokens"):
            repo.add_jev_tokens(call["input_tokens"])
    turn.reply.errors[:0] = errors
    if turn.reply.messages:
        try:
            effects.send(state.conversation_id, turn.reply)
        except Exception as e:  # never raise into RQ: a retry would answer twice
            turn.reply.errors.append({"type": "send_failed", "detail": str(e)[:300]})

    apply_decision(state, turn.decision, turn.reply, event)
    if turn.decision.close:
        try:
            effects.mark_spam(state.conversation_id)
        except Exception as e:
            turn.reply.errors.append({"type": "spam_failed", "detail": str(e)[:300]})
    write_lead(turn, effects, catalog)
    if plan:
        state.consultant = plan.consultant_name
        try:
            turn.reply.errors += effects.handoff(state.conversation_id, plan, state.lead, state.inbox_id)
        except Exception as e:
            turn.reply.errors.append({"type": "handoff_failed", "detail": str(e)[:300]})
    book_trials(turn, effects, catalog, plan)
    repo.save_state(state)
    emit_events(effects, state, turn.decision)
    try:
        repo.write_log(log_row(turn, turn.jev.log()))
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
