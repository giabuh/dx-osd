"""Acceptance scenarios (D-098): scripted customer chats with the outcome the business expects —
which branch, which kind of consultant, which Lead fields. Runs dry through `run_turn` with
RecordingEffects, so nothing is sent to Chatwoot and no Lead is written.

Offline the unit tests run them on the demo catalog; on a site
`bench --site crm.localhost execute mmm_custom.engine.scenarios.report` runs them on live data, and
`/crm/admin` calls `run_all`. Checks name consultant attributes (branch, specialty, level, B2B), never
people, so they hold on any dataset shaped like the demo."""

import copy
import json
from pathlib import Path

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.jev import JevResult
from mmm_custom.engine.pipeline import Event, run_turn
from mmm_custom.engine.routing import CENTRAL_TEAM
from mmm_custom.engine.state import ConversationState

ROLES = ("System Manager", "Sales Manager")
SCENARIOS_FILE = Path(__file__).resolve().parent / "eval" / "scenarios.json"
RETURNING_LEAD = "SCENARIO-RETURNING-LEAD"


def load_scenarios():
    return json.loads(SCENARIOS_FILE.read_text(encoding="utf-8"))


class SignalJev:
    """Stands in for Jev with fixed signals (hotness, intent), so a scenario states what Jev read
    instead of depending on a live model; every other question stays unanswered (keyword tier)."""

    def __init__(self, signals):
        self.signals = signals

    def ask(self, state, questions):
        answers = {}
        if "hotness" in self.signals and "hotness" in questions:
            answers["hotness"] = {"score": self.signals["hotness"], "confidence": self.signals.get("confidence", 0.9)}
        if "intent" in self.signals and "intent" in questions:
            answers["intent"] = {"choice": self.signals["intent"], "confidence": self.signals.get("confidence", 0.9)}
        if "wants_human" in self.signals and "wants_human" in questions:
            answers["wants_human"] = {"noul": self.signals["wants_human"]}
        return JevResult("ok", answers, questions, "scenario-signals", 0, 0)


class ScenarioRepo:
    """Wraps a repo (FakeRepo offline, FrappeRepo on a site): conversation state in memory, no logs,
    a fixed Jev stand-in, and an optional returning customer owned by a consultant of a given branch."""

    def __init__(self, base, scenario):
        self.base, self.scenario = base, scenario
        self.states, self.owner = {}, ""
        setup = scenario.get("setup") or {}
        if setup.get("returning_owner_branch"):
            people = [c for c in base.consultants() if c.get("branch") == setup["returning_owner_branch"]
                      and c.get("chatwoot_agent_id")]
            self.owner = sorted(people, key=lambda c: c["name"])[-1]["name"] if people else ""
        self.prefill = copy.deepcopy(setup.get("slots") or {})

    def __getattr__(self, name):
        return getattr(self.base, name)

    def jev_client(self):
        signals = self.scenario.get("signals")
        return SignalJev(signals) if signals else None

    def jev_budget(self):
        return 0, 0

    def add_jev_tokens(self, n):
        pass

    def load_state(self, event):
        if event.conversation_id in self.states:
            return copy.deepcopy(self.states[event.conversation_id])
        returning = bool(self.owner)
        return ConversationState(conversation_id=event.conversation_id, contact_id=str(event.contact.get("id") or ""),
                                 slots=copy.deepcopy(self.prefill), is_sandbox=True, is_returning=returning,
                                 lead=RETURNING_LEAD if returning else "")

    def save_state(self, state):
        self.states[state.conversation_id] = copy.deepcopy(state)

    def write_log(self, row):
        pass

    def write_signal(self, row):
        pass

    def lead_owner(self, lead):
        return self.owner if lead == RETURNING_LEAD else self.base.lead_owner(lead)


def _check(checks, name, expected, actual, ok=None):
    checks.append({"check": name, "expected": expected, "actual": actual,
                   "ok": bool(expected == actual if ok is None else ok)})


