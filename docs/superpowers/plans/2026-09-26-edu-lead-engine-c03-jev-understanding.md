# Edu Lead Engine C3 — Jev Understanding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Free-text Vietnamese messages are understood by TypeSafe Jev on top of the C2 keyword tier — slots, skills (multi-topic), intent/hotness/wants-human, a course advisor — with confidence bands and a confirmation turn, bounded by a cost guard, and gated by a labelled evaluation before Jev serves real customers.

**Architecture:** One Jev call per customer turn with parallel typed questions generated from CRM data (`engine/jev_questions.py`), sent by a small client with an 8 s budget (`engine/jev.py`). A pure `combine()` merges keyword and Jev understanding by the D-029/D-030 rules into the same `Understanding` that `decide()` already consumes; `decide()` gains a `confirm` decision and new handoff/spam triggers. A cost guard decides whether a turn may call Jev. The C3.1 evaluation tool runs the same question builder against real Jev on ~100 labelled utterances; the `jev_live` setting stays off until it passes.

**Tech Stack:** Frappe v15.121, TypeSafe Jev System One API (`choice` → `choice`/`confidence`/`probabilities`; `score` → `score`/`confidence`; `noul` → `noul` 0–1), Python `unittest` offline with a `FakeJev`.

**Spec:** `docs/superpowers/specs/2026-09-26-edu-lead-engine-design.md` §7.2 Part B (and Part C advisor, Part D cost guard) — binding decisions `decisions.md` D-028…D-033, D-039, D-040, D-044, D-055, D-061, D-063, and the C2 plan's D-068…D-072.

## Global Constraints

- Jev never writes text (D-003); it only answers choice/score/noul questions. All wording stays in templates.
- Everything works with no Jev key, with Jev failing, or with the cost guard blocking (spec §5.3): the turn continues on the keyword tier and the log records `disabled` / `unavailable` / `skipped_cost_guard` (D-056).
- Jev timeout 8 s in the bot path (D-031). Criteria in English with the Vietnamese names/aliases customers use (D-028). ≤255 options per choice.
- Jev serves real customers only after the C3.1 gate: 0 wrong course/branch/skill answers in the act band (D-033). Until then `Lead Engine Settings.jev_live` stays unchecked; the Playground can force Jev on.
- Never print or commit `typesafe_api_key` (it lives only in `sites/crm.localhost/site_config.json`).
- Messenger limits, commit style, staging rules, `-p crmverify` only for fresh benches, never `down -v` on real projects — as in the C2 plan.
- Offline test command: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests` — green after every task.
- `APP=frappe-custom/mmm_custom/mmm_custom`, `T=$APP/tests`, `SCRATCH` = your session's scratchpad directory. Before Task 2, save Appendix A (DocType field writer) as `$SCRATCH/dt.py` and Appendix B (`crmverify` port override) as `$SCRATCH/crmverify-ports.yml`. Snippets that say "run in the live bench" use Appendix C.

## Design decisions made by this plan (recorded as D-073…D-080 in Task 7)

- **D-073** `Lead Engine Settings.jev_live` (default off) is the go-live switch of D-033: Jev answers real customers only when it is checked; the Playground has its own Jev toggle.
- **D-074** Jev's state carries the last 10 turns, stored in `Bot Conversation.history` (customer and bot lines, capped at 20 entries).
- **D-075** Jev slot questions are asked for every slot still open *before* this message, even when the keyword tier matched it in this message — that is what lets D-029 detect a confident disagreement. `number` slots are asked as a choice over "1"…"99"; `text` slots are never asked.
- **D-076** A dropped connection is retried once inside the 8 s budget; any other failure goes straight to the keyword tier.
- **D-077** "Hot" early handoff = the `hotness` score rounds to *hot* with confidence ≥ `handoff_noul` (0.70). The bot's intent/hotness go to the Lead's `ai_intent`/`ai_hotness` when confidence ≥ 0.70, and `intelligence.analyze_conversation` skips conversations whose Bot Conversation is `active` (D-032).
- **D-078** Bot Slots get `ask_on_demand`: such slots (`goal`, `level`) are asked only when a skill needs them or the advisor asks, never in the normal slot sequence.
- **D-079** Advisor composite = `goal_weight · goal/2 + level_weight · level/2` over the score questions' 0–2 range; a course is excluded when its exclusion noul ≥ 0.70; the shortlist is capped by `advisor_shortlist` (8).
- **D-080** Two cost-guard/spam readings: "keywords fill every open slot" (D-061) is applied as "every content word was explained by a keyword match and the pending question, if any, is answered" (read literally, optional slots are nearly always open and the rule would never fire); and a confident spam intent closes the conversation only while it has no Lead — a model guess never silences a known customer.

## Review Focus

1. **Jev slow, dropping connections or returning partial/malformed answers** → the turn completes on keywords, logs `unavailable`, never raises. Pinned by `test_engine_jev.test_malformed_response_is_unavailable` and `test_engine_combine.test_partial_answers_only_touch_answered_questions` (Tasks 1–2).
2. **Keyword and Jev disagree** (customer corrects themselves: "không phải excel, word") → confident Jev value is confirmed, never silently swapped; a button choice is never overridden. Pinned by `test_keyword_and_confident_jev_disagree_asks_to_confirm`, `test_button_choice_is_never_overridden` (Task 2).
3. **A spammer or a chatty customer burning tokens** → hourly per-conversation cap, daily budget, spam stop. Pinned by `test_engine_cost_guard.*` and `test_spam_closes_without_lead` (Task 5).
4. **Customer taps "Không phải" on a confirmation** → no wrong value stored, the slot's buttons follow, a `confirm_rejected` learning signal is recorded. Pinned by `test_confirm_no_asks_with_buttons_and_records_signal` (Task 2).
5. **Advisor with Jev off or failing** → C2 data filter still recommends; at most one extra Jev call per turn. Pinned by `test_advisor_without_jev_uses_data_filter`, `test_advisor_makes_one_call` (Task 6).

## File map

| Path | Task | Responsibility |
|---|---|---|
| `$APP/engine/jev.py` | 1 | `JevClient`, `JevResult`, `jev_client(conf, settings, force)` |
| `$APP/engine/jev_questions.py` | 1 | `build_questions`, `jev_state`, `NONE` |
| `$APP/engine/evaluate.py`, `$APP/engine/eval/utterances.json` | 1 | C3.1 labelled set + gate tool |
| `$APP/engine/combine.py` | 2, 3, 4, 5 | Keyword + Jev → Understanding (slots 2, skills 3, intent/hotness/wants-human 4, spam 5) |
| `$APP/engine/cost_guard.py` | 5 | `allow_jev(...)` (pure) |
| `$APP/engine/catalog.py` | 1, 6 | Skill `description`/`examples`; C3 settings defaults; Slot `on_demand` |
| `$APP/engine/state.py`, `understand.py`, `decide.py`, `reply.py`, `pipeline.py`, `repo.py`, `effects.py`, `log.py`, `actions.py`, `playground.py`, page JS | 2–6 | Wiring |
| `$APP/intelligence.py` | 4 | Skip conversations the bot is handling |
| DocTypes `bot_conversation` (+`history` 2, `ai_signals` 4, `jev_calls` 5), `lead_engine_settings` (+Jev fields 2, cost guard 5, advisor 6), `bot_slot` (+`ask_on_demand` 6), `ai_decision_log` (+`jev_extra` 6) | | |
| `$APP/demo/saoviet/settings.json`, `bot_slots.json`, `bot_skills.json` | 2, 6 | Templates, thresholds; `goal`/`level` slots; advisor params |
| `$T/engine_fixtures.py` | 1+ | `FakeJev`, `FakeRepo.jev_client` |

---

### Task 1: C3.1 — Labelled utterance set, Jev client, question builder, evaluation tool

Implements layer **C3.1** (D-033) and the parts of C3.2 the gate needs: the client (D-031, D-076) and data-generated questions (D-028, D-039 question fan-out, D-075). Out of scope: using the answers in the bot (Tasks 2–6).

**Files:**
- Create: `$APP/engine/jev.py`, `$APP/engine/jev_questions.py`, `$APP/engine/evaluate.py`, `$APP/engine/eval/utterances.json`
- Modify: `$APP/engine/catalog.py` (Skill `description`, `examples`; C3 settings defaults), `$APP/engine/state.py` (`history`, `jev_calls`)
- Modify tests: `$T/engine_fixtures.py` (`FakeJev`)
- Create tests: `$T/test_engine_jev.py`, `$T/test_engine_jev_questions.py`, `$T/test_engine_evaluate.py`

**Interfaces:**
- Consumes: `Catalog`, `ConversationState`, `understand()`, `context.shown_slots`, `decide.slot_active`, `intelligence.INTENTS`/`HOTNESS`/`HOTNESS_CRITERIA`.
- Produces:
  - `jev.JevResult(status, answers, questions, model, input_tokens, latency_ms, error)` with `.log() -> dict`; statuses `ok | unavailable | disabled | skipped_cost_guard`.
  - `jev.JevClient(api_key, model="jev-latest", url=JEV_URL, timeout=8.0, post=None, clock=time.monotonic)` with `.ask(state, questions) -> JevResult`.
  - `jev.jev_client(conf, settings, force=None) -> JevClient | None` (None without key; `force=False` → None; `force=True` → client; `force=None` → client only if `settings["jev_live"]`).
  - `jev_questions.NONE = "none"`, `jev_questions.MAX_HISTORY = 20`, `jev_questions.jev_state(text, state, catalog) -> dict`, `jev_questions.build_questions(state, u, catalog, skills=True) -> dict`. Keys: `parent:<slot>`, `slot:<slot>`, `skill:<key>`, `intent`, `hotness`, `wants_human`.
  - `evaluate.load_utterances(path=UTTERANCES)`, `evaluate.item_state(item)`, `evaluate.expected_answers(item, questions, catalog)`, `evaluate.grade(key, answer, expected, catalog)`, `evaluate.evaluate_items(items, catalog, ask)`, `evaluate.summarize(rows)`, bench entry `evaluate.run(limit=None)`.
  - Settings defaults (in `DEFAULT_SETTINGS`): `jev_live 0, jev_timeout 8, catalog_act 0.85, catalog_confirm 0.55, choice_act 0.80, choice_confirm 0.50, skill_act 0.85, skill_confirm 0.60, handoff_noul 0.70, spam_threshold 0.80, jev_calls_per_hour 20, jev_daily_token_budget 0, playground_daily_token_budget 0, advisor_goal_weight 0.6, advisor_level_weight 0.4, advisor_floor 0.5, advisor_shortlist 8`, plus `confirm_slot_template`, `confirm_skill_template`.
  - `ConversationState.history: list`, `ConversationState.jev_calls: list` (persisted in Tasks 2 and 5).

- [ ] **Step 1: Write the failing tests**

Append to `$T/engine_fixtures.py`:

```python
class FakeJev:
    """Stands in for engine.jev.JevClient: answers from a dict (or a function of the questions)."""

    def __init__(self, answers=None, status="ok"):
        self.answers, self.status, self.calls = answers or {}, status, []

    def ask(self, state, questions):
        from mmm_custom.engine.jev import JevResult

        self.calls.append((state, questions))
        if self.status != "ok":
            return JevResult(self.status, questions=questions, error="fake failure")
        answers = self.answers(questions) if callable(self.answers) else self.answers
        return JevResult("ok", {k: v for k, v in answers.items() if k in questions}, questions, "jev-test", 120, 7)
```

`$T/test_engine_jev.py`:

```python
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_fixtures  # noqa: F401

from mmm_custom.engine.jev import JevClient, jev_client


class ConnectionError(Exception):  # same name as requests' ConnectionError, which the client retries
    pass


def response(data, status=200):
    r = MagicMock()
    r.json.return_value = data
    r.raise_for_status.side_effect = None if status == 200 else RuntimeError(f"HTTP {status}")
    return r


OK = {"model": "jev-1.13.0", "answers": {"intent": {"type": "choice", "choice": "price", "confidence": 1.0}},
      "usage": {"input_tokens": 344}}
Q = {"intent": {"type": "choice", "instructions": "x", "criteria": {"price": "p"}}}


class TestClient(unittest.TestCase):
    def test_ok_answer_with_model_and_tokens(self):
        post = MagicMock(return_value=response(OK))
        r = JevClient("k", post=post).ask({"latest_message": "hp?"}, Q)
        self.assertEqual((r.status, r.model, r.input_tokens), ("ok", "jev-1.13.0", 344))
        self.assertEqual(r.answers["intent"]["choice"], "price")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer k"})
        self.assertEqual(kwargs["json"]["questions"], Q)
        self.assertLessEqual(kwargs["timeout"], 8.0)

    def test_dropped_connection_is_retried_once(self):
        post = MagicMock(side_effect=[ConnectionError("Remote end closed"), response(OK)])
        self.assertEqual(JevClient("k", post=post).ask({}, Q).status, "ok")
        self.assertEqual(post.call_count, 2)

    def test_other_errors_are_unavailable_without_retry(self):
        post = MagicMock(return_value=response({}, status=500))
        r = JevClient("k", post=post).ask({}, Q)
        self.assertEqual((r.status, post.call_count), ("unavailable", 1))
        self.assertIn("HTTP 500", r.error)

    def test_malformed_response_is_unavailable(self):
        bad = MagicMock()
        bad.raise_for_status.side_effect = None
        bad.json.side_effect = ValueError("not json")
        self.assertEqual(JevClient("k", post=MagicMock(return_value=bad)).ask({}, Q).status, "unavailable")

    def test_no_questions_no_call(self):
        post = MagicMock()
        self.assertEqual(JevClient("k", post=post).ask({}, {}).status, "ok")
        post.assert_not_called()

    def test_log_shape(self):
        r = JevClient("k", post=MagicMock(return_value=response(OK))).ask({}, Q)
        self.assertEqual(set(r.log()), {"status", "questions", "answers", "model", "latency_ms", "input_tokens", "error"})


class TestFactory(unittest.TestCase):
    def test_key_and_switches(self):
        self.assertIsNone(jev_client({}, {"jev_live": 1}))
        self.assertIsNone(jev_client({"typesafe_api_key": "k"}, {"jev_live": 0}))
        self.assertIsNotNone(jev_client({"typesafe_api_key": "k"}, {"jev_live": 1}))
        self.assertIsNone(jev_client({"typesafe_api_key": "k"}, {"jev_live": 1}, force=False))
        c = jev_client({"typesafe_api_key": "k", "typesafe_model": "jev-x"}, {"jev_live": 0, "jev_timeout": 5}, force=True)
        self.assertEqual((c.model, c.timeout), ("jev-x", 5.0))


if __name__ == "__main__":
    unittest.main()
```

`$T/test_engine_jev_questions.py`:

```python
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, fill

from mmm_custom.engine.jev_questions import NONE, build_questions, jev_state
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding, understand

CAT = demo_catalog()


class TestQuestions(unittest.TestCase):
    def test_new_conversation_asks_open_slots_skills_and_signals(self):
        q = build_questions(ConversationState("1"), Understanding(), CAT)
        for key in ("parent:course", "slot:course", "parent:branch", "slot:branch", "slot:learner",
                    "slot:preferred_shift", "intent", "hotness", "wants_human"):
            self.assertIn(key, q)
        for key in ("slot:learner_age", "slot:customer_name", "slot:phone"):
            self.assertNotIn(key, q)
        self.assertEqual(len(q["slot:course"]["criteria"]), 47)  # 46 courses + none
        self.assertIn(NONE, q["slot:course"]["criteria"])
        self.assertEqual(sum(k.startswith("skill:") for k in q), 30)
        self.assertEqual(q["skill:fee_quote"]["type"], "noul")
        self.assertEqual((q["hotness"]["type"], q["wants_human"]["type"]), ("score", "noul"))

    def test_criteria_carry_vietnamese_aliases(self):
        q = build_questions(ConversationState("1"), Understanding(), CAT)
        self.assertIn("excel", q["slot:course"]["criteria"]["VP-EXCEL"])
        self.assertIn("di an", q["slot:branch"]["criteria"]["CN Dĩ An"])

    def test_filled_slots_are_not_asked_but_this_turns_keyword_matches_are(self):
        filled_before = ConversationState("1", slots={"course": fill("VP-EXCEL")})
        self.assertNotIn("slot:course", build_questions(filled_before, Understanding(), CAT))
        u = understand("excel", ConversationState("1"), CAT)
        self.assertIn("slot:course", build_questions(ConversationState("1"), u, CAT))

    def test_candidates_and_parent_narrow_the_choice(self):
        u = Understanding(ambiguous={"course": ["DH-AI", "DH-PTS"]})
        q = build_questions(ConversationState("1"), u, CAT)
        self.assertEqual(set(q["slot:course"]["criteria"]), {"DH-AI", "DH-PTS", NONE})
        self.assertNotIn("parent:course", q)
        q = build_questions(ConversationState("1", slots={"course": {"parent": "Kế toán"}}), Understanding(), CAT)
        self.assertEqual(len(q["slot:course"]["criteria"]), 6)

    def test_number_slot_asked_only_when_active(self):
        s = ConversationState("1", slots={"learner": fill("child")})
        q = build_questions(s, Understanding(), CAT)
        self.assertEqual(len(q["slot:learner_age"]["criteria"]), 100)
        self.assertEqual(q["slot:learner_age"]["criteria"]["9"], "9")

    def test_skills_can_be_left_out(self):
        self.assertFalse(any(k.startswith("skill:") for k in build_questions(ConversationState("1"), Understanding(), CAT, skills=False)))

    def test_state_for_jev(self):
        s = ConversationState("1", slots={"course": fill("VP-EXCEL")}, pending={"slot": "branch"},
                              history=[{"from": "customer", "text": str(i)} for i in range(30)])
        st = jev_state("ở dĩ an", s, CAT)
        self.assertEqual(st["latest_message"], "ở dĩ an")
        self.assertEqual(st["known"], {"course": "Excel từ cơ bản đến nâng cao"})
        self.assertEqual(st["bot_question"], "Chi nhánh")
        self.assertEqual(len(st["recent_turns"]), 20)


if __name__ == "__main__":
    unittest.main()
```

`$T/test_engine_evaluate.py`:

```python
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog

from mmm_custom.engine.evaluate import evaluate_items, expected_answers, grade, item_state, load_utterances, summarize
from mmm_custom.engine.jev_questions import NONE, build_questions
from mmm_custom.engine.understand import understand

CAT = demo_catalog()
ITEMS = load_utterances()


def perfect(item_by_text, wrong=None):
    """A fake Jev that answers every question as labelled, except `wrong` = {question: answer}."""
    def ask(state, questions):
        item = item_by_text[state["latest_message"]]
        exp = expected_answers(item, questions, CAT)
        out = {}
        for key, q in questions.items():
            want = exp.get(key, NONE if q["type"] == "choice" else False)
            if q["type"] == "noul":
                out[key] = {"noul": 0.97 if want else 0.02}
            elif q["type"] == "score":
                out[key] = {"score": 1.0, "confidence": 0.9}
            else:
                out[key] = {"choice": want, "confidence": 0.97}
        out.update(wrong or {})
        return out
    return ask


class TestUtterances(unittest.TestCase):
    def test_at_least_100_unique_and_all_labels_exist_in_the_catalog(self):
        self.assertGreaterEqual(len(ITEMS), 100)
        self.assertEqual(len({i["id"] for i in ITEMS}), len(ITEMS))
        for item in ITEMS:
            exp = item["expect"]
            for key, value in exp.get("slots", {}).items():
                slot = CAT.slot(key)
                self.assertIsNotNone(slot, item["id"])
                if slot.type == "catalog":
                    self.assertIn(value, CAT.courses if slot.source == "course" else CAT.branches, item["id"])
                elif slot.type == "choice":
                    self.assertIsNotNone(slot.option(value), item["id"])
            for key, value in exp.get("parents", {}).items():
                self.assertIn(value, CAT.groups if key == "course" else CAT.areas, item["id"])
            for skill in exp.get("skills", []):
                self.assertIn(skill, CAT.skills, item["id"])
            if item.get("pending"):
                self.assertIsNotNone(CAT.slot(item["pending"]), item["id"])

    def test_hard_categories_are_covered(self):
        tags = {t for i in ITEMS for t in i["tags"]}
        self.assertTrue({"no_diacritics", "abbreviation", "multi_slot", "multi_topic", "negation", "spam", "b2b",
                         "short_answer", "wants_human"} <= tags)


