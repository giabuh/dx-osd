"""C3.1 go-live gate (D-033). Labelled hard Vietnamese utterances go through the same keyword tier and
question builder as the bot and are answered by real Jev; every labelled question is graded by band.
Jev may serve real customers only when no course/branch/skill answer is wrong in the act band.

    bench --site crm.localhost execute mmm_custom.engine.evaluate.run            # all items
    bench --site crm.localhost execute mmm_custom.engine.evaluate.run --kwargs "{'limit': 5}"
"""

import json
from pathlib import Path

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine.jev_questions import NONE, build_questions, jev_state
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import understand

UTTERANCES = Path(__file__).resolve().parent / "eval" / "utterances.json"
CRITICAL = ("slot:course", "slot:branch", "skill")
BANDS = ("act", "confirm", "low")


def load_utterances(path=UTTERANCES):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def item_state(item):
    slots = {k: {"value": v, "source": "lead", "confidence": 1.0} for k, v in (item.get("known") or {}).items()}
    return ConversationState("eval", slots=slots, pending={"slot": item.get("pending") or "", "options": {}}, turns=1)


def expected_answers(item, questions, catalog):
    """The labelled answer of every asked question (none/False when the label is silent). Hotness, an
    unlabelled intent and the item's `skip` keys are not graded."""
    exp = item.get("expect") or {}
    slots, parents = exp.get("slots") or {}, exp.get("parents") or {}
    out = {}
    for key in questions:
        kind, _, name = key.partition(":")
        if kind == "slot":
            out[key] = str(slots[name]) if name in slots else NONE
        elif kind == "parent":
            slot, leaf = catalog.slot(name), slots.get(name)
            out[key] = parents.get(name) or (catalog.parent_of(slot, leaf) if slot and leaf else "") or NONE
        elif kind == "skill":
            out[key] = name in (exp.get("skills") or [])
        elif key == "wants_human":
            out[key] = bool(exp.get("wants_human"))
        elif key == "intent" and "intent" in exp:
            out[key] = exp["intent"]
    for key in exp.get("skip") or ():  # questions whose answer is genuinely debatable are not graded
        out.pop(key, None)
    return out


def _limits(key, catalog):
    s = catalog.settings
    if key.startswith(("slot:", "parent:")):
        slot = catalog.slot(key.split(":", 1)[1])
        if slot and slot.type == "catalog":
            return s["catalog_act"], s["catalog_confirm"]
        return s["choice_act"], s["choice_confirm"]
    if key.startswith("skill:"):
        return s["skill_act"], s["skill_confirm"]
    if key == "wants_human":
        return s["handoff_noul"], s["handoff_noul"]
    return s["spam_threshold"], s["spam_threshold"]  # intent: only "spam" makes the bot act


def grade(key, answer, expected, catalog):
    act, confirm = _limits(key, catalog)
    if "noul" in answer:
        strength = float(answer.get("noul") or 0)
        got = strength >= 0.5
        positive = got
    else:
        strength = float(answer.get("confidence") or 0)
        got = answer.get("choice")
        positive = got == "spam" if key == "intent" else got not in (None, NONE)
    band = ("act" if strength >= act else "confirm" if strength >= confirm else "low") if positive else "low"
    correct = got == expected
    return {"question": key, "family": "skill" if key.startswith("skill:") else key, "expected": expected, "got": got,
            "strength": round(strength, 3), "band": band, "correct": correct, "act_wrong": band == "act" and not correct}


def evaluate_items(items, catalog, ask):
    """`ask(state, questions)` returns Jev's answers dict, or None when the call failed."""
    rows = []
    for item in items:
        state = item_state(item)
        u = understand(item["text"], state, catalog)
        questions = build_questions(state, u, catalog)
        answers = ask(jev_state(item["text"], state, catalog), questions)
        if answers is None:
            rows.append({"item": item["id"], "question": "*", "family": "*", "error": True, "act_wrong": False})
            continue
        for key, expected in expected_answers(item, questions, catalog).items():
            if key in answers:
                rows.append({"item": item["id"], "text": item["text"], **grade(key, answers[key], expected, catalog)})
    return rows


def summarize(rows):
    families, errors = {}, 0
    for r in rows:
        if r.get("error"):
            errors += 1
            continue
        f = families.setdefault(r["family"], {"n": 0, "correct": 0, "bands": {b: {"n": 0, "wrong": 0} for b in BANDS}})
        f["n"] += 1
        f["correct"] += int(r["correct"])
        f["bands"][r["band"]]["n"] += 1
        f["bands"][r["band"]]["wrong"] += int(not r["correct"])
    critical = sum(1 for r in rows if r.get("act_wrong") and r["family"] in CRITICAL)
    return {"families": families, "errors": errors, "critical_act_wrong": critical,
            "passed": critical == 0 and errors == 0,
            "act_wrong": [r for r in rows if r.get("act_wrong")]}


def run(limit=None):
    """Bench entry: evaluate against real Jev (needs typesafe_api_key), write the full report to the
    site's private files and return the summary."""
    from mmm_custom.engine.jev import JevClient, JEV_URL
    from mmm_custom.engine.repo import load_catalog

    conf = frappe.conf
    client = JevClient(conf.get("typesafe_api_key"), conf.get("typesafe_model") or "jev-latest",
                       conf.get("typesafe_api_url") or JEV_URL, timeout=30)
    catalog, tokens = load_catalog(), {"input": 0, "model": ""}

    def ask(state, questions):
        for _ in range(2):  # a call that fails outright is asked once more: this grades reading, not uptime
            result = client.ask(state, questions)
            tokens["input"] += result.input_tokens
            tokens["model"] = result.model or tokens["model"]
            if result.status == "ok":
                return result.answers
            failures.append(result.error)
        return None

    failures = []

    items = load_utterances()[: int(limit)] if limit else load_utterances()
    rows = evaluate_items(items, catalog, ask)
    report = summarize(rows)
    report.update({"items": len(items), "input_tokens": tokens["input"], "model": tokens["model"],
                   "call_failures": failures})
    path = frappe.get_site_path("private", "files", "lead_engine_eval.json")
    Path(path).write_text(json.dumps({"report": report, "rows": rows}, ensure_ascii=False, indent=1, default=str),
                          encoding="utf-8")
    for name, f in sorted(report["families"].items()):
        bands = " ".join(f"{b}:{f['bands'][b]['n']}/{f['bands'][b]['wrong']}✗" for b in BANDS)
        print(f"{name:28} {f['correct']:>3}/{f['n']:<3} {bands}")
    return {k: report[k] for k in ("passed", "critical_act_wrong", "errors", "items", "input_tokens", "model")} | {
        "call_failures": len(failures), "report_file": path}
