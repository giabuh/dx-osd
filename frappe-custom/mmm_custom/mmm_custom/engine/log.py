"""AI Decision Log rows (D-056) and Bot Learning Signals (D-057), built from a finished turn (pure),
plus the daily retention purge (personal data, Decree 13/2023)."""

import json

try:
    import frappe
except ImportError:  # offline tests
    frappe = None


def _j(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def log_row(turn, jev=None):
    d, u, r, s = turn.decision, turn.understanding, turn.reply, turn.state
    jev = jev or {"status": "disabled"}
    return {
        "bot_conversation": s.conversation_id, "lead": s.lead or None, "message_id": str(turn.event.message_id or ""),
        "message_text": turn.event.text, "is_sandbox": int(s.is_sandbox),
        "tapped": int(u.tapped), "keyword_matches": _j(u.matches),
        "jev_status": jev.get("status", "disabled"), "jev_questions": _j(jev.get("questions") or {}),
        "jev_answers": _j(jev.get("answers") or {}), "model_version": jev.get("model") or "",
        "latency_ms": int(jev.get("latency_ms") or 0), "input_tokens": int(jev.get("input_tokens") or 0),
        "decision_type": d.type, "reason": turn.reason or d.reason, "asked_slot": d.ask or "",
        "handoff_reason": d.handoff_reason or "", "skills_answered": ", ".join(d.skills),
        "status_before": turn.status_before, "turns_before": turn.turns_before, "stuck_before": turn.stuck_before,
        "slots_before": _j(turn.slots_before), "pending_before": _j(turn.pending_before), "slots_after": _j(d.slots),
        "reply_text": "\n\n".join(r.messages), "reply_buttons": _j([b["title"] for b in r.buttons]),
        "reply_variants": _j(r.variants), "errors": _j(r.errors), "jev_extra": _j(r.jev_extra),
    }


def signals(turn):
    d, u, r, s = turn.decision, turn.understanding, turn.reply, turn.state
    base = {"bot_conversation": s.conversation_id, "lead": s.lead or None, "message_text": turn.event.text,
            "is_sandbox": int(s.is_sandbox), "status": "new"}
    out = []
    if d.type == "handoff" and d.handoff_reason == "stuck":
        out.append({**base, "signal_type": "stuck"})
        out += [{**base, "signal_type": "unmatched_term", "term": word} for word in u.unmatched]
    if u.rejected:
        out.append({**base, "signal_type": "confirm_rejected", "term": u.rejected.get("label", ""),
                    "details": _j(u.rejected)})
    out += [{**base, "signal_type": "render_error", "details": _j(e)} for e in r.errors if e.get("type") == "render_error"]
    return out


def purge_old_logs():
    """Daily job (hooks.py): delete decision-log rows older than Lead Engine Settings.log_retention_days."""
    days = int(frappe.db.get_single_value("Lead Engine Settings", "log_retention_days") or 180)
    cutoff = frappe.utils.add_days(frappe.utils.now_datetime(), -days)
    frappe.db.delete("AI Decision Log", {"creation": ["<", cutoff]})
    frappe.db.commit()
