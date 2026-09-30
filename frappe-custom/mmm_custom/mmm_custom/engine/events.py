"""Lead-engine events (D-036). Any app subscribes in its hooks.py, for example:

    lead_engine_events = {"handed_off": ["my_app.crm.notify_manager"]}

Events: slot_filled, skill_done, handed_off, lead_updated, assist_timeout (D-111: nobody answered in time).
Each handler receives one dict with the event name under "event". A failing handler is logged and never breaks
the bot turn.
"""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

EVENTS = ("slot_filled", "skill_done", "handed_off", "lead_updated", "assist_timeout")


def emit(event, payload, get_hooks=None, get_attr=None, log_error=None):
    get_hooks = get_hooks or frappe.get_hooks
    hooks = get_hooks("lead_engine_events")
    paths = list(hooks.get(event) or []) if isinstance(hooks, dict) else []
    if not paths:
        return
    get_attr = get_attr or frappe.get_attr
    log_error = log_error or frappe.log_error
    for path in paths:
        try:
            get_attr(path)({"event": event, **payload})
        except Exception:
            log_error(title=f"lead_engine_events: {event} -> {path}"[:140])
