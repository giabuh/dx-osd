"""Bot Playground (D-038, D-060): chat as a customer or replay a logged decision, and see every step.
Runs dry — RecordingEffects means nothing is sent to Chatwoot and no Lead is written; sandbox
conversations carry is_sandbox and are excluded from dashboards and consultant load."""

import copy
import json
from pathlib import Path

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine.context import shown_slots
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import Event, run_turn
from mmm_custom.engine.repo import FrappeRepo
from mmm_custom.engine.state import ConversationState
from mmm_custom.lifecycle import LABELS

ROLES = ("System Manager", "Sales Manager")
DEMO_SCRIPTS = Path(__file__).resolve().parent / "eval" / "demo_scripts.json"
DECISIONS = {"answer": "Trả lời", "ask_slot": "Hỏi thêm thông tin", "confirm": "Xác nhận lại", "handoff": "Giao tư vấn viên",
             "silent": "Không trả lời"}


def _loads(value):
    if isinstance(value, dict):
        return value
    return json.loads(value) if value else {}


def facts(slots, new_slots, catalog):
    """What the bot knows, in the catalog's slot order: every filled slot plus the required ones still missing."""
    shown = shown_slots(slots, catalog)
    return [{"key": s.key, "label": s.label, "value": shown.get(s.key, ""), "required": s.required, "new": s.key in new_slots}
            for s in catalog.slots if s.key in shown or s.required]


def keywords(matches, catalog):
    """What the keyword tier recognised, by name: "Khóa học", "Chi nhánh", "Câu hỏi: học phí"."""
    out = []
    for m in matches:
        if m.get("skill") in catalog.skills:
            name = f"Câu hỏi: {catalog.skills[m['skill']].title}"
        else:
            slot = catalog.slot(m.get("slot") or "")
            name = slot.label if slot else ""
        if name and name not in out:
            out.append(name)
    return out


def actions(calls, new_slots, catalog, consultant=""):
    """The side effects of a turn in words a manager reads: what a real conversation would write or do."""
    out = []
    for kind, data in calls:
        if kind == "save_lead":
            learned = [s.label for s in catalog.slots if s.key in new_slots and (s.lead_field or s.type == "catalog")]
            if learned:
                out.append("Ghi vào Lead: " + ", ".join(learned))
            status = (data.get("fields") or {}).get("status")
            if status:
                out.append(f"Trạng thái Lead → {LABELS.get(status, status)}")
        elif kind == "handoff":
            who = f"tư vấn viên {consultant}" if consultant else "tư vấn viên"
            out.append(f"Giao cho {who} · nhóm {data.get('team') or '—'}")
            if data.get("labels"):
                out.append("Gắn nhãn Chatwoot: " + ", ".join(data["labels"]))
            if data.get("summary"):
                out.append("Ghi chú tóm tắt hội thoại cho tư vấn viên")
        elif kind == "book_trial":
            out.append(f"Giữ chỗ học thử {data.get('booking') or ''} và tạo việc cho tư vấn viên".replace("  ", " "))
        elif kind == "enrol":
            out.append("Tạo phiếu ghi danh nháp" + (f": {data['class_title']}" if data.get("class_title") else ""))
        elif kind == "mark_spam":
            out.append("Đóng hội thoại rác")
    return out


def inspect(turn, effects, catalog=None):
    """One turn as the inspector shows it: keywords → Jev → decision → reply → events → side effects; with the
    catalog also the plain-language view (`summary`) the Playground shows first."""
    if turn is None:
        return {"duplicate": True}
    u, d, r, s = turn.understanding, turn.decision, turn.reply, turn.state
    result = {
        "understanding": {"tapped": u.tapped, "fills": u.fills, "parents": u.parents, "ambiguous": u.ambiguous,
                          "skills": u.skills, "matches": u.matches, "unmatched": u.unmatched,
                          "confirm": u.confirm, "rejected": u.rejected, "intent": u.intent,
                          "hotness": u.hotness, "wants_human": u.wants_human, "spam": u.spam},
        "jev": turn.jev.log() if turn.jev else {"status": "disabled"},
        "decision": {"type": d.type, "reason": turn.reason, "ask": d.ask, "skills": d.skills, "close": d.close,
                     "pending_skill": d.pending_skill, "handoff_reason": d.handoff_reason, "stuck_turns": d.stuck_turns},
        "reply": {"messages": r.messages, "buttons": [b["title"] for b in r.buttons], "variants": r.variants,
                  "attachments": r.attachments, "errors": r.errors},
        "events": effects.of("emit"),
        "effects": [call for call in effects.calls if call[0] not in ("send", "emit")],
        "state": {"status": s.status, "slots": s.slots, "lead": s.lead, "consultant": s.consultant,
                  "is_returning": s.is_returning},
    }
    if catalog is not None:
        result["summary"] = {
            "skills": [catalog.skills[k].title for k in d.skills if k in catalog.skills],
            "keywords": keywords(u.matches, catalog),
            "tapped": bool(u.tapped),
            "decision": DECISIONS.get(d.type, d.type),
            "facts": facts(s.slots, d.new_slots, catalog),
            "actions": actions(effects.calls, d.new_slots, catalog, s.consultant if d.type == "handoff" else ""),
        }
    return result