class TestGrading(unittest.TestCase):
    def test_expected_answers(self):
        item = {"id": "x", "text": "robot cho con 8 tuoi o di an", "pending": None,
                "expect": {"slots": {"course": "TE-ROBO", "branch": "CN Dĩ An", "learner": "child"}, "skills": ["fee_quote"]}}
        state = item_state(item)
        q = build_questions(state, understand(item["text"], state, CAT), CAT)
        exp = expected_answers(item, q, CAT)
        self.assertEqual((exp["slot:course"], exp["slot:branch"]), ("TE-ROBO", "CN Dĩ An"))
        self.assertEqual((exp["slot:preferred_shift"], exp["skill:fee_quote"], exp["skill:hotline"], exp["wants_human"]),
                         (NONE, True, False, False))
        self.assertNotIn("intent", exp)
        item["expect"]["skip"] = ["skill:hotline"]
        self.assertNotIn("skill:hotline", expected_answers(item, q, CAT))

    def test_grade_bands(self):
        self.assertTrue(grade("skill:hotline", {"noul": 0.9}, False, CAT)["act_wrong"])
        self.assertEqual(grade("skill:hotline", {"noul": 0.7}, False, CAT)["band"], "confirm")
        self.assertEqual(grade("slot:course", {"choice": NONE, "confidence": 0.99}, "VP-EXCEL", CAT)["band"], "low")
        row = grade("slot:course", {"choice": "VP-EXCEL", "confidence": 0.9}, "VP-EXCEL", CAT)
        self.assertEqual((row["band"], row["correct"], row["act_wrong"]), ("act", True, False))
        self.assertEqual(grade("intent", {"choice": "price_inquiry", "confidence": 0.99}, "spam", CAT)["band"], "low")

    def test_gate_passes_only_without_critical_act_errors(self):
        items = ITEMS[:12]
        by_text = {i["text"]: i for i in items}
        report = summarize(evaluate_items(items, CAT, perfect(by_text)))
        self.assertTrue(report["passed"])
        self.assertEqual(report["critical_act_wrong"], 0)
        bad = summarize(evaluate_items(items, CAT, perfect(by_text, {"skill:hotline": {"noul": 0.95}})))
        self.assertFalse(bad["passed"])
        self.assertGreater(bad["critical_act_wrong"], 0)

    def test_failed_calls_fail_the_gate(self):
        report = summarize(evaluate_items(ITEMS[:2], CAT, lambda state, questions: None))
        self.assertEqual((report["errors"], report["passed"]), (2, False))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | grep -E "Error:|^Ran|FAILED" | head`
Expected: ERROR — `No module named 'mmm_custom.engine.jev'` (and `jev_questions`, `evaluate`).

- [ ] **Step 3: Implement the client, the question builder and the catalog/state additions**

In `$APP/engine/catalog.py`:
- extend `DEFAULT_SETTINGS` with (after `"log_retention_days": 180,`):

```python
    # C3 Jev understanding (D-030 bands, D-031 timeout, D-061 cost guard, D-055 advisor, D-073 live switch).
    "jev_live": 0, "jev_timeout": 8, "catalog_act": 0.85, "catalog_confirm": 0.55, "choice_act": 0.80,
    "choice_confirm": 0.50, "skill_act": 0.85, "skill_confirm": 0.60, "handoff_noul": 0.70, "spam_threshold": 0.80,
    "jev_calls_per_hour": 20, "jev_daily_token_budget": 0, "playground_daily_token_budget": 0,
    "advisor_goal_weight": 0.6, "advisor_level_weight": 0.4, "advisor_floor": 0.5, "advisor_shortlist": 8,
    "confirm_slot_template": "Dạ ý {{ brand.you }} là {{ confirm.label }} phải không ạ?",
    "confirm_skill_template": "Dạ {{ brand.you }} muốn hỏi về {{ confirm.label }} phải không ạ?",
```

- add to `Skill` (after `media: str = ""`): `description: str = ""` and `examples: tuple = ()`;
- in `build_catalog`, the `Skill(...)` call gets `description=k.get("jev_description") or "", examples=tuple(line.strip() for line in (k.get("examples") or "").splitlines() if line.strip()),` after `media=…`.

In `$APP/engine/state.py` add after `answered`:

```python
    history: list = field(default_factory=list)    # last turns for Jev's state (D-074)
    jev_calls: list = field(default_factory=list)  # epoch seconds of Jev calls in the last hour (D-061)
```

`$APP/engine/jev.py`:

```python
"""TypeSafe Jev in the bot path (D-028, D-031, D-076): one System One call with parallel typed
questions and an 8 s budget. Any failure returns status "unavailable" and the turn continues on
the keyword tier; Jev never writes text (D-003)."""

import time
from dataclasses import dataclass, field

try:
    import requests
except ImportError:  # offline tests
    requests = None

JEV_URL = "https://api.typesafe.ai/v1/systemone"
RETRYABLE = ("ConnectionError", "RemoteDisconnected", "ChunkedEncodingError")


@dataclass
class JevResult:
    status: str  # ok | unavailable | disabled | skipped_cost_guard (D-056)
    answers: dict = field(default_factory=dict)
    questions: dict = field(default_factory=dict)
    model: str = ""
    input_tokens: int = 0
    latency_ms: int = 0
    error: str = ""

    def log(self):
        return {"status": self.status, "questions": self.questions, "answers": self.answers, "model": self.model,
                "latency_ms": self.latency_ms, "input_tokens": self.input_tokens, "error": self.error}


class JevClient:
    def __init__(self, api_key, model="jev-latest", url=JEV_URL, timeout=8.0, post=None, clock=time.monotonic):
        self.api_key, self.model, self.url, self.timeout = api_key, model, url, float(timeout)
        self.post = post or (lambda *args, **kwargs: requests.post(*args, **kwargs))
        self.clock = clock

    def _ms(self, start):
        return int((self.clock() - start) * 1000)

    def ask(self, state, questions):
        if not questions:
            return JevResult("ok")
        start, error = self.clock(), ""
        body = {"model": self.model, "state": state, "questions": questions}
        for attempt in range(2):
            try:
                resp = self.post(self.url, headers={"Authorization": f"Bearer {self.api_key}"}, json=body,
                                 timeout=max(self.timeout - (self.clock() - start), 1.0))
                resp.raise_for_status()
                data = resp.json()
                return JevResult("ok", dict(data.get("answers") or {}), questions, data.get("model") or "",
                                 int((data.get("usage") or {}).get("input_tokens") or 0), self._ms(start))
            except Exception as e:
                error = f"{type(e).__name__}: {e}"[:300]
                if attempt or type(e).__name__ not in RETRYABLE or self.clock() - start > self.timeout / 2:
                    break
        return JevResult("unavailable", questions=questions, latency_ms=self._ms(start), error=error)


def jev_client(conf, settings, force=None):
    """The client for this turn, or None: no key, forced off, or not live yet (D-073)."""
    key = conf.get("typesafe_api_key")
    if not key or force is False or not (force or settings.get("jev_live")):
        return None
    return JevClient(key, conf.get("typesafe_model") or "jev-latest", conf.get("typesafe_api_url") or JEV_URL,
                     timeout=float(settings.get("jev_timeout") or 8))
```

`$APP/engine/jev_questions.py`:

```python
"""Jev questions generated from CRM data (D-028, D-039, D-075): only what is still open, criteria in
English carrying the Vietnamese names and aliases customers use. Keys:
    parent:<slot>  course group / area          slot:<slot>  course, branch, choice or number value
    skill:<key>    one noul per Bot Skill        intent · hotness · wants_human (D-032)
"""

from mmm_custom.engine.context import shown_slots
from mmm_custom.engine.decide import slot_active
from mmm_custom.engine.state import filled
from mmm_custom.intelligence import HOTNESS_CRITERIA, INTENTS

NONE = "none"
NONE_TEXT = "None of these, or not said in the chat"
MAX_HISTORY = 20  # 10 turns of customer + bot lines (D-061, D-074)


def _named(name, aliases=()):
    return f"{name} (customers also write: {', '.join(aliases)})" if aliases else name


def _choice(instructions, criteria):
    return {"type": "choice", "instructions": instructions, "criteria": {**criteria, NONE: NONE_TEXT}}


def jev_state(text, state, catalog):
    pending = catalog.slot(state.pending.get("slot") or "")
    return {"latest_message": text, "recent_turns": list(state.history[-MAX_HISTORY:]),
            "known": shown_slots(state.slots, catalog), "bot_question": pending.label if pending else ""}


def _catalog_questions(slot, state, u, catalog):
    entry = state.slots.get(slot.key) or {}
    candidates = u.ambiguous.get(slot.key) or entry.get("candidates") or []
    parent = u.parents.get(slot.key) or entry.get("parent") or ""
    if slot.source == "course":
        parents = {g.name: _named(g.name, g.aliases) for g in catalog.groups.values()}
        leaves = {c.code: f"{_named(c.name, c.aliases)}; group: {c.group}; for: {c.audience}" for c in catalog.courses.values()}
        what, parent_what = "course", "course group (field of study)"
    else:
        parents = {a.name: _named(a.name, a.aliases) for a in catalog.areas.values()}
        leaves = {b.name: f"{_named(b.name, b.aliases)}; address: {b.address}" for b in catalog.branches.values()}
        what, parent_what = "branch (campus) where the customer wants to study", "province or area"
    if candidates:
        leaves = {k: v for k, v in leaves.items() if k in candidates}
    elif parent:
        leaves = {k: v for k, v in leaves.items() if catalog.parent_of(slot, k) == parent}
    out = {}
    if not parent and not candidates:
        out[f"parent:{slot.key}"] = _choice(f"Which {parent_what} does the customer mean in this Vietnamese chat?", parents)
    out[f"slot:{slot.key}"] = _choice(f"Which {what} does the customer mean in this Vietnamese chat?", leaves)
    return out


def build_questions(state, u, catalog, skills=True):
    q = {}
    for slot in catalog.slots:
        if not slot_active(slot, state.slots) or filled(state.slots, slot.key):
            continue  # D-075: open before this message; this turn's keyword matches are still cross-checked
        if slot.type == "catalog":
            q.update(_catalog_questions(slot, state, u, catalog))
        elif slot.type == "choice":
            q[f"slot:{slot.key}"] = _choice(f"What does the customer answer for '{slot.label}' in this Vietnamese chat?",
                                            {o.value: _named(o.label, o.aliases) for o in slot.options})
        elif slot.type == "number":
            q[f"slot:{slot.key}"] = _choice(f"Which number does the customer give for '{slot.label}'?",
                                            {str(n): str(n) for n in range(1, 100)})
    if skills:
        for key, skill in catalog.skills.items():
            question = {"type": "noul", "instructions": f"Does the customer's latest message ask about this: {skill.description or skill.title}?"}
            if skill.examples:
                question["criteria"] = {"true": "Messages like: " + " | ".join(skill.examples),
                                        "false": "The latest message is about something else"}
            q[f"skill:{key}"] = question
    q["intent"] = {"type": "choice", "instructions": "What does the customer want in this Vietnamese chat with a training centre?",
                   "criteria": INTENTS}
    q["hotness"] = {"type": "score", "instructions": "How close is the customer to enrolling, based on the whole chat?",
                    "criteria": HOTNESS_CRITERIA}
    q["wants_human"] = {"type": "noul", "instructions": "Does the customer ask to talk to a real person or consultant, or to be called back?"}
    return q