def evaluate(scenario, transcript, effects, consultants, final):
    """Compare what happened with `scenario["expect"]`; one row per expectation."""
    expect, checks = scenario.get("expect") or {}, []
    handoffs = effects.of("handoff")
    handoff = handoffs[-1] if handoffs else None
    people = {c["name"]: c for c in consultants}
    person = people.get(handoff["owner"], {}) if handoff else {}
    lead, courses = {}, []
    for row in effects.of("save_lead"):
        lead.update(row["fields"])
        courses += [c for c in row["courses"] if c not in courses]
    text = "\n".join(m for turn in transcript for m in turn["bot"]).lower()

    if "decision" in expect:
        _check(checks, "Bot quyết định", expect["decision"], final.decision.type if final else "")
    if "handoff" in expect:
        _check(checks, "Chuyển cho người", expect["handoff"], bool(handoff))
    if "team" in expect:
        _check(checks, "Team Chatwoot", expect["team"], handoff["team"] if handoff else "")
    c = expect.get("consultant") or {}
    if c.get("central"):
        _check(checks, "Người nhận thuộc", CENTRAL_TEAM, person.get("branch") or (CENTRAL_TEAM if person else ""))
    if "branch" in c:
        _check(checks, "Chi nhánh người nhận", c["branch"], person.get("branch", ""))
    if "specialty" in c:
        _check(checks, "Chuyên môn người nhận", c["specialty"], ", ".join(person.get("specialties") or []),
               c["specialty"] in (person.get("specialties") or []))
    if "level" in c:
        _check(checks, "Cấp bậc người nhận", c["level"], person.get("level", ""))
    if "handles_b2b" in c:
        _check(checks, "Người nhận phụ trách B2B", bool(c["handles_b2b"]), bool(person.get("handles_b2b")))
    if c.get("returning_owner"):
        _check(checks, "Giao lại người phụ trách cũ", "người phụ trách Lead", handoff["owner"] if handoff else "",
               bool(handoff) and handoff["owner"] == c["returning_owner"])
    for label in expect.get("labels") or []:
        got = handoff["labels"] if handoff else []
        _check(checks, f"Nhãn “{label}”", label, ", ".join(got), label in got)
    for key, value in (expect.get("lead") or {}).items():
        _check(checks, f"Lead · {key}", value, lead.get(key, ""))
    if "lead_written" in expect:
        _check(checks, "Có ghi Lead", expect["lead_written"], bool(effects.of("save_lead")) and any(
            r["fields"] or r["courses"] for r in effects.of("save_lead")))
    for code in expect.get("courses") or []:
        _check(checks, f"Khóa {code} trên Lead", code, ", ".join(courses), code in courses)
    for code in expect.get("no_courses") or []:
        _check(checks, f"Không gắn khóa {code}", "không có", ", ".join(courses) or "không có", code not in courses)
    for key, value in (expect.get("slots") or {}).items():
        got = ((final.state.slots if final else {}).get(key) or {}).get("value")
        _check(checks, f"Hiểu {key}", value, got)
    for key in expect.get("slots_empty") or []:
        got = ((final.state.slots if final else {}).get(key) or {}).get("value")
        _check(checks, f"Không điền {key}", None, got)
    for phrase in expect.get("reply_has") or []:
        _check(checks, f"Bot nói “{phrase}”", phrase, "có" if phrase.lower() in text else "không có", phrase.lower() in text)
    for phrase in expect.get("reply_lacks") or []:
        _check(checks, f"Bot không nói “{phrase}”", "không có", "có" if phrase.lower() in text else "không có",
               phrase.lower() not in text)
    if expect.get("closed"):
        _check(checks, "Đóng hội thoại rác", True, bool(effects.of("mark_spam")))
    return checks


def run_scenario(scenario, base_repo, render):
    repo, effects = ScenarioRepo(base_repo, scenario), RecordingEffects()
    cid, transcript, final = f"scenario-{scenario['id']}", [], None
    for i, text in enumerate(scenario["messages"], 1):
        before = len(effects.of("send"))
        turn = run_turn(Event("customer_message", cid, i, text, {"id": cid}), repo, effects, render)
        sent = effects.of("send")[before:]
        final = turn or final
        transcript.append({"customer": text, "bot": [m for s in sent for m in s["messages"]],
                           "buttons": [b for s in sent for b in s["buttons"]],
                           "decision": turn.decision.type if turn else "", "reason": turn.reason if turn else ""})
    checks = evaluate(scenario, transcript, effects, base_repo.consultants(), final)
    handoff = (effects.of("handoff") or [None])[-1]
    return {"id": scenario["id"], "title": scenario["title"], "why": scenario.get("why", ""),
            "passed": all(c["ok"] for c in checks), "checks": checks, "transcript": transcript,
            "assigned": {"owner": handoff["owner"], "team": handoff["team"]} if handoff else None}


def run_scenarios(base_repo, render, scenarios=None):
    results = [run_scenario(s, base_repo, render) for s in (scenarios or load_scenarios())]
    return {"total": len(results), "passed": sum(r["passed"] for r in results), "results": results}


def _site_run():
    from mmm_custom.engine.render import frappe_renderer
    from mmm_custom.engine.repo import FrappeRepo

    return run_scenarios(FrappeRepo(sandbox=True), frappe_renderer)


@frappe.whitelist() if frappe else (lambda f: f)
def run_all():
    """Run every scenario on this site's live catalog and consultants (dry)."""
    frappe.only_for(ROLES)
    return json.loads(json.dumps(_site_run(), default=str))


def report():
    """`bench --site crm.localhost execute mmm_custom.engine.scenarios.report`: a readable pass/fail table."""
    out = _site_run()
    for r in out["results"]:
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['id']}  {r['title']}")
        for c in r["checks"]:
            if not c["ok"]:
                print(f"        ✗ {c['check']}: mong đợi {c['expected']!r}, thực tế {c['actual']!r}")
    print(f"{out['passed']}/{out['total']} kịch bản đạt")
    return {"passed": out["passed"], "total": out["total"]}