def load_demo_scripts(path=DEMO_SCRIPTS):
    """The Playground's sample chats: [{id, title, messages}], a message is text or {"tap": n} (the n-th button
    of the bot's last reply)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


@frappe.whitelist() if frappe else (lambda f: f)
def demo_scripts():
    frappe.only_for(ROLES)
    return load_demo_scripts()


def replay_state(log, conv):
    return ConversationState(
        conversation_id=f"replay-{log['name']}", contact_id=str(conv.get("contact_id") or ""), lead=log.get("lead") or "",
        status=log.get("status_before") or "active", slots=_loads(log.get("slots_before")),
        pending=_loads(log.get("pending_before")), turns=int(log.get("turns_before") or 0),
        stuck_turns=int(log.get("stuck_before") or 0), is_returning=bool(conv.get("is_returning")), is_sandbox=True)


class ReplayRepo(FrappeRepo):
    """Current catalog and data, the logged state, and no writes at all."""

    def __init__(self, state, force_jev=False):
        super().__init__(sandbox=True, force_jev=force_jev)
        self.state = state

    def load_state(self, event):
        return copy.deepcopy(self.state)

    def save_state(self, state):
        pass

    def write_log(self, row):
        pass

    def write_signal(self, row):
        pass

    def save_quiz_attempt(self, state, change):
        pass


def _renderer():
    from mmm_custom.engine.render import frappe_renderer

    return frappe_renderer


@frappe.whitelist() if frappe else (lambda f: f)
def simulate(session, text, lead=None, jev=0):
    frappe.only_for(ROLES)
    cid = f"sandbox-{session}"
    last = frappe.db.get_value("Bot Conversation", {"conversation_id": cid}, "last_message_id") or 0
    event = Event("customer_message", cid, int(last) + 1, (text or "")[:1000], {"id": cid})
    effects = RecordingEffects()
    repo = FrappeRepo(sandbox=True, sandbox_lead=lead or None, force_jev=bool(int(jev or 0)))
    turn = run_turn(event, repo, effects, _renderer())
    frappe.db.commit()
    return json.loads(json.dumps(inspect(turn, effects, repo.catalog()), default=str))


@frappe.whitelist() if frappe else (lambda f: f)
def reset(session):
    frappe.only_for(ROLES)
    frappe.db.delete("Quiz Attempt", {"conversation": f"sandbox-{session}", "is_sandbox": 1})
    frappe.db.delete("Bot Conversation", {"conversation_id": f"sandbox-{session}", "is_sandbox": 1})
    frappe.db.commit()


@frappe.whitelist() if frappe else (lambda f: f)
def replay(log_name, jev=0):
    """Run a logged message again with today's data, templates and settings; show then vs now."""
    frappe.only_for(ROLES)
    log = frappe.get_doc("AI Decision Log", log_name).as_dict()
    conv = frappe.db.get_value("Bot Conversation", log.get("bot_conversation"), ["contact_id", "is_returning"],
                               as_dict=True) or {}
    state = replay_state(log, conv)
    effects = RecordingEffects()
    turn = run_turn(Event("customer_message", state.conversation_id, 0, log.get("message_text") or "",
                          {"id": state.contact_id}), ReplayRepo(state, bool(int(jev or 0))), effects, _renderer())
    then = {k: log.get(k) for k in ("creation", "decision_type", "reason", "skills_answered", "reply_text", "reply_buttons")}
    return json.loads(json.dumps({"then": then, "now": inspect(turn, effects)}, default=str))