```

- [ ] **Step 4: Write the labelled utterance set**

`$APP/engine/eval/utterances.json`:

```json
[
 {"id": "u001", "tags": ["no_diacritics", "multi_topic"], "text": "hoc phi khoa excel bao nhieu vay shop", "pending": null, "expect": {"slots": {"course": "VP-EXCEL"}, "skills": ["fee_quote"]}},
 {"id": "u002", "tags": ["no_diacritics", "multi_slot"], "text": "cho minh hoi lop autocad o thu duc khi nao khai giang", "pending": null, "expect": {"slots": {"course": "VKT-CAD2D", "branch": "CN Thủ Đức"}, "skills": ["schedule_lookup"]}},
 {"id": "u003", "tags": ["no_diacritics"], "text": "e muon hoc ke toan thue", "pending": null, "expect": {"slots": {"course": "KT-THUE"}}},
 {"id": "u004", "tags": ["no_diacritics", "abbreviation"], "text": "photoshop nang cao hp bn a", "pending": null, "expect": {"slots": {"course": "DH-PTS-NC"}, "skills": ["fee_quote"]}},
 {"id": "u005", "tags": ["no_diacritics", "abbreviation", "multi_slot"], "text": "co lop python cho be 11t ko", "pending": null, "expect": {"slots": {"course": "TE-PY", "learner": "child"}, "skills": ["schedule_lookup"]}},
 {"id": "u006", "tags": ["no_diacritics", "multi_slot"], "text": "robot cho con 8 tuoi o di an", "pending": null, "expect": {"slots": {"course": "TE-ROBO", "branch": "CN Dĩ An", "learner": "child"}}},
 {"id": "u007", "tags": ["no_diacritics", "multi_slot"], "text": "hoc do hoa o bien hoa", "pending": null, "expect": {"parents": {"course": "Thiết kế đồ họa"}, "slots": {"branch": "CN Biên Hòa"}}},
 {"id": "u008", "tags": ["no_diacritics", "abbreviation", "multi_slot"], "text": "tin hoc van phong o q7 hoc toi", "pending": null, "expect": {"parents": {"course": "Tin học văn phòng"}, "slots": {"branch": "CN Quận 7", "preferred_shift": "evening"}}},
 {"id": "u009", "tags": ["no_diacritics", "abbreviation", "multi_slot"], "text": "lop revit o tdm", "pending": null, "expect": {"slots": {"course": "VKT-REVIT", "branch": "CN Thủ Dầu Một"}}},
 {"id": "u010", "tags": ["no_diacritics"], "text": "3ds max hoc bao lau", "pending": null, "expect": {"slots": {"course": "VKT-3DS"}, "skills": ["duration"]}},
 {"id": "u011", "tags": ["no_diacritics", "abbreviation"], "text": "sketchup gia bn", "pending": null, "expect": {"slots": {"course": "VKT-SKP"}, "skills": ["fee_quote"]}},
 {"id": "u012", "tags": ["no_diacritics"], "text": "chi nhanh o binh duong nam o dau", "pending": null, "expect": {"parents": {"branch": "Bình Dương"}, "skills": ["branch_info"]}},
 {"id": "u013", "tags": ["no_diacritics"], "text": "hoc phan mem misa", "pending": null, "expect": {"slots": {"course": "KT-MISA"}}},
 {"id": "u014", "tags": ["no_diacritics", "abbreviation"], "text": "hoc chay ads fb", "pending": null, "expect": {"slots": {"course": "MKT-FB"}}},
 {"id": "u015", "tags": ["no_diacritics"], "text": "muon hoc seo len top google", "pending": null, "expect": {"slots": {"course": "MKT-SEO"}}},
 {"id": "u016", "tags": ["no_diacritics"], "text": "khoa n8n tu dong hoa cong viec", "pending": null, "expect": {"slots": {"course": "AI-N8N"}}},
 {"id": "u017", "tags": ["no_diacritics"], "text": "vibe coding hoc o dau", "pending": null, "expect": {"slots": {"course": "AI-VIBE"}, "skills": ["branch_info"]}},
 {"id": "u018", "tags": ["no_diacritics"], "text": "luyen thi mos quoc te", "pending": null, "expect": {"slots": {"course": "VP-MOS"}}},
 {"id": "u019", "tags": ["no_diacritics", "abbreviation"], "text": "hoc ppt lam slide thuyet trinh", "pending": null, "expect": {"slots": {"course": "VP-PPT"}}},
 {"id": "u020", "tags": ["no_diacritics"], "text": "hoc word soan thao van ban", "pending": null, "expect": {"slots": {"course": "VP-WORD"}}},
 {"id": "u021", "tags": ["no_diacritics"], "text": "e can hoc may tinh can ban", "pending": null, "expect": {"slots": {"course": "VP-CB"}}},
 {"id": "u022", "tags": ["no_diacritics", "multi_slot"], "text": "scratch cho be 7 tuoi", "pending": null, "expect": {"slots": {"course": "TE-SCRATCH", "learner": "child"}}},
 {"id": "u023", "tags": ["no_diacritics"], "text": "hoc premiere dung video", "pending": null, "expect": {"slots": {"course": "DH-PR"}}},
 {"id": "u024", "tags": ["no_diacritics"], "text": "corel in an bang ron", "pending": null, "expect": {"slots": {"course": "DH-CRD"}}},
 {"id": "u025", "tags": ["no_diacritics"], "text": "solidworks thiet ke co khi", "pending": null, "expect": {"slots": {"course": "VKT-SW"}}},
 {"id": "u026", "tags": ["no_diacritics"], "text": "lap trinh app dien thoai android", "pending": null, "expect": {"slots": {"course": "LT-MOBILE"}}},
 {"id": "u027", "tags": ["no_diacritics"], "text": "vba macro excel tu dong", "pending": null, "expect": {"slots": {"course": "LT-VBA"}}},
 {"id": "u028", "tags": ["no_diacritics"], "text": "excel nang cao pivot dashboard", "pending": null, "expect": {"slots": {"course": "VP-EXCEL-NC"}}},
 {"id": "u029", "tags": ["no_diacritics", "abbreviation", "multi_slot"], "text": "ke toan tong hop thuc hanh o q12", "pending": null, "expect": {"slots": {"course": "KT-TH", "branch": "CN Quận 12"}}},
 {"id": "u030", "tags": ["no_diacritics"], "text": "ai cho nguoi moi bat dau", "pending": null, "expect": {"slots": {"course": "AI-BASIC"}}},
 {"id": "u031", "tags": ["abbreviation", "multi_slot", "multi_topic"], "text": "Học phí AutoCAD 3D ở Tân Bình bn ạ", "pending": null, "expect": {"slots": {"course": "VKT-CAD3D", "branch": "CN Tân Bình"}, "skills": ["fee_quote"]}},
 {"id": "u032", "tags": ["abbreviation"], "text": "Cho e hỏi lịch khai giảng Illustrator tuần sau", "pending": null, "expect": {"slots": {"course": "DH-AI"}, "skills": ["schedule_lookup"]}},
 {"id": "u033", "tags": ["abbreviation"], "text": "Khóa after effect học mấy tháng", "pending": null, "expect": {"slots": {"course": "DH-AE"}, "skills": ["duration"]}},
 {"id": "u034", "tags": ["abbreviation", "multi_slot"], "text": "e ở Long Thành muốn học kế toán cơ bản", "pending": null, "expect": {"slots": {"course": "KT-CB", "branch": "CN Long Thành"}}},
 {"id": "u035", "tags": ["multi_slot"], "text": "Vũng Tàu có lớp Excel không ạ", "pending": null, "expect": {"slots": {"course": "VP-EXCEL", "branch": "CN Vũng Tàu"}, "skills": ["schedule_lookup"]}},
 {"id": "u036", "tags": ["multi_topic"], "text": "học phí và lịch học khóa python", "pending": null, "expect": {"slots": {"course": "LT-PY"}, "skills": ["fee_quote", "schedule_lookup"]}},
 {"id": "u037", "tags": ["multi_topic", "multi_slot", "abbreviation"], "text": "autocad học phí bn, có lớp tối ko, ở thủ đức", "pending": null, "expect": {"slots": {"course": "VKT-CAD2D", "branch": "CN Thủ Đức", "preferred_shift": "evening"}, "skills": ["fee_quote", "schedule_lookup"]}},
 {"id": "u038", "tags": ["multi_topic"], "text": "khóa word học bao lâu, có chứng chỉ không", "pending": null, "expect": {"slots": {"course": "VP-WORD"}, "skills": ["duration", "certificate_info"]}},
 {"id": "u039", "tags": ["multi_topic"], "text": "địa chỉ chi nhánh bình thạnh với số hotline", "pending": null, "expect": {"slots": {"branch": "CN Bình Thạnh"}, "skills": ["branch_info", "hotline"]}},
 {"id": "u040", "tags": ["multi_topic"], "text": "có học thử không, có cần mang laptop không", "pending": null, "expect": {"skills": ["trial_class", "laptop"]}},
 {"id": "u041", "tags": ["multi_topic"], "text": "khóa excel đang có khuyến mãi gì không, đóng tiền sao", "pending": null, "expect": {"slots": {"course": "VP-EXCEL"}, "skills": ["promotions", "payment"]}},
 {"id": "u042", "tags": ["negation"], "text": "không phải excel, em muốn học word", "pending": null, "expect": {"slots": {"course": "VP-WORD"}}},
 {"id": "u043", "tags": ["negation"], "text": "em không học ở Dĩ An nữa, chuyển qua Thuận An", "pending": null, "expect": {"slots": {"branch": "CN Thuận An"}}},
 {"id": "u044", "tags": ["negation"], "text": "không cần gặp tư vấn viên đâu, cho em hỏi học phí thôi", "pending": null, "expect": {"skills": ["fee_quote"], "wants_human": false}},
 {"id": "u045", "tags": ["negation"], "text": "mình không ở Sài Gòn, mình ở Đồng Nai", "pending": null, "expect": {"parents": {"branch": "Đồng Nai"}}},
 {"id": "u046", "tags": ["negation"], "text": "chưa muốn đăng ký đâu, chỉ hỏi giá photoshop", "pending": null, "expect": {"slots": {"course": "DH-PTS"}, "skills": ["fee_quote"]}},
 {"id": "u047", "tags": ["negation"], "text": "không phải cho con, em tự học", "pending": null, "expect": {"slots": {"learner": "self"}}},
 {"id": "u048", "tags": ["negation"], "text": "tối em bận, học buổi sáng được không", "pending": null, "expect": {"slots": {"preferred_shift": "morning"}, "skills": ["shifts"]}},
 {"id": "u049", "tags": ["spam"], "text": "Vay tiền nhanh lãi suất thấp, giải ngân trong ngày, liên hệ 0909123456", "pending": null, "expect": {"intent": "spam"}},
 {"id": "u050", "tags": ["spam"], "text": "Tuyển CTV bán hàng online thu nhập 20tr/tháng inbox ngay", "pending": null, "expect": {"intent": "spam"}},
 {"id": "u051", "tags": ["spam"], "text": "Click link nhận quà miễn phí http://bit.ly/qua-tang", "pending": null, "expect": {"intent": "spam"}},
 {"id": "u052", "tags": ["spam"], "text": "Bán acc game liên quân giá rẻ uy tín", "pending": null, "expect": {"intent": "spam"}},
 {"id": "u053", "tags": ["spam"], "text": "Dịch vụ tăng like tăng follow fanpage giá rẻ", "pending": null, "expect": {"intent": "spam"}},
 {"id": "u054", "tags": ["b2b", "multi_slot"], "text": "công ty mình cần đào tạo excel cho 20 nhân viên", "pending": null, "expect": {"slots": {"course": "VP-EXCEL", "learner": "staff"}, "skills": ["corporate_training"]}},
 {"id": "u055", "tags": ["b2b"], "text": "bên em muốn mở lớp kế toán riêng cho doanh nghiệp", "pending": null, "expect": {"parents": {"course": "Kế toán"}, "slots": {"learner": "staff"}, "skills": ["corporate_training"]}},
 {"id": "u056", "tags": ["b2b"], "text": "doanh nghiệp đăng ký lớp AI văn phòng cho phòng nhân sự", "pending": null, "expect": {"slots": {"course": "VP-AI", "learner": "staff"}, "skills": ["corporate_training"]}},
 {"id": "u057", "tags": ["b2b"], "text": "cần báo giá đào tạo tin học văn phòng cho nhân viên nhà máy", "pending": null, "expect": {"parents": {"course": "Tin học văn phòng"}, "slots": {"learner": "staff"}, "skills": ["corporate_training"]}},
 {"id": "u058", "tags": ["wants_human"], "text": "cho em gặp tư vấn viên", "pending": null, "expect": {"skills": ["talk_to_human"], "wants_human": true}},
 {"id": "u059", "tags": ["wants_human"], "text": "gọi lại cho mình số 0901234567 nhé", "pending": null, "expect": {"skills": ["talk_to_human"], "wants_human": true}},
 {"id": "u060", "tags": ["wants_human"], "text": "nói chuyện với người thật được không", "pending": null, "expect": {"skills": ["talk_to_human"], "wants_human": true}},
 {"id": "u061", "tags": ["wants_human"], "text": "bot trả lời không đúng, cho mình gặp nhân viên", "pending": null, "expect": {"skills": ["talk_to_human"], "wants_human": true}},
 {"id": "u062", "tags": ["skill"], "text": "học mà giảng viên dạy chán quá, rất không hài lòng", "pending": null, "expect": {"skills": ["complaint"]}},
 {"id": "u063", "tags": ["skill"], "text": "em muốn bảo lưu khóa học", "pending": null, "expect": {"skills": ["refund"]}},
 {"id": "u064", "tags": ["skill"], "text": "cho em tra cứu chứng nhận đã học", "pending": null, "expect": {"skills": ["certificate_lookup"]}},
 {"id": "u065", "tags": ["short_answer"], "text": "excel", "pending": "course", "expect": {"slots": {"course": "VP-EXCEL"}}},
 {"id": "u066", "tags": ["short_answer"], "text": "cái đồ họa á", "pending": "course", "expect": {"parents": {"course": "Thiết kế đồ họa"}}},
 {"id": "u067", "tags": ["short_answer", "no_diacritics"], "text": "di an", "pending": "branch", "expect": {"slots": {"branch": "CN Dĩ An"}}},
 {"id": "u068", "tags": ["short_answer", "abbreviation"], "text": "q7", "pending": "branch", "expect": {"slots": {"branch": "CN Quận 7"}}},
 {"id": "u069", "tags": ["short_answer"], "text": "bình dương", "pending": "branch", "expect": {"parents": {"branch": "Bình Dương"}}},
 {"id": "u070", "tags": ["short_answer"], "text": "cho con", "pending": "learner", "expect": {"slots": {"learner": "child"}}},
 {"id": "u071", "tags": ["short_answer"], "text": "mình học", "pending": "learner", "expect": {"slots": {"learner": "self"}}},
 {"id": "u072", "tags": ["short_answer", "abbreviation"], "text": "cty", "pending": "learner", "expect": {"slots": {"learner": "staff"}}},
 {"id": "u073", "tags": ["short_answer"], "text": "bé 9 tuổi rồi", "pending": "learner_age", "known": {"learner": "child"}, "expect": {"slots": {"learner_age": 9}}},
 {"id": "u074", "tags": ["short_answer", "abbreviation"], "text": "7t", "pending": "learner_age", "known": {"learner": "child"}, "expect": {"slots": {"learner_age": 7}}},
 {"id": "u075", "tags": ["short_answer"], "text": "tối", "pending": "preferred_shift", "expect": {"slots": {"preferred_shift": "evening"}}},
 {"id": "u076", "tags": ["short_answer"], "text": "sáng thứ 7", "pending": "preferred_shift", "expect": {"slots": {"preferred_shift": "morning"}}},
 {"id": "u077", "tags": ["short_answer"], "text": "buổi chiều", "pending": "preferred_shift", "expect": {"slots": {"preferred_shift": "afternoon"}}},
 {"id": "u078", "tags": ["short_answer"], "text": "tối hoặc cuối tuần đều được", "pending": "preferred_shift", "expect": {"slots": {"preferred_shift": "evening"}}},
 {"id": "u079", "tags": ["short_answer"], "text": "autocad 2d", "pending": "course", "expect": {"slots": {"course": "VKT-CAD2D"}}},
 {"id": "u080", "tags": ["short_answer"], "text": "chưa biết học gì, tư vấn giúp em", "pending": "course", "expect": {"skills": ["course_advisor"]}},
 {"id": "u081", "tags": ["short_answer"], "text": "cho bé học lập trình", "pending": "course", "expect": {"parents": {"course": "Tin học trẻ em"}, "slots": {"learner": "child"}, "skip": ["slot:course"]}},
 {"id": "u082", "tags": ["skill"], "text": "trung tâm mở cửa mấy giờ", "pending": null, "expect": {"skills": ["opening_hours"]}},
 {"id": "u083", "tags": ["skill"], "text": "có học online không", "pending": null, "expect": {"skills": ["online_learning"]}},
 {"id": "u084", "tags": ["skill"], "text": "lớp khoảng bao nhiêu người", "pending": null, "expect": {"skills": ["class_size"]}},
 {"id": "u085", "tags": ["skill"], "text": "giảng viên là ai vậy", "pending": null, "expect": {"skills": ["teachers"]}},
 {"id": "u086", "tags": ["skill"], "text": "học xong có xin được việc không", "pending": null, "expect": {"skills": ["career"]}},
 {"id": "u087", "tags": ["skill"], "text": "mất gốc có học được không", "pending": null, "expect": {"skills": ["beginner_ok"]}},
 {"id": "u088", "tags": ["skill"], "text": "bé 5 tuổi học được khóa nào", "pending": null, "expect": {"slots": {"learner": "child"}, "skills": ["kids_courses"], "skip": ["skill:age_fit"]}},
 {"id": "u089", "tags": ["skill"], "text": "học xong excel thì học gì tiếp", "pending": null, "expect": {"slots": {"course": "VP-EXCEL"}, "skills": ["next_course"]}},
 {"id": "u090", "tags": ["skill"], "text": "nội dung khóa illustrator gồm những gì", "pending": null, "expect": {"slots": {"course": "DH-AI"}, "skills": ["course_content"]}},
 {"id": "u091", "tags": ["skill"], "text": "đăng ký giữ chỗ lớp photoshop", "pending": null, "expect": {"slots": {"course": "DH-PTS"}, "skills": ["register"]}},
 {"id": "u092", "tags": ["skill"], "text": "học chưa vững có được học lại miễn phí không", "pending": null, "expect": {"skills": ["unlimited_sessions"]}},
 {"id": "u093", "tags": ["skill"], "text": "xin chào shop", "pending": null, "expect": {"skills": ["greeting"]}},
 {"id": "u094", "tags": ["skill"], "text": "bên mình có những ca học nào", "pending": null, "expect": {"skills": ["shifts"]}},
 {"id": "u095", "tags": ["skill"], "text": "mình làm văn phòng muốn nâng cao kỹ năng máy tính, nên học gì", "pending": null, "expect": {"parents": {"course": "Tin học văn phòng"}, "slots": {"learner": "self"}, "skills": ["course_advisor"], "skip": ["slot:course"]}},
 {"id": "u096", "tags": ["skill"], "text": "dạo này có ưu đãi gì không", "pending": null, "expect": {"skills": ["promotions"]}},
 {"id": "u097", "tags": ["skill"], "text": "chuyển khoản học phí được không", "pending": null, "expect": {"skills": ["payment"]}},
 {"id": "u098", "tags": ["skill"], "text": "cho xin số zalo trung tâm", "pending": null, "expect": {"skills": ["hotline"]}},
 {"id": "u099", "tags": ["skill"], "text": "chứng chỉ IC3 có giá trị không", "pending": null, "expect": {"slots": {"course": "VP-IC3"}, "skills": ["certificate_info"]}},
 {"id": "u100", "tags": ["skill"], "text": "ok em cảm ơn", "pending": null, "expect": {}},
 {"id": "u101", "tags": ["skill"], "text": "hi", "pending": null, "expect": {"skills": ["greeting"]}},
 {"id": "u102", "tags": ["no_diacritics", "multi_slot"], "text": "con toi 10 tuoi muon hoc robotics nang cao o binh thanh", "pending": null, "expect": {"slots": {"course": "TE-ROBO-NC", "branch": "CN Bình Thạnh", "learner": "child"}}},
 {"id": "u103", "tags": ["abbreviation"], "text": "hp khoá tiktok ads", "pending": null, "expect": {"slots": {"course": "MKT-TT"}, "skills": ["fee_quote"]}},
 {"id": "u104", "tags": ["negation", "short_answer"], "text": "không, word thôi", "pending": "course", "expect": {"slots": {"course": "VP-WORD"}}}
]
```

- [ ] **Step 5: Implement the evaluation tool**

`$APP/engine/evaluate.py`:

```python
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
        result = client.ask(state, questions)
        tokens["input"] += result.input_tokens
        tokens["model"] = result.model or tokens["model"]
        return result.answers if result.status == "ok" else None

    items = load_utterances()[: int(limit)] if limit else load_utterances()
    rows = evaluate_items(items, catalog, ask)
    report = summarize(rows)
    report.update({"items": len(items), "input_tokens": tokens["input"], "model": tokens["model"]})
    path = frappe.get_site_path("private", "files", "lead_engine_eval.json")
    Path(path).write_text(json.dumps({"report": report, "rows": rows}, ensure_ascii=False, indent=1, default=str),
                          encoding="utf-8")
    for name, f in sorted(report["families"].items()):
        bands = " ".join(f"{b}:{f['bands'][b]['n']}/{f['bands'][b]['wrong']}✗" for b in BANDS)
        print(f"{name:28} {f['correct']:>3}/{f['n']:<3} {bands}")
    return {k: report[k] for k in ("passed", "critical_act_wrong", "errors", "items", "input_tokens", "model")} | {"report_file": path}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 7: Verify against real Jev (small sample)**

```bash
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost execute mmm_custom.engine.evaluate.run --kwargs \"{'limit': 3}\""
```
Expected: a per-family table and a dict with `errors: 0`, `items: 3`, `input_tokens > 0`, `model` like `jev-1.x`. (The full run is Task 7; do not tune on 3 items.)

- [ ] **Step 8: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/engine/jev.py frappe-custom/mmm_custom/mmm_custom/engine/jev_questions.py \
  frappe-custom/mmm_custom/mmm_custom/engine/evaluate.py frappe-custom/mmm_custom/mmm_custom/engine/eval/utterances.json \
  frappe-custom/mmm_custom/mmm_custom/engine/catalog.py frappe-custom/mmm_custom/mmm_custom/engine/state.py \
  frappe-custom/mmm_custom/mmm_custom/tests/engine_fixtures.py frappe-custom/mmm_custom/mmm_custom/tests/test_engine_jev.py \
  frappe-custom/mmm_custom/mmm_custom/tests/test_engine_jev_questions.py frappe-custom/mmm_custom/mmm_custom/tests/test_engine_evaluate.py
git commit -m "feat(ai): add Jev client, data-generated questions and labelled evaluation gate"
```

---

### Task 2: C3.2 — Combine keyword + Jev slots, confirmation turn, Jev in the pipeline

Implements **C3.2** (D-029 combination, D-030 bands + confirmation turn, D-031 fallback, D-073 live switch, D-074 history). Skills, intent/hotness and spam come in Tasks 3–5; this task only consumes `slot:*` and `parent:*` answers.

**Files:**
- Create: `$APP/engine/combine.py`
- Modify: `$APP/engine/understand.py` (Understanding fields; `confirm_yes`/`confirm_no` actions; yes/no text for a pending confirmation), `$APP/engine/decide.py` (`confirm` decision; `next_slot` re-asks slots in `first`), `$APP/engine/reply.py` (confirm paragraph + buttons), `$APP/engine/pipeline.py` (`understand_turn`, `Turn.jev`, history, pending confirmation, log), `$APP/engine/log.py` (`confirm_rejected` signal), `$APP/engine/repo.py` (`force_jev`, `jev_client()`, history persistence), `$APP/engine/playground.py` + page JS (Jev toggle, Jev section), DocTypes `bot_conversation` (+`history`), `lead_engine_settings` (+Jev section)
- Modify tests: `$T/engine_fixtures.py` (`FakeRepo.jev`, `FakeRepo.jev_client`)
- Create tests: `$T/test_engine_combine.py`, `$T/test_engine_confirm.py`; modify `$T/test_engine_pipeline.py`, `$T/test_engine_playground.py`

**Interfaces:**
- Consumes (Task 1): `JevResult`, `jev_client(conf, settings, force)`, `build_questions`, `jev_state`, `NONE`, `MAX_HISTORY`, settings `catalog_act/confirm`, `choice_act/confirm`, `confirm_slot_template`, `confirm_skill_template`, `ConversationState.history`.
- Produces:
  - `Understanding` new fields: `confirm: dict` (one of `{"kind": "slot", "slot", "value", "label"}` / `{"kind": "skill", "skill", "label"}`), `rejected: dict`, `intent: dict`, `hotness: dict`, `wants_human: float`, `spam: float` (the last four are filled in Tasks 4–5).
  - `combine.combine(u, answers, questions, state, catalog) -> Understanding` (returns a new object; never mutates `u`); helpers `combine.slot_limits(slot, settings)`, `combine.ask_confirm(u, confirm)`.
  - `Decision.confirm: dict`, decision type `"confirm"`; `decide.IMMEDIATE = ("button", "skill")` (handoff reasons that beat a confirmation).
  - `reply.CONFIRM_YES = "Đúng ạ"`, `reply.CONFIRM_NO = "Không phải"`.
  - `pipeline.understand_turn(text, state, catalog, jev) -> (Understanding, JevResult)`; `Turn.jev`.
  - `FrappeRepo(sandbox=False, sandbox_lead=None, force_jev=None)`, `FrappeRepo.jev_client()`; `FakeRepo.jev` (default None) + `FakeRepo.jev_client()`.
  - `playground.simulate(session, text, lead=None, jev=0)`, `playground.replay(log_name, jev=0)`.

- [ ] **Step 1: Write the failing tests**

In `$T/engine_fixtures.py`, in `FakeRepo.__init__` add `self.jev = None` after `self.consultant_rows, …`, and add the method:

```python
    def jev_client(self):
        return self.jev
```

`$T/test_engine_combine.py`:

```python
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, fill

from mmm_custom.engine.combine import combine
from mmm_custom.engine.jev_questions import NONE, build_questions
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding

CAT = demo_catalog()
NEW = ConversationState("1")


def pick(choice, confidence):
    return {"choice": choice, "confidence": confidence}


def run(answers, u=None, state=NEW):
    u = u or Understanding()
    return combine(u, answers, build_questions(state, u, CAT), state, CAT)


class TestSlots(unittest.TestCase):
    def test_act_band_fills_from_jev(self):
        out = run({"slot:course": pick("VKT-REVIT", 0.93)})
        self.assertEqual(out.fills["course"], {"value": "VKT-REVIT", "source": "jev", "confidence": 0.93})
        self.assertIn({"slot": "course", "kind": "jev", "value": "VKT-REVIT", "confidence": 0.93}, out.matches)
        self.assertEqual(out.confirm, {})

    def test_confirm_band_asks_to_confirm(self):
        out = run({"slot:course": pick("VKT-REVIT", 0.7)})
        self.assertNotIn("course", out.fills)
        self.assertEqual(out.confirm, {"kind": "slot", "slot": "course", "value": "VKT-REVIT", "label": "Revit kiến trúc"})

    def test_low_band_and_none_change_nothing(self):
        self.assertEqual(run({"slot:course": pick("VKT-REVIT", 0.4)}), Understanding())
        self.assertEqual(run({"slot:course": pick(NONE, 0.99)}), Understanding())

    def test_choice_slot_uses_its_own_thresholds(self):
        self.assertEqual(run({"slot:preferred_shift": pick("evening", 0.81)}).fills["preferred_shift"]["value"], "evening")
        self.assertEqual(run({"slot:preferred_shift": pick("evening", 0.6)}).confirm["label"], "Tối")

    def test_keyword_and_confident_jev_disagree_asks_to_confirm(self):
        u = Understanding(fills={"course": fill("VP-EXCEL")})
        out = run({"slot:course": pick("VP-WORD", 0.95)}, u)
        self.assertNotIn("course", out.fills)
        self.assertEqual(out.confirm["value"], "VP-WORD")

    def test_keyword_wins_over_unsure_or_silent_jev(self):
        u = Understanding(fills={"course": fill("VP-EXCEL")})
        self.assertEqual(run({"slot:course": pick("VP-WORD", 0.7)}, u).fills["course"]["value"], "VP-EXCEL")
        self.assertEqual(run({"slot:course": pick(NONE, 0.99)}, u).fills["course"]["value"], "VP-EXCEL")

    def test_jev_picks_among_ambiguous_candidates(self):
        u = Understanding(ambiguous={"course": ["VP-EXCEL", "VP-WORD"]})
        out = run({"slot:course": pick("VP-WORD", 0.9)}, u)
        self.assertEqual((out.fills["course"]["value"], out.ambiguous), ("VP-WORD", {}))

    def test_answer_outside_the_question_is_ignored(self):
        u = Understanding(ambiguous={"course": ["VP-EXCEL", "VP-WORD"]})
        self.assertNotIn("course", run({"slot:course": pick("VKT-REVIT", 0.99)}, u).fills)
        self.assertEqual(run({"slot:course": pick("NOT-A-COURSE", 0.99)}), Understanding())

    def test_button_choice_is_never_overridden(self):
        u = Understanding(fills={"course": fill("VP-EXCEL", "button")}, tapped=True)
        out = combine(u, {"slot:course": pick("VP-WORD", 0.99)}, {"slot:course": {"criteria": {"VP-WORD": ""}}}, NEW, CAT)
        self.assertEqual((out.fills["course"]["value"], out.confirm), ("VP-EXCEL", {}))

    def test_partial_answers_only_touch_answered_questions(self):
        out = run({"slot:branch": pick("CN Dĩ An", 0.9), "slot:course": "garbage", "parent:course": None})
        self.assertEqual(list(out.fills), ["branch"])

    def test_parent_mismatch_drops_child_keeps_parent(self):
        out = run({"slot:course": pick("VP-EXCEL", 0.9), "parent:course": pick("Kế toán", 0.92)})
        self.assertNotIn("course", out.fills)
        self.assertEqual(out.parents["course"], "Kế toán")

    def test_confident_parent_alone_is_kept(self):
        out = run({"parent:branch": pick("Bình Dương", 0.9)})
        self.assertEqual(out.parents, {"branch": "Bình Dương"})
        self.assertEqual(run({"parent:branch": pick("Bình Dương", 0.6)}).parents, {})

    def test_number_slot(self):
        state = ConversationState("1", slots={"learner": fill("child")})
        self.assertEqual(run({"slot:learner_age": pick("9", 0.9)}, state=state).fills["learner_age"]["value"], 9)

    def test_only_one_confirmation_per_turn_in_slot_order(self):
        out = run({"slot:course": pick("VKT-REVIT", 0.7), "slot:branch": pick("CN Dĩ An", 0.7)})
        self.assertEqual(out.confirm["slot"], "course")

    def test_input_is_not_mutated(self):
        u = Understanding()
        run({"slot:course": pick("VKT-REVIT", 0.93)}, u)
        self.assertEqual(u, Understanding())


