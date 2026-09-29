"""Reminder for level tests left half-way (D-106): once, a couple of hours after the customer's last message
and well inside Messenger's 24-hour window, the bot sends "còn 2 câu nữa là xong…" with the buttons of the
question they stopped at. Never after a consultant has written, never twice, never in the playground.

Cron (hooks.py, every 15 minutes): `run`. `reminder_reply` and `due` are pure."""

from datetime import timedelta

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine import offers
from mmm_custom.engine.actions import run_action
from mmm_custom.engine.context import base_context
from mmm_custom.engine.render import RenderError, render_text
from mmm_custom.engine.reply import Reply, add_buttons, split_messages

LAST_HOURS = 20  # stay well inside Messenger's 24-hour window


def due(last_activity, now, after_hours, last_hours=LAST_HOURS):
    """Whether a conversation quiet since `last_activity` should get the reminder now."""
    quiet = now - last_activity
    return timedelta(hours=after_hours) <= quiet < timedelta(hours=last_hours)


def reminder_reply(state, key, catalog, render, data=None, today=None):
    """The reminder with the current question's buttons, or None when that quiz has nothing left to ask."""
    skill = catalog.skills.get(key)
    if not skill or skill.action != "level_quiz" or not catalog.settings["quiz_reminder_template"]:
        return None
    ctx = base_context(state.slots, catalog, state)
    out = run_action(skill, ctx, state.slots, catalog, data, today)
    q = out.get("quiz") or {}
    if q.get("done", True) or not out.get("_buttons"):
        return None
    try:
        text = render_text(catalog.settings["quiz_reminder_template"], {**ctx, "quiz": q}, render)
    except RenderError:
        return None
    reply = Reply(messages=split_messages([text]))
    add_buttons(reply, out["_buttons"])
    return reply


def run():
    from frappe.utils import now_datetime
    from frappe.utils.synchronization import filelock

    from mmm_custom.engine.effects import chatwoot_effects
    from mmm_custom.engine.pipeline import Event
    from mmm_custom.engine.render import frappe_renderer
    from mmm_custom.engine.repo import FrappeRepo

    repo = FrappeRepo()
    catalog = repo.catalog()
    after = int(catalog.settings["quiz_remind_after_hours"] or 2)
    now = now_datetime()
    rows = frappe.get_all("Quiz Attempt", fields=["name", "conversation", "quiz"],
                          filters={"status": offers.STARTED, "is_sandbox": 0, "reminded_at": ["is", "not set"],
                                   "modified": [">", now - timedelta(days=3)]})
    effects = None
    for row in rows:
        conv = frappe.db.get_value("Bot Conversation", row.conversation, ["status", "consultant_replied", "modified"],
                                  as_dict=True)
        if not conv or conv.status != "active" or conv.consultant_replied or not due(conv.modified, now, after):
            continue
        try:
            with filelock(f"lead_engine_conversation_{row.conversation}", timeout=60):
                state = repo.load_state(Event("customer_message", row.conversation))
                if state.offers.get(row.quiz) != offers.STARTED:
                    continue
                reply = reminder_reply(state, row.quiz, catalog, frappe_renderer, repo, repo.today())
                if reply:
                    effects = effects or chatwoot_effects(frappe.conf)
                    effects.send(state.conversation_id, reply)
                    state.pending = {"slot": "", "options": reply.options()}  # the taps answer the quiz again
                state.offers[row.quiz] = offers.REMINDED
                repo.save_state(state)
                frappe.db.set_value("Quiz Attempt", row.name, "reminded_at", now)
                frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title="Lead engine: level test reminder failed", message=frappe.get_traceback())