if __name__ == "__main__":
    unittest.main()
```

`$T/test_engine_confirm.py` (understand → decide → compose for the confirmation turn):

```python
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, fill, render

from mmm_custom.engine.decide import Decision, decide
from mmm_custom.engine.reply import compose
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding, understand

CAT = demo_catalog()
CONFIRM = {"kind": "slot", "slot": "course", "value": "VKT-REVIT", "label": "Revit kiến trúc"}


def pending_state(confirm=CONFIRM):
    options = {"Đúng ạ": {"type": "confirm_yes", **confirm}, "Không phải": {"type": "confirm_no", **confirm}}
    return ConversationState("1", turns=1, pending={"slot": "", "options": options, "confirm": confirm})


class TestUnderstandConfirmation(unittest.TestCase):
    def test_yes_tap_fills_as_confirmed(self):
        u = understand("Đúng ạ", pending_state(), CAT)
        self.assertEqual(u.fills["course"], {"value": "VKT-REVIT", "source": "confirmed", "confidence": 1.0})

    def test_no_tap_rejects_and_focuses_the_slot(self):
        u = understand("Không phải", pending_state(), CAT)
        self.assertEqual((u.focus, u.rejected["value"], u.fills), ("course", "VKT-REVIT", {}))

    def test_typed_yes_or_no_answers_the_confirmation(self):
        self.assertEqual(understand("dung roi", pending_state(), CAT).fills["course"]["value"], "VKT-REVIT")
        u = understand("không", pending_state(), CAT)
        self.assertTrue(u.tapped)
        self.assertEqual(u.rejected["slot"], "course")

    def test_other_text_is_understood_normally(self):
        u = understand("revit", pending_state(), CAT)
        self.assertEqual((u.rejected, u.fills["course"]["value"]), ({}, "VKT-REVIT"))

    def test_skill_confirmation(self):
        c = {"kind": "skill", "skill": "fee_quote", "label": "học phí"}
        self.assertEqual(understand("Đúng ạ", pending_state(c), CAT).skills, ["fee_quote"])


class TestConfirmDecision(unittest.TestCase):
    def test_confirm_instead_of_asking_the_next_slot(self):
        d = decide(ConversationState("1", turns=1), Understanding(confirm=CONFIRM), CAT)
        self.assertEqual((d.type, d.confirm, d.ask, d.stuck_turns), ("confirm", CONFIRM, "", 0))
        self.assertIn("Revit kiến trúc", d.reason)

    def test_first_turn_confirmation_is_greeted(self):
        self.assertTrue(decide(ConversationState("1"), Understanding(confirm=CONFIRM), CAT).greet)

    def test_skills_are_still_answered_with_the_confirmation(self):
        d = decide(ConversationState("1", turns=1), Understanding(confirm=CONFIRM, skills=["hotline"]), CAT)
        self.assertEqual((d.type, d.skills), ("confirm", ["hotline"]))

    def test_handoff_button_beats_a_confirmation(self):
        d = decide(ConversationState("1", turns=1), Understanding(confirm=CONFIRM, handoff=True), CAT)
        self.assertEqual(d.type, "handoff")

    def test_required_filled_waits_for_the_confirmation(self):
        slots = {"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An"), "phone": fill("+84901234567")}
        c = {"kind": "slot", "slot": "preferred_shift", "value": "evening", "label": "Tối"}
        d = decide(ConversationState("1", turns=1, slots=slots), Understanding(confirm=c), CAT)
        self.assertEqual(d.type, "confirm")

    def test_rejected_confirmation_reasks_even_an_asked_optional_slot(self):
        slots = {"course": fill("VP-EXCEL"), "preferred_shift": {"asked": 1}}
        u = Understanding(focus="preferred_shift", rejected={"slot": "preferred_shift"})
        self.assertEqual(decide(ConversationState("1", turns=2, slots=slots), u, CAT).ask, "preferred_shift")


class TestConfirmReply(unittest.TestCase):
    def test_confirm_paragraph_and_two_buttons(self):
        r = compose(Decision("confirm", confirm=CONFIRM), ConversationState("1", turns=1), CAT, render)
        self.assertEqual(r.messages, ["Dạ ý anh/chị là Revit kiến trúc phải không ạ?"])
        self.assertEqual([b["title"] for b in r.buttons], ["Đúng ạ", "Không phải"])
        self.assertEqual(r.buttons[1]["action"], {"type": "confirm_no", **CONFIRM})

    def test_skill_confirmation_wording(self):
        c = {"kind": "skill", "skill": "fee_quote", "label": "học phí"}
        r = compose(Decision("confirm", confirm=c), ConversationState("1", turns=1), CAT, render)
        self.assertEqual(r.messages, ["Dạ anh/chị muốn hỏi về học phí phải không ạ?"])


if __name__ == "__main__":
    unittest.main()
```

Append to `$T/test_engine_pipeline.py` (new class after `TestRunTurn`; add `from engine_fixtures import FakeJev` to the imports):

```python
class TestJevTurn(unittest.TestCase):
    def setUp(self):
        self.repo, self.fx = FakeRepo(CAT), RecordingEffects()

    def turn(self, text, message_id=5):
        return run_turn(parse_event(incoming(text, message_id)), self.repo, self.fx, render)

    def test_without_a_client_jev_is_disabled(self):
        t = self.turn("alo")
        self.assertEqual((t.jev.status, self.repo.logs[0]["jev_status"]), ("disabled", "disabled"))

    def test_jev_answer_fills_a_slot_and_is_logged(self):
        self.repo.jev = FakeJev({"slot:course": {"choice": "VKT-REVIT", "confidence": 0.93}})
        t = self.turn("mình muốn học vẽ nhà")
        self.assertEqual(self.repo.states["7"].slots["course"]["source"], "jev")
        self.assertEqual(t.decision.ask, "branch")
        log = self.repo.logs[0]
        self.assertEqual((log["jev_status"], log["input_tokens"], log["model_version"]), ("ok", 120, "jev-test"))
        self.assertIn("slot:course", log["jev_questions"])

    def test_jev_unavailable_falls_back_to_keywords(self):
        self.repo.jev = FakeJev(status="unavailable")
        t = self.turn("excel bạn ơi")  # a leftover word keeps the Task 5 cost guard from skipping Jev
        self.assertEqual((t.jev.status, self.repo.states["7"].slots["course"]["value"]), ("unavailable", "VP-EXCEL"))
        self.assertEqual(self.repo.logs[0]["jev_status"], "unavailable")

    def test_confirm_no_asks_with_buttons_and_records_signal(self):
        self.repo.jev = FakeJev({"slot:course": {"choice": "VKT-REVIT", "confidence": 0.7}})
        t1 = self.turn("mình muốn học vẽ nhà")
        self.assertEqual(t1.decision.type, "confirm")
        self.assertEqual([b["title"] for b in t1.reply.buttons], ["Đúng ạ", "Không phải"])
        self.assertEqual(self.repo.states["7"].pending["confirm"]["value"], "VKT-REVIT")
        t2 = self.turn("Không phải", message_id=6)
        self.assertEqual((t2.decision.type, t2.decision.ask), ("ask_slot", "course"))
        self.assertTrue(t2.reply.buttons)
        self.assertNotIn("value", self.repo.states["7"].slots.get("course", {}))
        self.assertEqual(len(self.repo.jev.calls), 1)  # the tap needed no Jev call
        self.assertEqual([s["signal_type"] for s in self.repo.signals], ["confirm_rejected"])

    def test_confirm_yes_fills(self):
        self.repo.jev = FakeJev({"slot:course": {"choice": "VKT-REVIT", "confidence": 0.7}})
        self.turn("mình muốn học vẽ nhà")
        self.turn("Đúng ạ", message_id=6)
        self.assertEqual(self.repo.states["7"].slots["course"]["value"], "VKT-REVIT")

    def test_history_is_kept_and_capped(self):
        self.turn("alo")
        self.assertEqual([h["from"] for h in self.repo.states["7"].history], ["customer", "bot"])
        for i in range(1, 30):  # after the stuck handoff the bot is silent: customer lines only
            self.turn(f"alo {i}", message_id=5 + i)
        history = self.repo.states["7"].history
        self.assertEqual(len(history), 20)
        self.assertEqual(history[-1], {"from": "customer", "text": "alo 29"})
```

Append to `$T/test_engine_playground.py`, inside `TestInspect` (add `FakeJev` to the `engine_fixtures` import):

```python
    def test_inspect_shows_the_jev_result(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        repo.jev = FakeJev({"slot:course": {"choice": "VKT-REVIT", "confidence": 0.7}})
        out = inspect(run_turn(Event("customer_message", "7", 5, "học vẽ nhà", {"id": 9}), repo, fx, render), fx)
        self.assertEqual((out["jev"]["status"], out["jev"]["input_tokens"]), ("ok", 120))
        self.assertEqual(out["understanding"]["confirm"]["value"], "VKT-REVIT")
```

(`CAT` is the module-level `demo_catalog()` the file already defines; add it if missing.)

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | grep -E "^(ERROR|FAIL):|^Ran|FAILED" | head -40`
Expected: ERROR `No module named 'mmm_custom.engine.combine'`; ERROR in `test_engine_confirm`; FAIL/ERROR in the new pipeline/playground tests (`unexpected keyword argument 'confirm'`, `'Turn' object has no attribute 'jev'`, …). All C2 tests still pass.

- [ ] **Step 3: Understanding, confirmation actions, yes/no text**

In `$APP/engine/understand.py`:
- add to `Understanding` after `unmatched`:

```python
    confirm: dict = field(default_factory=dict)    # one value to confirm with [Đúng ạ] [Không phải] (D-030)
    rejected: dict = field(default_factory=dict)   # the confirmation the customer just rejected (D-057)
    intent: dict = field(default_factory=dict)     # {"value", "confidence"} from Jev (D-032)
    hotness: dict = field(default_factory=dict)    # {"value", "score", "confidence"} from Jev
    wants_human: float = 0.0                       # Jev noul: asks for a person
    spam: float = 0.0                              # Jev confidence that the message is spam
```

- add below the imports:

```python
# Typed answers to a pending confirmation, diacritic-folded (D-030).
YES = frozenset({"dung", "dung roi", "dung a", "dung roi a", "phai", "phai a", "vang", "da", "da dung", "da phai",
                 "ok", "oke", "uh", "u", "chuan", "chinh xac"})
NO = frozenset({"khong", "khong phai", "khong a", "khong phai a", "ko", "k", "sai", "sai roi", "khong dung"})
```

- in `apply_action`, add before the final `elif kind == "handoff":` branch:

```python
    elif kind == "confirm_yes":
        if action.get("slot"):
            u.fills[action["slot"]] = {"value": action["value"], "source": "confirmed", "confidence": 1.0}
        elif action.get("skill"):
            u.skills.append(action["skill"])
    elif kind == "confirm_no":
        u.rejected = {k: v for k, v in action.items() if k != "type"}
        if action.get("slot"):
            u.focus = action["slot"]  # "Không phải" → buttons for that slot
```

- in `understand()`, right after the `if action: … return u` block:

```python
    confirm = state.pending.get("confirm")
    if confirm and fold(text) in YES | NO:  # a typed answer to the confirmation is as exact as a tap
        u.tapped = True
        apply_action(u, {"type": "confirm_yes" if fold(text) in YES else "confirm_no", **confirm})
        return u
```

- [ ] **Step 4: `combine.py`**

`$APP/engine/combine.py`:

```python
"""Keyword tier + Jev answers → one Understanding (D-029, D-030, D-063). Pure, no I/O.

Rules: a button tap is final; a unique keyword match wins unless Jev confidently picks another value
(→ confirm, never a silent swap); Jev picks among ambiguous candidates; a child outside a confident
parent is dropped; per slot type, act ≥ act threshold, confirm ≥ confirm threshold, else nothing.
At most one confirmation per turn, in slot order."""

import copy

from mmm_custom.engine.context import display
from mmm_custom.engine.jev_questions import NONE


def slot_limits(slot, settings):
    if slot.type == "catalog":
        return float(settings["catalog_act"]), float(settings["catalog_confirm"])
    return float(settings["choice_act"]), float(settings["choice_confirm"])


def ask_confirm(u, confirm):
    if not u.confirm:
        u.confirm = confirm


def _choice(answers, questions, key):
    """(choice, confidence) when Jev answered `key` with one of the question's own options, else (None, 0)."""
    answer = answers.get(key)
    if not isinstance(answer, dict) or key not in questions:
        return None, 0.0
    choice = answer.get("choice")
    if choice in (None, "", NONE) or str(choice) not in (questions[key].get("criteria") or {}):
        return None, 0.0
    try:
        return str(choice), float(answer.get("confidence") or 0)
    except (TypeError, ValueError):
        return None, 0.0


def _slots(u, answers, questions, catalog):
    for slot in catalog.slots:
        choice, p = _choice(answers, questions, f"slot:{slot.key}")
        if choice is None:
            continue
        value = int(choice) if slot.type == "number" else choice
        act, confirm = slot_limits(slot, catalog.settings)
        candidate = {"kind": "slot", "slot": slot.key, "value": value, "label": display(slot, value, catalog)}
        keyword = u.fills.get(slot.key)
        if keyword:
            if keyword["value"] != value and p >= act:  # D-029: confident disagreement → confirm
                del u.fills[slot.key]
                ask_confirm(u, candidate)
            continue
        if p >= act:
            u.fills[slot.key] = {"value": value, "source": "jev", "confidence": round(p, 3)}
            u.ambiguous.pop(slot.key, None)
            u.matches.append({"slot": slot.key, "kind": "jev", "value": value, "confidence": round(p, 3)})
        elif p >= confirm:
            ask_confirm(u, candidate)


def _parents(u, answers, questions, catalog):
    for slot in catalog.slots:
        parent, p = _choice(answers, questions, f"parent:{slot.key}")
        if parent is None or p < float(catalog.settings["catalog_act"]):
            continue
        fill = u.fills.get(slot.key)
        if fill and catalog.parent_of(slot, fill["value"]) != parent:
            del u.fills[slot.key]  # D-029: drop the child, keep the confident parent
        if u.confirm.get("slot") == slot.key and catalog.parent_of(slot, u.confirm["value"]) != parent:
            u.confirm = {}
        if slot.key not in u.fills:
            u.parents.setdefault(slot.key, parent)


def combine(u, answers, questions, state, catalog):
    if u.tapped:
        return u  # buttons (and typed answers to a confirmation) are never overridden
    out = copy.deepcopy(u)
    answers = answers if isinstance(answers, dict) else {}
    _slots(out, answers, questions, catalog)
    _parents(out, answers, questions, catalog)
    return out
```

- [ ] **Step 5: `decide` — confirm decision, re-asking slots in `first`**

In `$APP/engine/decide.py`:
- `Decision`: change the `type` comment to `# answer | confirm | ask_slot | handoff | silent` and add after `reason: str = ""`:

```python
    confirm: dict = field(default_factory=dict)  # the value asked with [Đúng ạ] [Không phải]
```

- below `HANDOFF_REASONS` add:

```python
IMMEDIATE = ("button", "skill")  # handoff reasons that do not wait for a pending confirmation
```

- in `next_slot`, change `if not slot.required and (entry.get("asked") or entry.get("skipped")):` to

```python
        if slot.key not in first and not slot.required and (entry.get("asked") or entry.get("skipped")):
```

- in `decide`, change the `progress = …` line to

```python
    progress = bool(new or changed or skills or waiting or u.handoff or u.focus or u.confirm or u.rejected)
```

- replace

```python
    why = handoff_reason(u, skills, slots, stuck, catalog)
    if why:
        return Decision("handoff", **common, handoff_reason=why, reason=HANDOFF_REASONS[why])
```

with

```python
    why = handoff_reason(u, skills, slots, stuck, catalog)
    if why and (why in IMMEDIATE or not u.confirm):
        return Decision("handoff", **common, handoff_reason=why, reason=HANDOFF_REASONS[why])
    if u.confirm:
        reason = f"Xác nhận: {u.confirm['label']}" + (f"; trả lời: {answered}" if skills else "")
        return Decision("confirm", **common, confirm=u.confirm, greet=greet, reason=reason)
```

- [ ] **Step 6: `compose` — confirmation paragraph and buttons**

In `$APP/engine/reply.py`:
- below `MAX_FOLLOW_UPS` add:

```python
CONFIRM_YES, CONFIRM_NO = "Đúng ạ", "Không phải"  # D-030 confirmation buttons
```

- in `compose`, right before `ask_buttons = []` insert:

```python
    confirm_buttons = []
    if decision.type == "confirm":
        c = decision.confirm
        template = settings["confirm_slot_template"] if c.get("kind") == "slot" else settings["confirm_skill_template"]
        say(template, {**ctx, "confirm": c}, "confirm")
        confirm_buttons = [{"title": CONFIRM_YES, "action": {"type": "confirm_yes", **c}},
                           {"title": CONFIRM_NO, "action": {"type": "confirm_no", **c}}]
```

- change the button loop to `for group in (confirm_buttons, action_buttons, ask_buttons, follow_ups[:MAX_FOLLOW_UPS]):`.

- [ ] **Step 7: Pipeline — Jev call, pending confirmation, history, log; learning signal**

In `$APP/engine/pipeline.py`:
- imports: add

```python
from mmm_custom.engine.combine import combine
from mmm_custom.engine.jev import JevResult
from mmm_custom.engine.jev_questions import MAX_HISTORY, build_questions, jev_state
```

- `Turn`: add `jev: object = None` after `reason: str = ""`.
- add above `apply_decision`:

```python
def understand_turn(text, state, catalog, jev):
    """Keyword tier always; one Jev call when a client is given; Jev failure → keyword result (D-031)."""
    u = understand(text, state, catalog)
    if jev is None:
        return u, JevResult("disabled")
    if u.tapped:
        return u, JevResult("skipped_cost_guard", error="button")
    questions = build_questions(state, u, catalog)
    result = jev.ask(jev_state(text, state, catalog), questions)
    if result.status != "ok":
        return u, result
    return combine(u, result.answers, questions, state, catalog), result
```

- in `apply_decision`, replace

```python
    if decision.type != "silent":
        state.pending = {"slot": decision.ask, "options": reply.options()}
```

with

```python
    if decision.type != "silent":
        state.pending = {"slot": decision.ask, "options": reply.options()}
        if decision.confirm:
            state.pending["confirm"] = decision.confirm
    lines = [{"from": "customer", "text": event.text[:300]}]
    if reply.messages:
        lines.append({"from": "bot", "text": " ".join(reply.messages)[:300]})
    state.history = (state.history + lines)[-MAX_HISTORY:]  # D-074
```

- in `run_turn`, replace `turn.understanding = understand(event.text, state, catalog)` with

```python
    turn.understanding, turn.jev = understand_turn(event.text, state, catalog, repo.jev_client())
```

  and replace `repo.write_log(log_row(turn))` with `repo.write_log(log_row(turn, turn.jev.log()))`.

In `$APP/engine/log.py`, in `signals()`, add before the `render_error` line:

```python
    if u.rejected:
        out.append({**base, "signal_type": "confirm_rejected", "term": u.rejected.get("label", ""),
                    "details": _j(u.rejected)})
```

- [ ] **Step 8: Repo — Jev client and history persistence; DocType fields**

In `$APP/engine/repo.py`:
- `FrappeRepo.__init__`:

```python
    def __init__(self, sandbox=False, sandbox_lead=None, force_jev=None):
        self.sandbox, self.sandbox_lead, self.force_jev = sandbox, sandbox_lead, force_jev
        self._catalog = None
```

- add after `today()`:

```python
    def jev_client(self):
        """Jev for this turn (D-073): live only when Lead Engine Settings.jev_live, or forced by the Playground."""
        from mmm_custom.engine.jev import jev_client

        return jev_client(frappe.conf, self.catalog().settings, self.force_jev)
```

- `load_state`: add the argument `history=json.loads(d.history) if d.history else [],` after `answered=…` (inside the `ConversationState(...)` call; `d.history` may already be a list when Frappe parses JSON — use `d.history if isinstance(d.history, list) else (json.loads(d.history) if d.history else [])`).
- `save_state`: add `"history": json.dumps(state.history, ensure_ascii=False),` to `values`.

DocType fields — run with the Appendix A helper (`cd $SCRATCH && python3 -c "from dt import *; ..."`, or a small script that does `from dt import add_fields, field`):

```python
add_fields("Bot Conversation", [field("history", "JSON", "Recent turns (Jev state)", read_only=1)])
add_fields("Lead Engine Settings", [
    field("jev_section", "Section Break", "Jev understanding"),
    field("jev_live", "Check", "Jev answers real customers",
          description="Turn on only after the evaluation gate passes (bench execute mmm_custom.engine.evaluate.run)."),
    field("jev_timeout", "Int", "Jev timeout (seconds)", description="Default 8"),
    field("catalog_act", "Float", "Catalog slot: act at", description="Default 0.85"),
    field("catalog_confirm", "Float", "Catalog slot: confirm at", description="Default 0.55"),
    field("choice_act", "Float", "Choice slot: act at", description="Default 0.80"),
    field("choice_confirm", "Float", "Choice slot: confirm at", description="Default 0.50"),
    field("skill_act", "Float", "Skill: answer at", description="Default 0.85"),
    field("skill_confirm", "Float", "Skill: confirm at", description="Default 0.60"),
    field("handoff_noul", "Float", "Early handoff (wants human / hot) at", description="Default 0.70"),
    field("spam_threshold", "Float", "Spam: stop at", description="Default 0.80"),
    field("confirm_slot_template", "Small Text", "Confirm slot template"),
    field("confirm_skill_template", "Small Text", "Confirm skill template"),
])
```

- [ ] **Step 9: Playground — Jev toggle and Jev section**

In `$APP/engine/playground.py`:
- in `inspect`, replace `"jev": {"status": "disabled"},` with `"jev": turn.jev.log() if turn.jev else {"status": "disabled"},` and extend `"understanding"` with `"confirm": u.confirm, "rejected": u.rejected, "intent": u.intent, "hotness": u.hotness, "wants_human": u.wants_human, "spam": u.spam,`.
- `simulate(session, text, lead=None, jev=0)`: construct `FrappeRepo(sandbox=True, sandbox_lead=lead or None, force_jev=bool(int(jev or 0)))`.
- `ReplayRepo.__init__(self, state, force_jev=False)`: `super().__init__(sandbox=True, force_jev=force_jev)`; `replay(log_name, jev=0)` passes `ReplayRepo(state, bool(int(jev or 0)))`.

In `$APP/mmm_custom/page/bot_playground/bot_playground.js`:
- after the `this.lead = page.add_field({...});` statement add:

```js
		this.jev = page.add_field({
			fieldname: "jev", label: __("Use Jev"), fieldtype: "Check",
			description: __("Ask TypeSafe Jev in this sandbox even when it is not live for customers"),
		});
```

- in `send`, change the args to `args: { session: this.session, text, lead: this.lead.get_value() || null, jev: this.jev.get_value() ? 1 : 0 },`
- in `ask_replay`, change the args to `args: { log_name: values.log, jev: this.jev.get_value() ? 1 : 0 }`.

- [ ] **Step 10: Run the tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 11: Migrate and check live (Jev forced on in the sandbox)**

```bash
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost migrate >/dev/null && bench --site crm.localhost clear-cache"
docker exec -i crm-frappe-1 bash -c "cd frappe-bench/sites && ../env/bin/python" <<'EOF'
import frappe
frappe.init(site="crm.localhost"); frappe.connect(); frappe.set_user("Administrator")
from mmm_custom.engine import playground
playground.reset("c3t2")
out = playground.simulate("c3t2", "mình muốn học vẽ nhà ở bình dương", jev=1)
print(out["jev"]["status"], out["jev"]["latency_ms"], out["jev"]["input_tokens"])
print(out["understanding"]["fills"], out["understanding"]["parents"], out["understanding"]["confirm"])
print(out["decision"]["type"], out["decision"]["reason"], out["reply"]["buttons"])
playground.reset("c3t2")
EOF
```
Expected: `ok` with latency < 8000 and tokens > 0; the course is filled from Jev or confirmed (Revit/SketchUp/AutoCAD family) and `parents` holds `Bình Dương`; decision `answer`/`ask_slot`/`confirm` with a Vietnamese reason. The exact course may differ — record what Jev returned in the ledger; do not change code to force a value.

- [ ] **Step 12: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/engine/combine.py frappe-custom/mmm_custom/mmm_custom/engine/understand.py \
  frappe-custom/mmm_custom/mmm_custom/engine/decide.py frappe-custom/mmm_custom/mmm_custom/engine/reply.py \
  frappe-custom/mmm_custom/mmm_custom/engine/pipeline.py frappe-custom/mmm_custom/mmm_custom/engine/log.py \
  frappe-custom/mmm_custom/mmm_custom/engine/repo.py frappe-custom/mmm_custom/mmm_custom/engine/playground.py \
  frappe-custom/mmm_custom/mmm_custom/mmm_custom/page/bot_playground/bot_playground.js \
  frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/bot_conversation/bot_conversation.json \
  frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/lead_engine_settings/lead_engine_settings.json \
  frappe-custom/mmm_custom/mmm_custom/tests/
git commit -m "feat(ai): combine keyword and Jev slot understanding with confidence bands and a confirmation turn"
```

---

### Task 3: C3.3 — Multi-topic messages: one `noul` per skill

Implements **C3.3** (D-039 fan-out, D-063 alias lift). With Jev the skill's `noul` sets the band and an alias match lifts it to at least confirm; without Jev (Task 2's `disabled`/`unavailable` paths) the C2 keyword behaviour is unchanged.

**Files:**
- Modify: `$APP/engine/combine.py` (`_noul`, `_skills`)
- Modify tests: `$T/test_engine_combine.py` (new class), `$T/test_engine_pipeline.py` (`TestJevTurn`)

**Interfaces:**
- Consumes (Tasks 1–2): `skill:<key>` noul questions; `ask_confirm`; settings `skill_act` 0.85 / `skill_confirm` 0.60; `Understanding.confirm` with `{"kind": "skill", "skill", "label"}` (compose and `apply_action` already handle it).
- Produces: `combine._noul(answers, questions, key) -> float | None`; `combine` now also rewrites `u.skills`; Jev-added skills are recorded in `u.matches` as `{"skill": key, "kind": "jev", "confidence": n}`.

- [ ] **Step 1: Write the failing tests**

Append to `$T/test_engine_combine.py`:

```python
def yes(n):
    return {"noul": n}


class TestSkills(unittest.TestCase):
    def test_every_confident_skill_is_answered(self):
        out = run({"skill:hotline": yes(0.93), "skill:opening_hours": yes(0.9), "skill:payment": yes(0.2)})
        self.assertEqual(sorted(out.skills), ["hotline", "opening_hours"])
        self.assertIn({"skill": "hotline", "kind": "jev", "confidence": 0.93}, out.matches)

    def test_confirm_band_asks_about_the_skill(self):
        out = run({"skill:fee_quote": yes(0.7)})
        self.assertEqual((out.skills, out.confirm), ([], {"kind": "skill", "skill": "fee_quote", "label": "học phí"}))

    def test_alias_match_is_kept_when_jev_agrees_or_is_silent(self):
        self.assertEqual(run({"skill:hotline": yes(0.9)}, Understanding(skills=["hotline"])).skills, ["hotline"])
        self.assertEqual(run({}, Understanding(skills=["hotline"])).skills, ["hotline"])

    def test_alias_match_with_a_low_score_is_lifted_to_confirm(self):
        out = run({"skill:hotline": yes(0.1)}, Understanding(skills=["hotline"]))
        self.assertEqual((out.skills, out.confirm["skill"]), ([], "hotline"))

    def test_a_slot_confirmation_wins_over_a_skill_confirmation(self):
        out = run({"slot:course": pick("VKT-REVIT", 0.7), "skill:fee_quote": yes(0.7)})
        self.assertEqual(out.confirm["kind"], "slot")

    def test_malformed_noul_is_ignored(self):
        self.assertEqual(run({"skill:hotline": {"noul": "yes"}, "skill:payment": {"choice": "x"}}).skills, [])
```

(`fee_quote`'s title in the demo data is "học phí"; if the assertion fails on the label, read the title from `CAT.skills["fee_quote"].title` in the test instead of changing the data.)

Append to `TestJevTurn` in `$T/test_engine_pipeline.py`:

```python
    def test_two_topics_in_one_message_are_both_answered(self):
        self.repo.jev = FakeJev({"skill:opening_hours": {"noul": 0.92}, "skill:hotline": {"noul": 0.9}})
        t = self.turn("trung tâm nghỉ lúc nào, liên lạc bằng cách nào")
        self.assertEqual(sorted(t.decision.skills), ["hotline", "opening_hours"])
        self.assertEqual(t.decision.type, "answer")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | grep -E "^(ERROR|FAIL):|^Ran|FAILED" | head -20`
Expected: the new `TestSkills` tests and `test_two_topics_in_one_message_are_both_answered` FAIL (skills are ignored); everything else passes.

- [ ] **Step 3: Implement**

In `$APP/engine/combine.py` add after `_choice`:

```python
def _noul(answers, questions, key):
    answer = answers.get(key)
    if key not in questions or not isinstance(answer, dict) or "noul" not in answer:
        return None
    try:
        return float(answer["noul"])
    except (TypeError, ValueError):
        return None


def _skills(u, answers, questions, catalog):
    """D-039 fan-out; D-063: with Jev the noul sets the band, an alias match lifts it to at least confirm."""
    act, confirm = float(catalog.settings["skill_act"]), float(catalog.settings["skill_confirm"])

    def candidate(key):
        return {"kind": "skill", "skill": key, "label": catalog.skills[key].title}

    kept = []
    for key in u.skills:  # keyword (alias) hits
        n = _noul(answers, questions, f"skill:{key}")
        if n is None or n >= act:
            kept.append(key)
        else:
            ask_confirm(u, candidate(key))
    for key in catalog.skills:
        if key in u.skills:
            continue
        n = _noul(answers, questions, f"skill:{key}")
        if n is None:
            continue
        if n >= act:
            kept.append(key)
            u.matches.append({"skill": key, "kind": "jev", "confidence": round(n, 3)})
        elif n >= confirm:
            ask_confirm(u, candidate(key))
    u.skills = kept
```

and in `combine()` call `_skills(out, answers, questions, catalog)` after `_parents(...)` (slots first, so a slot confirmation wins).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/engine/combine.py frappe-custom/mmm_custom/mmm_custom/tests/test_engine_combine.py \
  frappe-custom/mmm_custom/mmm_custom/tests/test_engine_pipeline.py
git commit -m "feat(ai): answer every confidently detected skill in a multi-topic message"
```

---

### Task 4: C3.4 — Intent, hotness, wants-human → early handoff; no double spend with `intelligence.py`

Implements **C3.4** (D-032, D-058 triggers "wants-human noul" and "hot", D-077).

**Files:**
- Modify: `$APP/engine/combine.py` (`_signals`), `$APP/engine/decide.py` (reasons `wants_human`, `hot`; `Decision.ai`), `$APP/engine/handoff.py` (label `hot`, `ai` in the summary context), `$APP/engine/pipeline.py` (`ai_fields`, Lead write), `$APP/engine/state.py` (`ai`), `$APP/engine/repo.py` (persist `ai`), `$APP/intelligence.py` (skip conversations the bot handles), DocType `bot_conversation` (+`ai_signals`), `$APP/demo/saoviet/settings.json` (summary line)
- Create tests: `$T/test_engine_signals.py`; modify `$T/test_intelligence.py`

**Interfaces:**
- Consumes: `intent` (choice over `intelligence.INTENTS`), `hotness` (score 0–2 over `HOTNESS_CRITERIA`), `wants_human` (noul) answers; `Understanding.intent/hotness/wants_human`; setting `handoff_noul` 0.70.
- Produces:
  - `combine._signals(u, answers, questions, catalog)`.
  - `decide.HANDOFF_REASONS["wants_human"]`, `["hot"]`; `decide.IMMEDIATE = ("button", "wants_human", "skill")`; `Decision.ai: dict` (`{"intent": {...}, "hotness": {...}}`, only the keys Jev answered).
  - `pipeline.ai_fields(u, settings) -> dict` (`ai_intent` / `ai_hotness` at confidence ≥ `handoff_noul`).
  - `ConversationState.ai: dict` (what was last written to the Lead), persisted as `Bot Conversation.ai_signals`.
  - `intelligence.bot_active(conversation_id) -> bool`.

- [ ] **Step 1: Write the failing tests**

`$T/test_engine_signals.py`:

```python
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeJev, FakeRepo, demo_catalog, demo_consultants, fill, render

from mmm_custom.engine.combine import combine
from mmm_custom.engine.decide import Decision, decide
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.handoff import plan_handoff
from mmm_custom.engine.jev_questions import build_questions
from mmm_custom.engine.pipeline import ai_fields, parse_event, run_turn
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding

CAT = demo_catalog()
NEW = ConversationState("1")
CONFIRM = {"kind": "slot", "slot": "course", "value": "VKT-REVIT", "label": "Revit kiến trúc"}


def run(answers):
    u = Understanding()
    return combine(u, answers, build_questions(NEW, u, CAT), NEW, CAT)


class TestCombineSignals(unittest.TestCase):
    def test_intent_hotness_and_wants_human(self):
        out = run({"intent": {"choice": "purchase", "confidence": 0.9}, "hotness": {"score": 1.8, "confidence": 0.8},
                   "wants_human": {"noul": 0.75}})
        self.assertEqual(out.intent, {"value": "purchase", "confidence": 0.9})
        self.assertEqual(out.hotness, {"value": "hot", "score": 1.8, "confidence": 0.8})
        self.assertEqual(out.wants_human, 0.75)

    def test_out_of_range_or_malformed_answers_are_ignored(self):
        out = run({"intent": {"choice": "buy_now", "confidence": 0.9}, "hotness": {"score": "x"}, "wants_human": {}})
        self.assertEqual((out.intent, out.hotness, out.wants_human), ({}, {}, 0.0))
        self.assertEqual(run({"hotness": {"score": 7, "confidence": 1}}).hotness["value"], "hot")


class TestEarlyHandoff(unittest.TestCase):
    def test_wants_human_hands_off_even_with_a_pending_confirmation(self):
        d = decide(ConversationState("1", turns=1), Understanding(wants_human=0.8, confirm=CONFIRM), CAT)
        self.assertEqual((d.type, d.handoff_reason), ("handoff", "wants_human"))

    def test_hot_customer_hands_off(self):
        u = Understanding(hotness={"value": "hot", "score": 1.9, "confidence": 0.8})
        d = decide(ConversationState("1", turns=1, slots={"course": fill("VP-EXCEL")}), u, CAT)
        self.assertEqual((d.type, d.handoff_reason), ("handoff", "hot"))
        self.assertEqual(d.ai["hotness"]["value"], "hot")

    def test_below_threshold_does_not_hand_off(self):
        u = Understanding(wants_human=0.6, hotness={"value": "hot", "score": 1.6, "confidence": 0.5})
        self.assertEqual(decide(ConversationState("1", turns=1), u, CAT).type, "ask_slot")

    def test_hot_waits_for_a_pending_confirmation(self):
        u = Understanding(hotness={"value": "hot", "score": 1.9, "confidence": 0.9}, confirm=CONFIRM)
        self.assertEqual(decide(ConversationState("1", turns=1), u, CAT).type, "confirm")


class TestHandoffPlanSignals(unittest.TestCase):
    def test_hot_label_and_summary_line(self):
        repo = FakeRepo(CAT)
        repo.consultant_rows = demo_consultants()
        ai = {"hotness": {"value": "hot", "score": 1.9, "confidence": 0.82}, "intent": {"value": "purchase", "confidence": 0.9}}
        d = Decision("handoff", slots={"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An")}, handoff_reason="hot",
                     reason="Khách hot, sẵn sàng đăng ký", ai=ai)
        plan = plan_handoff(ConversationState("1"), d, CAT, repo, render)
        self.assertIn("hot", plan.labels)
        self.assertIn("🔥 hot (0.82) · ý định: purchase", plan.summary)

    def test_no_signal_no_line(self):
        repo = FakeRepo(CAT)
        repo.consultant_rows = demo_consultants()
        d = Decision("handoff", slots={"course": fill("VP-EXCEL")}, handoff_reason="button", reason="x")
        plan = plan_handoff(ConversationState("1"), d, CAT, repo, render)
        self.assertNotIn("hot", plan.labels)
        self.assertNotIn("🔥", plan.summary)


class TestLeadSignals(unittest.TestCase):
    def test_ai_fields_need_confidence(self):
        u = Understanding(intent={"value": "price_inquiry", "confidence": 0.9},
                          hotness={"value": "warm", "score": 1.0, "confidence": 0.5})
        self.assertEqual(ai_fields(u, CAT.settings), {"ai_intent": "price_inquiry"})

    def test_bot_writes_intent_and_hotness_to_the_lead_once(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        repo.prefill = {}
        repo.jev = FakeJev({"intent": {"choice": "price_inquiry", "confidence": 0.9},
                            "hotness": {"score": 1.0, "confidence": 0.8}})
        state = ConversationState("7", contact_id="9", lead="CRM-LEAD-1", turns=1)
        repo.states["7"] = state
        run_turn(parse_event(incoming("cho hỏi chút")), repo, fx, render)
        run_turn(parse_event(incoming("cho hỏi thêm", 6)), repo, fx, render)
        writes = fx.of("save_lead")
        self.assertEqual(len(writes), 1)
        self.assertEqual((writes[0]["fields"]["ai_intent"], writes[0]["fields"]["ai_hotness"]), ("price_inquiry", "warm"))
        self.assertEqual(repo.states["7"].ai, {"ai_intent": "price_inquiry", "ai_hotness": "warm"})


def incoming(text, message_id=5):
    return {"event": "message_created", "id": message_id, "content": text, "message_type": "incoming",
            "private": False, "sender": {"id": 9, "name": "Lan", "type": "contact"},
            "conversation": {"id": 7, "inbox_id": 3, "meta": {"sender": {"id": 9, "name": "Lan", "custom_attributes": {}}}}}


if __name__ == "__main__":
    unittest.main()
```

In `$T/test_intelligence.py`, `TestEnqueue.setUp`: add `self.frappe.db.exists.return_value = None` (a MagicMock is truthy and would make every existing test look like a bot conversation), and add:

```python
    def test_skips_conversations_the_bot_is_handling(self):
        self.frappe.db.exists.return_value = "7"
        with patch.object(intel, "frappe", self.frappe):
            result = intel.enqueue_analysis({"message_type": "incoming", "conversation": {"id": 7}})
        self.assertEqual(result, {"status": "ignored", "reason": "bot_active"})
        self.frappe.enqueue.assert_not_called()
        self.frappe.db.exists.assert_called_with("Bot Conversation",
                                                 {"conversation_id": "7", "status": "active", "is_sandbox": 0})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | grep -E "^(ERROR|FAIL):|^Ran|FAILED" | head -20`
Expected: ERROR `cannot import name 'ai_fields'`; FAIL `test_skips_conversations_the_bot_is_handling`.

- [ ] **Step 3: Combine and decide**

In `$APP/engine/combine.py`:
- add the import `from mmm_custom.intelligence import HOTNESS` and

```python
def _signals(u, answers, questions, catalog):
    """D-032: the bot's own call supplies intent, hotness and wants-human while it handles the chat."""
    intent, p = _choice(answers, questions, "intent")
    if intent:
        u.intent = {"value": intent, "confidence": round(p, 3)}
    hot = answers.get("hotness")
    if "hotness" in questions and isinstance(hot, dict):
        try:
            score = float(hot.get("score"))
            u.hotness = {"value": HOTNESS[min(max(round(score), 0), len(HOTNESS) - 1)], "score": round(score, 3),
                         "confidence": round(float(hot.get("confidence") or 0), 3)}
        except (TypeError, ValueError):
            pass
    n = _noul(answers, questions, "wants_human")
    if n is not None:
        u.wants_human = round(n, 3)
```

- call `_signals(out, answers, questions, catalog)` last in `combine()`.

`_choice` rejects `NONE` and values outside the question's criteria, so an intent outside `INTENTS` is ignored.

In `$APP/engine/decide.py`:
- `HANDOFF_REASONS` gets `"wants_human": "Khách muốn gặp tư vấn viên",` and `"hot": "Khách hot, sẵn sàng đăng ký",`; `IMMEDIATE = ("button", "wants_human", "skill")`.
- `Decision` gets `ai: dict = field(default_factory=dict)  # Jev intent/hotness of this turn (D-032)`.
- `handoff_reason`:

```python
def handoff_reason(u, skills, slots, stuck, catalog):
    floor = float(catalog.settings["handoff_noul"])
    if u.handoff:
        return "button"
    if u.wants_human >= floor:
        return "wants_human"
    if any(catalog.skills[k].action == "handoff" or catalog.skills[k].handoff_after for k in skills):
        return "skill"
    if u.hotness.get("value") == "hot" and u.hotness.get("confidence", 0) >= floor:
        return "hot"
    if required_filled(slots, catalog):
        return "required_filled"
    if stuck >= int(catalog.settings["max_stuck_turns"]):
        return "stuck"
    return ""
```

- in `decide`, extend `common` with `ai={k: v for k, v in (("intent", u.intent), ("hotness", u.hotness)) if v}`.
- leave `progress` unchanged: a turn that only carries signals is not progress.

- [ ] **Step 4: Handoff label and summary line**

In `$APP/engine/handoff.py` `plan_handoff`:
- after `plan.labels = [...]` add

```python
    if decision.ai.get("hotness", {}).get("value") == "hot":
        plan.labels.append("hot")
```

- add `"ai": decision.ai,` to `summary_ctx` (always present: the template reads `ai.hotness`).

In `$APP/demo/saoviet/settings.json`, in `summary_template`, insert after the `🎓 …` line (keep the `\n` separators of the JSON string):

```
{% if ai.hotness %}🔥 {{ ai.hotness.value }} ({{ ai.hotness.confidence }}){% if ai.intent %} · ý định: {{ ai.intent.value }}{% endif %}\n{% endif %}
```

(i.e. the JSON string gains `{% if ai.hotness %}🔥 {{ ai.hotness.value }} ({{ ai.hotness.confidence }}){% if ai.intent %} · ý định: {{ ai.intent.value }}{% endif %}\n{% endif %}` between the `🎓` line's trailing `\n` and `💬`).

- [ ] **Step 5: Lead fields and state**

In `$APP/engine/state.py` add after `jev_calls`:

```python
    ai: dict = field(default_factory=dict)  # ai_intent / ai_hotness last written to the Lead (D-077)
```

In `$APP/engine/pipeline.py` add above `write_lead`:

```python
def ai_fields(u, settings):
    """D-077: the bot's intent/hotness go to the Lead only when Jev is confident."""
    floor, out = float(settings["handoff_noul"]), {}
    if u.intent.get("confidence", 0) >= floor:
        out["ai_intent"] = u.intent["value"]
    if u.hotness.get("confidence", 0) >= floor:
        out["ai_hotness"] = u.hotness["value"]
    return out
```

and change `write_lead` to:

```python
def write_lead(turn, effects, catalog):
    """C2.4: write what the conversation learned to the CRM Lead (D-014, D-022), plus Jev's intent/hotness."""
    state, decision = turn.state, turn.decision
    lead_slots = [k for k in decision.new_slots if catalog.slot(k) and catalog.slot(k).lead_field]
    wanted = not state.lead and any(catalog.skills[k].creates_lead for k in decision.skills)
    ai = {k: v for k, v in ai_fields(turn.understanding, catalog.settings).items() if state.ai.get(k) != v}
    if not (lead_slots or wanted or (ai and state.lead)):
        return
    fields, courses = lead_updates(state.slots, catalog)
    fields.update(ai)
    try:
        state.lead = effects.save_lead(state, fields, courses, turn.event.contact) or state.lead
    except Exception as e:
        turn.reply.errors.append({"type": "lead_failed", "detail": str(e)[:300]})
        return
    state.ai.update(ai)
    effects.emit("lead_updated", {"conversation_id": state.conversation_id, "lead": state.lead,
                                  "is_sandbox": state.is_sandbox, "fields": sorted(fields),
                                  "courses": [c.code for c in courses]})
```

In `$APP/engine/repo.py`: `load_state` gets `ai=_json(d.ai_signals),` (`_json` already returns `{}` for empty); `save_state` gets `"ai_signals": json.dumps(state.ai, ensure_ascii=False),`.

DocType (Appendix A helper): `add_fields("Bot Conversation", [field("ai_signals", "JSON", "Intent / hotness written to the Lead", read_only=1)])`.

- [ ] **Step 6: `intelligence.py` skips what the bot handles**

In `$APP/intelligence.py` add above `enqueue_analysis`:

```python
def bot_active(conversation_id) -> bool:
    """D-032: while the lead engine handles a conversation its own Jev call supplies intent/hotness."""
    return bool(frappe.db.exists("Bot Conversation",
                                 {"conversation_id": str(conversation_id), "status": "active", "is_sandbox": 0}))
```

and in `enqueue_analysis`, right after the `Missing conversation id` return:

```python
    if bot_active(conversation["id"]):
        return {"status": "ignored", "reason": "bot_active"}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 8: Migrate, refresh the live summary template, check in the sandbox**

```bash
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost migrate >/dev/null && bench --site crm.localhost clear-cache"
docker cp frappe-custom/mmm_custom/mmm_custom/demo/saoviet/settings.json crm-frappe-1:/tmp/lead_engine_settings.json
docker exec -i crm-frappe-1 bash -c "cd frappe-bench/sites && ../env/bin/python" <<'EOF'
import json, frappe
frappe.init(site="crm.localhost"); frappe.connect(); frappe.set_user("Administrator")
frappe.db.set_single_value("Lead Engine Settings", "summary_template", json.load(open("/tmp/lead_engine_settings.json"))["summary_template"])
frappe.db.commit()
from mmm_custom.engine import playground
playground.reset("c3t4")
out = playground.simulate("c3t4", "cho mình gặp tư vấn viên luôn, mình muốn đăng ký excel ở dĩ an, sđt 0901234567", jev=1)
print(out["jev"]["status"], out["understanding"]["intent"], out["understanding"]["hotness"], out["understanding"]["wants_human"])
print(out["decision"]["type"], out["decision"]["handoff_reason"], out["decision"]["reason"])
print([c for c in out["effects"] if c[0] == "handoff"])
playground.reset("c3t4")
EOF
```
Expected: `ok`; intent `purchase` (or another high-intent value), `wants_human` ≥ 0.7; decision `handoff` with reason `wants_human` (or `button`/`skill` if the alias "tu van vien" matched `talk_to_human` first — both are correct); the recorded handoff call shows the labels (with `hot` when hotness came back hot) and a summary containing the 🔥 line when hotness was answered.

- [ ] **Step 9: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/engine/combine.py frappe-custom/mmm_custom/mmm_custom/engine/decide.py \
  frappe-custom/mmm_custom/mmm_custom/engine/handoff.py frappe-custom/mmm_custom/mmm_custom/engine/pipeline.py \
  frappe-custom/mmm_custom/mmm_custom/engine/state.py frappe-custom/mmm_custom/mmm_custom/engine/repo.py \
  frappe-custom/mmm_custom/mmm_custom/intelligence.py frappe-custom/mmm_custom/mmm_custom/demo/saoviet/settings.json \
  frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/bot_conversation/bot_conversation.json \
  frappe-custom/mmm_custom/mmm_custom/tests/test_engine_signals.py frappe-custom/mmm_custom/mmm_custom/tests/test_intelligence.py
git commit -m "feat(ai): hand off early on wants-human or hot, write bot intent and hotness to the Lead"
```

---

### Task 5: C3.5 — Cost guard and spam stop

Implements **C3.5** (D-044, D-061) and **D-080**.

**Files:**
- Create: `$APP/engine/cost_guard.py`
- Modify: `$APP/engine/combine.py` (spam), `$APP/engine/decide.py` (`close`), `$APP/engine/pipeline.py` (guard, token accounting, `mark_spam`), `$APP/engine/effects.py` (`mark_spam`), `$APP/engine/repo.py` (`now`, `jev_budget`, `add_jev_tokens`, `warn_budget`, persist `jev_calls`), `$APP/engine/playground.py` (`close` in the inspector), DocTypes `bot_conversation` (+`jev_calls`), `lead_engine_settings` (+cost guard section)
- Modify tests: `$T/engine_fixtures.py` (`FakeRepo` clock/tokens/budget/warnings); create `$T/test_engine_cost_guard.py`

**Interfaces:**
- Consumes: `ConversationState.jev_calls`, settings `jev_calls_per_hour` 20, `jev_daily_token_budget` 0, `playground_daily_token_budget` 0, `spam_threshold` 0.80; `Understanding.unmatched` (content words no alias explained).
- Produces:
  - `cost_guard.HOUR = 3600`, `cost_guard.recent_calls(calls, now) -> list`, `cost_guard.allow_jev(u, state, catalog, now, tokens_today=0, budget=0) -> (bool, reason)`; reasons `button | keywords_resolved | hourly_cap | daily_budget`.
  - `pipeline.understand_turn(text, state, catalog, jev, now=0.0, tokens_today=0, budget=0)` (replaces Task 2's signature; the tap check moves into the guard).
  - `Decision.close: bool`; `Effects.mark_spam(conversation_id)`.
  - Repo: `now() -> float`, `jev_budget() -> (tokens_today, budget)`, `add_jev_tokens(n)`, `warn_budget()`. `FakeRepo.clock`, `.tokens`, `.budget`, `.warnings`.

- [ ] **Step 1: Write the failing tests**

In `$T/engine_fixtures.py`, `FakeRepo.__init__` add

```python
        self.clock, self.tokens, self.budget, self.warnings = 1_800_000_000.0, 0, 0, 0
```

and the methods

```python
    def now(self):
        return self.clock

    def jev_budget(self):
        return self.tokens, self.budget

    def add_jev_tokens(self, n):
        self.tokens += n

    def warn_budget(self):
        self.warnings += 1
```

`$T/test_engine_cost_guard.py`:

```python
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeJev, FakeRepo, demo_catalog, fill, render

from mmm_custom.engine.cost_guard import allow_jev, recent_calls
from mmm_custom.engine.decide import decide
from mmm_custom.engine.effects import ChatwootEffects, RecordingEffects
from mmm_custom.engine.pipeline import parse_event, run_turn
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding

CAT = demo_catalog()
NOW = 1_800_000_000.0
SPAM = {"intent": {"choice": "spam", "confidence": 0.95}}


def incoming(text, message_id=5):
    return {"event": "message_created", "id": message_id, "content": text, "message_type": "incoming",
            "private": False, "sender": {"id": 9, "name": "Lan", "type": "contact"},
            "conversation": {"id": 7, "inbox_id": 3, "meta": {"sender": {"id": 9, "name": "Lan", "custom_attributes": {}}}}}


class TestAllowJev(unittest.TestCase):
    def test_button_tap(self):
        self.assertEqual(allow_jev(Understanding(tapped=True), ConversationState("1"), CAT, NOW), (False, "button"))

    def test_keywords_explained_everything(self):
        state = ConversationState("1", pending={"slot": "course"})
        u = Understanding(fills={"course": fill("VP-EXCEL")})
        self.assertEqual(allow_jev(u, state, CAT, NOW), (False, "keywords_resolved"))
        self.assertEqual(allow_jev(Understanding(), ConversationState("1"), CAT, NOW), (False, "keywords_resolved"))

    def test_leftover_words_or_unanswered_question_need_jev(self):
        state = ConversationState("1", pending={"slot": "course"})
        u = Understanding(fills={"course": fill("VP-EXCEL")}, unmatched=["nua"])
        self.assertEqual(allow_jev(u, state, CAT, NOW), (True, ""))
        self.assertEqual(allow_jev(Understanding(fills={"branch": fill("CN Dĩ An")}), state, CAT, NOW), (True, ""))

    def test_hourly_cap(self):
        u = Understanding(unmatched=["x"])
        busy = ConversationState("1", jev_calls=[NOW - 10] * 20)
        self.assertEqual(allow_jev(u, busy, CAT, NOW), (False, "hourly_cap"))
        old = ConversationState("1", jev_calls=[NOW - 4000] * 20)
        self.assertEqual(allow_jev(u, old, CAT, NOW), (True, ""))
        self.assertEqual(recent_calls([NOW - 4000, NOW - 5], NOW), [NOW - 5])

    def test_daily_budget(self):
        u = Understanding(unmatched=["x"])
        self.assertEqual(allow_jev(u, ConversationState("1"), CAT, NOW, 1000, 1000), (False, "daily_budget"))
        self.assertEqual(allow_jev(u, ConversationState("1"), CAT, NOW, 10**9, 0), (True, ""))


class TestGuardInTheTurn(unittest.TestCase):
    def setUp(self):
        self.repo, self.fx = FakeRepo(CAT), RecordingEffects()
        self.repo.jev = FakeJev({"slot:course": {"choice": "VKT-REVIT", "confidence": 0.93}})

    def turn(self, text, message_id=5):
        return run_turn(parse_event(incoming(text, message_id)), self.repo, self.fx, render)

    def test_call_and_tokens_are_counted(self):
        self.turn("mình muốn học vẽ nhà")
        self.assertEqual((self.repo.states["7"].jev_calls, self.repo.tokens), ([NOW], 120))

    def test_hourly_cap_skips_jev(self):
        self.repo.states["7"] = ConversationState("7", contact_id="9", turns=1, jev_calls=[NOW - 1] * 20)
        t = self.turn("mình muốn học vẽ nhà")
        self.assertEqual((t.jev.status, t.jev.error, self.repo.jev.calls), ("skipped_cost_guard", "hourly_cap", []))
        self.assertEqual(self.repo.logs[0]["jev_status"], "skipped_cost_guard")

    def test_budget_reached_warns(self):
        self.repo.tokens, self.repo.budget = 500, 500
        t = self.turn("mình muốn học vẽ nhà")
        self.assertEqual((t.jev.error, self.repo.warnings), ("daily_budget", 1))

    def test_spam_closes_without_lead(self):
        self.repo.jev = FakeJev(SPAM)
        t = self.turn("Vay tiền nhanh lãi suất thấp giải ngân trong ngày")
        self.assertEqual((t.decision.type, t.decision.close, self.repo.states["7"].status), ("silent", True, "closed"))
        self.assertEqual(self.fx.of("mark_spam"), [{"conversation_id": "7"}])
        self.assertEqual((self.fx.of("send"), self.fx.of("save_lead")), ([], []))
        self.assertIn("rác", self.repo.logs[0]["reason"])

    def test_spam_guess_never_closes_a_known_customer(self):
        self.repo.jev = FakeJev(SPAM)
        self.repo.states["7"] = ConversationState("7", contact_id="9", lead="CRM-LEAD-1", turns=1)
        t = self.turn("Vay tiền nhanh lãi suất thấp giải ngân trong ngày")
        self.assertFalse(t.decision.close)
        self.assertEqual(self.repo.states["7"].status, "active")

    def test_low_spam_confidence_is_not_spam(self):
        self.repo.jev = FakeJev({"intent": {"choice": "spam", "confidence": 0.6}})
        self.assertFalse(self.turn("abc xyz").decision.close)


class TestSpamDecisionAndEffects(unittest.TestCase):
    def test_decide(self):
        d = decide(ConversationState("1", turns=1), Understanding(spam=0.9, skills=["hotline"]), CAT)
        self.assertEqual((d.type, d.close, d.skills), ("silent", True, []))

    def test_chatwoot_marks_and_resolves(self):
        bot = MagicMock()
        ChatwootEffects(bot, MagicMock()).mark_spam("7")
        bot.add_labels.assert_called_once_with("7", ["spam"])
        bot.toggle_status.assert_called_once_with("7", "resolved")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | grep -E "^(ERROR|FAIL):|^Ran|FAILED" | head -20`
Expected: ERROR `No module named 'mmm_custom.engine.cost_guard'`.

- [ ] **Step 3: `cost_guard.py`**

```python
"""Cost guard (D-044, D-061): may this turn call Jev? Pure. Any "no" keeps the turn on the keyword tier
and is logged as skipped_cost_guard with the reason."""

HOUR = 3600


def recent_calls(calls, now):
    return [t for t in calls if now - t < HOUR]


def keywords_resolved(u, state):
    """Every content word was explained by a keyword match and the pending question, if any, is answered.
    (D-061 says "keywords fill every open slot": taken literally, optional slots are almost always open and
    the rule would never apply — D-080 records this reading.)"""
    pending = state.pending.get("slot") or ""
    return not u.unmatched and (not pending or pending in u.fills or pending in u.parents)


def allow_jev(u, state, catalog, now, tokens_today=0, budget=0):
    settings = catalog.settings
    if u.tapped:
        return False, "button"
    if keywords_resolved(u, state):
        return False, "keywords_resolved"
    if len(recent_calls(state.jev_calls, now)) >= int(settings["jev_calls_per_hour"]):
        return False, "hourly_cap"
    if budget and tokens_today >= budget:
        return False, "daily_budget"
    return True, ""
```

- [ ] **Step 4: Pipeline, decide, combine, effects**

`$APP/engine/pipeline.py`:
- import `from mmm_custom.engine.cost_guard import allow_jev, recent_calls`.
- replace `understand_turn` with

```python
def understand_turn(text, state, catalog, jev, now=0.0, tokens_today=0, budget=0):
    """Keyword tier always; one Jev call when a client is given and the cost guard allows it (D-031, D-061)."""
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
```

- in `run_turn`, replace the `turn.understanding, turn.jev = …` line with

```python
    jev = repo.jev_client()
    tokens, budget = repo.jev_budget() if jev else (0, 0)
    turn.understanding, turn.jev = understand_turn(event.text, state, catalog, jev, repo.now(), tokens, budget)
    if turn.jev.input_tokens:
        repo.add_jev_tokens(turn.jev.input_tokens)
    if turn.jev.error == "daily_budget":
        repo.warn_budget()
```

- in `apply_decision` add at the end `if decision.close: state.status = "closed"`.
- in `run_turn`, right after `apply_decision(...)`:

```python
    if turn.decision.close:
        try:
            effects.mark_spam(state.conversation_id)
        except Exception as e:
            turn.reply.errors.append({"type": "spam_failed", "detail": str(e)[:300]})
```

`$APP/engine/decide.py`:
- `Decision` gets `close: bool = False  # spam: close the conversation (D-061)`.
- in `decide`, after the `consultant_replied` check:

```python
    if u.spam and not state.lead:  # D-080: a model guess never closes a conversation that has a Lead
        return Decision("silent", **keep, close=True, reason=f"Tin nhắn rác ({u.spam:.2f}): bot dừng, không tạo Lead")
```

`$APP/engine/combine.py`, in `_signals` after setting `u.intent`:

```python
        if intent == "spam" and p >= float(catalog.settings["spam_threshold"]):
            u.spam = round(p, 3)
```

`$APP/engine/effects.py`:
- `RecordingEffects`:

```python
    def mark_spam(self, conversation_id):
        self.calls.append(("mark_spam", {"conversation_id": conversation_id}))
```

- `ChatwootEffects`:

```python
    def mark_spam(self, conversation_id):
        """D-061: label spam and resolve; the bot stays silent and no Lead is created."""
        self.bot.add_labels(conversation_id, ["spam"])
        self.bot.toggle_status(conversation_id, "resolved")
```

`$APP/engine/playground.py` `inspect`: add `"close": d.close,` to `"decision"`.

- [ ] **Step 5: Repo, DocTypes**

`$APP/engine/repo.py`: add `import time` and in `FrappeRepo`:

```python
    def now(self):
        return time.time()

    def _token_key(self):
        return f"lead_engine_jev_tokens:{'playground' if self.sandbox else 'live'}:{self.today()}"

    def jev_budget(self):
        """(tokens used today, daily budget) — the Playground has its own budget (D-060); 0 = unlimited."""
        settings = self.catalog().settings
        budget = settings["playground_daily_token_budget"] if self.sandbox else settings["jev_daily_token_budget"]
        return int(frappe.cache().get(self._token_key()) or 0), int(budget or 0)

    def add_jev_tokens(self, n):
        cache, key = frappe.cache(), self._token_key()
        cache.incrby(key, int(n))
        cache.expire(key, 2 * 86400)

    def warn_budget(self):
        """Once per day per budget: an Error Log entry the admin sees (D-061 "keyword-only + warning")."""
        key = f"{self._token_key()}:warned"
        if frappe.cache().set(key, 1, ex=2 * 86400, nx=True):
            frappe.log_error(title="Lead engine: Jev daily token budget reached",
                             message=f"{key}: the bot runs on keywords only until tomorrow. Raise the budget in Lead Engine Settings.")
```

(`frappe.cache()` is a `redis.Redis` subclass, so the raw `get`/`incrby`/`expire`/`set(nx=)` calls use unprefixed keys consistently. Verify in Step 7.)

- `load_state`: `jev_calls=d.jev_calls if isinstance(d.jev_calls, list) else (json.loads(d.jev_calls) if d.jev_calls else []),`; `save_state`: `"jev_calls": json.dumps(state.jev_calls),`.

DocTypes (Appendix A helper):

```python
add_fields("Bot Conversation", [field("jev_calls", "JSON", "Jev calls in the last hour", read_only=1)])
add_fields("Lead Engine Settings", [
    field("cost_section", "Section Break", "Jev cost guard"),
    field("jev_calls_per_hour", "Int", "Jev calls per conversation per hour", description="Default 20"),
    field("jev_daily_token_budget", "Int", "Daily input-token budget (customers)", description="0 = unlimited"),
    field("playground_daily_token_budget", "Int", "Daily input-token budget (Playground)", description="0 = unlimited"),
])
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: `OK`. If a Task 2–4 pipeline test now gets `skipped_cost_guard` because its message is fully explained by keywords, change that test's text to include a word no alias matches (e.g. append " nha ban") — not the guard.

- [ ] **Step 7: Migrate and check live**

```bash
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost migrate >/dev/null && bench --site crm.localhost clear-cache"
docker exec -i crm-frappe-1 bash -c "cd frappe-bench/sites && ../env/bin/python" <<'EOF'
import frappe
frappe.init(site="crm.localhost"); frappe.connect(); frappe.set_user("Administrator")
from mmm_custom.engine import playground
from mmm_custom.engine.repo import FrappeRepo
before = FrappeRepo(sandbox=True).jev_budget()[0]
playground.reset("c3t5")
out = playground.simulate("c3t5", "Vay tiền nhanh lãi suất thấp, giải ngân trong ngày, liên hệ 0909123456", jev=1)
print(out["jev"]["status"], out["understanding"]["intent"], out["decision"])
print([c for c in out["effects"] if c[0] == "mark_spam"], out["state"]["status"])
print("tokens counted:", FrappeRepo(sandbox=True).jev_budget()[0] - before)
playground.reset("c3t5")
out = playground.simulate("c3t5", "excel", jev=1)
print(out["jev"])
playground.reset("c3t5")
EOF
```
Expected: `ok`, intent `spam` with confidence ≥ 0.8, decision `silent` with `close: True`, one `mark_spam` effect, status `closed`, tokens counted > 0. Then `excel` (a new conversation, turn 0, no pending question, every word explained) gives `skipped_cost_guard` with error `keywords_resolved`. If Jev rates the spam text below 0.8, record the confidence in the ledger — that is data for the Task 7 gate, not a code change.

- [ ] **Step 8: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/engine/cost_guard.py frappe-custom/mmm_custom/mmm_custom/engine/combine.py \
  frappe-custom/mmm_custom/mmm_custom/engine/decide.py frappe-custom/mmm_custom/mmm_custom/engine/pipeline.py \
  frappe-custom/mmm_custom/mmm_custom/engine/effects.py frappe-custom/mmm_custom/mmm_custom/engine/repo.py \
  frappe-custom/mmm_custom/mmm_custom/engine/playground.py \
  frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/bot_conversation/bot_conversation.json \
  frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/lead_engine_settings/lead_engine_settings.json \
  frappe-custom/mmm_custom/mmm_custom/tests/engine_fixtures.py frappe-custom/mmm_custom/mmm_custom/tests/test_engine_cost_guard.py
git commit -m "feat(ai): add Jev cost guard with hourly cap and daily budget, stop on confident spam"
```

---

### Task 6: C3.6 — Course advisor with Jev fit scoring

Implements **C3.6** (D-040, D-055, D-078, D-079). Without Jev (or when it fails) the C2 data filter (D-071) still recommends.

**Files:**
- Create: `$APP/engine/advisor.py`
- Modify: `$APP/engine/catalog.py` (`Slot.on_demand`), `$APP/engine/decide.py` (`next_slot` skips on-demand slots), `$APP/engine/understand.py` (on-demand slots only while pending), `$APP/engine/jev_questions.py` (same), `$APP/engine/actions.py` (`ActionInput.jev`, `.jev_state`; `recommend_courses`), `$APP/engine/reply.py` (`Reply.ask`, `.pending_skill`, `.jev_extra`; one extra call), `$APP/engine/pipeline.py` (pass Jev to compose, count the extra call), `$APP/engine/log.py` (`jev_extra`), `$APP/engine/repo.py` (`ask_on_demand` in `load_rows`), `$APP/demo/loader.py` (`ask_on_demand`), `$APP/demo/saoviet/bot_slots.json` (`goal`, `level`), DocTypes `bot_slot` (+`ask_on_demand`), `ai_decision_log` (+`jev_extra`), `lead_engine_settings` (+advisor section)
- Create tests: `$T/test_engine_advisor.py`; modify `$T/test_demo_data.py` (slot count 7 → 9)

**Interfaces:**
- Consumes: `JevResult`, `jev_state`, settings `advisor_goal_weight` 0.6, `advisor_level_weight` 0.4, `advisor_floor` 0.5, `advisor_shortlist` 8.
- Produces:
  - `Slot.on_demand: bool` (from Bot Slot `ask_on_demand`).
  - `advisor.GOAL_FIT`, `advisor.LEVEL_FIT`, `advisor.EXCLUDE_AT = 0.70`, `advisor.advisor_questions(courses) -> dict`, `advisor.score_courses(courses, answers, settings) -> [(Course, composite)]`.
  - `ActionInput.jev = None`, `ActionInput.jev_state = None`; `run_action(skill, ctx, slots, catalog, data, today, jev=None, jev_state=None)`.
  - `recommend_courses` may return `_jev` (the extra call's `JevResult.log()`) and `_ask` (slot key to ask instead of recommending).
  - `compose(decision, state, catalog, render, data=None, today=None, extra=None, jev=None, jev_state=None)`; `Reply.ask`, `Reply.pending_skill`, `Reply.jev_extra`.
  - AI Decision Log `jev_extra` (JSON list).

- [ ] **Step 1: Demo slots `goal` and `level`**

Append to `$APP/demo/saoviet/bot_slots.json` (before the closing `]`; keep the existing entries):

```json
,
{"slot_key": "goal", "label": "Mục tiêu học", "slot_type": "choice", "catalog_source": "", "required": 0, "sort_order": 32,
 "ask_on_demand": 1, "ask_template": "{{ brand.you | capitalize }} học để phục vụ mục tiêu gì ạ?",
 "options": [
  {"value": "office", "label": "Công việc văn phòng", "button_label": "Công việc văn phòng", "aliases": "van phong, di lam van phong"},
  {"value": "certificate", "label": "Lấy chứng chỉ", "button_label": "Lấy chứng chỉ", "aliases": "lay chung chi, thi chung chi"},
  {"value": "kids_start", "label": "Cho bé làm quen máy tính", "button_label": "Cho bé làm quen", "aliases": "be lam quen, lam quen may tinh"},
  {"value": "career", "label": "Chuyển nghề / tìm việc", "button_label": "Chuyển nghề", "aliases": "chuyen nghe, tim viec, xin viec"},
  {"value": "hobby", "label": "Sở thích cá nhân", "button_label": "Sở thích", "aliases": "so thich, hoc cho vui"}],
 "depends_on_slot": "", "depends_on_value": "", "lead_field": ""},
{"slot_key": "level", "label": "Trình độ hiện tại", "slot_type": "choice", "catalog_source": "", "required": 0, "sort_order": 34,
 "ask_on_demand": 1, "ask_template": "{{ brand.you | capitalize }} đã biết về lĩnh vực này tới đâu rồi ạ?",
 "options": [
  {"value": "beginner", "label": "Chưa biết gì", "button_label": "Chưa biết gì", "aliases": "chua biet gi, mat goc, moi bat dau"},
  {"value": "basic", "label": "Biết cơ bản", "button_label": "Biết cơ bản", "aliases": "biet co ban, biet chut chut"},
  {"value": "advanced", "label": "Muốn nâng cao", "button_label": "Muốn nâng cao", "aliases": "muon nang cao, da biet kha"}],
 "depends_on_slot": "", "depends_on_value": "", "lead_field": ""}
```

In `$T/test_demo_data.py` change `self.assertEqual(len(self.slots), 7)` to `9`.

- [ ] **Step 2: Write the failing tests**

`$T/test_engine_advisor.py`:

```python
import sys
from datetime import date
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeJev, FakeRepo, demo_catalog, fill, render

from mmm_custom.engine.actions import run_action
from mmm_custom.engine.advisor import advisor_questions, score_courses
from mmm_custom.engine.context import base_context
from mmm_custom.engine.decide import Decision, decide, next_slot
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.jev_questions import build_questions
from mmm_custom.engine.pipeline import parse_event, run_turn
from mmm_custom.engine.reply import compose
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding, understand

CAT = demo_catalog()
TODAY = date(2026, 9, 28)
KIDS = ["TE-THUD", "TE-SCRATCH", "TE-PY", "TE-ROBO", "TE-ROBO-NC"]


def fits(goal, level, exclude=()):
    """Fake Jev answers: goal/level scores per course code (default 1), exclusion nouls."""
    def answer(questions):
        out = {}
        for key in questions:
            kind, _, code = key.partition(":")
            if kind == "goal_fit":
                out[key] = {"score": goal.get(code, 1), "confidence": 0.9}
            elif kind == "level_fit":
                out[key] = {"score": level.get(code, 1), "confidence": 0.9}
            elif kind == "exclude":
                out[key] = {"noul": 0.9 if code in exclude else 0.05}
        return out
    return answer


def act(skill_key, slots, jev=None):
    ctx = base_context(slots, CAT, ConversationState("1", slots=slots))
    return run_action(CAT.skills[skill_key], ctx, slots, CAT, FakeRepo(CAT), TODAY, jev, {"latest_message": "x"})


class TestAdvisorMath(unittest.TestCase):
    def test_three_questions_per_course(self):
        q = advisor_questions([CAT.courses["TE-ROBO"]])
        self.assertEqual(set(q), {"goal_fit:TE-ROBO", "level_fit:TE-ROBO", "exclude:TE-ROBO"})
        self.assertEqual((q["goal_fit:TE-ROBO"]["type"], q["exclude:TE-ROBO"]["type"]), ("score", "noul"))
        self.assertIn("Robotics cơ bản", q["goal_fit:TE-ROBO"]["instructions"])

    def test_composite_exclusion_and_order(self):
        courses = [CAT.courses[c] for c in KIDS]
        answers = fits({"TE-ROBO": 2, "TE-PY": 2}, {"TE-ROBO": 2}, exclude={"TE-SCRATCH"})(advisor_questions(courses))
        ranked = score_courses(courses, answers, CAT.settings)
        self.assertEqual([(c.code, s) for c, s in ranked],
                         [("TE-ROBO", 1.0), ("TE-PY", 0.8), ("TE-THUD", 0.5), ("TE-ROBO-NC", 0.5)])

    def test_unanswered_courses_are_left_out(self):
        courses = [CAT.courses["TE-ROBO"], CAT.courses["TE-PY"]]
        answers = {"goal_fit:TE-ROBO": {"score": 2}, "level_fit:TE-ROBO": {"score": 2}}
        self.assertEqual([c.code for c, _ in score_courses(courses, answers, CAT.settings)], ["TE-ROBO"])


class TestRecommendWithJev(unittest.TestCase):
    def test_advisor_without_jev_uses_data_filter(self):
        out = act("kids_courses", {})
        self.assertEqual([r["code"] for r in out["recommendations"]], ["TE-THUD", "TE-SCRATCH", "TE-PY"])
        self.assertNotIn("_jev", out)

    def test_jev_ranks_the_shortlist(self):
        jev = FakeJev(fits({"TE-ROBO": 2, "TE-PY": 2}, {"TE-ROBO": 2}, exclude={"TE-SCRATCH"}))
        out = act("kids_courses", {}, jev)
        self.assertEqual([(r["code"], r["score"]) for r in out["recommendations"]],
                         [("TE-ROBO", 1.0), ("TE-PY", 0.8), ("TE-THUD", 0.5)])
        self.assertEqual(out["_buttons"][0]["action"]["value"], "TE-ROBO")
        self.assertEqual((out["_jev"]["status"], len(jev.calls)), ("ok", 1))
        self.assertEqual(len(jev.calls[0][1]), 15)

    def test_shortlist_is_capped(self):
        jev = FakeJev(fits({}, {}))
        act("course_advisor", {"learner": fill("self")}, jev)
        self.assertEqual(len(jev.calls[0][1]), 3 * 8)

    def test_below_the_floor_asks_goal_then_level(self):
        low = FakeJev(fits({}, {}))  # every score 1 → composite 0.5; floor 0.5 is not "below"
        self.assertNotIn("_ask", act("kids_courses", {}, low))
        zero = fits({c: 0 for c in KIDS}, {c: 0 for c in KIDS})
        self.assertEqual(act("kids_courses", {}, FakeJev(zero))["_ask"], "goal")
        self.assertEqual(act("kids_courses", {"goal": fill("kids_start")}, FakeJev(zero))["_ask"], "level")
        both = act("kids_courses", {"goal": fill("kids_start"), "level": fill("beginner")}, FakeJev(zero))
        self.assertNotIn("_ask", both)
        self.assertEqual(len(both["recommendations"]), 3)

    def test_jev_failure_falls_back_to_the_data_filter(self):
        out = act("kids_courses", {}, FakeJev(status="unavailable"))
        self.assertEqual([r["code"] for r in out["recommendations"]], ["TE-THUD", "TE-SCRATCH", "TE-PY"])
        self.assertEqual(out["_jev"]["status"], "unavailable")


class TestComposeAdvisor(unittest.TestCase):
    def test_advisor_makes_one_call(self):
        jev = FakeJev(fits({}, {}))
        d = Decision("answer", slots={"learner": fill("child")}, skills=["kids_courses", "course_advisor"])
        r = compose(d, ConversationState("1", turns=1), CAT, render, FakeRepo(CAT), TODAY, jev=jev, jev_state={})
        self.assertEqual((len(jev.calls), len(r.jev_extra)), (1, 1))

    def test_advisor_ask_replaces_the_answer(self):
        zero = fits({c: 0 for c in KIDS}, {c: 0 for c in KIDS})
        d = Decision("answer", slots={}, skills=["kids_courses"], ask="course")
        r = compose(d, ConversationState("1", turns=1), CAT, render, FakeRepo(CAT), TODAY, jev=FakeJev(zero), jev_state={})
        self.assertEqual((r.ask, r.pending_skill), ("goal", "kids_courses"))
        self.assertEqual(r.messages, ["Anh/chị học để phục vụ mục tiêu gì ạ?"])
        self.assertEqual([b["action"]["slot"] for b in r.buttons], ["goal"] * 5)


class TestOnDemandSlots(unittest.TestCase):
    def test_never_in_the_normal_sequence(self):
        slots = {"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An"), "learner": fill("self"),
                 "preferred_shift": fill("evening"), "customer_name": fill("Lan")}
        self.assertEqual(next_slot(slots, CAT), "phone")
        self.assertEqual(next_slot(slots, CAT, first=["goal"]), "goal")

    def test_matched_and_asked_only_while_pending(self):
        self.assertNotIn("level", understand("muốn nâng cao excel", ConversationState("1"), CAT).fills)
        pending = ConversationState("1", pending={"slot": "level"})
        self.assertEqual(understand("muốn nâng cao", pending, CAT).fills["level"]["value"], "advanced")
        self.assertNotIn("slot:goal", build_questions(ConversationState("1"), Understanding(), CAT))
        self.assertIn("slot:goal", build_questions(ConversationState("1", pending={"slot": "goal"}), Understanding(), CAT))


class TestAdvisorTurn(unittest.TestCase):
    def test_goal_question_then_recommendation(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        zero = fits({c: 0 for c in KIDS}, {c: 0 for c in KIDS})
        repo.jev = FakeJev(lambda q: {"skill:kids_courses": {"noul": 0.95}, **zero(q)})
        msg = {"event": "message_created", "id": 5, "content": "bé nhà mình học khóa nào được nhỉ", "message_type": "incoming",
               "private": False, "sender": {"id": 9, "type": "contact"},
               "conversation": {"id": 7, "inbox_id": 3, "meta": {"sender": {"id": 9, "custom_attributes": {}}}}}
        t = run_turn(parse_event(msg), repo, fx, render)
        state = repo.states["7"]
        self.assertEqual((state.pending["slot"], state.pending_skill), ("goal", "kids_courses"))
        self.assertEqual(state.slots["goal"]["asked"], 1)
        self.assertEqual(len(repo.jev.calls), 2)  # the turn's call + one advisor call
        self.assertEqual((state.jev_calls, repo.tokens), ([repo.clock, repo.clock], 240))
        self.assertIn("goal_fit:TE-ROBO", repo.logs[0]["jev_extra"])


if __name__ == "__main__":
    unittest.main()
```

(If a demo course's fixed data changes the expected order, e.g. `TE-ROBO` has an age range that the default slots exclude, read the kids list from `act("kids_courses", {})` in the test rather than editing the data.)

- [ ] **Step 3: Run them to verify they fail**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | grep -E "^(ERROR|FAIL):|^Ran|FAILED" | head -20`
Expected: ERROR `No module named 'mmm_custom.engine.advisor'`; other suites still pass except any test that counts the demo slots (now fixed to 9).

- [ ] **Step 4: On-demand slots**

- `catalog.py`: `Slot` gets `on_demand: bool = False  # asked only by a skill or the advisor (D-078)`; in `build_catalog`'s `Slot(...)` add `on_demand=bool(s.get("ask_on_demand")),`.
- `decide.py` `next_slot`: after `entry = …` add `if slot.on_demand and slot.key not in first: continue`.
- `understand.py` `understand()`: build `slots` as `[(s, REGISTRY[s.type]) for s in catalog.slots if s.type in REGISTRY and (not s.on_demand or pending == s.key)]`.
- `jev_questions.py` `build_questions`: in the slot loop add `if slot.on_demand and state.pending.get("slot") != slot.key: continue`.
- `repo.py` `load_rows`: add `"ask_on_demand"` to the Bot Slot field list.
- `demo/loader.py`: the Bot Slot `put(...)` values gain `"ask_on_demand": s.get("ask_on_demand", 0),`.
- DocTypes (Appendix A helper):

```python
add_fields("Bot Slot", [field("ask_on_demand", "Check", "Ask only when a skill needs it",
                              description="Not part of the normal question sequence (e.g. goal, level for the course advisor)")])
add_fields("AI Decision Log", [field("jev_extra", "JSON", "Extra Jev calls (course advisor)")])
add_fields("Lead Engine Settings", [
    field("advisor_section", "Section Break", "Course advisor"),
    field("advisor_goal_weight", "Float", "Goal fit weight", description="Default 0.6"),
    field("advisor_level_weight", "Float", "Level fit weight", description="Default 0.4"),
    field("advisor_floor", "Float", "Ask goal/level below", description="Default 0.5"),
    field("advisor_shortlist", "Int", "Courses scored per call", description="Default 8"),
])
```

- [ ] **Step 5: `advisor.py`**

```python
"""Course advisor scoring (D-040, D-055, D-079): Jev scores how well each shortlisted course fits the
customer's goal and level (0–2) and whether anything rules it out; code computes the composite."""

GOAL_FIT = ["0: does not serve what the customer wants to achieve", "1: partly serves it",
            "2: clearly serves what the customer wants to achieve"]
LEVEL_FIT = ["0: wrong level for the customer (too hard or too basic)", "1: acceptable level",
             "2: exactly the customer's level"]
EXCLUDE_AT = 0.70


def _about(c):
    ages = f"; ages {c.min_age}–{c.max_age}" if c.min_age or c.max_age else ""
    return f"'{c.name}' (group: {c.group}; for: {c.audience}{ages})"


def advisor_questions(courses):
    q = {}
    for c in courses:
        about = _about(c)
        q[f"goal_fit:{c.code}"] = {"type": "score", "criteria": GOAL_FIT,
                                   "instructions": f"How well does the course {about} fit what the customer wants to achieve?"}
        q[f"level_fit:{c.code}"] = {"type": "score", "criteria": LEVEL_FIT,
                                    "instructions": f"How well does the course {about} match the customer's current level?"}
        q[f"exclude:{c.code}"] = {"type": "noul", "instructions":
                                  f"Does anything in the chat rule out the course {about} (wrong age, already taken, explicitly not wanted)?"}
    return q


def _num(answers, key, field):
    try:
        return float((answers.get(key) or {})[field])
    except (KeyError, TypeError, ValueError):
        return None


def score_courses(courses, answers, settings):
    gw, lw = float(settings["advisor_goal_weight"]), float(settings["advisor_level_weight"])
    ranked = []
    for c in courses:
        goal, level = _num(answers, f"goal_fit:{c.code}", "score"), _num(answers, f"level_fit:{c.code}", "score")
        if goal is None or level is None or (_num(answers, f"exclude:{c.code}", "noul") or 0) >= EXCLUDE_AT:
            continue
        ranked.append((c, round(gw * min(max(goal, 0), 2) / 2 + lw * min(max(level, 0), 2) / 2, 3)))
    return sorted(ranked, key=lambda pair: -pair[1])  # stable: ties keep the data order
```

- [ ] **Step 6: `recommend_courses`, `run_action`, `compose`, pipeline, log**

`$APP/engine/actions.py`:
- `ActionInput` gets `jev: object = None` and `jev_state: dict = None` (after `today`).
- `run_action(skill, ctx, slots, catalog, data, today, jev=None, jev_state=None)` passes them: `ActionInput(skill, ctx, slots, catalog, data, today, jev, jev_state)`.
- import `from mmm_custom.engine.advisor import advisor_questions, score_courses` and `from mmm_custom.engine.state import filled, value`.
- replace `recommend_courses` with:

```python
@action("recommend_courses")
def recommend_courses(a):
    """Course advisor: data filters from action_config (D-071), then Jev fit scoring of the shortlist
    with one extra call (D-055); below the floor it asks goal/level instead."""
    cfg, settings = a.skill.config, a.catalog.settings
    learner = value(a.slots, CUSTOMER_SLOTS["learner"])
    age = value(a.slots, CUSTOMER_SLOTS["learner_age"])
    audiences = [cfg["audience"]] if cfg.get("audience") else list((cfg.get("audience_by_learner") or {}).get(learner or "", []))
    course_slot = a.catalog.slot_for("course")
    group = (a.slots.get(course_slot.key) or {}).get("parent", "") if course_slot else ""
    candidates = [c for c in a.catalog.courses.values()
                  if (not audiences or c.audience in audiences)
                  and (not age or (c.min_age or 0) <= int(age) <= (c.max_age or 200))
                  and (not group or c.group == group)]
    top, out, scores = int(cfg.get("top", 3)), {}, {}
    picked = candidates[:top]
    if a.jev is not None and len(candidates) > 1:
        shortlist = candidates[: int(settings["advisor_shortlist"])]
        result = a.jev.ask(a.jev_state or {}, advisor_questions(shortlist))
        out["_jev"] = result.log()
        ranked = score_courses(shortlist, result.answers, settings) if result.status == "ok" else []
        if ranked and ranked[0][1] < float(settings["advisor_floor"]):
            ask = next((k for k in ("goal", "level") if a.catalog.slot(k) and not filled(a.slots, k)), "")
            if ask:
                return {**out, "_ask": ask}
        if ranked:
            picked, scores = [c for c, _ in ranked[:top]], dict((c.code, s) for c, s in ranked)
    buttons = [{"title": c.button, "action": {"type": "slot", "slot": course_slot.key, "value": c.code}}
               for c in picked] if course_slot else []
    out.update(recommendations=[{"course": c.name, "code": c.code, "fee": c.fee, "score": scores.get(c.code)}
                                for c in picked], _buttons=buttons)
    return out
```

`$APP/engine/reply.py`:
- `Reply` gets `ask: str = ""`, `pending_skill: str = ""`, `jev_extra: list = field(default_factory=list)`.
- `compose(decision, state, catalog, render, data=None, today=None, extra=None, jev=None, jev_state=None)`; in the skill loop:

```python
        try:
            out = run_action(skill, ctx, decision.slots, catalog, data, today, jev, jev_state)
        except Exception as e:
            reply.errors.append({"type": "action_error", "source": key, "detail": str(e)[:300]})
            out = {}
        if "_jev" in out:
            reply.jev_extra.append(out["_jev"])
            jev = None  # D-055: at most one extra Jev call per turn
        if out.get("_ask"):
            reply.ask, reply.pending_skill = reply.ask or out["_ask"], reply.pending_skill or key
            continue
```

- in the ask block use `ask_key = reply.ask or decision.ask` instead of `decision.ask` (both the `if` and `catalog.slot(...)`).

`$APP/engine/pipeline.py`:
- import `from mmm_custom.engine.context import shown_slots`.
- in `run_turn`, build the compose call as

```python
    advisor_jev = jev if turn.jev.status == "ok" else None
    advisor_state = {**jev_state(event.text, state, catalog), "known": shown_slots(turn.decision.slots, catalog)}
    turn.reply = compose(turn.decision, state, catalog, render, repo, repo.today(), extra, advisor_jev, advisor_state)
    for call in turn.reply.jev_extra:
        state.jev_calls.append(repo.now())
        if call.get("input_tokens"):
            repo.add_jev_tokens(call["input_tokens"])
```

- `apply_decision`:

```python
    state.pending_skill = reply.pending_skill or decision.pending_skill
    state.answered = list(dict.fromkeys(state.answered + [k for k in decision.skills if k != reply.pending_skill]))
    if decision.type != "silent":
        state.pending = {"slot": reply.ask or decision.ask, "options": reply.options()}
        ...
    if reply.ask:
        state.slots.setdefault(reply.ask, {})["asked"] = 1
```

(keep the rest of `apply_decision` from Tasks 2 and 5.)

`$APP/engine/log.py` `log_row`: add `"jev_extra": _j(r.jev_extra),`.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 8: Migrate, load the new slots, check live**

```bash
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost migrate >/dev/null && bench --site crm.localhost execute mmm_custom.demo.loader.load --kwargs \"{'anchor': '2026-09-28'}\" && bench --site crm.localhost clear-cache"
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost execute mmm_custom.engine.chatwoot_setup.ensure_conversation_attributes"
docker exec -i crm-frappe-1 bash -c "cd frappe-bench/sites && ../env/bin/python" <<'EOF'
import frappe
frappe.init(site="crm.localhost"); frappe.connect(); frappe.set_user("Administrator")
print(frappe.db.count("Course Schedule"), frappe.db.count("Bot Slot"))
from mmm_custom.engine import playground
playground.reset("c3t6")
for text in ("mình làm kế toán muốn học thêm để làm báo cáo nhanh hơn, nên học khóa nào", "Cho tôi"):
    out = playground.simulate("c3t6", text, jev=1)
    print(out["jev"]["status"], out["decision"]["type"], out["decision"]["skills"], out["reply"]["messages"], out["reply"]["buttons"])
playground.reset("c3t6")
EOF
```
Expected: the loader's anchor is the same `2026-09-28` used before, so the schedule count is unchanged (no duplicates) and `Bot Slot` = 9; `ensure_conversation_attributes` reports `bot_goal`, `bot_level` created (or none if they exist). The first message asks who will study (course_advisor waits for `learner`) or recommends; after "Cho tôi" the reply lists up to 3 courses with fees (Excel/Kế toán trên Excel family expected) or asks the goal. Record what came back.

- [ ] **Step 9: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/engine/advisor.py frappe-custom/mmm_custom/mmm_custom/engine/catalog.py \
  frappe-custom/mmm_custom/mmm_custom/engine/decide.py frappe-custom/mmm_custom/mmm_custom/engine/understand.py \
  frappe-custom/mmm_custom/mmm_custom/engine/jev_questions.py frappe-custom/mmm_custom/mmm_custom/engine/actions.py \
  frappe-custom/mmm_custom/mmm_custom/engine/reply.py frappe-custom/mmm_custom/mmm_custom/engine/pipeline.py \
  frappe-custom/mmm_custom/mmm_custom/engine/log.py frappe-custom/mmm_custom/mmm_custom/engine/repo.py \
  frappe-custom/mmm_custom/mmm_custom/demo/loader.py frappe-custom/mmm_custom/mmm_custom/demo/saoviet/bot_slots.json \
  frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/bot_slot/bot_slot.json \
  frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/ai_decision_log/ai_decision_log.json \
  frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/lead_engine_settings/lead_engine_settings.json \
  frappe-custom/mmm_custom/mmm_custom/tests/test_engine_advisor.py frappe-custom/mmm_custom/mmm_custom/tests/test_demo_data.py
git commit -m "feat(ai): score course advisor shortlist with Jev goal and level fit, ask goal or level below the floor"
```

---

### Task 7: Verification — evaluation gate against real Jev, fresh bench, Playground, docs

Implements the C3 part of **D-062** and the **D-033** gate run. No new engine behaviour.

**Files:**
- Modify: `docs/superpowers/specs/2026-09-26-edu-lead-engine-design.md` (rows C3.1–C3.6), `docs/superpowers/specs/2026-09-26-edu-lead-engine/decisions.md` (D-073…D-080), `…/current-state.md`, `…/README.md`, `AGENTS.md` ([I] row)
- Possibly modify (only per Step 2's rules): `$APP/engine/jev_questions.py` (criteria wording), `$APP/demo/saoviet/settings.json` / `DEFAULT_SETTINGS` (thresholds), `$APP/engine/eval/utterances.json` (a label that is genuinely wrong)

- [ ] **Step 1: Offline suite and live stacks**

```bash
python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3
curl -s -o /dev/null -w "crm %{http_code}\n" http://127.0.0.1:8000; curl -s -o /dev/null -w "cw %{http_code}\n" http://127.0.0.1:3000
SECRET=$(docker exec crm-frappe-1 python3 -c "import json; print(json.load(open('/home/frappe/frappe-bench/sites/crm.localhost/site_config.json'))['chatwoot_webhook_secret'])")
python scripts/test-chatwoot-crm-sync.py --secret "$SECRET" 2>&1 | tail -3
```
Expected: `OK`; `crm 200`; `cw 200` or `302`; sync test `5/5`. Never echo `$SECRET` or the Jev key.

- [ ] **Step 2: The go-live gate (D-033) against real Jev**

Run it in the background (≈104 calls, a few minutes):

```bash
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost execute mmm_custom.engine.evaluate.run" > "$SCRATCH/eval-run-1.txt" 2>&1
tail -30 "$SCRATCH/eval-run-1.txt"
docker exec crm-frappe-1 python3 -c "import json; r=json.load(open('/home/frappe/frappe-bench/sites/crm.localhost/private/files/lead_engine_eval.json'))['report']; print(json.dumps(r['act_wrong'], ensure_ascii=False, indent=1)[:6000])"
```
Expected: the per-family table, then `passed`, `critical_act_wrong`, `errors`, `items: 104`, `input_tokens`, `model`. Record all of it in the ledger (tokens included — this is the cost of one gate run).

If `passed` is false, allowed changes, each ledgered as a ruling with the item ids it fixes:
1. **Raise an act threshold** of the failing family (`catalog_act`, `choice_act`, `skill_act`) in `DEFAULT_SETTINGS` and `demo/saoviet/settings.json` — never lower one.
2. **Improve the criteria wording** in `jev_questions.py` (e.g. clearer instructions, or a skill's `jev_description`/`examples` in `bot_skills.json`), for a whole family — never special-case an utterance.
3. **Fix a label** only when a reasonable Vietnamese reader agrees the label is wrong or the item is genuinely ambiguous (then add the key to that item's `skip`); write the reason in the ruling.

Re-run at most twice (`eval-run-2.txt`, `eval-run-3.txt`); after each change run the offline suite. Whether or not the gate passes, **leave `jev_live` unchecked**: switching Jev on for real customers is the user's decision, like enabling the Agent Bot on the real inbox. The final message reports the last run's numbers, what was changed, and whether the gate passed.

- [ ] **Step 3: Live Playground scenarios with Jev**

```bash
docker exec -i crm-frappe-1 bash -c "cd frappe-bench/sites && ../env/bin/python" <<'EOF' > "$SCRATCH/c3-live.txt"
import json, frappe
frappe.init(site="crm.localhost"); frappe.connect(); frappe.set_user("Administrator")
from mmm_custom.engine import playground
SCENARIOS = {
    "multi_topic": ["autocad học phí bn, có lớp tối ko, ở thủ đức"],
    "negation": ["em muốn học excel", "à không phải excel, word cơ"],
    "no_diacritics": ["robot cho con 8 tuoi o di an"],
    "wants_human": ["cho mình nói chuyện với người thật"],
    "spam": ["Tuyển CTV bán hàng online thu nhập 20tr/tháng inbox ngay"],
    "advisor": ["mình làm văn phòng muốn nâng cao kỹ năng máy tính, nên học gì", "Cho tôi"],
}
for name, texts in SCENARIOS.items():
    playground.reset(f"c3v-{name}")
    for text in texts:
        out = playground.simulate(f"c3v-{name}", text, jev=1)
        print(name, "|", text)
        print("  jev:", out["jev"]["status"], out["jev"].get("latency_ms"), "ms", out["jev"].get("input_tokens"), "tok")
        print("  understood:", json.dumps({k: out["understanding"][k] for k in ("fills", "parents", "skills", "confirm", "intent", "hotness", "wants_human", "spam")}, ensure_ascii=False))
        print("  decision:", out["decision"]["type"], "|", out["decision"]["reason"])
        print("  reply:", out["reply"]["messages"], out["reply"]["buttons"])
    playground.reset(f"c3v-{name}")
EOF
cat "$SCRATCH/c3-live.txt"
```
Expected, per scenario (values come from real Jev, so judge the behaviour, not exact numbers): every `jev` is `ok` under 8000 ms; multi_topic answers fee and schedule for AutoCAD 2D at Thủ Đức with the evening shift; negation ends with Word filled or a Word confirmation (never Excel silently kept); no_diacritics fills Robotics, Dĩ An, child; wants_human hands off; spam is `silent` and closed; advisor recommends office courses with fees or asks the goal. A scenario that behaves wrongly is a finding: debug it (superpowers:systematic-debugging) before going on.

- [ ] **Step 4: Playground screenshots**

With the Playwright MCP tools: log in at `http://127.0.0.1:8000/login` (Administrator / admin123), open `/app/bot-playground`, tick **Use Jev**, send `autocad học phí bn, có lớp tối ko, ở thủ đức`, screenshot; then **New conversation**, send `học vẽ nhà` and screenshot the confirmation chips. Save screenshots under the repo (Playwright requires it), then move them to `$SCRATCH/c3-playground-*.png`, delete `.playwright-mcp/`, and read the images to confirm: chips render, section "2 · Jev" shows questions/answers/tokens, the reason is Vietnamese.

- [ ] **Step 5: Fresh bench (`-p crmverify`) + integration script**

```bash
cd crm/docker
docker compose -p crmverify -f docker-compose.yml -f docker-compose.override.yml -f "$SCRATCH/crmverify-ports.yml" up -d
until [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18000)" = "200" ]; do sleep 10; done   # background/Monitor, ~10–15 min
docker compose -p crmverify exec -T frappe bash -c "cd frappe-bench && bench --site crm.localhost list-apps && bench --site crm.localhost set-config chatwoot_bot_webhook_secret verify-bot-secret && bench --site crm.localhost execute mmm_custom.demo.loader.load --kwargs \"{'anchor': '2026-09-21'}\""
cd ../.. && python scripts/test-bot-conversation.py --url http://127.0.0.1:18000 --secret verify-bot-secret
```
Expected: `list-apps` shows `mmm_custom`; migrate created the new fields (the loader succeeds with `goal`/`level`, 9 slots); the script prints `5/5 passed` (Jev is off there: no key, keyword tier only — this proves the degraded mode, spec §5.3). Tear down only the verify project:

```bash
cd crm/docker && docker compose -p crmverify -f docker-compose.yml -f docker-compose.override.yml -f "$SCRATCH/crmverify-ports.yml" down -v
docker volume ls --format '{{.Name}}' | grep -E '^crm'   # crm_frappe-bench-data and crm_mariadb-data must remain
```

- [ ] **Step 6: Update the docs**

1. Spec §6.2: rows C3.1…C3.6 from `📝` to `✅` (edit those six lines only). If the gate did not pass, C3.1 stays `✅` (the set and tool exist) and add to the README position that Jev is not live because the gate failed, with the numbers.
2. `decisions.md`: append rows D-073…D-080 exactly as listed in this plan's "Design decisions" section (date 2026-09-27, status approved — the user approved the C3 work without further questions), plus any threshold/criteria change from Step 2 as its own row.
3. `current-state.md`: header "as of 2026-09-27, C1 + C2 + C3 done"; module rows for `engine/jev.py`, `jev_questions.py`, `combine.py`, `cost_guard.py`, `advisor.py`, `evaluate.py` + `eval/utterances.json`; changed rows for `understand.py` (confirmation), `decide.py` (confirm, wants_human/hot, spam close), `pipeline.py` (`understand_turn`, token accounting), `intelligence.py` (skips conversations the bot handles); new DocType fields (Bot Conversation `history`, `ai_signals`, `jev_calls`; Lead Engine Settings Jev/cost/advisor sections; Bot Slot `ask_on_demand`; AI Decision Log `jev_extra`); demo slots now 9; running config: `typesafe_api_key` present on the dev site, `jev_live` off, last gate result and date.
4. `README.md` position line: "C1, C2 and C3 done (plans `…c01-data-foundation.md`, `…c02-conversation-engine.md`, `…c03-jev-understanding.md`); Jev evaluation gate: <passed/failed, N critical act-band errors, date>; `jev_live` off until the user switches it on. C4+ not designed."
5. `AGENTS.md` repository map, row "[I] AI agents (optional)": paths add `mmm_custom/engine/jev.py`, `combine.py`, `evaluate.py`; check text becomes "Unit tests pass; `bench execute mmm_custom.engine.evaluate.run` reports the gate; with `typesafe_api_key` set, the Playground with **Use Jev** shows Jev answers, and after handoff an incoming message on a Lead's conversation updates `ai_intent`/`ai_hotness` and labels the conversation".

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/specs/2026-09-26-edu-lead-engine-design.md docs/superpowers/specs/2026-09-26-edu-lead-engine/decisions.md \
  docs/superpowers/specs/2026-09-26-edu-lead-engine/current-state.md docs/superpowers/specs/2026-09-26-edu-lead-engine/README.md AGENTS.md
git commit -m "docs(spec): mark edu lead engine C3 Jev understanding done and record the evaluation gate"
```

(Stage any Step 2 code/data changes in their own commit first: `fix(ai): tune Jev thresholds after the evaluation gate`.)

- [ ] **Step 8: Final whole-branch review**

Per the executing-plans skill: review package from the C3 plan's first commit to HEAD, reviewer on the most capable model with this plan's Review Focus verbatim; fix Critical/Important findings with RED→GREEN tests in one pass; report rulings and deferred minors.

---

## Appendix A — DocType field writer (save once as `$SCRATCH/dt.py`, not committed)

```python
"""Scratch helper: write or extend Frappe DocType folders (not committed)."""
import json
from pathlib import Path

ROOT = Path("/home/giabao/dev/dx-osd/frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype")
TS = "2026-09-26 00:00:00.000000"
FULL = {"read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1}
MANAGERS = [{"role": "System Manager", **FULL}, {"role": "Sales Manager", **FULL}]
SALES_READ = [{"role": "Sales User", "read": 1, "report": 1}]
MANAGERS_READ = [{"role": "System Manager", "read": 1, "delete": 1, "report": 1, "export": 1},
                 {"role": "Sales Manager", "read": 1, "report": 1, "export": 1}]


def field(fieldname, fieldtype, label=None, **kw):
    f = {"fieldname": fieldname, "fieldtype": fieldtype, "label": label or fieldname.replace("_", " ").title()}
    f.update(kw)
    return f


def write(name, fields, autoname=None, permissions=None, controller=None, **extra):
    snake = name.lower().replace(" ", "_")
    folder = ROOT / snake
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "__init__.py").touch()
    data = {
        "actions": [], "creation": TS, "doctype": "DocType", "engine": "InnoDB",
        "field_order": [f["fieldname"] for f in fields], "fields": fields, "links": [], "modified": TS,
        "modified_by": "Administrator", "module": "MMM Custom", "name": name, "owner": "Administrator",
        "permissions": MANAGERS + SALES_READ if permissions is None else permissions,
        "row_format": "Dynamic", "sort_field": "creation", "sort_order": "DESC", "states": [],
    }
    if autoname:
        data["autoname"] = autoname
        data["naming_rule"] = "By fieldname" if autoname.startswith("field:") else "Random"
    data.update(extra)
    (folder / f"{snake}.json").write_text(json.dumps(dict(sorted(data.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    cls = name.replace(" ", "")
    (folder / f"{snake}.py").write_text(controller or f"from frappe.model.document import Document\n\n\nclass {cls}(Document):\n\tpass\n", encoding="utf-8")


def add_fields(name, fields):
    """Append fields (skipping ones already present) to an existing DocType JSON."""
    snake = name.lower().replace(" ", "_")
    path = ROOT / snake / f"{snake}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    have = {f["fieldname"] for f in data["fields"]}
    data["fields"] += [f for f in fields if f["fieldname"] not in have]
    data["field_order"] = [f["fieldname"] for f in data["fields"]]
    data["modified"] = TS
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
```

Usage from `$SCRATCH`: `python3 -c "from dt import add_fields, field; add_fields('Bot Conversation', [field('history', 'JSON', 'Recent turns (Jev state)', read_only=1)])"` — or put a task's `add_fields(...)` calls in a small script next to `dt.py` and run it. `add_fields` skips fields that already exist, so re-running is safe.

## Appendix B — `crmverify` port override (save as `$SCRATCH/crmverify-ports.yml`)

```yaml
services:
  frappe:
    ports: !override
      - "127.0.0.1:18000:8000"
      - "127.0.0.1:19000:9000"
```

## Appendix C — Python inside the live bench

```bash
docker exec -i crm-frappe-1 bash -c "cd frappe-bench/sites && ../env/bin/python" <<'EOF'
import frappe
frappe.init(site="crm.localhost"); frappe.connect(); frappe.set_user("Administrator")
# ... snippet ...
EOF
```
