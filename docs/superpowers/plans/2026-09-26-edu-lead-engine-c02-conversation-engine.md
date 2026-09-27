# Edu Lead Engine C2 — Conversation Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Messenger customer is fully served by a data-driven bot with buttons and keywords only (no Jev yet): it answers questions from CRM data, fills the slots, writes the Lead, hands off to the right consultant with a summary, and every turn is visible in the AI Decision Log and the Playground.

**Architecture:** A new package `mmm_custom/engine/` holds the engine. The Agent Bot webhook verifies HMAC and enqueues one deduplicated job per message. The job takes a per-conversation lock and runs load → understand (keyword tier) → `decide` (pure) → act. Every side effect goes through an `Effects` object: real Chatwoot/CRM calls in production, a recorder in the Playground and in tests. All business content (slots, skills, templates, catalog, thresholds) is read from the C1 DocTypes through an immutable `Catalog` snapshot built from dataset-shaped dicts, so offline tests build it straight from `demo/saoviet/*.json`.

**Tech Stack:** Frappe v15.121 (DocTypes, `frappe.enqueue(job_id, deduplicate)`, `frappe.utils.synchronization.filelock`, hooks `doc_events`/`scheduler_events`/`jinja`, desk Page), Jinja2 sandbox, Chatwoot REST API v1 (Agent Bot), Python `unittest` + `unittest.mock` (offline, no Frappe).

**Spec:** `docs/superpowers/specs/2026-09-26-edu-lead-engine-design.md` §7.2 (Parts A, C, D; Part B keyword tier only) — binding decisions in `docs/superpowers/specs/2026-09-26-edu-lead-engine/decisions.md` (D-021…D-027, D-034…D-038, D-043, D-048…D-054, D-056…D-063).

## Global Constraints

- Code, identifiers, comments, docs in English; bot copy in Vietnamese (spec §4).
- Jev never writes text; every customer-facing sentence comes from a template + CRM data (D-003). C2 has **no Jev call at all**; `jev_status` is logged as `disabled`.
- Everything must work with no Jev key (spec §5.3).
- Messenger limits: ≤13 quick replies per message, ≤20 chars per title, 2,000 chars per message (spec §4, D-054).
- Quick-reply taps come back as the **button title**; map them exactly through `Bot Conversation.pending` (D-034).
- No edits inside vendored `crm/` or `chatwoot/`.
- Security unchanged: HMAC + 300 s anti-replay on the webhook; no secrets in git; never print `.env` or site secrets.
- Never run `docker compose down -v` on the `chatwoot`/`crm`/`dx-osd` projects; fresh-bench checks use `-p crmverify` only, removed afterwards.
- Commits: single-line conventional message, no body, no Co-Authored-By trailer; stage explicit paths only.
- Engine modules use 4-space indentation (like `bot_api.py`, `api.py`, `intelligence.py`); DocType controllers use tabs (Frappe default, like C1).
- Offline test command (the area check): `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests` — must stay green after every task.
- `SCRATCH=/tmp/claude-1000/-home-giabao-dev-dx-osd/035e8dd8-981c-46e8-98a7-2d3604765935/scratchpad` — Appendix A's DocType writer lives there (not committed).

## Design decisions made by this plan (recorded as D-068…D-072 in Task 8)

- **D-068** Choice-slot phrases of one word ("toi", "con", "sang") are matched only while that slot is the pending question; phrases of two or more words match anywhere. Folding makes "tối"/"tôi" identical, so single words out of context are too ambiguous.
- **D-069** In the keyword tier, `number` and `text` slots are filled only while pending (a `text` slot only if nothing else was understood in the message). Free-text ages/names outside the pending question are Jev's job (C3.2).
- **D-070** A returning customer's new conversation is prefilled from the Lead for every single-valued `lead_field` (branch, phone, name, learner, shift…) but never `products`: each conversation asks what the customer wants now, and new courses are appended to the Lead (D-022).
- **D-071** `recommend_courses` filters are data: `action_config` holds `top`, an optional fixed `audience`, and `audience_by_learner` (learner option value → audiences). C3.6 adds Jev scoring on top.
- **D-072** Buttons of a turn come from exactly one source, first non-empty of: action buttons (e.g. recommended courses) → the asked slot's buttons → up to 3 follow-ups of the answered skills.

## Review Focus

1. **Webhook delivered twice or concurrently** (Chatwoot retries after 5 s) → exactly one reply: RQ `deduplicate` + per-conversation lock + `last_message_id` check. Pinned by `test_engine_pipeline.TestRunTurn.test_redelivered_message_is_ignored` (Task 1).
2. **Chatwoot unreachable or rejecting a call mid-turn** → the turn still saves state, logs the error, and never raises into RQ (a raise would retry and double-send). Pinned by `test_send_failure_is_recorded_and_state_saved` (Task 1) and `test_handoff_step_failure_does_not_stop_others` (Task 6).
3. **Template referring to data the turn does not have** (no course yet, missing key) → never shows `{{ … }}`; the fallback wording goes out and a `render_error` is recorded. Pinned by `test_engine_reply.test_missing_course_uses_fallback_and_records_error` (Task 3).
4. **Too many / too long / duplicate button titles** → ≤13 unique titles, each ≤20 chars. Pinned by `test_engine_reply.test_buttons_are_unique_capped_and_truncated` (Task 3).
5. **Returning customer whose Lead holds values outside the catalog** (old `CS1 Bình Thạnh` branch, placeholder name) → those are not prefilled and the bot asks. Pinned by `test_engine_lead.test_prefill_skips_values_outside_catalog` (Task 4).

## File map

| Path | Task | Responsibility |
|---|---|---|
| `mmm_custom/engine/__init__.py` | 1 | Package marker |
| `mmm_custom/engine/catalog.py` | 1 | Immutable snapshot of catalog + slots + skills + settings; `build_catalog(dataset_dict)` |
| `mmm_custom/engine/state.py` | 1 | `ConversationState` + `value()`/`filled()` helpers |
| `mmm_custom/engine/understand.py` | 1, 2 | `Understanding` dataclass (1); keyword tier + exact button mapping (2) |
| `mmm_custom/engine/decide.py` | 1 | Pure `decide()` → `Decision` |
| `mmm_custom/engine/reply.py` | 1, 2, 3 | `Reply`, message splitting, buttons; `compose()` (full in 3) |
| `mmm_custom/engine/effects.py` | 1, 4, 6 | `RecordingEffects`, `ChatwootEffects` |
| `mmm_custom/engine/events.py` | 1 | `lead_engine_events` hook dispatch (D-036) |
| `mmm_custom/engine/pipeline.py` | 1, 3–6 | `parse_event`, `run_turn`, `process_event` (RQ job) |
| `mmm_custom/engine/repo.py` | 1, 3–6 | Frappe data access: catalog rows (cached), state, schedules, promotions, Lead writes, consultants, logs |
| `mmm_custom/engine/text.py` | 2 | Diacritic folding, whole-word phrase search, VN phone |
| `mmm_custom/engine/slot_types.py` | 2 | Slot-type registry: understand + buttons per type |
| `mmm_custom/engine/render.py` | 3 | Render guard, `vnd`/`date_vi` filters, renderers |
| `mmm_custom/engine/context.py` | 3 | Template context contract (D-050) |
| `mmm_custom/engine/actions.py` | 3 | Action registry (D-049) |
| `mmm_custom/engine/lead.py` | 4 | Slots ↔ Lead field mapping, prefill (pure) |
| `mmm_custom/engine/log.py` | 5 | Decision-log row + learning signals (pure), retention purge |
| `mmm_custom/engine/learning.py` | 5 | `consultant_corrected` capture on CRM Lead update |
| `mmm_custom/engine/routing.py` | 6 | C2.6 consultant pick (pure) |
| `mmm_custom/engine/handoff.py` | 6 | Handoff plan: consultant, team, labels, attributes, summary |
| `mmm_custom/engine/chatwoot_setup.py` | 6 | Chatwoot conversation custom-attribute definitions for slots |
| `mmm_custom/engine/playground.py` | 7 | Whitelisted `simulate`/`reset`/`replay` + pure `inspect` |
| `mmm_custom/mmm_custom/page/bot_playground/` | 7 | Desk page `/app/bot-playground` |
| DocTypes `bot_conversation` (1), `ai_decision_log` + `bot_learning_signal` (5); `lead_engine_settings` fields (3, 5, 6) | | |
| `bot_api.py` | 1, 6 | Webhook: verify → classify → enqueue / silence rules |
| `api.py` | 4 | Sync webhook detects courses from the catalog, writes `products` |
| `setup.py` | 4 | CRM Lead slot fields in `CATALOG_FIELDS` |
| `chatwoot_client.py` | 6 | `assign_team`, `set_conversation_attributes`, custom-attribute definitions |
| `hooks.py` | 1, 3, 5 | `doc_events`, `jinja` filters, daily purge |
| `demo/saoviet/bot_skills.json`, `settings.json` | 3, 6 | Data fixes + new settings values |
| `bot_engine.py`, `tests/test_bot_engine.py` | 2 | Deleted (replaced by the engine) |
| `scripts/test-bot-conversation.py` | 8 | Signed-webhook integration check (D-062) |
| `tests/engine_fixtures.py` | 1+ | Demo catalog + in-memory `FakeRepo` |

All `mmm_custom/…` paths are under `frappe-custom/mmm_custom/mmm_custom/`; tests under `frappe-custom/mmm_custom/mmm_custom/tests/`. Below, `APP=frappe-custom/mmm_custom/mmm_custom` and `T=$APP/tests`.

## Appendix A — DocType writer (save once as `$SCRATCH/dt.py`, not committed)

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

Run a writer step as: `python3 - <<'EOF'` → `import sys; sys.path.insert(0, "$SCRATCH"); from dt import *` → calls → `EOF` (expand `$SCRATCH` yourself; heredocs with `'EOF'` do not).

---

### Task 1: C2.1 — Bot Conversation, async pipeline, decide, Effects, events

Implements layer **C2.1** (D-024, D-025, D-036, D-059 first half, D-060 Effects, D-063). Out of scope here: keyword understanding (Task 2), skill answers (Task 3), Lead writes (Task 4), log (Task 5), handoff side effects and silence on agent messages (Task 6).

**Files:**
- Create: `$APP/engine/__init__.py`, `catalog.py`, `state.py`, `understand.py`, `decide.py`, `reply.py`, `effects.py`, `events.py`, `pipeline.py`, `repo.py` (all under `$APP/engine/`)
- Create: DocType `Bot Conversation` (`$APP/mmm_custom/doctype/bot_conversation/`)
- Modify: `$APP/bot_api.py` (whole file), `$APP/hooks.py` (after `after_migrate`)
- Create tests: `$T/engine_fixtures.py`, `$T/test_engine_catalog.py`, `$T/test_engine_decide.py`, `$T/test_engine_pipeline.py`
- Replace tests: `$T/test_bot_api.py`
- Modify tests: `$T/test_doctype_json.py` (expected list)

**Interfaces:**
- Consumes: C1 dataset shape (`mmm_custom.demo.loader.load_dataset()` → keys `areas`, `course_groups`, `courses`, `bot_slots`, `bot_skills`, `settings`, …), `mmm_custom.demo.loader.map_url(address)`, `ChatwootClient.send_message/send_quick_replies`.
- Produces:
  - `catalog.build_catalog(data: dict) -> Catalog`; `Catalog.slot(key)`, `.slot_for(source)`, `.courses_in(group)`, `.branches_in(area)`, `.parent_of(slot, value)`; dataclasses `Option, Slot, Group, Course, Area, Branch, Template, FollowUp, Skill`; `DEFAULT_SETTINGS`.
  - `state.ConversationState`, `state.value(slots, key)`, `state.filled(slots, key)`.
  - `understand.Understanding` (fields `fills, parents, ambiguous, skipped, skills, handoff, focus, tapped, matches, spans, unmatched`), `understand.understand(text, state, catalog) -> Understanding`.
  - `decide.Decision`, `decide.decide(state, u, catalog) -> Decision`, `decide.slot_active`, `decide.required_filled`.
  - `reply.Reply` (`messages, buttons, variants, attachments, errors`, `.options()`), `reply.split_messages`, `reply.add_buttons`, `reply.compose(decision, state, catalog, render)`.
  - `effects.RecordingEffects` (`calls`, `.of(kind)`, `send`, `emit`), `effects.ChatwootEffects(bot, user)`, `effects.chatwoot_effects(conf)`.
  - `events.emit(event, payload, get_hooks=None, get_attr=None, log_error=None)`.
  - `pipeline.Event`, `pipeline.Turn`, `pipeline.parse_event(payload) -> Event`, `pipeline.run_turn(event, repo, effects, render) -> Turn | None`, `pipeline.process_event(payload)`.
  - `repo.FrappeRepo(sandbox=False, sandbox_lead=None)` with `catalog()`, `load_state(event)`, `save_state(state)`; `repo.load_rows()`, `repo.load_catalog()`, `repo.clear_catalog_cache(doc=None, method=None)`.

- [ ] **Step 1: Write the fixtures and failing tests**

`$T/engine_fixtures.py`:

```python
"""Shared offline fixtures for the lead-engine tests: the demo catalog and in-memory fakes."""

import copy
import sys
from datetime import date
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import jinja2
import jinja2.sandbox

from mmm_custom.demo.loader import load_dataset
from mmm_custom.engine.catalog import build_catalog
from mmm_custom.engine.state import ConversationState

_ENV = jinja2.sandbox.SandboxedEnvironment(undefined=jinja2.DebugUndefined)


def render(template, context):
    return _ENV.from_string(template).render(context)


def demo_catalog(**settings):
    data = load_dataset()
    data["settings"] = {**data["settings"], **settings}
    return build_catalog(data)


def fill(value, source="keyword"):
    return {"value": value, "source": source, "confidence": 1.0}


class FakeRepo:
    """In-memory stand-in for engine.repo.FrappeRepo."""

    def __init__(self, catalog, today=date(2026, 9, 28)):
        self._catalog, self._today = catalog, today
        self.states = {}
        self.prefill = {}

    def catalog(self):
        return self._catalog

    def today(self):
        return self._today

    def load_state(self, event):
        if event.conversation_id in self.states:
            return copy.deepcopy(self.states[event.conversation_id])
        return ConversationState(conversation_id=event.conversation_id,
                                 contact_id=str(event.contact.get("id") or ""), slots=copy.deepcopy(self.prefill))

    def save_state(self, state):
        self.states[state.conversation_id] = copy.deepcopy(state)
```

`$T/test_engine_catalog.py`:

```python
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog

from mmm_custom.engine.catalog import build_catalog


class TestBuildCatalog(unittest.TestCase):
    def setUp(self):
        self.cat = demo_catalog()

    def test_counts_match_demo_dataset(self):
        self.assertEqual((len(self.cat.groups), len(self.cat.courses), len(self.cat.areas), len(self.cat.branches)),
                         (8, 46, 4, 13))
        self.assertEqual(len(self.cat.skills), 30)

    def test_slots_sorted_with_dependency(self):
        self.assertEqual([s.key for s in self.cat.slots],
                         ["course", "branch", "learner", "learner_age", "preferred_shift", "customer_name", "phone"])
        self.assertEqual(self.cat.slot("learner_age").depends_on, ("learner", "child"))
        self.assertEqual(self.cat.slot("learner").option("child").button, "Cho con em")

    def test_branch_fields_and_map_url(self):
        b = self.cat.branches["CN Dĩ An"]
        self.assertEqual((b.area, b.button, b.tier), ("Bình Dương", "Dĩ An", "standard"))
        self.assertTrue(b.map_url.startswith("https://www.google.com/maps/search/"))
        self.assertIn("di an", b.aliases)

    def test_course_and_parent_lookup(self):
        c = self.cat.courses["VP-EXCEL"]
        self.assertEqual((c.group, c.fee, c.button), ("Tin học văn phòng", 1800000.0, "Excel"))
        self.assertEqual(c.next_courses, ("VP-EXCEL-NC", "VP-MOS"))
        self.assertEqual(self.cat.parent_of(self.cat.slot("course"), "VP-EXCEL"), "Tin học văn phòng")
        self.assertEqual(self.cat.parent_of(self.cat.slot("branch"), "CN Dĩ An"), "Bình Dương")
        self.assertEqual(self.cat.slot_for("branch").key, "branch")
        self.assertEqual(len(self.cat.courses_in("Kế toán")), 5)
        self.assertEqual(len(self.cat.branches_in("Bình Dương")), 4)

    def test_skill_fields(self):
        s = self.cat.skills["schedule_lookup"]
        self.assertEqual((s.action, s.params, s.config), ("schedule_lookup", ("course",), {"limit": 3}))
        self.assertEqual([t.key for t in s.templates], ["default", "none"])
        self.assertEqual(s.follow_ups[0].target, "fee_quote")

    def test_settings_defaults_fill_gaps_but_zero_and_empty_do_not_override(self):
        self.assertEqual(self.cat.settings["max_skills_per_reply"], 3)
        self.assertEqual(demo_catalog(max_skills_per_reply=0).settings["max_skills_per_reply"], 3)
        self.assertEqual(demo_catalog(max_skills_per_reply=2).settings["max_skills_per_reply"], 2)
        self.assertEqual(self.cat.settings["brand_name"], "Tin Học Sao Việt")

    def test_inactive_rows_are_left_out(self):
        cat = build_catalog({"bot_slots": [
            {"slot_key": "a", "label": "A", "slot_type": "text", "active": 0},
            {"slot_key": "b", "label": "B", "slot_type": "text"}]})
        self.assertEqual([s.key for s in cat.slots], ["b"])


if __name__ == "__main__":
    unittest.main()
```

`$T/test_engine_decide.py`:

```python
import sys
from dataclasses import replace
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, fill

from mmm_custom.engine.decide import decide
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding

CAT = demo_catalog()


def state(**kw):
    return ConversationState(conversation_id="1", **kw)


class TestDecide(unittest.TestCase):
    def test_first_message_not_understood_greets_and_asks_course(self):
        d = decide(state(), Understanding(), CAT)
        self.assertEqual((d.type, d.ask, d.greet, d.fallback, d.stuck_turns), ("ask_slot", "course", True, False, 0))
        self.assertEqual(d.slots["course"]["asked"], 1)

    def test_course_filled_asks_branch_and_records_parent(self):
        d = decide(state(turns=1), Understanding(fills={"course": fill("VP-EXCEL")}), CAT)
        self.assertEqual((d.type, d.ask, d.new_slots), ("ask_slot", "branch", ["course"]))
        self.assertEqual(d.slots["course"]["parent"], "Tin học văn phòng")
        self.assertFalse(d.greet)

    def test_required_slots_filled_hands_off(self):
        u = Understanding(fills={"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An"), "phone": fill("+84901234567")})
        d = decide(state(), u, CAT)
        self.assertEqual((d.type, d.handoff_reason), ("handoff", "required_filled"))

    def test_stuck_turns_hand_off(self):
        d = decide(state(turns=3, stuck_turns=1), Understanding(), CAT)
        self.assertEqual((d.type, d.handoff_reason, d.stuck_turns), ("handoff", "stuck", 2))

    def test_unclear_later_turn_uses_fallback_and_counts_stuck(self):
        d = decide(state(turns=2), Understanding(), CAT)
        self.assertEqual((d.type, d.fallback, d.stuck_turns), ("ask_slot", True, 1))

    def test_skill_with_params_answers_and_asks_next(self):
        u = Understanding(fills={"course": fill("VP-EXCEL")}, skills=["fee_quote"])
        d = decide(state(turns=1), u, CAT)
        self.assertEqual((d.type, d.skills, d.ask, d.pending_skill), ("answer", ["fee_quote"], "branch", ""))

    def test_skill_missing_param_is_remembered_then_answered(self):
        d = decide(state(turns=1), Understanding(skills=["fee_quote"]), CAT)
        self.assertEqual((d.type, d.pending_skill, d.ask), ("ask_slot", "fee_quote", "course"))
        d2 = decide(state(turns=2, pending_skill="fee_quote"), Understanding(fills={"course": fill("VP-EXCEL")}), CAT)
        self.assertEqual((d2.type, d2.skills, d2.pending_skill), ("answer", ["fee_quote"], ""))

    def test_waiting_skill_param_is_asked_first(self):
        cat = demo_catalog()
        cat.skills["branch_info"] = replace(cat.skills["branch_info"], params=("branch",))
        d = decide(state(turns=1), Understanding(skills=["branch_info"]), cat)
        self.assertEqual((d.ask, d.pending_skill), ("branch", "branch_info"))

    def test_skill_count_is_capped_and_ordered(self):
        cat = demo_catalog(max_skills_per_reply=2)
        keys = ["payment", "hotline", "shifts"]
        d = decide(state(turns=1), Understanding(skills=keys), cat)
        expected = sorted(keys, key=lambda k: cat.skills[k].order)[:2]
        self.assertEqual(d.skills, expected)

    def test_handoff_skill_and_button(self):
        self.assertEqual(decide(state(turns=1), Understanding(skills=["talk_to_human"]), CAT).handoff_reason, "skill")
        self.assertEqual(decide(state(turns=1), Understanding(handoff=True), CAT).handoff_reason, "button")

    def test_silent_when_consultant_replied_or_closed(self):
        self.assertEqual(decide(state(consultant_replied=True), Understanding(skills=["hotline"]), CAT).type, "silent")
        self.assertEqual(decide(state(status="closed"), Understanding(skills=["hotline"]), CAT).type, "silent")

    def test_after_handoff_only_skills_are_answered(self):
        self.assertEqual(decide(state(status="handed_off", turns=4), Understanding(), CAT).type, "silent")
        d = decide(state(status="handed_off", turns=4), Understanding(skills=["hotline"]), CAT)
        self.assertEqual((d.type, d.skills, d.ask), ("answer", ["hotline"], ""))

    def test_parent_change_drops_course_of_other_group(self):
        s = state(turns=2, slots={"course": {**fill("VP-EXCEL"), "parent": "Tin học văn phòng"}})
        d = decide(s, Understanding(parents={"course": "Thiết kế đồ họa"}), CAT)
        self.assertNotIn("value", d.slots["course"])
        self.assertEqual((d.slots["course"]["parent"], d.ask), ("Thiết kế đồ họa", "course"))

    def test_ambiguous_values_become_candidates(self):
        d = decide(state(turns=1), Understanding(ambiguous={"course": ["DH-AI", "DH-PTS"]}), CAT)
        self.assertEqual(d.slots["course"]["candidates"], ["DH-AI", "DH-PTS"])
        self.assertEqual(d.stuck_turns, 0)

    def test_optional_slot_asked_once_and_dependency_respected(self):
        slots = {"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An"), "learner": {"asked": 1}}
        d = decide(state(turns=3, slots=slots), Understanding(), CAT)
        self.assertEqual(d.ask, "preferred_shift")
        d2 = decide(state(turns=3, slots={**slots, "learner": fill("child")}), Understanding(), CAT)
        self.assertEqual(d2.ask, "learner_age")

    def test_focus_asks_that_slot(self):
        d = decide(state(turns=1), Understanding(focus="preferred_shift"), CAT)
        self.assertEqual(d.ask, "preferred_shift")


if __name__ == "__main__":
    unittest.main()
```

`$T/test_engine_pipeline.py`:

```python
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, fill, render

from mmm_custom.engine import events
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import Event, parse_event, run_turn
from mmm_custom.engine.understand import Understanding

CAT = demo_catalog()


def incoming(text="xin chào", message_id=5, conversation_id=7, contact_id=9):
    return {"event": "message_created", "id": message_id, "content": text, "message_type": "incoming",
            "private": False, "sender": {"id": contact_id, "name": "Lan", "type": "contact"},
            "conversation": {"id": conversation_id, "inbox_id": 3,
                             "meta": {"sender": {"id": contact_id, "name": "Lan", "custom_attributes": {}}}}}


class TestParseEvent(unittest.TestCase):
    def test_customer_message(self):
        e = parse_event(incoming())
        self.assertEqual((e.kind, e.conversation_id, e.message_id, e.text, e.contact["id"], e.inbox_id),
                         ("customer_message", "7", 5, "xin chào", 9, "3"))

    def test_text_is_capped(self):
        self.assertEqual(len(parse_event(incoming("a" * 5000)).text), 1000)

    def test_agent_bot_and_private_and_activity_are_ignored(self):
        own = {**incoming(), "message_type": "outgoing", "sender": {"id": 1, "type": "agent_bot"}}
        note = {**incoming(), "message_type": "outgoing", "private": True, "sender": {"id": 2, "type": "user"}}
        activity = {**incoming(), "message_type": "activity"}
        for payload in (own, note, activity):
            self.assertEqual(parse_event(payload).kind, "ignore")

    def test_human_agent_message(self):
        e = parse_event({**incoming(), "message_type": "outgoing", "sender": {"id": 2, "type": "user"}})
        self.assertEqual((e.kind, e.conversation_id), ("agent_message", "7"))

    def test_resolved(self):
        self.assertEqual(parse_event({"event": "conversation_resolved", "id": 7}).kind, "resolved")
        self.assertEqual(parse_event({"event": "conversation_status_changed", "id": 7, "status": "resolved"}).kind, "resolved")
        self.assertEqual(parse_event({"event": "conversation_status_changed", "id": 7, "status": "open"}).kind, "ignore")


class TestRunTurn(unittest.TestCase):
    def setUp(self):
        self.repo, self.fx = FakeRepo(CAT), RecordingEffects()

    def turn(self, text="xin chào", message_id=5):
        return run_turn(parse_event(incoming(text, message_id)), self.repo, self.fx, render)

    def test_first_message_greets_asks_and_saves_state(self):
        t = self.turn()
        sent = self.fx.of("send")
        self.assertEqual(len(sent), 1)
        self.assertIn("Trợ lý Sao Việt", sent[0]["messages"][0])
        self.assertIn("Anh/chị quan tâm khóa học nào ạ?", sent[0]["messages"][0])
        saved = self.repo.states["7"]
        self.assertEqual((saved.last_message_id, saved.turns, saved.pending["slot"]), (5, 1, "course"))
        self.assertEqual(t.decision.type, "ask_slot")

    def test_redelivered_message_is_ignored(self):
        self.turn()
        self.assertIsNone(self.turn())
        self.assertEqual(len(self.fx.of("send")), 1)

    def test_send_failure_is_recorded_and_state_saved(self):
        fx = RecordingEffects()
        fx.send = MagicMock(side_effect=RuntimeError("chatwoot down"))
        t = run_turn(parse_event(incoming()), self.repo, fx, render)
        self.assertEqual(t.reply.errors[0]["type"], "send_failed")
        self.assertEqual(self.repo.states["7"].last_message_id, 5)

    def test_events_for_filled_slots(self):
        with patch("mmm_custom.engine.pipeline.understand", return_value=Understanding(fills={"course": fill("VP-EXCEL")})):
            self.turn("excel")
        emitted = self.fx.of("emit")
        self.assertEqual(emitted[0]["event"], "slot_filled")
        self.assertEqual((emitted[0]["slot"], emitted[0]["value"]), ("course", "VP-EXCEL"))

    def test_handoff_changes_status_and_emits(self):
        with patch("mmm_custom.engine.pipeline.understand", return_value=Understanding(handoff=True)):
            self.turn("gặp tư vấn viên")
        self.assertEqual(self.repo.states["7"].status, "handed_off")
        self.assertIn("handed_off", [e["event"] for e in self.fx.of("emit")])


class TestEvents(unittest.TestCase):
    def test_handlers_receive_payload_and_failures_are_logged(self):
        got, log = [], MagicMock()

        def boom(payload):
            raise RuntimeError("x")

        attrs = {"a.ok": got.append, "a.boom": boom}
        events.emit("handed_off", {"lead": "L1"}, get_hooks=lambda name: {"handed_off": ["a.boom", "a.ok"]},
                    get_attr=attrs.__getitem__, log_error=log)
        self.assertEqual(got, [{"event": "handed_off", "lead": "L1"}])
        log.assert_called_once()

    def test_no_hooks_registered(self):
        events.emit("slot_filled", {}, get_hooks=lambda name: [], get_attr=None, log_error=None)


if __name__ == "__main__":
    unittest.main()
```

`$T/test_bot_api.py` (replace the whole file):

```python
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
import unittest
from unittest.mock import MagicMock

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import mmm_custom.bot_api as bot_api_mod
from mmm_custom.bot_api import agent_bot_webhook

SECRET = "bot-secret"


def sign(secret, ts, body):
    return "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


def incoming(message_type="incoming", sender_type="contact", private=False, message_id=77):
    return {"event": "message_created", "id": message_id, "content": "xin chào", "message_type": message_type,
            "private": private, "sender": {"id": 9, "type": sender_type},
            "conversation": {"id": 5, "meta": {"sender": {"id": 9, "name": "Lan"}}}}


class TestAgentBotWebhook(unittest.TestCase):
    def setUp(self):
        self.fr = bot_api_mod.frappe
        self.fr.conf = {"chatwoot_bot_webhook_secret": SECRET}
        self.fr.enqueue = MagicMock()

    def post(self, payload, secret=SECRET, ts=None, raw=None):
        body = raw if raw is not None else json.dumps(payload).encode()
        ts = ts or str(int(time.time()))
        req = MagicMock()
        req.headers = {"X-Chatwoot-Timestamp": ts, "X-Chatwoot-Signature": sign(secret, ts, body)}
        req.get_data.return_value = body
        self.fr.request = req
        return agent_bot_webhook()

    def test_missing_secret_is_rejected(self):
        self.fr.conf = {}
        with self.assertRaises(self.fr.AuthenticationError):
            self.post(incoming())

    def test_bad_signature_is_rejected(self):
        with self.assertRaises(self.fr.AuthenticationError):
            self.post(incoming(), secret="wrong")

    def test_stale_timestamp_is_rejected(self):
        with self.assertRaises(self.fr.AuthenticationError):
            self.post(incoming(), ts=str(int(time.time()) - 600))

    def test_customer_message_is_enqueued_once_per_message_id(self):
        payload = incoming()
        self.assertEqual(self.post(payload), {"status": "queued"})
        self.fr.enqueue.assert_called_once_with("mmm_custom.engine.pipeline.process_event", queue="short",
                                                job_id="lead_engine_msg_77", deduplicate=True, payload=payload)

    def test_bot_own_message_and_private_note_are_not_enqueued(self):
        self.post(incoming(message_type="outgoing", sender_type="agent_bot"))
        self.post(incoming(message_type="outgoing", sender_type="user", private=True))
        self.fr.enqueue.assert_not_called()

    def test_invalid_json(self):
        self.assertEqual(self.post(None, raw=b"{not json")["status"], "error")


if __name__ == "__main__":
    unittest.main()
```

In `$T/test_doctype_json.py`, extend the tuple in `test_expected_doctypes_present` with `"Bot Conversation"` (the tuple ends `…, "Bot Skill Follow Up", "Lead Engine Settings", "Bot Conversation"):`).

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -5`
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'mmm_custom.engine'` in the engine tests, `test_bot_api` errors, `Bot Conversation` missing in `test_doctype_json`.

- [ ] **Step 3: Write the engine core**

`$APP/engine/__init__.py`: empty file.

`$APP/engine/catalog.py`:

```python
"""Read-only snapshot of the lead-engine data: catalog, bot slots, bot skills and settings.

`build_catalog` takes plain dicts shaped like the demo dataset (`mmm_custom/demo/saoviet/*.json`);
tests build it offline from those files and `engine.repo` builds the same shape from the database.
"""

from dataclasses import dataclass, field

from mmm_custom.demo.loader import map_url

# Used when Lead Engine Settings leaves a field empty (Frappe stores unset Int as 0).
DEFAULT_SETTINGS = {
    "brand_name": "", "bot_name": "", "address_customer": "anh/chị", "address_self": "em",
    "hotline": "", "zalo": "", "website": "", "email": "", "signoff": "",
    "greeting_template": "", "fallback_template": "", "handoff_template": "", "summary_template": "",
    "max_skills_per_reply": 3, "max_stuck_turns": 2, "log_retention_days": 180,
}


def _aliases(text):
    return tuple(a.strip() for a in (text or "").split(",") if a.strip())


@dataclass(frozen=True)
class Option:
    value: str
    label: str
    button: str
    aliases: tuple = ()


@dataclass(frozen=True)
class Slot:
    key: str
    label: str
    type: str
    source: str = ""
    required: bool = False
    order: int = 0
    ask_template: str = ""
    options: tuple = ()
    depends_on: tuple = ()  # (slot_key, value) or ()
    lead_field: str = ""

    def option(self, value):
        return next((o for o in self.options if o.value == value), None)


@dataclass(frozen=True)
class Group:
    name: str
    button: str
    emoji: str = ""
    order: int = 0
    aliases: tuple = ()


@dataclass(frozen=True)
class Course:
    code: str
    name: str
    button: str
    group: str
    fee: float = 0.0
    duration: str = ""
    audience: str = ""
    min_age: int = 0
    max_age: int = 0
    certificate: str = ""
    offer: str = "all"
    aliases: tuple = ()
    next_courses: tuple = ()
    image: str = ""


@dataclass(frozen=True)
class Area:
    name: str
    button: str
    aliases: tuple = ()


@dataclass(frozen=True)
class Branch:
    name: str
    button: str
    area: str
    code: str = ""
    tier: str = "standard"
    address: str = ""
    hotline: str = ""
    map_url: str = ""
    aliases: tuple = ()


@dataclass(frozen=True)
class Template:
    key: str
    when: str
    text: str


@dataclass(frozen=True)
class FollowUp:
    title: str
    target_type: str
    target: str = ""


@dataclass(frozen=True)
class Skill:
    key: str
    title: str
    action: str
    params: tuple = ()
    aliases: tuple = ()
    missing_policy: str = "ask"
    config: dict = field(default_factory=dict)
    templates: tuple = ()
    follow_ups: tuple = ()
    creates_lead: bool = True
    handoff_after: bool = False
    order: int = 0
    media: str = ""


@dataclass
class Catalog:
    groups: dict
    courses: dict
    areas: dict
    branches: dict
    slots: list
    skills: dict
    settings: dict

    def slot(self, key):
        return next((s for s in self.slots if s.key == key), None)

    def slot_for(self, source):
        """The catalog slot holding courses ("course") or branches ("branch"), if configured."""
        return next((s for s in self.slots if s.type == "catalog" and s.source == source), None)

    def courses_in(self, group):
        return [c for c in self.courses.values() if c.group == group]

    def branches_in(self, area):
        return [b for b in self.branches.values() if b.area == area]

    def parent_of(self, slot, value):
        if slot.source == "course" and value in self.courses:
            return self.courses[value].group
        if slot.source == "branch" and value in self.branches:
            return self.branches[value].area
        return ""


def _active(row):
    return row.get("active", 1) not in (0, "0", False)


def _int(value):
    return int(value or 0)


def build_catalog(data):
    groups = {g["group_name"]: Group(g["group_name"], g.get("button_label") or g["group_name"], g.get("emoji") or "",
                                     _int(g.get("sort_order")), _aliases(g.get("aliases")))
              for g in sorted(data.get("course_groups") or [], key=lambda g: _int(g.get("sort_order")))}
    courses = {c["product_code"]: Course(
        code=c["product_code"], name=c["product_name"], button=c.get("button_label") or c["product_name"],
        group=c.get("course_group") or "", fee=float(c.get("standard_rate") or 0),
        duration=c.get("duration_text") or "", audience=c.get("audience") or "",
        min_age=_int(c.get("min_age")), max_age=_int(c.get("max_age")), certificate=c.get("certificate") or "",
        offer=c.get("offer") or "all", aliases=_aliases(c.get("aliases")),
        next_courses=tuple(c.get("next_courses") or ()), image=c.get("image") or "")
        for c in data.get("courses") or [] if _active(c)}
    areas, branches = {}, {}
    for a in (data.get("areas") or {}).get("areas", []):
        areas[a["territory_name"]] = Area(a["territory_name"], a.get("button_label") or a["territory_name"],
                                          _aliases(a.get("aliases")))
        for b in a.get("branches", []):
            address = b.get("address") or ""
            branches[b["territory_name"]] = Branch(
                name=b["territory_name"], button=b.get("button_label") or b["territory_name"], area=a["territory_name"],
                code=b.get("branch_code") or "", tier=b.get("tier") or "standard", address=address,
                hotline=b.get("hotline") or "", map_url=b.get("map_url") or (map_url(address) if address else ""),
                aliases=_aliases(b.get("aliases")))
    slots = sorted((Slot(
        key=s["slot_key"], label=s["label"], type=s["slot_type"], source=s.get("catalog_source") or "",
        required=bool(s.get("required")), order=_int(s.get("sort_order")), ask_template=s.get("ask_template") or "",
        options=tuple(Option(o["value"], o["label"], o.get("button_label") or o["label"], _aliases(o.get("aliases")))
                      for o in s.get("options") or ()),
        depends_on=(s["depends_on_slot"], s.get("depends_on_value") or "") if s.get("depends_on_slot") else (),
        lead_field=s.get("lead_field") or "")
        for s in data.get("bot_slots") or [] if _active(s)), key=lambda s: s.order)
    skills = {k["skill_key"]: Skill(
        key=k["skill_key"], title=k["title"], action=k["action_type"], params=tuple(k.get("parameters") or ()),
        aliases=_aliases(k.get("aliases")), missing_policy=k.get("missing_policy") or "ask",
        config=dict(k.get("action_config") or {}),
        templates=tuple(Template(t["variant_key"], t.get("when") or "", t["template"]) for t in k.get("templates") or ()),
        follow_ups=tuple(FollowUp(f["title"], f["target_type"], f.get("target") or "") for f in k.get("follow_ups") or ()),
        creates_lead=bool(k.get("creates_lead", 1)), handoff_after=bool(k.get("handoff_after")),
        order=_int(k.get("sort_order")), media=k.get("media") or "")
        for k in data.get("bot_skills") or [] if _active(k)}
    settings = dict(DEFAULT_SETTINGS)
    settings.update({k: v for k, v in (data.get("settings") or {}).items() if v not in (None, "", 0)})
    return Catalog(groups, courses, areas, branches, slots, skills, settings)
```

`$APP/engine/state.py`:

```python
"""Per-conversation bot state (the `Bot Conversation` DocType, D-024) as a plain object.

`slots` maps slot_key → entry dict: `value` (when filled), `source` (button / keyword / jev / lead /
contact), `confidence`, and bookkeeping keys `parent` (chosen course group / area), `candidates`
(ambiguous values), `asked`, `skipped`. `pending` holds the question being asked and the offered
buttons as title → action (D-034).
"""

from dataclasses import dataclass, field


@dataclass
class ConversationState:
    conversation_id: str
    contact_id: str = ""
    inbox_id: str = ""
    lead: str = ""
    status: str = "active"  # active | handed_off | closed
    slots: dict = field(default_factory=dict)
    pending: dict = field(default_factory=dict)
    pending_skill: str = ""
    stuck_turns: int = 0
    last_message_id: int = 0
    consultant_replied: bool = False
    consultant: str = ""
    is_sandbox: bool = False
    is_returning: bool = False
    turns: int = 0


def value(slots, key):
    return (slots.get(key) or {}).get("value")


def filled(slots, key):
    return value(slots, key) not in (None, "")
```

`$APP/engine/understand.py` (the keyword tier arrives in Task 2):

```python
"""What a customer message says, as data for decide(): filled slots, chosen parents, skills."""

from dataclasses import dataclass, field


@dataclass
class Understanding:
    fills: dict = field(default_factory=dict)      # slot_key -> {"value", "source", "confidence"}
    parents: dict = field(default_factory=dict)    # slot_key -> chosen course group / area
    ambiguous: dict = field(default_factory=dict)  # slot_key -> [candidate values]
    skipped: list = field(default_factory=list)    # optional slots the customer skipped
    skills: list = field(default_factory=list)     # skill keys, in the order they appeared
    handoff: bool = False                          # a "talk to a person" button was tapped
    focus: str = ""                                # a follow-up button asked for this slot
    tapped: bool = False                           # the message was a quick-reply tap
    matches: list = field(default_factory=list)    # what matched, for the decision log
    spans: list = field(default_factory=list)      # (start, end) of matched phrases in the folded text
    unmatched: list = field(default_factory=list)  # content words that matched nothing


def understand(text, state, catalog):
    return Understanding()
```

`$APP/engine/decide.py`:

```python
"""decide(): the pure heart of a bot turn (D-025) — no I/O, offline-testable.

Given the conversation state, what the message was understood to say, and the catalog, return one
Decision: answer skill(s) (and ask the next slot), ask the next missing slot, hand off, or stay silent.
"""

import copy
from dataclasses import dataclass, field

from mmm_custom.engine.state import filled, value

HANDOFF_REASONS = {
    "button": "Khách chọn gặp tư vấn viên",
    "skill": "Câu hỏi cần tư vấn viên xử lý",
    "required_filled": "Đã đủ thông tin bắt buộc",
    "stuck": "Bot chưa hiểu khách nhiều lượt liên tiếp",
}


@dataclass
class Decision:
    type: str                                   # answer | ask_slot | handoff | silent
    slots: dict = field(default_factory=dict)   # slots after this turn
    new_slots: list = field(default_factory=list)
    skills: list = field(default_factory=list)  # skill keys to answer, in reply order
    ask: str = ""                               # slot whose question ends the reply
    greet: bool = False
    fallback: bool = False
    handoff_reason: str = ""                    # button | skill | required_filled | stuck
    pending_skill: str = ""
    stuck_turns: int = 0
    reason: str = ""


def slot_active(slot, slots):
    return not slot.depends_on or value(slots, slot.depends_on[0]) == slot.depends_on[1]


def required_filled(slots, catalog):
    return all(filled(slots, s.key) for s in catalog.slots if s.required and slot_active(s, slots))


def merge(slots, u, catalog):
    """Apply an Understanding to the slots; returns (slots, newly filled keys, other changed keys)."""
    out = copy.deepcopy(slots)
    changed = []
    for key, parent in u.parents.items():
        slot, entry = catalog.slot(key), out.setdefault(key, {})
        if slot and entry.get("parent") != parent:
            entry["parent"] = parent
            entry.pop("candidates", None)
            changed.append(key)
            if filled(out, key) and catalog.parent_of(slot, entry["value"]) != parent:
                entry.pop("value", None)  # D-029: a course outside the chosen group is dropped
    for key, candidates in u.ambiguous.items():
        if key not in u.fills:
            out.setdefault(key, {})["candidates"] = list(candidates)
            changed.append(key)
    new = []
    for key, fill in u.fills.items():
        slot, entry = catalog.slot(key), out.setdefault(key, {})
        if entry.get("value") != fill["value"]:
            entry.update(fill)
            new.append(key)
        entry.pop("candidates", None)
        parent = catalog.parent_of(slot, fill["value"]) if slot else ""
        if parent:
            entry["parent"] = parent
    for key in u.skipped:
        out.setdefault(key, {})["skipped"] = 1
        changed.append(key)
    return out, new, changed


def pick_skills(state, u, slots, catalog):
    """Skills to answer now (capped, by sort_order) and the first one still waiting for a slot."""
    keys = list(dict.fromkeys(u.skills + ([state.pending_skill] if state.pending_skill else [])))
    ready, waiting = [], ""
    for key in keys:
        skill = catalog.skills.get(key)
        if not skill:
            continue
        missing = [p for p in skill.params if catalog.slot(p) and not filled(slots, p)]
        if missing and skill.missing_policy == "ask":
            waiting = waiting or key
            continue
        ready.append(skill)
    ready.sort(key=lambda s: s.order)
    return [s.key for s in ready[: int(catalog.settings["max_skills_per_reply"])]], waiting


def next_slot(slots, catalog, first=()):
    ordered = [catalog.slot(k) for k in first if catalog.slot(k)] + list(catalog.slots)
    for slot in ordered:
        entry = slots.get(slot.key) or {}
        if filled(slots, slot.key) or not slot_active(slot, slots):
            continue
        if not slot.required and (entry.get("asked") or entry.get("skipped")):
            continue
        return slot.key
    return ""


def handoff_reason(u, skills, slots, stuck, catalog):
    if u.handoff:
        return "button"
    if any(catalog.skills[k].action == "handoff" or catalog.skills[k].handoff_after for k in skills):
        return "skill"
    if required_filled(slots, catalog):
        return "required_filled"
    if stuck >= int(catalog.settings["max_stuck_turns"]):
        return "stuck"
    return ""


def decide(state, u, catalog):
    keep = dict(slots=copy.deepcopy(state.slots), stuck_turns=state.stuck_turns, pending_skill=state.pending_skill)
    if state.status == "closed":
        return Decision("silent", **keep, reason="Hội thoại đã đóng")
    if state.consultant_replied:
        return Decision("silent", **keep, reason="Tư vấn viên đã nhắn khách, bot im lặng")

    slots, new, changed = merge(state.slots, u, catalog)
    skills, waiting = pick_skills(state, u, slots, catalog)
    greet = state.turns == 0 and not skills
    progress = bool(new or changed or skills or waiting or u.handoff or u.focus)
    stuck = 0 if progress or greet else state.stuck_turns + 1
    common = dict(slots=slots, new_slots=new, skills=skills, pending_skill=waiting, stuck_turns=stuck)
    answered = ", ".join(catalog.skills[k].title for k in skills)

    if state.status == "handed_off":
        if skills:
            return Decision("answer", **common, reason=f"Đã chuyển tư vấn viên; trả lời: {answered}")
        return Decision("silent", **common, reason="Đã chuyển tư vấn viên, chờ tư vấn viên nhắn")

    why = handoff_reason(u, skills, slots, stuck, catalog)
    if why:
        return Decision("handoff", **common, handoff_reason=why, reason=HANDOFF_REASONS[why])

    first = ([u.focus] if u.focus else []) + (list(catalog.skills[waiting].params) if waiting else [])
    ask = next_slot(slots, catalog, first)
    if ask:
        slots.setdefault(ask, {})["asked"] = 1
    label = catalog.slot(ask).label.lower() if ask else ""
    reason = f"Trả lời: {answered}" if skills else ""
    if ask:
        reason = f"{reason}; hỏi tiếp {label}" if reason else f"Hỏi {label} (còn thiếu)"
    return Decision("answer" if skills else "ask_slot", **common, ask=ask, greet=greet,
                    fallback=not progress and not greet, reason=reason)
```

`$APP/engine/reply.py` (the full composer arrives in Task 3):

```python
"""Turn a Decision into the messages and quick-reply buttons the customer sees."""

from dataclasses import dataclass, field

MAX_MESSAGE = 2000  # Messenger text limit
MAX_BUTTONS = 13    # Messenger quick replies per message
MAX_TITLE = 20      # Messenger quick-reply title


@dataclass
class Reply:
    messages: list = field(default_factory=list)
    buttons: list = field(default_factory=list)      # [{"title": str, "action": dict}]
    variants: list = field(default_factory=list)     # [{"skill": key, "variant": key}]
    attachments: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def options(self):
        return {b["title"]: b["action"] for b in self.buttons}


def brand_context(settings):
    return {"name": settings["brand_name"], "bot_name": settings["bot_name"], "you": settings["address_customer"],
            "me": settings["address_self"], "hotline": settings["hotline"], "zalo": settings["zalo"],
            "website": settings["website"], "signoff": settings["signoff"]}


def split_messages(paragraphs, limit=MAX_MESSAGE):
    """Join paragraphs with blank lines, starting a new message before `limit` is exceeded."""
    messages, current = [], ""
    for p in (p.strip() for p in paragraphs if p):
        if not p:
            continue
        while len(p) > limit:  # a single oversized paragraph is cut hard
            if current:
                messages.append(current)
                current = ""
            messages.append(p[:limit])
            p = p[limit:]
        candidate = f"{current}\n\n{p}" if current else p
        if len(candidate) > limit:
            messages.append(current)
            current = p
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages


def add_buttons(reply, buttons):
    seen = {b["title"] for b in reply.buttons}
    for b in buttons:
        title = b["title"][:MAX_TITLE].strip()
        if title and title not in seen and len(reply.buttons) < MAX_BUTTONS:
            reply.buttons.append({"title": title, "action": b["action"]})
            seen.add(title)


def compose(decision, state, catalog, render):
    reply = Reply()
    if decision.type == "silent":
        return reply
    settings = catalog.settings
    ctx = {"brand": brand_context(settings)}
    paragraphs = []
    if decision.greet and settings["greeting_template"]:
        paragraphs.append(render(settings["greeting_template"], ctx))
    if decision.fallback and settings["fallback_template"]:
        paragraphs.append(render(settings["fallback_template"], ctx))
    if decision.ask:
        paragraphs.append(render(catalog.slot(decision.ask).ask_template, ctx))
    reply.messages = split_messages(paragraphs)
    return reply
```

`$APP/engine/events.py`:

```python
"""Lead-engine events (D-036). Any app subscribes in its hooks.py, for example:

    lead_engine_events = {"handed_off": ["my_app.crm.notify_manager"]}

Events: slot_filled, skill_done, handed_off, lead_updated. Each handler receives one dict with the
event name under "event". A failing handler is logged and never breaks the bot turn.
"""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

EVENTS = ("slot_filled", "skill_done", "handed_off", "lead_updated")


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
```

`$APP/engine/effects.py`:

```python
"""Every side effect of a bot turn goes through an Effects object (D-060): real Chatwoot/CRM calls
in production (`ChatwootEffects`), a recorder in the Playground and in tests (`RecordingEffects`)."""

from mmm_custom.chatwoot_client import ChatwootClient
from mmm_custom.engine import events


class RecordingEffects:
    """Dry run: remembers what would have happened, touches nothing."""

    def __init__(self):
        self.calls = []

    def of(self, kind):
        return [payload for name, payload in self.calls if name == kind]

    def send(self, conversation_id, reply):
        self.calls.append(("send", {"messages": list(reply.messages), "buttons": [b["title"] for b in reply.buttons]}))

    def emit(self, event, payload):
        self.calls.append(("emit", {"event": event, **payload}))


class ChatwootEffects:
    """Customer-facing calls use the Agent Bot token so Chatwoot marks them as the bot's own messages
    (which the webhook then ignores); contact updates need the admin user token."""

    def __init__(self, bot_client, user_client):
        self.bot, self.user = bot_client, user_client

    def send(self, conversation_id, reply):
        last = len(reply.messages) - 1
        for i, text in enumerate(reply.messages):
            if i == last and reply.buttons:
                items = [{"title": b["title"], "value": b["title"]} for b in reply.buttons]
                self.bot.send_quick_replies(conversation_id, text, items)
            else:
                self.bot.send_message(conversation_id, text)

    def emit(self, event, payload):
        events.emit(event, payload)


def chatwoot_effects(conf):
    base = conf.get("chatwoot_base_url") or conf.get("chatwoot_api_url") or "http://chatwoot-rails:3000"
    account = int(conf.get("chatwoot_bot_account_id") or conf.get("chatwoot_account_id") or 1)
    bot_token = conf.get("chatwoot_bot_api_token") or ""
    return ChatwootEffects(ChatwootClient(base, bot_token, account),
                           ChatwootClient(base, conf.get("chatwoot_api_token") or bot_token, account))
```

`$APP/engine/pipeline.py`:

```python
"""A bot turn (D-025): webhook payload → Event → per-conversation lock → load → understand →
decide (pure) → act through Effects. `process_event` is the RQ job the webhook enqueues."""

import copy
from dataclasses import dataclass, field

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine.decide import decide
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
    turn.reply = compose(turn.decision, state, catalog, render)
    if turn.reply.messages:
        try:
            effects.send(state.conversation_id, turn.reply)
        except Exception as e:  # never raise into RQ: a retry would answer twice
            turn.reply.errors.append({"type": "send_failed", "detail": str(e)[:300]})
    apply_decision(state, turn.decision, turn.reply, event)
    repo.save_state(state)
    emit_events(effects, state, turn.decision)
    return turn


def process_event(payload):
    """RQ job (enqueued by bot_api.agent_bot_webhook with job_id = message id, deduplicated)."""
    from frappe.utils.synchronization import filelock

    from mmm_custom.engine.effects import chatwoot_effects
    from mmm_custom.engine.repo import FrappeRepo

    event = parse_event(payload)
    if event.kind != "customer_message" or not event.conversation_id:
        return
    with filelock(f"lead_engine_conversation_{event.conversation_id}", timeout=60):
        run_turn(event, FrappeRepo(), chatwoot_effects(frappe.conf), frappe.render_template)
        frappe.db.commit()
```

`$APP/engine/repo.py`:

```python
"""Database side of the engine: the catalog snapshot (cached in Redis, cleared on edits) and
Bot Conversation state. Verified against a running bench (the offline tests use FakeRepo)."""

import json

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine.catalog import DEFAULT_SETTINGS, build_catalog
from mmm_custom.engine.state import ConversationState

CACHE_KEY = "lead_engine_catalog_rows"


def _children(doctype, parent_doctype, parentfield, fields):
    rows = frappe.get_all(doctype, filters={"parenttype": parent_doctype, "parentfield": parentfield},
                          fields=["parent", *fields], order_by="idx asc", parent_doctype=parent_doctype)
    out = {}
    for r in rows:
        out.setdefault(r.parent, []).append({f: r.get(f) for f in fields})
    return out


def _territories():
    rows = frappe.get_all("CRM Territory", fields=[
        "name", "parent_crm_territory", "is_group", "branch_code", "button_label", "branch_tier", "address",
        "hotline", "map_url", "aliases"])
    by_name = {r.name: r for r in rows}
    areas = {}
    for r in rows:
        parent = by_name.get(r.parent_crm_territory)
        if r.is_group or not parent:
            continue
        area = areas.setdefault(parent.name, {"territory_name": parent.name, "button_label": parent.button_label,
                                              "aliases": parent.aliases, "branches": []})
        area["branches"].append({"territory_name": r.name, "branch_code": r.branch_code, "button_label": r.button_label,
                                 "tier": r.branch_tier, "address": r.address, "hotline": r.hotline,
                                 "map_url": r.map_url, "aliases": r.aliases})
    return {"areas": list(areas.values())}


def load_rows():
    """The whole engine catalog from the database, in the demo-dataset shape build_catalog expects."""
    products = frappe.get_all("CRM Product", filters={"disabled": 0, "course_group": ["is", "set"]}, fields=[
        "name", "product_code", "product_name", "button_label", "course_group", "standard_rate", "duration_text",
        "audience", "min_age", "max_age", "certificate", "offer", "aliases", "image"])
    code_of = {p.name: p.product_code for p in products}
    nexts = _children("Course Link", "CRM Product", "next_courses", ["course"])
    courses = [{**p, "next_courses": [code_of.get(n["course"], n["course"]) for n in nexts.get(p.name, [])]}
               for p in products]
    groups = frappe.get_all("Course Group", fields=["group_name", "button_label", "emoji", "sort_order", "aliases",
                                                    "description"], order_by="sort_order asc")
    slots = frappe.get_all("Bot Slot", filters={"active": 1}, fields=[
        "slot_key", "label", "slot_type", "catalog_source", "required", "sort_order", "ask_template",
        "depends_on_slot", "depends_on_value", "lead_field"])
    options = _children("Bot Slot Option", "Bot Slot", "options", ["value", "label", "button_label", "aliases"])
    skills = frappe.get_all("Bot Skill", filters={"active": 1}, fields=[
        "skill_key", "title", "jev_description", "examples", "aliases", "missing_policy", "action_type",
        "action_config", "media", "creates_lead", "handoff_after", "sort_order"])
    params = _children("Bot Slot Link", "Bot Skill", "parameters", ["bot_slot"])
    templates = _children("Bot Skill Template", "Bot Skill", "templates", ["variant_key", "when", "template"])
    follow_ups = _children("Bot Skill Follow Up", "Bot Skill", "follow_ups", ["title", "target_type", "target"])
    for s in skills:
        s["action_config"] = json.loads(s.action_config) if s.action_config else {}
        s["parameters"] = [p["bot_slot"] for p in params.get(s.skill_key, [])]
        s["templates"] = templates.get(s.skill_key, [])
        s["follow_ups"] = follow_ups.get(s.skill_key, [])
    settings_doc = frappe.get_single("Lead Engine Settings").as_dict()
    settings = {k: v for k, v in settings_doc.items() if k in DEFAULT_SETTINGS or k.endswith("_template")}
    return {
        "areas": _territories(), "course_groups": [dict(g) for g in groups], "courses": courses,
        "bot_slots": [{**s, "options": options.get(s.slot_key, [])} for s in slots],
        "bot_skills": [dict(s) for s in skills], "settings": settings,
    }


def load_catalog():
    cache = frappe.cache()
    rows = cache.get_value(CACHE_KEY)
    if rows is None:
        rows = load_rows()
        cache.set_value(CACHE_KEY, rows)
    return build_catalog(rows)


def clear_catalog_cache(doc=None, method=None):
    """doc_events hook: any edit to catalog, slot, skill or settings data takes effect on the next message."""
    frappe.cache().delete_value(CACHE_KEY)


def _json(value):
    if isinstance(value, dict):
        return value
    return json.loads(value) if value else {}


class FrappeRepo:
    def __init__(self, sandbox=False, sandbox_lead=None):
        self.sandbox, self.sandbox_lead = sandbox, sandbox_lead
        self._catalog = None

    def catalog(self):
        if self._catalog is None:
            self._catalog = load_catalog()
        return self._catalog

    def today(self):
        return frappe.utils.getdate()

    def load_state(self, event):
        name = frappe.db.get_value("Bot Conversation", {"conversation_id": event.conversation_id})
        if not name:
            return self.new_state(event)
        d = frappe.get_doc("Bot Conversation", name)
        return ConversationState(
            conversation_id=d.conversation_id, contact_id=d.contact_id or "", inbox_id=d.inbox_id or "",
            lead=d.lead or "", status=d.status or "active", slots=_json(d.slots), pending=_json(d.pending),
            pending_skill=d.pending_skill or "", stuck_turns=d.stuck_turns or 0,
            last_message_id=int(d.last_message_id or 0), consultant_replied=bool(d.consultant_replied),
            consultant=d.consultant or "", is_sandbox=bool(d.is_sandbox), is_returning=bool(d.is_returning),
            turns=d.turns or 0)

    def new_state(self, event):
        return ConversationState(conversation_id=event.conversation_id, contact_id=str(event.contact.get("id") or ""),
                                 inbox_id=event.inbox_id, is_sandbox=self.sandbox)

    def save_state(self, state):
        values = {
            "conversation_id": state.conversation_id, "contact_id": state.contact_id, "inbox_id": state.inbox_id,
            "lead": state.lead or None, "status": state.status, "slots": json.dumps(state.slots, ensure_ascii=False),
            "pending": json.dumps(state.pending, ensure_ascii=False), "pending_skill": state.pending_skill or None,
            "stuck_turns": state.stuck_turns, "last_message_id": state.last_message_id,
            "consultant_replied": int(state.consultant_replied), "consultant": state.consultant or None,
            "is_sandbox": int(state.is_sandbox), "is_returning": int(state.is_returning), "turns": state.turns,
        }
        name = frappe.db.get_value("Bot Conversation", {"conversation_id": state.conversation_id})
        if name:
            doc = frappe.get_doc("Bot Conversation", name)
            doc.update(values)
            doc.save(ignore_permissions=True)
        else:
            frappe.get_doc({"doctype": "Bot Conversation", **values}).insert(ignore_permissions=True)
```

- [ ] **Step 4: Create the Bot Conversation DocType**

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, "/tmp/claude-1000/-home-giabao-dev-dx-osd/035e8dd8-981c-46e8-98a7-2d3604765935/scratchpad")
from dt import *
write("Bot Conversation", [
    field("conversation_id", "Data", "Chatwoot Conversation", reqd=1, unique=1, in_list_view=1),
    field("contact_id", "Data", "Chatwoot Contact"),
    field("inbox_id", "Data", "Chatwoot Inbox"),
    field("lead", "Link", options="CRM Lead", in_list_view=1),
    field("status", "Select", options="active\nhanded_off\nclosed", default="active", in_list_view=1, in_standard_filter=1),
    field("consultant", "Link", options="Consultant", in_standard_filter=1),
    field("slots", "JSON"),
    field("pending", "JSON"),
    field("pending_skill", "Link", options="Bot Skill"),
    field("stuck_turns", "Int"),
    field("turns", "Int"),
    field("last_message_id", "Int", "Last Message ID"),
    field("consultant_replied", "Check"),
    field("is_returning", "Check"),
    field("is_sandbox", "Check", in_standard_filter=1),
], autoname="field:conversation_id")
EOF
```

- [ ] **Step 5: Replace the webhook and wire the hooks**

`$APP/bot_api.py` (whole file):

```python
"""Webhook endpoint for the Chatwoot Agent Bot (spec 2026-09-26-edu-lead-engine §7.2).

Verifies the HMAC signature and anti-replay timestamp, then hands each customer message to the lead
engine as a background job (job_id = message id, deduplicated) so Chatwoot gets its answer well
inside its 5 s timeout and a retried delivery never produces a second reply (D-025).
"""

import hashlib
import hmac
import json
import time

try:
    import frappe
except ImportError:
    from unittest.mock import MagicMock

    class AuthenticationError(Exception):
        pass

    frappe = MagicMock()

    def _whitelist(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

    def _throw(msg, exc=Exception, *args, **kwargs):
        if isinstance(exc, type) and issubclass(exc, BaseException):
            raise exc(msg)
        raise Exception(msg)

    frappe.whitelist = _whitelist
    frappe.AuthenticationError = AuthenticationError
    frappe.throw = _throw

from mmm_custom.engine.pipeline import parse_event


def _verify_hmac(raw_body: bytes, secret: str, timestamp: str, signature: str):
    """Validate HMAC-SHA256 signature and anti-replay timestamp."""
    if not timestamp:
        frappe.throw("Timestamp expired or missing", frappe.AuthenticationError)

    try:
        ts_val = float(timestamp)
    except (ValueError, TypeError):
        frappe.throw("Timestamp expired or missing", frappe.AuthenticationError)

    if abs(time.time() - ts_val) > 300:
        frappe.throw("Timestamp expired or missing", frappe.AuthenticationError)

    hex_digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + raw_body,
        hashlib.sha256,
    ).hexdigest()
    expected = "sha256=" + hex_digest

    if not signature or not (
        hmac.compare_digest(expected, signature)
        or hmac.compare_digest(hex_digest, signature)
    ):
        frappe.throw("Invalid HMAC signature", frappe.AuthenticationError)


def _raw_body(req) -> bytes:
    if hasattr(req, "get_data") and callable(req.get_data):
        raw = req.get_data()
    else:
        raw = getattr(req, "data", b"")
    if isinstance(raw, str):
        return raw.encode("utf-8")
    return raw if isinstance(raw, bytes) else bytes(raw or b"")


@frappe.whitelist(allow_guest=True)
def agent_bot_webhook():
    """Receive Agent Bot webhook events from Chatwoot."""
    req = frappe.request
    headers = getattr(req, "headers", {}) or {}
    raw_body = _raw_body(req)

    conf = getattr(frappe, "conf", None)
    secret = conf.get("chatwoot_bot_webhook_secret") if conf else None
    if not secret:
        # No built-in fallback: a default secret in a public repo would let anyone forge webhooks.
        frappe.throw("chatwoot_bot_webhook_secret is not configured", frappe.AuthenticationError)

    _verify_hmac(raw_body, secret, headers.get("X-Chatwoot-Timestamp"), headers.get("X-Chatwoot-Signature", ""))

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {"status": "error", "message": "Invalid JSON body"}
    if not isinstance(payload, dict):
        return {"status": "error", "message": "Invalid JSON body"}

    event = parse_event(payload)
    if event.kind == "customer_message" and event.conversation_id:
        frappe.enqueue("mmm_custom.engine.pipeline.process_event", queue="short",
                       job_id=f"lead_engine_msg_{event.message_id}", deduplicate=True, payload=payload)
        return {"status": "queued"}
    return {"status": "ignored", "event": payload.get("event")}
```

In `$APP/hooks.py`, directly below the `after_migrate = [...]` line, add:

```python
# Lead engine (spec 2026-09-26-edu-lead-engine): any edit to catalog, slot, skill or settings data
# clears the engine's cached catalog snapshot so the next customer message sees it.
_LEAD_ENGINE_DATA = ("Course Group", "CRM Product", "CRM Territory", "Bot Slot", "Bot Skill", "Lead Engine Settings")
doc_events = {
	dt: {"on_update": "mmm_custom.engine.repo.clear_catalog_cache", "on_trash": "mmm_custom.engine.repo.clear_catalog_cache"}
	for dt in _LEAD_ENGINE_DATA
}

# Other apps subscribe to engine events with their own `lead_engine_events` hook (see engine/events.py).
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: `OK` (the old `test_bot_engine.py` still passes; `bot_engine.py` is removed in Task 2).

- [ ] **Step 7: Verify on the running bench**

```bash
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost migrate >/tmp/mig.log 2>&1; tail -2 /tmp/mig.log"
docker exec crm-frappe-1 bash -c "cd frappe-bench && ../env/bin/python -W ignore -c \"
import frappe; frappe.init(site='crm.localhost', sites_path='sites'); frappe.connect()
from mmm_custom.engine.repo import load_catalog, clear_catalog_cache
clear_catalog_cache(); c = load_catalog()
print(len(c.courses), len(c.branches), len(c.slots), len(c.skills), c.settings['brand_name'])
print(frappe.db.exists('DocType', 'Bot Conversation'))\""
```
Expected: migrate ends without a traceback; prints `46 13 7 30 Tin Học Sao Việt` and `Bot Conversation`. If `get_all(..., parent_doctype=...)` is rejected, drop that keyword (ruling) — the result must still be the same counts.

- [ ] **Step 8: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/engine frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/bot_conversation \
  frappe-custom/mmm_custom/mmm_custom/bot_api.py frappe-custom/mmm_custom/mmm_custom/hooks.py \
  frappe-custom/mmm_custom/mmm_custom/tests/engine_fixtures.py frappe-custom/mmm_custom/mmm_custom/tests/test_engine_catalog.py \
  frappe-custom/mmm_custom/mmm_custom/tests/test_engine_decide.py frappe-custom/mmm_custom/mmm_custom/tests/test_engine_pipeline.py \
  frappe-custom/mmm_custom/mmm_custom/tests/test_bot_api.py frappe-custom/mmm_custom/mmm_custom/tests/test_doctype_json.py
git commit -m "feat(bot): add lead engine conversation state, async pipeline, decide and effects"
```

### Task 2: C2.2 — Slot behaviour: text folding, slot-type registry, keyword tier, tiered buttons, exact taps

Implements layer **C2.2** (D-023, D-028 tier 1, D-029 keyword part, D-034, D-068, D-069). Out of scope: Jev (C3.2), skill answers (Task 3).

**Files:**
- Create: `$APP/engine/text.py`, `$APP/engine/slot_types.py`
- Modify: `$APP/engine/understand.py` (replace `understand()`), `$APP/engine/reply.py` (`compose` adds the asked slot's buttons)
- Delete: `$APP/bot_engine.py`, `$T/test_bot_engine.py` (the phone normaliser moves to `text.py`; nothing else imports `bot_engine` since Task 1)
- Create tests: `$T/test_engine_text.py`, `$T/test_engine_understand.py`

**Interfaces:**
- Consumes (Task 1): `Understanding`, `Catalog`, `ConversationState`, `state.value`, `reply.add_buttons`.
- Produces:
  - `text.fold(text) -> str`, `text.find_phrases(folded_text, table: {value: iterable[str]}, min_words=1) -> {value: (start, end)}`, `text.normalize_vn_phone(raw) -> str | None`, `text.find_phone(text) -> str | None`, `text.slug(text) -> str`, `text.content_words(folded_text, spans) -> list[str]`.
  - `slot_types.REGISTRY: dict[str, SlotType]`, `slot_types.register(name)`, `SlotType.understand(slot, text, folded, pending, catalog, u)`, `SlotType.buttons(slot, slots, catalog) -> [{"title", "action"}]`, `slot_types.course_phrases(catalog)`.
  - Button actions (stored in `pending.options`, D-034): `{"type": "slot", "slot", "value"}`, `{"type": "parent", "slot", "value"}`, `{"type": "skip", "slot"}`, `{"type": "skill", "skill"}`, `{"type": "ask", "slot"}`, `{"type": "handoff"}`.
  - `understand.understand(text, state, catalog)`, `understand.apply_action(u, action)`, `understand.match_courses(text, catalog) -> list[Course]`.

- [ ] **Step 1: Write the failing tests**

`$T/test_engine_text.py`:

```python
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_fixtures  # noqa: F401  (puts the app on sys.path)

from mmm_custom.engine.text import content_words, find_phone, find_phrases, fold, normalize_vn_phone, slug


class TestText(unittest.TestCase):
    def test_fold_strips_diacritics_case_and_punctuation(self):
        self.assertEqual(fold("Học phí Excel ở Dĩ An, Q.7?"), "hoc phi excel o di an q 7")
        self.assertEqual(fold("ĐỒ HỌA"), "do hoa")
        self.assertEqual(fold(None), "")

    def test_find_phrases_whole_words_only(self):
        self.assertEqual(find_phrases("hoc excel", {"X": ["excel"]}), {"X": (5, 10)})
        self.assertEqual(find_phrases("hoc excelsior", {"X": ["excel"]}), {})

    def test_longer_phrase_of_another_value_wins(self):
        table = {"EXCEL": ["excel"], "EXCEL-NC": ["excel nang cao"], "KT": ["ke toan excel"]}
        self.assertEqual(set(find_phrases(fold("Excel nâng cao"), table)), {"EXCEL-NC"})
        self.assertEqual(set(find_phrases(fold("kế toán excel"), table)), {"KT"})
        self.assertEqual(set(find_phrases(fold("excel va ke toan excel"), table)), {"EXCEL", "KT"})

    def test_min_words(self):
        self.assertEqual(find_phrases("toi muon hoc", {"evening": ["toi", "buoi toi"]}, min_words=2), {})
        self.assertIn("evening", find_phrases("hoc buoi toi", {"evening": ["toi", "buoi toi"]}, min_words=2))

    def test_phone(self):
        self.assertEqual(normalize_vn_phone("0901.234.567"), "+84901234567")
        self.assertEqual(normalize_vn_phone("+84 901 234 567"), "+84901234567")
        self.assertIsNone(normalize_vn_phone("12345"))
        self.assertEqual(find_phone("sdt em 0901 234 567 nha"), "+84901234567")
        self.assertIsNone(find_phone("lop 12 nguoi"))

    def test_slug_and_content_words(self):
        self.assertEqual(slug("CN Dĩ An"), "cn-di-an")
        folded = fold("abcxyz excel nha")
        spans = list(find_phrases(folded, {"X": ["excel"]}).values())
        self.assertEqual(content_words(folded, spans), ["abcxyz"])


if __name__ == "__main__":
    unittest.main()
```

`$T/test_engine_understand.py`:

```python
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, fill

from mmm_custom import catalog_rules
from mmm_custom.engine.reply import compose
from mmm_custom.engine.decide import decide
from mmm_custom.engine.slot_types import REGISTRY
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import match_courses, understand

CAT = demo_catalog()


def st(pending_slot="", options=None, slots=None):
    return ConversationState("1", pending={"slot": pending_slot, "options": options or {}}, slots=slots or {}, turns=1)


class TestKeywordTier(unittest.TestCase):
    def test_multi_slot_free_text(self):
        u = understand("học phí excel ở bình thạnh", st(), CAT)
        self.assertEqual(u.fills["course"]["value"], "VP-EXCEL")
        self.assertEqual(u.fills["branch"]["value"], "CN Bình Thạnh")
        self.assertEqual(u.fills["course"]["source"], "keyword")
        self.assertEqual(u.skills, ["fee_quote"])
        self.assertFalse(u.tapped)

    def test_longest_course_alias_wins(self):
        self.assertEqual(understand("autocad 3d", st(), CAT).fills["course"]["value"], "VKT-CAD3D")
        self.assertEqual(understand("Excel nâng cao", st(), CAT).fills["course"]["value"], "VP-EXCEL-NC")

    def test_group_and_area_become_parents(self):
        u = understand("muốn học đồ họa ở bình dương", st(), CAT)
        self.assertEqual(u.parents, {"course": "Thiết kế đồ họa", "branch": "Bình Dương"})
        self.assertNotIn("course", u.fills)

    def test_ambiguous_courses_keep_candidates_and_common_parent(self):
        u = understand("photoshop hay illustrator", st(), CAT)
        self.assertEqual(u.ambiguous["course"], ["DH-AI", "DH-PTS"])
        self.assertEqual(u.parents["course"], "Thiết kế đồ họa")

    def test_exact_tap_maps_to_stored_action(self):
        options = {"Excel": {"type": "slot", "slot": "course", "value": "VP-EXCEL"}}
        u = understand("Excel", st("course", options), CAT)
        self.assertTrue(u.tapped)
        self.assertEqual(u.fills["course"], fill("VP-EXCEL", "button"))

    def test_stale_or_retyped_title_falls_back_to_keywords(self):
        options = {"Ca sáng": {"type": "slot", "slot": "preferred_shift", "value": "morning"}}
        u = understand("excel", st("preferred_shift", options), CAT)
        self.assertFalse(u.tapped)
        self.assertEqual(u.fills["course"]["value"], "VP-EXCEL")

    def test_single_word_choice_alias_only_when_pending(self):
        self.assertNotIn("preferred_shift", understand("tôi muốn hỏi", st(), CAT).fills)
        self.assertEqual(understand("học buổi tối", st(), CAT).fills["preferred_shift"]["value"], "evening")
        self.assertEqual(understand("tối", st("preferred_shift"), CAT).fills["preferred_shift"]["value"], "evening")
        self.assertEqual(understand("con", st("learner"), CAT).fills["learner"]["value"], "child")

    def test_number_and_text_only_when_pending(self):
        self.assertEqual(understand("bé 8 tuổi", st("learner_age"), CAT).fills["learner_age"]["value"], 8)
        self.assertNotIn("learner_age", understand("bé 8 tuổi", st(), CAT).fills)
        self.assertEqual(understand("Lan", st("customer_name"), CAT).fills["customer_name"]["value"], "Lan")
        u = understand("học phí bao nhiêu", st("customer_name"), CAT)
        self.assertNotIn("customer_name", u.fills)
        self.assertEqual(u.skills, ["fee_quote"])

    def test_phone_anywhere(self):
        self.assertEqual(understand("sdt em 0901 234 567", st(), CAT).fills["phone"]["value"], "+84901234567")

    def test_unmatched_words_are_collected(self):
        self.assertEqual(understand("abcxyz", st(), CAT).unmatched, ["abcxyz"])

    def test_match_courses_for_sync_webhook(self):
        self.assertEqual([c.code for c in match_courses("photoshop và illustrator", CAT)], ["DH-PTS", "DH-AI"])
        self.assertEqual(match_courses("xin chào", CAT), [])


class TestButtons(unittest.TestCase):
    def buttons(self, key, slots=None):
        slot = CAT.slot(key)
        return REGISTRY[slot.type].buttons(slot, slots or {}, CAT)

    def test_registry_matches_select_options(self):
        self.assertEqual(set(REGISTRY), set(catalog_rules.SLOT_TYPES))

    def test_course_buttons_are_tiered(self):
        top = self.buttons("course")
        self.assertEqual([b["title"] for b in top][:2], ["Tin học văn phòng", "Đồ họa"])
        self.assertEqual(top[0]["action"], {"type": "parent", "slot": "course", "value": "Tin học văn phòng"})
        inner = self.buttons("course", {"course": {"parent": "Kế toán"}})
        self.assertEqual(len(inner), 5)
        self.assertEqual(inner[0]["action"]["type"], "slot")

    def test_candidates_limit_buttons(self):
        got = self.buttons("course", {"course": {"candidates": ["DH-AI", "DH-PTS"]}})
        self.assertEqual({b["action"]["value"] for b in got}, {"DH-AI", "DH-PTS"})

    def test_advanced_course_offers_only_full_branches(self):
        got = self.buttons("branch", {"course": fill("VKT-REVIT"), "branch": {"parent": "TP. Hồ Chí Minh"}})
        self.assertEqual({b["title"] for b in got}, {"Bình Thạnh", "Thủ Đức"})
        none_there = self.buttons("branch", {"course": fill("VKT-REVIT"), "branch": {"parent": "Bà Rịa - Vũng Tàu"}})
        self.assertEqual(none_there[0]["action"]["type"], "parent")

    def test_choice_and_phone_buttons(self):
        self.assertEqual([b["title"] for b in self.buttons("learner")], ["Cho tôi", "Cho con em", "Cho công ty"])
        self.assertEqual(self.buttons("phone"), [])

    def test_compose_attaches_asked_slot_buttons(self):
        d = decide(ConversationState("1", turns=1), understand("xyz", st(), CAT), CAT)
        from engine_fixtures import render
        r = compose(d, ConversationState("1"), CAT, render)
        self.assertEqual(len(r.buttons), 8)
        self.assertEqual(r.options()["Kế toán"], {"type": "parent", "slot": "course", "value": "Kế toán"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -p "test_engine_*.py" 2>&1 | tail -3`
Expected: FAIL/ERROR — `No module named 'mmm_custom.engine.text'`.

- [ ] **Step 3: Implement text helpers and the slot-type registry**

`$APP/engine/text.py`:

```python
"""Text helpers for the keyword tier (D-028): Vietnamese diacritic folding, whole-word phrase search,
Vietnamese phone numbers."""

import re
import unicodedata

WORD_RE = re.compile(r"[a-z0-9]+")
PHONE_RE = re.compile(r"(?:\+?84|0)(?:[\s.\-]?\d){8,10}")
# Folded filler words ignored when collecting unmatched terms for learning signals (D-057).
STOPWORDS = frozenset(
    "cho toi minh em anh chi hoc khoa muon can hoi co khong the nao duoc voi nha nhe vay sao thi nhu bao "
    "nhieu lam roi dang biet giup xin chao cam on oke ok uhm uh".split())


def fold(text):
    """Lowercase, drop Vietnamese diacritics (đ → d) and punctuation: "Dĩ An, Q.7" → "di an q 7"."""
    text = (text or "").lower().replace("đ", "d")
    text = "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
    return " ".join(WORD_RE.findall(text))


def find_phrases(folded_text, table, min_words=1):
    """Values whose phrases occur as whole words in `folded_text`, as {value: (start, end)}.

    A hit lying inside a longer hit of another value is dropped, so "excel nang cao" beats "excel".
    Positions index into `folded_text`.
    """
    padded = f" {folded_text} "
    hits = []
    for value, phrases in table.items():
        for phrase in phrases:
            p = fold(phrase)
            if not p or len(p.split()) < min_words:
                continue
            at = padded.find(f" {p} ")
            if at >= 0:
                hits.append((at, at + len(p), value))
    best = {}
    for s, e, v in hits:
        if any(s2 <= s and e <= e2 and e2 - s2 > e - s and v2 != v for s2, e2, v2 in hits):
            continue
        if v not in best or e - s > best[v][1] - best[v][0]:
            best[v] = (s, e)
    return best


def content_words(folded_text, spans):
    """Words of 3+ letters that no matched phrase covers and that are not filler."""
    out = []
    for m in WORD_RE.finditer(folded_text):
        word = m.group()
        if len(word) < 3 or word.isdigit() or word in STOPWORDS:
            continue
        if any(s <= m.start() and m.end() <= e for s, e in spans):
            continue
        out.append(word)
    return list(dict.fromkeys(out))


def normalize_vn_phone(raw):
    """0901234567 / +84 901 234 567 / 84901234567 → +84901234567; anything else → None."""
    digits = re.sub(r"[\s.\-()]+", "", (raw or "").strip())
    if digits.startswith("+84"):
        digits = "0" + digits[3:]
    elif digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    return "+84" + digits[1:] if re.fullmatch(r"0\d{9}", digits) else None


def find_phone(text):
    for m in PHONE_RE.finditer(text or ""):
        phone = normalize_vn_phone(m.group(0))
        if phone:
            return phone
    return None


def slug(text):
    return fold(text).replace(" ", "-")
```

`$APP/engine/slot_types.py`:

```python
"""Slot-type registry (D-023): how each kind of slot is understood from a message and offered as
quick-reply buttons. A new kind of answer = one SlotType subclass + @register("name") + the Select
option in catalog_rules.SLOT_TYPES / the Bot Slot DocType."""

import re

from mmm_custom.engine.state import value
from mmm_custom.engine.text import find_phone, find_phrases

REGISTRY = {}


def register(name):
    def wrap(cls):
        REGISTRY[name] = cls()
        return cls
    return wrap


def _fill(u, slot, val):
    u.fills[slot.key] = {"value": val, "source": "keyword", "confidence": 1.0}


def course_phrases(catalog):
    return {c.code: (c.name, c.button, *c.aliases) for c in catalog.courses.values()}


class SlotType:
    late = False  # understood after skills (free-text answers such as a name)

    def understand(self, slot, text, folded, pending, catalog, u):
        pass

    def buttons(self, slot, slots, catalog):
        return []


@register("catalog")
class CatalogSlot(SlotType):
    """Courses (group → course) or branches (area → branch), matched on names, button labels and aliases."""

    def tables(self, slot, catalog):
        if slot.source == "course":
            parents = {g.name: (g.name, g.button, *g.aliases) for g in catalog.groups.values()}
            return course_phrases(catalog), parents
        leaves = {b.name: (b.name, b.button, *b.aliases) for b in catalog.branches.values()}
        parents = {a.name: (a.name, a.button, *a.aliases) for a in catalog.areas.values()}
        return leaves, parents

    def understand(self, slot, text, folded, pending, catalog, u):
        leaves, parents = self.tables(slot, catalog)
        hits = find_phrases(folded, leaves)
        if hits:
            u.spans.extend(hits.values())
            u.matches.append({"slot": slot.key, "kind": "value", "values": sorted(hits)})
            if len(hits) == 1:
                _fill(u, slot, next(iter(hits)))
                return
            u.ambiguous[slot.key] = sorted(hits)
            common = {catalog.parent_of(slot, v) for v in hits}
            if len(common) == 1:
                u.parents[slot.key] = common.pop()
            return
        found = find_phrases(folded, parents)
        u.spans.extend(found.values())
        if len(found) == 1:
            u.parents[slot.key] = next(iter(found))
            u.matches.append({"slot": slot.key, "kind": "parent", "values": sorted(found)})

    def items(self, slot, slots, catalog):
        """(value, button title, parent) of every offerable leaf, in catalog order."""
        if slot.source == "course":
            return [(c.code, c.button, c.group) for c in catalog.courses.values()]
        course_slot = catalog.slot_for("course")
        course = catalog.courses.get(value(slots, course_slot.key)) if course_slot else None
        full_only = course is not None and course.offer == "full"  # advanced courses run at full branches only
        return [(b.name, b.button, b.area) for b in catalog.branches.values() if not full_only or b.tier == "full"]

    def buttons(self, slot, slots, catalog):
        entry = slots.get(slot.key) or {}
        items = self.items(slot, slots, catalog)
        chosen = []
        if entry.get("candidates"):
            chosen = [i for i in items if i[0] in entry["candidates"]]
        elif entry.get("parent"):
            chosen = [i for i in items if i[2] == entry["parent"]]
        if not chosen:
            order = catalog.groups if slot.source == "course" else catalog.areas
            parents = [p for p in order if any(i[2] == p for i in items)]
            if len(parents) > 1:
                return [{"title": order[p].button, "action": {"type": "parent", "slot": slot.key, "value": p}}
                        for p in parents]
            chosen = items
        return [{"title": title, "action": {"type": "slot", "slot": slot.key, "value": val}} for val, title, _ in chosen]


@register("choice")
class ChoiceSlot(SlotType):
    def understand(self, slot, text, folded, pending, catalog, u):
        table = {o.value: (o.label, o.button, *o.aliases) for o in slot.options}
        hits = find_phrases(folded, table, min_words=1 if pending else 2)  # D-068
        if len(hits) == 1:
            _fill(u, slot, next(iter(hits)))
            u.spans.extend(hits.values())
            u.matches.append({"slot": slot.key, "kind": "value", "values": sorted(hits)})
        elif hits and pending:
            u.ambiguous[slot.key] = sorted(hits)

    def buttons(self, slot, slots, catalog):
        return [{"title": o.button, "action": {"type": "slot", "slot": slot.key, "value": o.value}} for o in slot.options]


@register("phone")
class PhoneSlot(SlotType):
    def understand(self, slot, text, folded, pending, catalog, u):
        phone = find_phone(text)
        if phone:
            _fill(u, slot, phone)
            u.matches.append({"slot": slot.key, "kind": "phone", "values": [phone]})

    def buttons(self, slot, slots, catalog):
        return [] if slot.required else [{"title": "Bỏ qua", "action": {"type": "skip", "slot": slot.key}}]


@register("number")
class NumberSlot(SlotType):
    def understand(self, slot, text, folded, pending, catalog, u):
        m = re.search(r"\b(\d{1,3})\b", folded) if pending else None  # D-069
        if m and 0 < int(m.group(1)) < 120:
            _fill(u, slot, int(m.group(1)))


@register("text")
class TextSlot(SlotType):
    late = True

    def understand(self, slot, text, folded, pending, catalog, u):
        if not pending or u.fills or u.skills or u.parents or u.ambiguous:  # D-069
            return
        answer = " ".join((text or "").split())[:60]
        if answer and len(answer.split()) <= 6:
            _fill(u, slot, answer)
```

In `$APP/engine/understand.py`, add the imports below the dataclass import and replace `understand()`:

```python
from mmm_custom.engine.slot_types import REGISTRY, course_phrases
from mmm_custom.engine.text import content_words, find_phrases, fold
```

```python
def apply_action(u, action):
    """A quick-reply tap: the stored action decides exactly what the customer chose (D-034)."""
    kind = action.get("type")
    if kind == "slot":
        u.fills[action["slot"]] = {"value": action["value"], "source": "button", "confidence": 1.0}
    elif kind == "parent":
        u.parents[action["slot"]] = action["value"]
    elif kind == "skip":
        u.skipped.append(action["slot"])
    elif kind == "skill":
        u.skills.append(action["skill"])
    elif kind == "ask":
        u.focus = action["slot"]
    elif kind == "handoff":
        u.handoff = True


def _match_skills(folded, catalog, u):
    hits = find_phrases(folded, {k: s.aliases for k, s in catalog.skills.items()})
    for key, span in sorted(hits.items(), key=lambda kv: kv[1][0]):
        u.skills.append(key)
        u.spans.append(span)
        u.matches.append({"skill": key, "kind": "skill"})


def understand(text, state, catalog):
    """Keyword tier (D-028): exact button taps first, then folded aliases/regexes per slot type and skill."""
    u = Understanding()
    action = (state.pending.get("options") or {}).get((text or "").strip())
    if action:
        u.tapped = True
        apply_action(u, action)
        return u
    folded = fold(text)
    pending = state.pending.get("slot") or ""
    slots = [(s, REGISTRY[s.type]) for s in catalog.slots if s.type in REGISTRY]
    for slot, handler in slots:
        if not handler.late:
            handler.understand(slot, text or "", folded, pending == slot.key, catalog, u)
    _match_skills(folded, catalog, u)
    for slot, handler in slots:
        if handler.late:
            handler.understand(slot, text or "", folded, pending == slot.key, catalog, u)
    u.unmatched = content_words(folded, u.spans)
    return u


def match_courses(text, catalog):
    """Courses mentioned in free text, in order of appearance (used by the sync webhook, api.py)."""
    hits = find_phrases(fold(text), course_phrases(catalog))
    return [catalog.courses[code] for code, _ in sorted(hits.items(), key=lambda kv: kv[1][0])]
```

In `$APP/engine/reply.py`, add `from mmm_custom.engine.slot_types import REGISTRY` below the dataclass import, and in `compose` replace

```python
    if decision.ask:
        paragraphs.append(render(catalog.slot(decision.ask).ask_template, ctx))
```

with

```python
    if decision.ask:
        slot = catalog.slot(decision.ask)
        paragraphs.append(render(slot.ask_template, ctx))
        if slot.type in REGISTRY:
            add_buttons(reply, REGISTRY[slot.type].buttons(slot, decision.slots, catalog))
```

Delete the old engine: `git rm frappe-custom/mmm_custom/mmm_custom/bot_engine.py frappe-custom/mmm_custom/mmm_custom/tests/test_bot_engine.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: `OK`. Also `grep -rn "bot_engine" frappe-custom scripts --include=*.py` prints nothing.

- [ ] **Step 5: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/engine/text.py frappe-custom/mmm_custom/mmm_custom/engine/slot_types.py \
  frappe-custom/mmm_custom/mmm_custom/engine/understand.py frappe-custom/mmm_custom/mmm_custom/engine/reply.py \
  frappe-custom/mmm_custom/mmm_custom/tests/test_engine_text.py frappe-custom/mmm_custom/mmm_custom/tests/test_engine_understand.py
git commit -m "feat(bot): add slot-type registry, diacritic-folded keyword matcher and tiered buttons"
```

(`git rm` already staged the two deletions.)

### Task 3: C2.3 — Skill executor: action registry, context contract, guarded rendering, reply composition

Implements layer **C2.3** (D-035, D-037, D-048…D-054, D-071, D-072). Out of scope: Jev skill choice (C3.3), advisor scoring (C3.6), course cards (C5.5), the handoff paragraph (Task 6).

**Files:**
- Create: `$APP/engine/render.py`, `$APP/engine/context.py`, `$APP/engine/actions.py`
- Replace: `$APP/engine/reply.py` (whole file)
- Modify: `$APP/engine/pipeline.py` (compose call, renderer), `$APP/engine/repo.py` (schedules, promotions), `$APP/hooks.py` (`jinja` filters)
- Modify data: `$APP/demo/saoviet/bot_skills.json`, `$APP/demo/saoviet/settings.json`; DocType `Lead Engine Settings` (+`max_skills_per_reply`)
- Modify tests: `$T/engine_fixtures.py` (renderer + fake data sources)
- Create tests: `$T/test_engine_render.py`, `$T/test_engine_actions.py`, `$T/test_engine_reply.py`

**Interfaces:**
- Consumes: `Decision` (Task 1), `REGISTRY` buttons (Task 2), `Catalog`, `state.value/filled`.
- Produces:
  - `render.vnd(value) -> "1.200.000đ"`, `render.date_vi(value) -> "Thứ 7, 04/10"`, `render.RenderError`, `render.render_text(template, context, renderer) -> str` (raises `RenderError` on exceptions or leftover `{{`/`{%`), `render.condition(expr, context, renderer) -> bool`, `render.frappe_renderer(template, context)`, `render.jinja_renderer() -> callable`, `render.WEEKDAYS`.
  - `context.base_context(slots, catalog, state) -> dict` (keys exactly: `brand, customer, course, branch, area, schedules, promotions, final_fee, recommendations, slots, missing`), `context.brand_context(settings)`, `context.course_context(course, catalog)`, `context.branch_context(branch)`, `context.shown_slots(slots, catalog)`, `context.CUSTOMER_SLOTS`.
  - `actions.ACTIONS`, `actions.action(name)`, `actions.run_action(skill, ctx, slots, catalog, data, today) -> dict`, `actions.applicable(promo, course_ctx, branch_name)`, `actions.find_schedules(data, ctx, today, limit) -> list`.
  - `reply.compose(decision, state, catalog, render, data=None, today=None, extra=None) -> Reply` (`extra` is merged into the context; Task 6 passes `consultant`).
  - Data-source protocol used by actions (implemented by `FrappeRepo` and `FakeRepo`): `open_schedules(course_code, branch|None, shift_prefix|None, today, limit) -> [{"date", "weekday", "shift", "weekdays", "branch", "seats_left"}]`, `active_promotions(today) -> [{"title", "discount_type", "discount_value", "courses", "course_groups", "branches"}]`.

- [ ] **Step 1: Update fixtures and write the failing tests**

In `$T/engine_fixtures.py` replace the three lines

```python
_ENV = jinja2.sandbox.SandboxedEnvironment(undefined=jinja2.DebugUndefined)


def render(template, context):
    return _ENV.from_string(template).render(context)
```

with

```python
from mmm_custom.engine.render import jinja_renderer

render = jinja_renderer()
```

and delete the now-unused `import jinja2` / `import jinja2.sandbox` lines. In `FakeRepo.__init__` add `self.schedules, self.promotions = [], []`, and add these methods to `FakeRepo`:

```python
    def open_schedules(self, course, branch, shift, today, limit):
        rows = [s for s in self.schedules if s["course"] == course and s["date"] >= today
                and (not branch or s["branch"] == branch) and (not shift or s["shift"].startswith(shift))]
        return sorted(rows, key=lambda s: s["date"])[:limit]

    def active_promotions(self, today):
        return list(self.promotions)
```

and add these module-level helpers:

```python
def schedule(course, branch, day, shift="Tối 17:00–21:00", weekdays="T3, T5, T7", seats=6):
    return {"course": course, "branch": branch, "date": day, "shift": shift, "weekdays": weekdays,
            "seats_left": seats}


def promo(title, kind="Percent", amount=10, courses=(), groups=(), branches=()):
    return {"title": title, "discount_type": kind, "discount_value": amount, "courses": list(courses),
            "course_groups": list(groups), "branches": list(branches)}
```

`$T/test_engine_render.py`:

```python
import sys
from datetime import date
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import render

from mmm_custom.engine.render import RenderError, condition, date_vi, render_text, vnd


class TestFilters(unittest.TestCase):
    def test_vnd(self):
        self.assertEqual(vnd(1200000), "1.200.000đ")
        self.assertEqual(vnd(1620000.0), "1.620.000đ")
        self.assertEqual(vnd(None), "0đ")

    def test_date_vi(self):
        self.assertEqual(date_vi(date(2026, 10, 4)), "Chủ nhật, 04/10")
        self.assertEqual(date_vi("2026-10-06"), "Thứ 3, 06/10")

    def test_filters_available_in_templates(self):
        self.assertEqual(render("{{ 1500000 | vnd }} · {{ d | date_vi }}", {"d": date(2026, 10, 3)}),
                         "1.500.000đ · Thứ 7, 03/10")


class TestGuard(unittest.TestCase):
    def test_renders(self):
        self.assertEqual(render_text("Chào {{ brand.you }}", {"brand": {"you": "anh/chị"}}, render), "Chào anh/chị")

    def test_missing_key_is_blocked(self):
        with self.assertRaises(RenderError):
            render_text("Chào {{ brand.you }}", {"brand": {}}, render)

    def test_undefined_object_is_blocked(self):
        with self.assertRaises(RenderError):
            render_text("Khóa {{ course.name }}", {}, render)

    def test_syntax_error_is_blocked(self):
        with self.assertRaises(RenderError):
            render_text("{% if %}x{% endif %}", {}, render)

    def test_condition(self):
        self.assertTrue(condition("not schedules", {"schedules": []}, render))
        self.assertFalse(condition("not schedules", {"schedules": [1]}, render))


if __name__ == "__main__":
    unittest.main()
```

`$T/test_engine_actions.py`:

```python
import sys
from datetime import date
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, fill, promo, schedule

from mmm_custom import catalog_rules
from mmm_custom.engine.actions import ACTIONS, run_action
from mmm_custom.engine.context import base_context
from mmm_custom.engine.state import ConversationState

CAT = demo_catalog()
TODAY = date(2026, 9, 28)


def act(skill_key, slots, repo=None):
    ctx = base_context(slots, CAT, ConversationState("1", slots=slots))
    return run_action(CAT.skills[skill_key], ctx, slots, CAT, repo or FakeRepo(CAT), TODAY)


class TestContext(unittest.TestCase):
    def test_contract_keys_and_values(self):
        slots = {"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An"), "learner": fill("child"),
                 "customer_name": fill("Lan")}
        ctx = base_context(slots, CAT, ConversationState("1", is_returning=True))
        self.assertEqual(set(ctx), {"brand", "customer", "course", "branch", "area", "schedules", "promotions",
                                    "final_fee", "recommendations", "slots", "missing"})
        self.assertEqual((ctx["course"]["name"], ctx["course"]["fee"]), ("Excel từ cơ bản đến nâng cao", 1800000.0))
        self.assertEqual(ctx["course"]["next_courses"], ["Excel nâng cao & Dashboard", "Luyện thi MOS quốc tế"])
        self.assertEqual((ctx["branch"]["name"], ctx["area"]), ("CN Dĩ An", "Bình Dương"))
        self.assertEqual(ctx["customer"], {"name": "Lan", "learner": "Con em", "learner_age": "", "shift": "",
                                           "is_returning": True})
        self.assertEqual(ctx["slots"]["course"], "Excel từ cơ bản đến nâng cao")
        self.assertEqual(ctx["missing"], ["Số điện thoại"])
        self.assertEqual(ctx["brand"]["you"], "anh/chị")

    def test_empty_slots(self):
        ctx = base_context({}, CAT, ConversationState("1"))
        self.assertEqual((ctx["course"], ctx["branch"], ctx["area"], ctx["final_fee"]), ({}, {}, "", 0))


class TestActions(unittest.TestCase):
    def test_registry_matches_select_options(self):
        self.assertEqual(set(ACTIONS), set(catalog_rules.ACTION_TYPES))

    def test_fee_quote_takes_best_applicable_promotion(self):
        repo = FakeRepo(CAT)
        repo.promotions = [promo("Tất cả -10%"), promo("Long Thành -15%", amount=15, branches=["CN Long Thành"]),
                           promo("KT tổng hợp -500k", "Amount", 500000, courses=["KT-TH"])]
        out = act("fee_quote", {"course": fill("VP-EXCEL")}, repo)
        self.assertEqual((out["final_fee"], [p["title"] for p in out["promotions"]]), (1620000.0, ["Tất cả -10%"]))
        out = act("fee_quote", {"course": fill("VP-EXCEL"), "branch": fill("CN Long Thành")}, repo)
        self.assertEqual(out["final_fee"], 1530000.0)
        out = act("fee_quote", {"course": fill("KT-TH")}, repo)
        self.assertEqual(out["final_fee"], 3000000.0)
        self.assertEqual(out["promotions"][1]["discount"], "500.000đ")

    def test_schedule_lookup_falls_back_from_branch_and_shift(self):
        repo = FakeRepo(CAT)
        repo.schedules = [schedule("VP-EXCEL", "CN Dĩ An", date(2026, 10, 6)),
                          schedule("VP-EXCEL", "CN Dĩ An", date(2026, 9, 1))]
        out = act("schedule_lookup", {"course": fill("VP-EXCEL"), "branch": fill("CN Bình Thạnh"),
                                      "preferred_shift": fill("morning")}, repo)
        self.assertEqual([s["date"] for s in out["schedules"]], [date(2026, 10, 6)])
        self.assertEqual(act("schedule_lookup", {}, repo), {"schedules": []})

    def test_recommend_courses_filters_by_data(self):
        kids = act("kids_courses", {})
        self.assertEqual([r["code"] for r in kids["recommendations"]], ["TE-THUD", "TE-SCRATCH", "TE-PY"])
        self.assertEqual(kids["_buttons"][0]["action"], {"type": "slot", "slot": "course", "value": "TE-THUD"})
        teen = act("kids_courses", {"learner_age": fill(13)})
        self.assertEqual([r["code"] for r in teen["recommendations"]], ["TE-PY", "TE-ROBO-NC"])
        adult = act("course_advisor", {"learner": fill("self")})
        self.assertTrue(all(CAT.courses[r["code"]].audience != "Trẻ em" for r in adult["recommendations"]))

    def test_branch_info_lists_area_branches(self):
        out = act("branch_info", {"branch": {"parent": "Đồng Nai"}})
        self.assertEqual([b["name"] for b in out["branches"]], ["CN Biên Hòa", "CN Long Thành"])

    def test_send_media_without_image_attaches_nothing(self):
        self.assertEqual(act("course_content", {"course": fill("VP-EXCEL")}), {})


if __name__ == "__main__":
    unittest.main()
```

`$T/test_engine_reply.py`:

```python
import sys
from datetime import date
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, fill, promo, render, schedule

from mmm_custom.engine.decide import Decision, decide
from mmm_custom.engine.reply import Reply, add_buttons, compose, split_messages
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding

CAT = demo_catalog()


class TestCompose(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo(CAT)

    def compose(self, decision, state=None):
        return compose(decision, state or ConversationState("1"), CAT, render, self.repo, self.repo.today())

    def test_fee_answer_with_promotion_then_next_question_and_its_buttons(self):
        self.repo.promotions = [promo("Tất cả -10%")]
        d = decide(ConversationState("1", turns=1),
                   Understanding(fills={"course": fill("VP-EXCEL")}, skills=["fee_quote"]), CAT)
        r = self.compose(d)
        self.assertEqual(len(r.messages), 1)
        self.assertIn("Dạ khóa Excel từ cơ bản đến nâng cao học phí 1.800.000đ, đang ưu đãi còn 1.620.000đ ạ.",
                      r.messages[0])
        self.assertTrue(r.messages[0].endswith("Anh/chị muốn học ở chi nhánh nào ạ?"))
        self.assertEqual([b["title"] for b in r.buttons], ["TP.HCM", "Bình Dương", "Đồng Nai", "Vũng Tàu"])
        self.assertEqual(r.variants, [{"skill": "fee_quote", "variant": "default"}])

    def test_schedule_variants(self):
        d = Decision("answer", slots={"course": fill("VP-EXCEL")}, skills=["schedule_lookup"])
        self.assertEqual(self.compose(d).variants[0]["variant"], "none")
        self.repo.schedules = [schedule("VP-EXCEL", "CN Dĩ An", date(2026, 10, 6))]
        r = self.compose(d)
        self.assertIn("• Thứ 3, 06/10 (T3, T5, T7, Tối 17:00–21:00) tại CN Dĩ An", r.messages[0])

    def test_follow_ups_when_nothing_is_asked(self):
        d = Decision("answer", slots={"course": fill("VP-EXCEL")}, skills=["fee_quote"])
        r = self.compose(d)
        self.assertEqual([b["title"] for b in r.buttons], ["Xem lịch khai giảng", "Đăng ký tư vấn"])
        self.assertEqual(r.options()["Đăng ký tư vấn"], {"type": "handoff"})

    def test_recommendation_buttons_win(self):
        d = Decision("answer", slots={"learner": fill("child")}, skills=["course_advisor"], ask="branch")
        r = self.compose(d)
        self.assertEqual([b["action"]["slot"] for b in r.buttons], ["course", "course", "course"])

    def test_missing_course_uses_fallback_and_records_error(self):
        d = Decision("answer", slots={}, skills=["duration"])
        r = self.compose(d)
        self.assertEqual(r.errors[0]["type"], "render_error")
        self.assertIn("chưa hiểu ý", r.messages[0])
        self.assertFalse(any("{{" in m or "{%" in m for m in r.messages))

    def test_greeting_first(self):
        d = decide(ConversationState("1"), Understanding(), CAT)
        self.assertIn("Trợ lý Sao Việt của Tin Học Sao Việt", self.compose(d).messages[0])

    def test_silent_sends_nothing(self):
        r = self.compose(Decision("silent"))
        self.assertEqual((r.messages, r.buttons), ([], []))


class TestLimits(unittest.TestCase):
    def test_buttons_are_unique_capped_and_truncated(self):
        r = Reply()
        many = [{"title": "Một tiêu đề rất rất dài quá mức", "action": {}}] * 2
        many += [{"title": f"Nút {i}", "action": {}} for i in range(20)]
        add_buttons(r, many)
        titles = [b["title"] for b in r.buttons]
        self.assertEqual(len(titles), 13)
        self.assertEqual(len(set(titles)), 13)
        self.assertTrue(all(len(t) <= 20 for t in titles))

    def test_long_reply_is_split(self):
        self.assertEqual([len(m) for m in split_messages(["a" * 1500, "b" * 1500])], [1500, 1500])
        self.assertEqual([len(m) for m in split_messages(["c" * 4500])], [2000, 2000, 500])
        self.assertEqual(split_messages(["x", "", "y"]), ["x\n\ny"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -p "test_engine_*.py" 2>&1 | tail -3`
Expected: ERROR — `No module named 'mmm_custom.engine.render'`.

- [ ] **Step 3: Implement render, context and actions**

`$APP/engine/render.py`:

```python
"""Template rendering for the bot (D-016, D-050, D-051): Vietnamese filters and the render guard.

Frappe's Jinja is sandboxed but uses DebugUndefined, so a missing value prints as template syntax;
`render_text` refuses any output that still contains `{{` or `{%` (and any rendering exception), and
the caller sends the fallback wording instead. The filters are registered in hooks.py (`jinja`).
"""

from datetime import date, datetime

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

WEEKDAYS = ("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật")


class RenderError(Exception):
    pass


def vnd(value):
    """1200000 → "1.200.000đ"."""
    try:
        amount = int(round(float(value or 0)))
    except (TypeError, ValueError):
        return str(value)
    return f"{amount:,}".replace(",", ".") + "đ"


def date_vi(value):
    """date(2026, 10, 4) → "Chủ nhật, 04/10"."""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    if not isinstance(value, date):
        return str(value)
    return f"{WEEKDAYS[value.weekday()]}, {value:%d/%m}"


def render_text(template, context, renderer):
    try:
        out = renderer(template or "", context)
    except Exception as e:
        raise RenderError(f"{type(e).__name__}: {e}") from e
    if "{{" in out or "{%" in out:
        raise RenderError("template syntax left in the output (missing value)")
    return out.strip()


def condition(expr, context, renderer):
    """Evaluate a Bot Skill Template `when` expression, e.g. "not schedules"."""
    return render_text("{% if " + expr + " %}1{% endif %}", context, renderer) == "1"


def frappe_renderer(template, context):
    return frappe.render_template(template, context)


def jinja_renderer():
    """Same sandbox, undefined handling and filters as the bench, without Frappe (tests, tools)."""
    import jinja2
    import jinja2.sandbox

    env = jinja2.sandbox.SandboxedEnvironment(undefined=jinja2.DebugUndefined)
    env.filters.update(vnd=vnd, date_vi=date_vi)
    return lambda template, context: env.from_string(template).render(context)
```

`$APP/engine/context.py`:

```python
"""The template context contract (D-050). Every template — skill answers, slot questions, greeting,
fallback, handoff and summary — gets exactly these keys; a skill's action adds schedules, promotions,
final_fee or recommendations for that skill only."""

from mmm_custom.engine.state import filled, value

# customer.* keys and the Bot Slot rows that feed them.
CUSTOMER_SLOTS = {"name": "customer_name", "learner": "learner", "learner_age": "learner_age", "shift": "preferred_shift"}


def brand_context(settings):
    return {"name": settings["brand_name"], "bot_name": settings["bot_name"], "you": settings["address_customer"],
            "me": settings["address_self"], "hotline": settings["hotline"], "zalo": settings["zalo"],
            "website": settings["website"], "signoff": settings["signoff"]}


def course_context(course, catalog):
    if not course:
        return {}
    return {"code": course.code, "name": course.name, "group": course.group, "fee": course.fee,
            "duration": course.duration, "audience": course.audience, "min_age": course.min_age,
            "max_age": course.max_age, "certificate": course.certificate, "image": course.image,
            "next_courses": [catalog.courses[c].name for c in course.next_courses if c in catalog.courses]}


def branch_context(branch):
    if not branch:
        return {}
    return {"name": branch.name, "address": branch.address, "hotline": branch.hotline, "map_url": branch.map_url,
            "area": branch.area}


def display(slot, raw, catalog):
    """A filled slot as a person reads it: option label, course name, or the raw value."""
    if slot.type == "choice" and slot.option(raw):
        return slot.option(raw).label
    if slot.type == "catalog" and slot.source == "course" and raw in catalog.courses:
        return catalog.courses[raw].name
    return str(raw)


def shown_slots(slots, catalog):
    return {s.key: display(s, value(slots, s.key), catalog) for s in catalog.slots if filled(slots, s.key)}


def base_context(slots, catalog, state):
    shown = shown_slots(slots, catalog)
    course_slot, branch_slot = catalog.slot_for("course"), catalog.slot_for("branch")
    course = catalog.courses.get(value(slots, course_slot.key)) if course_slot else None
    branch = catalog.branches.get(value(slots, branch_slot.key)) if branch_slot else None
    area = branch.area if branch else ((slots.get(branch_slot.key) or {}).get("parent", "") if branch_slot else "")
    customer = {key: shown.get(slot_key, "") for key, slot_key in CUSTOMER_SLOTS.items()}
    customer["is_returning"] = state.is_returning
    return {
        "brand": brand_context(catalog.settings), "customer": customer, "course": course_context(course, catalog),
        "branch": branch_context(branch), "area": area, "schedules": [], "promotions": [],
        "final_fee": course.fee if course else 0, "recommendations": [], "slots": shown,
        "missing": [s.label for s in catalog.slots if s.required and not filled(slots, s.key)],
    }
```

`$APP/engine/actions.py`:

```python
"""Action registry (D-049): what a Bot Skill computes before its template renders. All lookups and
arithmetic are code here, never Jev (D-003). A new action = one function decorated with
@action("name") + the Select option in catalog_rules.ACTION_TYPES / the Bot Skill DocType.

An action returns extra template context; keys starting with "_" are instructions for the composer
(`_attachments`, `_buttons`), not template data."""

from dataclasses import dataclass

from mmm_custom.engine.context import CUSTOMER_SLOTS, branch_context
from mmm_custom.engine.render import vnd
from mmm_custom.engine.state import value

ACTIONS = {}


def action(name):
    def register(fn):
        ACTIONS[name] = fn
        return fn
    return register


@dataclass
class ActionInput:
    skill: object
    ctx: dict
    slots: dict
    catalog: object
    data: object
    today: object


def run_action(skill, ctx, slots, catalog, data, today):
    fn = ACTIONS.get(skill.action)
    return fn(ActionInput(skill, ctx, slots, catalog, data, today)) if fn else {}


@action("answer_template")
def answer_template(a):
    return {}


@action("handoff")
def handoff(a):
    return {}  # decide() hands the conversation off after this answer (D-058)


def find_schedules(data, ctx, today, limit):
    """Next open classes for the context's course; widen from branch + shift to anywhere when nothing
    matches. Also used for the handoff summary's next-step line (Task 6)."""
    course = ctx["course"]
    if not course:
        return []
    branch, shift = ctx["branch"].get("name"), ctx["customer"]["shift"] or None
    for b, s in dict.fromkeys(((branch, shift), (branch, None), (None, shift), (None, None))):
        rows = data.open_schedules(course["code"], b, s, today, limit)
        if rows:
            return rows
    return []


@action("schedule_lookup")
def schedule_lookup(a):
    return {"schedules": find_schedules(a.data, a.ctx, a.today, int(a.skill.config.get("limit", 3)))}


def applicable(promo, course, branch):
    """Empty course / group / branch lists on a promotion mean "all"."""
    return ((not promo["courses"] or course["code"] in promo["courses"])
            and (not promo["course_groups"] or course["group"] in promo["course_groups"])
            and (not promo["branches"] or branch in promo["branches"]))


def _discount(promo, fee):
    if promo["discount_type"] == "Percent":
        return fee * float(promo["discount_value"]) / 100
    return float(promo["discount_value"])


def _label(promo):
    if promo["discount_type"] == "Percent":
        return f"{float(promo['discount_value']):g}%"
    return vnd(promo["discount_value"])


@action("fee_quote")
def fee_quote(a):
    """Listed fee, every promotion that applies, and the final fee after the single best one."""
    course = a.ctx["course"]
    if not course:
        return {}
    promos = [p for p in a.data.active_promotions(a.today) if applicable(p, course, a.ctx["branch"].get("name"))]
    best = max((_discount(p, course["fee"]) for p in promos), default=0)
    return {"promotions": [{"title": p["title"], "discount": _label(p)} for p in promos],
            "final_fee": max(course["fee"] - best, 0)}


@action("branch_info")
def branch_info(a):
    area = a.ctx["area"]
    branches = a.catalog.branches_in(area) if area else list(a.catalog.branches.values())
    return {"branches": [branch_context(b) for b in branches]}


@action("send_media")
def send_media(a):
    media = a.skill.media or a.ctx["course"].get("image") or ""
    return {"_attachments": [media]} if media else {}


@action("recommend_courses")
def recommend_courses(a):
    """C2 course advisor: filters are data in action_config (D-071); C3.6 adds Jev fit scoring."""
    cfg = a.skill.config
    learner = value(a.slots, CUSTOMER_SLOTS["learner"])
    age = value(a.slots, CUSTOMER_SLOTS["learner_age"])
    audiences = [cfg["audience"]] if cfg.get("audience") else list((cfg.get("audience_by_learner") or {}).get(learner or "", []))
    course_slot = a.catalog.slot_for("course")
    group = (a.slots.get(course_slot.key) or {}).get("parent", "") if course_slot else ""
    picked = [c for c in a.catalog.courses.values()
              if (not audiences or c.audience in audiences)
              and (not age or (c.min_age or 0) <= int(age) <= (c.max_age or 200))
              and (not group or c.group == group)][: int(cfg.get("top", 3))]
    buttons = [{"title": c.button, "action": {"type": "slot", "slot": course_slot.key, "value": c.code}}
               for c in picked] if course_slot else []
    return {"recommendations": [{"course": c.name, "code": c.code, "fee": c.fee, "score": None} for c in picked],
            "_buttons": buttons}
```

- [ ] **Step 4: Replace the composer**

`$APP/engine/reply.py` (whole file):

```python
"""Turn a Decision into what the customer sees (D-050…D-054, D-072): paragraphs rendered from
templates with the context contract and the render guard, split under Messenger's limit, plus one set
of quick-reply buttons."""

from dataclasses import dataclass, field

from mmm_custom.engine.actions import run_action
from mmm_custom.engine.context import base_context
from mmm_custom.engine.render import RenderError, condition, render_text
from mmm_custom.engine.slot_types import REGISTRY

MAX_MESSAGE = 2000  # Messenger text limit
MAX_BUTTONS = 13    # Messenger quick replies per message
MAX_TITLE = 20      # Messenger quick-reply title
MAX_FOLLOW_UPS = 3  # D-054

FOLLOW_UP_ACTIONS = {
    "skill": lambda target: {"type": "skill", "skill": target},
    "slot": lambda target: {"type": "ask", "slot": target},
    "handoff": lambda target: {"type": "handoff"},
}


@dataclass
class Reply:
    messages: list = field(default_factory=list)
    buttons: list = field(default_factory=list)      # [{"title": str, "action": dict}]
    variants: list = field(default_factory=list)     # [{"skill": key, "variant": key}]
    attachments: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def options(self):
        return {b["title"]: b["action"] for b in self.buttons}


def split_messages(paragraphs, limit=MAX_MESSAGE):
    """Join paragraphs with blank lines, starting a new message before `limit` is exceeded."""
    messages, current = [], ""
    for p in (p.strip() for p in paragraphs if p):
        if not p:
            continue
        while len(p) > limit:  # a single oversized paragraph is cut hard
            if current:
                messages.append(current)
                current = ""
            messages.append(p[:limit])
            p = p[limit:]
        candidate = f"{current}\n\n{p}" if current else p
        if len(candidate) > limit:
            messages.append(current)
            current = p
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages


def add_buttons(reply, buttons):
    seen = {b["title"] for b in reply.buttons}
    for b in buttons:
        title = b["title"][:MAX_TITLE].strip()
        if title and title not in seen and len(reply.buttons) < MAX_BUTTONS:
            reply.buttons.append({"title": title, "action": b["action"]})
            seen.add(title)


def choose_template(skill, ctx, render):
    """First variant whose `when` holds; otherwise the variant without a condition."""
    default = None
    for t in skill.templates:
        if not t.when.strip():
            default = default or t
            continue
        try:
            if condition(t.when, ctx, render):
                return t
        except RenderError:
            continue
    return default


def compose(decision, state, catalog, render, data=None, today=None, extra=None):
    reply = Reply()
    if decision.type == "silent":
        return reply
    settings = catalog.settings
    ctx = {**base_context(decision.slots, catalog, state), **(extra or {})}
    paragraphs = []

    def fallback_text():
        try:
            return render_text(settings["fallback_template"], ctx, render) if settings["fallback_template"] else ""
        except RenderError:
            return ""

    def say(template, context, source):
        if not template:
            return
        try:
            paragraphs.append(render_text(template, context, render))
        except RenderError as e:  # D-051: never show template syntax
            reply.errors.append({"type": "render_error", "source": source, "detail": str(e)[:300]})
            text = fallback_text()
            if text and text not in paragraphs:
                paragraphs.append(text)

    if decision.greet:
        say(settings["greeting_template"], ctx, "greeting")
    if decision.fallback:
        say(settings["fallback_template"], ctx, "fallback")

    action_buttons, follow_ups = [], []
    for key in decision.skills:
        skill = catalog.skills[key]
        try:
            out = run_action(skill, ctx, decision.slots, catalog, data, today)
        except Exception as e:
            reply.errors.append({"type": "action_error", "source": key, "detail": str(e)[:300]})
            out = {}
        skill_ctx = {**ctx, **{k: v for k, v in out.items() if not k.startswith("_")}}
        template = choose_template(skill, skill_ctx, render)
        if template:
            say(template.text, skill_ctx, key)
            reply.variants.append({"skill": key, "variant": template.key})
        reply.attachments += out.get("_attachments", [])
        action_buttons += out.get("_buttons", [])
        follow_ups += [{"title": f.title, "action": FOLLOW_UP_ACTIONS[f.target_type](f.target)}
                       for f in skill.follow_ups if f.target_type in FOLLOW_UP_ACTIONS]

    ask_buttons = []
    if decision.ask:
        slot = catalog.slot(decision.ask)
        say(slot.ask_template, ctx, f"slot:{slot.key}")
        if slot.type in REGISTRY:
            ask_buttons = REGISTRY[slot.type].buttons(slot, decision.slots, catalog)

    for group in (action_buttons, ask_buttons, follow_ups[:MAX_FOLLOW_UPS]):  # D-072: one source of buttons
        if group:
            add_buttons(reply, group)
            break
    reply.messages = split_messages(paragraphs)
    return reply
```

- [ ] **Step 5: Wire pipeline, repo, hooks and data**

In `$APP/engine/pipeline.py` replace `turn.reply = compose(turn.decision, state, catalog, render)` with

```python
    turn.reply = compose(turn.decision, state, catalog, render, repo, repo.today())
```

and in `process_event` add `from mmm_custom.engine.render import frappe_renderer` to its local imports and replace `frappe.render_template` in the `run_turn(...)` call with `frappe_renderer`.

In `$APP/engine/repo.py` add `from mmm_custom.engine.render import WEEKDAYS` to the imports and these methods to `FrappeRepo`:

```python
    def open_schedules(self, course, branch, shift, today, limit):
        filters = {"course": course, "status": "Open", "start_date": [">=", today]}
        if branch:
            filters["branch"] = branch
        if shift:
            filters["shift"] = ["like", f"{shift}%"]
        rows = frappe.get_all("Course Schedule", filters=filters, fields=["start_date", "shift", "weekdays", "branch", "seats"],
                              order_by="start_date asc", limit=limit)
        return [{"date": r.start_date, "weekday": WEEKDAYS[r.start_date.weekday()], "shift": r.shift,
                 "weekdays": r.weekdays, "branch": r.branch, "seats_left": r.seats} for r in rows]

    def active_promotions(self, today):
        rows = frappe.get_all("Course Promotion", filters={"active": 1},
                              fields=["name", "title", "discount_type", "discount_value", "valid_from", "valid_to"])
        rows = [r for r in rows if (not r.valid_from or r.valid_from <= today) and (not r.valid_to or today <= r.valid_to)]
        courses = _children("Course Link", "Course Promotion", "courses", ["course"])
        groups = _children("Course Group Link", "Course Promotion", "course_groups", ["course_group"])
        branches = _children("Territory Link", "Course Promotion", "branches", ["branch"])
        return [{"title": r.title, "discount_type": r.discount_type, "discount_value": r.discount_value,
                 "courses": [c["course"] for c in courses.get(r.name, [])],
                 "course_groups": [g["course_group"] for g in groups.get(r.name, [])],
                 "branches": [b["branch"] for b in branches.get(r.name, [])]} for r in rows]
```

In `$APP/hooks.py`, below the `doc_events` block from Task 1, add:

```python
# Template filters for bot copy: {{ course.fee | vnd }} → "1.800.000đ", {{ s.date | date_vi }} → "Thứ 7, 04/10".
jinja = {"filters": ["mmm_custom.engine.render.vnd", "mmm_custom.engine.render.date_vi"]}
```

Data changes (demo copy + D-071 configs), then the settings field:

```bash
python3 - <<'EOF'
import json
from pathlib import Path
d = Path("/home/giabao/dev/dx-osd/frappe-custom/mmm_custom/mmm_custom/demo/saoviet")
skills = json.loads((d / "bot_skills.json").read_text(encoding="utf-8"))
by = {s["skill_key"]: s for s in skills}
by["branch_info"]["parameters"] = ["branch"]
by["kids_courses"]["action_config"] = {"top": 3, "audience": "Trẻ em"}
by["course_advisor"]["action_config"] = {"top": 3, "audience_by_learner": {
    "child": ["Trẻ em"], "self": ["Người đi làm", "Học sinh – Sinh viên"], "staff": ["Người đi làm", "Doanh nghiệp"]}}
by["greeting"]["templates"][0]["template"] = "Dạ {{ brand.me }} chào {{ brand.you }} ạ!"
(d / "bot_skills.json").write_text(json.dumps(skills, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
settings = json.loads((d / "settings.json").read_text(encoding="utf-8"))
settings["greeting_template"] = "Dạ {{ brand.me }} là {{ brand.bot_name }} của {{ brand.name }}, rất vui được hỗ trợ {{ brand.you }} ạ."
settings["max_skills_per_reply"] = 3
(d / "settings.json").write_text(json.dumps(settings, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
EOF
python3 - <<'EOF'
import sys; sys.path.insert(0, "/tmp/claude-1000/-home-giabao-dev-dx-osd/035e8dd8-981c-46e8-98a7-2d3604765935/scratchpad")
from dt import *
add_fields("Lead Engine Settings", [
    field("engine_section", "Section Break", "Conversation engine"),
    field("max_skills_per_reply", "Int", default="3", description="Most answers combined into one reply (D-054)"),
])
EOF
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 7: Verify on the running bench**

```bash
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost migrate >/tmp/mig.log 2>&1; tail -1 /tmp/mig.log; bench --site crm.localhost execute mmm_custom.demo.loader.load"
docker exec crm-frappe-1 bash -c "cd frappe-bench && ../env/bin/python -W ignore -c \"
import frappe; frappe.init(site='crm.localhost', sites_path='sites'); frappe.connect()
from mmm_custom.engine.repo import FrappeRepo, clear_catalog_cache
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import Event, run_turn
from mmm_custom.engine.render import frappe_renderer
clear_catalog_cache()
print(frappe.render_template('{{ 1800000 | vnd }}', {}))
fx = RecordingEffects()
t = run_turn(Event('customer_message', 'verify-c23', 1, 'học phí excel ở bình thạnh', {'id': 'verify'}), FrappeRepo(sandbox=True), fx, frappe_renderer)
print(t.reply.messages); print([b['title'] for b in t.reply.buttons]); print(t.reply.errors)
frappe.db.rollback()\""
```
Expected: `1.800.000đ`; one message with `học phí 1.800.000đ, đang ưu đãi còn 1.620.000đ ạ.` followed by the learner question ("Khóa học này dành cho ai ạ?"); buttons `['Cho tôi', 'Cho con em', 'Cho công ty']`; errors `[]`. (`rollback` leaves no sandbox row.)

- [ ] **Step 8: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/engine/render.py frappe-custom/mmm_custom/mmm_custom/engine/context.py \
  frappe-custom/mmm_custom/mmm_custom/engine/actions.py frappe-custom/mmm_custom/mmm_custom/engine/reply.py \
  frappe-custom/mmm_custom/mmm_custom/engine/pipeline.py frappe-custom/mmm_custom/mmm_custom/engine/repo.py \
  frappe-custom/mmm_custom/mmm_custom/hooks.py frappe-custom/mmm_custom/mmm_custom/demo/saoviet/bot_skills.json \
  frappe-custom/mmm_custom/mmm_custom/demo/saoviet/settings.json \
  frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/lead_engine_settings/lead_engine_settings.json \
  frappe-custom/mmm_custom/mmm_custom/tests/engine_fixtures.py frappe-custom/mmm_custom/mmm_custom/tests/test_engine_render.py \
  frappe-custom/mmm_custom/mmm_custom/tests/test_engine_actions.py frappe-custom/mmm_custom/mmm_custom/tests/test_engine_reply.py
git commit -m "feat(bot): add skill action registry, template context contract and guarded reply composition"
```

### Task 4: C2.4 — Lead writes (`territory`, `products`, slot fields) and returning-customer prefill

Implements layer **C2.4** (D-014, D-022, D-070). Out of scope: routing back to the Lead owner (Task 6 uses `is_returning`), duplicate merging (C7.2).

**Files:**
- Create: `$APP/engine/lead.py`
- Modify: `$APP/engine/repo.py` (`find_lead`, `save_lead`, `add_products`, `FrappeRepo.new_state` prefill), `$APP/engine/effects.py` (`save_lead`), `$APP/engine/pipeline.py` (`write_lead` step), `$APP/setup.py` (`CATALOG_FIELDS["CRM Lead"]`), `$APP/api.py` (catalog-based course detection + `products`)
- Create tests: `$T/test_engine_lead.py`
- Modify tests: `$T/test_engine_pipeline.py` (lead step), `$T/test_api.py` (Sao Việt courses)

**Interfaces:**
- Consumes: `Catalog`, `Slot.lead_field`, `Slot.option()`, `understand.match_courses(text, catalog)` (Task 2), `Decision.new_slots/skills`, `Skill.creates_lead`.
- Produces:
  - `lead.lead_updates(slots, catalog) -> (fields: dict, courses: list[Course])`, `lead.prefill_slots(lead_values: dict, catalog) -> dict`, `lead.contact_prefill(contact: dict, catalog) -> dict`, `lead.PLACEHOLDER_NAMES`.
  - `repo.find_lead(contact_id, contact, phone=None, email=None) -> str | None`, `repo.save_lead(state, fields, courses, contact) -> str`, `repo.add_products(lead_name, courses)`.
  - Effects method `save_lead(state, fields, courses, contact) -> str` (Recording: records `("save_lead", {"fields", "courses"})`, returns `state.lead`).
  - `pipeline.write_lead(turn, effects, catalog)`; event `lead_updated` payload `{conversation_id, lead, is_sandbox, fields: [names], courses: [codes]}`.
  - `api.detect_courses(text, catalog=None) -> list[Course]`, `api.detect_course_interest(text, catalog=None) -> str | None`.

- [ ] **Step 1: Write the failing tests**

`$T/test_engine_lead.py`:

```python
import importlib
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, fill

from mmm_custom.engine.lead import contact_prefill, lead_updates, prefill_slots

CAT = demo_catalog()


def lead_source(value):
    return {"value": value, "source": "lead", "confidence": 1.0}


class TestLeadMapping(unittest.TestCase):
    def test_slots_to_lead_fields(self):
        slots = {"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An"), "learner": fill("child"),
                 "learner_age": fill(8), "preferred_shift": fill("evening"), "customer_name": fill("Lan"),
                 "phone": fill("+84901234567"), "learner_extra": {"asked": 1}}
        fields, courses = lead_updates(slots, CAT)
        self.assertEqual(fields, {"territory": "CN Dĩ An", "learner_type": "Con em", "learner_age": 8,
                                  "preferred_shift": "Tối", "first_name": "Lan", "mobile_no": "+84901234567"})
        self.assertEqual([c.code for c in courses], ["VP-EXCEL"])

    def test_prefill_from_lead_never_courses(self):
        values = {"territory": "CN Dĩ An", "mobile_no": "+84901234567", "first_name": "Lan", "learner_type": "Con em",
                  "preferred_shift": "Tối", "learner_age": 9}
        self.assertEqual(prefill_slots(values, CAT), {
            "branch": lead_source("CN Dĩ An"), "learner": lead_source("child"), "learner_age": lead_source(9),
            "preferred_shift": lead_source("evening"), "customer_name": lead_source("Lan"),
            "phone": lead_source("+84901234567")})

    def test_prefill_skips_values_outside_catalog(self):
        values = {"territory": "CS1 Bình Thạnh", "first_name": "Khách Messenger", "learner_type": "Học sinh",
                  "learner_age": 0, "mobile_no": ""}
        self.assertEqual(prefill_slots(values, CAT), {})

    def test_contact_name_prefills_customer_name(self):
        self.assertEqual(contact_prefill({"name": "Nguyễn Văn A"}, CAT),
                         {"customer_name": {"value": "Nguyễn Văn A", "source": "contact", "confidence": 1.0}})
        self.assertEqual(contact_prefill({"name": "Khách Messenger"}, CAT), {})
        self.assertEqual(contact_prefill({}, CAT), {})

    def test_every_slot_lead_field_exists_on_crm_lead(self):
        saved = sys.modules.get("frappe")
        sys.modules["frappe"] = MagicMock()
        try:
            setup_mod = importlib.import_module("mmm_custom.setup")
        finally:
            if saved is None:
                sys.modules.pop("frappe", None)
            else:
                sys.modules["frappe"] = saved
        custom = {f["fieldname"] for f in setup_mod.CATALOG_FIELDS["CRM Lead"]}
        for slot in CAT.slots:
            self.assertIn(slot.lead_field, custom | {"products", "territory", "first_name", "mobile_no"}, slot.key)


if __name__ == "__main__":
    unittest.main()
```

Add to `$T/test_engine_pipeline.py`, inside `class TestRunTurn`:

```python
    def test_lead_saved_when_a_lead_field_slot_is_filled(self):
        with patch("mmm_custom.engine.pipeline.understand", return_value=Understanding(fills={"course": fill("VP-EXCEL")})):
            self.turn("excel")
        self.assertEqual(self.fx.of("save_lead")[0]["courses"], ["VP-EXCEL"])
        self.assertIn("lead_updated", [e["event"] for e in self.fx.of("emit")])

    def test_no_lead_write_for_greeting_or_no_lead_skill(self):
        self.turn("xin chào")
        with patch("mmm_custom.engine.pipeline.understand", return_value=Understanding(skills=["certificate_lookup"])):
            self.turn("tra cứu chứng nhận", message_id=6)
        self.assertEqual(self.fx.of("save_lead"), [])
        with patch("mmm_custom.engine.pipeline.understand", return_value=Understanding(skills=["hotline"])):
            self.turn("hotline", message_id=7)
        self.assertEqual(len(self.fx.of("save_lead")), 1)

    def test_lead_failure_is_recorded(self):
        fx = RecordingEffects()
        fx.save_lead = MagicMock(side_effect=RuntimeError("db"))
        with patch("mmm_custom.engine.pipeline.understand", return_value=Understanding(fills={"course": fill("VP-EXCEL")})):
            t = run_turn(parse_event(incoming("excel")), self.repo, fx, render)
        self.assertEqual(t.reply.errors[-1]["type"], "lead_failed")
        self.assertEqual(self.repo.states["7"].slots["course"]["value"], "VP-EXCEL")
```

In `$T/test_api.py`:
1. Below the existing `sys.path` block add:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog

CAT = demo_catalog()
```

2. At the end of `setUp` add:

```python
        catalog_patch = patch("mmm_custom.api.load_catalog", return_value=CAT)
        products_patch = patch("mmm_custom.api.add_products")
        catalog_patch.start()
        self.mock_add_products = products_patch.start()
        self.addCleanup(catalog_patch.stop)
        self.addCleanup(products_patch.stop)
```

3. Replace course fixtures and expectations (exact strings):
   - `"messages": [{"content": "Dang ky hoc tieng Anh"}],` → `"messages": [{"content": "Dang ky hoc excel"}],` and, in the same test, `"course_interest", "Tiếng Anh")` → `"course_interest", "Excel từ cơ bản đến nâng cao")`.
   - `"Chào cô, em muốn đăng ký học toán tư duy cho cháu"` → `"Chào cô, em muốn đăng ký học AutoCAD cho cháu"`, and `"course_interest": "Toán tư duy",` → `"course_interest": "AutoCAD 2D",`; at the end of that test add
     ```python
                    args = self.mock_add_products.call_args[0]
                    self.assertEqual((args[0], [c.code for c in args[1]]), ("CRM-LEAD-MATH-001", ["VKT-CAD2D"]))
     ```
   - `"Toi muon cho con hoc boi loi"` → `"Toi muon cho con hoc robotics"`, and `"course_interest", "Bơi lội")` → `"course_interest", "Robotics cơ bản")`.
   - Replace the whole `test_detect_course_interest_various_keywords` method with:
     ```python
    def test_detect_course_interest_from_catalog(self):
        self.assertEqual(detect_course_interest("Em muốn học Excel nâng cao", CAT), "Excel nâng cao & Dashboard")
        self.assertEqual(detect_course_interest("hoc autocad o dau"), "AutoCAD 2D")
        self.assertEqual(detect_course_interest("Robotics cho con 8 tuoi", CAT), "Robotics cơ bản")
        self.assertEqual(detect_course_interest("photoshop va illustrator", CAT), "Photoshop cơ bản, Illustrator")
        for text in ("Xin chào trung tâm!", "Tư vấn học phí giúp em", "", None):
            self.assertIsNone(detect_course_interest(text, CAT))
     ```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: FAIL/ERROR — `No module named 'mmm_custom.engine.lead'`, `RecordingEffects` has no `save_lead`, `mmm_custom.api` has no `load_catalog`.

- [ ] **Step 3: Implement the mapping, the Lead writes and the prefill**

`$APP/engine/lead.py`:

```python
"""What a conversation's slots mean for the CRM Lead, both ways (D-014, D-022, D-070) — pure.

Each Bot Slot names its Lead field in `lead_field`: `products` appends the course to the Lead's
standard products table, `territory` stores the branch, anything else is set as is (choice slots
store the option label, which is what a person reads in the CRM)."""

from mmm_custom.engine.state import filled, value

PLACEHOLDER_NAMES = ("Khách Messenger", "EduFlow Student", "")


def lead_updates(slots, catalog):
    fields, courses = {}, []
    for slot in catalog.slots:
        if not slot.lead_field or not filled(slots, slot.key):
            continue
        raw = value(slots, slot.key)
        if slot.lead_field == "products":
            if raw in catalog.courses:
                courses.append(catalog.courses[raw])
        elif slot.type == "choice":
            option = slot.option(raw)
            fields[slot.lead_field] = option.label if option else raw
        else:
            fields[slot.lead_field] = raw
    return fields, courses


def _entry(val, source):
    return {"value": val, "source": source, "confidence": 1.0}


def prefill_slots(lead_values, catalog):
    """Known facts from an existing Lead (source "lead"); never `products` — every conversation asks
    what the customer wants now (D-070). Values the catalog does not know are left for the bot to ask."""
    out = {}
    for slot in catalog.slots:
        if not slot.lead_field or slot.lead_field == "products":
            continue
        raw = lead_values.get(slot.lead_field)
        if raw in (None, "", 0):
            continue
        if slot.type == "catalog":
            known = catalog.branches if slot.source == "branch" else catalog.courses
            if raw not in known:
                continue
        elif slot.type == "choice":
            option = next((o for o in slot.options if raw in (o.label, o.value)), None)
            if not option:
                continue
            raw = option.value
        elif slot.lead_field == "first_name" and raw in PLACEHOLDER_NAMES:
            continue
        out[slot.key] = _entry(raw, "lead")
    return out


def contact_prefill(contact, catalog):
    """The name Facebook/Chatwoot already knows fills the name slot, so the bot never asks it."""
    name = " ".join(str(contact.get("name") or "").split())
    slot = next((s for s in catalog.slots if s.lead_field == "first_name"), None)
    if not slot or name in PLACEHOLDER_NAMES:
        return {}
    return {slot.key: _entry(name, "contact")}
```

In `$APP/engine/repo.py` add imports

```python
from mmm_custom.dedupe import find_matching_lead, normalize_phone
from mmm_custom.engine.lead import PLACEHOLDER_NAMES, contact_prefill, prefill_slots
```

these module functions (below `_json`):

```python
def find_lead(contact_id, contact, phone=None, email=None):
    """The Lead for a Chatwoot contact: crm_lead_id → chatwoot_contact_id → phone/email match."""
    attrs = contact.get("custom_attributes") or {}
    if attrs.get("crm_lead_id") and frappe.db.exists("CRM Lead", attrs["crm_lead_id"]):
        return attrs["crm_lead_id"]
    if contact_id:
        name = frappe.db.get_value("CRM Lead", {"chatwoot_contact_id": str(contact_id)})
        if name:
            return name
    if phone or email:
        matched = find_matching_lead(email, phone)
        if matched:
            return matched.name if hasattr(matched, "name") else matched.get("name")
    return None


def _append_products(doc, courses):
    have = {p.product_code for p in doc.get("products") or []}
    for c in courses:
        if c.code not in have:
            doc.append("products", {"product_code": c.code, "product_name": c.name, "qty": 1, "rate": c.fee,
                                    "amount": c.fee, "net_amount": c.fee})
    names = [p.product_name or p.product_code for p in doc.get("products") or []]
    if names:
        doc.course_interest = ", ".join(names)[:140]  # readable summary kept beside products (D-014)


def add_products(lead_name, courses):
    doc = frappe.get_doc("CRM Lead", lead_name)
    _append_products(doc, courses)
    doc.flags.lead_engine = True
    doc.save(ignore_permissions=True)


def save_lead(state, fields, courses, contact):
    """Create or update the conversation's Lead. Never overwrites a real name or a different phone a
    person entered; courses are appended, not replaced (D-022)."""
    name = state.lead if state.lead and frappe.db.exists("CRM Lead", state.lead) else None
    name = name or find_lead(state.contact_id, contact, fields.get("mobile_no"), contact.get("email"))
    if name:
        doc = frappe.get_doc("CRM Lead", name)
    else:
        raw_name = " ".join(str(contact.get("name") or "").split())
        doc = frappe.new_doc("CRM Lead")
        doc.update({"first_name": raw_name or PLACEHOLDER_NAMES[0], "source": "Messenger Bot",
                    "email": contact.get("email") or None, "chatwoot_contact_id": state.contact_id or None})
    for field, val in fields.items():
        if not doc.meta.has_field(field):
            continue
        if field == "first_name":
            if doc.first_name not in PLACEHOLDER_NAMES:
                continue
            doc.lead_name = val
        if field == "mobile_no":
            val = normalize_phone(val)
            if doc.mobile_no and doc.mobile_no != val:
                continue
        doc.set(field, val)
    _append_products(doc, courses)
    doc.flags.lead_engine = True  # learning.on_lead_update skips the engine's own saves (D-057)
    if name:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)
    return doc.name
```

and replace `FrappeRepo.new_state` with:

```python
    def new_state(self, event):
        """A new conversation starts from what CRM already knows about the contact (D-022, D-070)."""
        catalog = self.catalog()
        state = ConversationState(conversation_id=event.conversation_id, contact_id=str(event.contact.get("id") or ""),
                                  inbox_id=event.inbox_id, is_sandbox=self.sandbox,
                                  slots=contact_prefill(event.contact, catalog))
        lead = self.sandbox_lead if self.sandbox else find_lead(state.contact_id, event.contact)
        if not lead or not frappe.db.exists("CRM Lead", lead):
            return state
        meta = frappe.get_meta("CRM Lead")
        fields = sorted({s.lead_field for s in catalog.slots
                         if s.lead_field and s.lead_field != "products" and meta.has_field(s.lead_field)})
        values = (frappe.db.get_value("CRM Lead", lead, fields, as_dict=True) or {}) if fields else {}
        state.slots.update(prefill_slots(values, catalog))
        state.lead = lead
        earlier = state.contact_id and frappe.db.exists("Bot Conversation", {"contact_id": state.contact_id, "is_sandbox": 0})
        has_products = frappe.db.count("CRM Products", {"parenttype": "CRM Lead", "parent": lead})
        state.is_returning = bool(earlier or has_products or values.get("territory"))
        return state
```

In `$APP/engine/effects.py` add `import logging`, `from mmm_custom.data_quality import compute_data_quality`, `logger = logging.getLogger(__name__)`, and the methods:

```python
    # RecordingEffects
    def save_lead(self, state, fields, courses, contact):
        self.calls.append(("save_lead", {"fields": dict(fields), "courses": [c.code for c in courses]}))
        return state.lead
```

```python
    # ChatwootEffects
    def save_lead(self, state, fields, courses, contact):
        from mmm_custom.engine import repo

        name = repo.save_lead(state, fields, courses, contact)
        if state.contact_id and (contact.get("custom_attributes") or {}).get("crm_lead_id") != name:
            try:
                self.user.update_contact(state.contact_id, {"crm_lead_id": name})
            except Exception:
                logger.exception("crm_lead_id write-back to Chatwoot failed")
        try:
            compute_data_quality(name)
        except Exception:
            logger.exception("data quality update failed")
        return name
```

In `$APP/engine/pipeline.py` add `from mmm_custom.engine.lead import lead_updates` to the imports, this function above `run_turn`:

```python
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
```

and in `run_turn` insert `write_lead(turn, effects, catalog)` on the line between `apply_decision(...)` and `repo.save_state(state)`.

In `$APP/setup.py`, add a third key to `CATALOG_FIELDS` (after the `"CRM Product": [...]` list):

```python
	# Bot Slot lead_field targets that are not standard CRM Lead fields.
	"CRM Lead": [
		{"fieldname": "learner_type", "label": "Learner", "fieldtype": "Data", "insert_after": "course_interest"},
		{"fieldname": "learner_age", "label": "Learner Age", "fieldtype": "Int", "insert_after": "learner_type"},
		{"fieldname": "preferred_shift", "label": "Preferred Shift", "fieldtype": "Data", "insert_after": "learner_age"},
	],
```

In `$APP/api.py`:
- delete `COURSE_KEYWORD_PATTERNS` and the old `detect_course_interest`; delete `import re` if `grep -n "re\." frappe-custom/mmm_custom/mmm_custom/api.py` shows no other use;
- add imports `from mmm_custom.engine.repo import add_products, load_catalog` and `from mmm_custom.engine.understand import match_courses`;
- add:

```python
def detect_courses(text, catalog=None):
    """Courses named in the text, matched against the CRM catalog aliases (C2.4 replaces 3 hardcoded courses)."""
    if not text or not isinstance(text, str):
        return []
    try:
        catalog = catalog or load_catalog()
    except Exception:
        return []
    return match_courses(text, catalog)


def detect_course_interest(text, catalog=None):
    return ", ".join(c.name for c in detect_courses(text, catalog)) or None
```

- in `chatwoot_sync` replace `course_interest = detect_course_interest(msg_text)` with

```python
    courses = detect_courses(msg_text)
    course_interest = ", ".join(c.name for c in courses) or None
```

and directly before the `# 3. Log conversation to FCRM Note` comment add

```python
    if courses:
        try:
            add_products(lead_name, courses)
        except Exception as e:
            if hasattr(frappe, "log_error"):
                frappe.log_error(title="Failed to add course products to Lead", message=str(e))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: `OK`. If another `test_api` test now detects a course in its fixture text and its exact `get_doc` payload changes, update that expectation to the catalog course (ruling in the ledger).

- [ ] **Step 5: Verify on the running bench**

```bash
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost migrate >/tmp/mig.log 2>&1; tail -1 /tmp/mig.log"
docker exec crm-frappe-1 bash -c "cd frappe-bench && ../env/bin/python -W ignore -c \"
import frappe; frappe.init(site='crm.localhost', sites_path='sites'); frappe.connect()
from mmm_custom.engine import repo
from mmm_custom.engine.lead import lead_updates
from mmm_custom.engine.pipeline import Event
from mmm_custom.engine.state import ConversationState
cat = repo.load_catalog()
slots = {k: {'value': v} for k, v in {'course': 'VP-EXCEL', 'branch': 'CN Dĩ An', 'learner': 'child', 'phone': '+84901234567'}.items()}
fields, courses = lead_updates(slots, cat)
contact = {'id': 'verify-c24', 'name': 'Khách Kiểm Tra'}
name = repo.save_lead(ConversationState('verify-c24', contact_id='verify-c24'), fields, courses, contact)
d = frappe.get_doc('CRM Lead', name)
print(d.territory, d.learner_type, d.mobile_no, [p.product_code for p in d.products], d.course_interest)
s = repo.FrappeRepo().new_state(Event('customer_message', 'verify-c24b', 1, '', contact))
print(s.lead == name, s.is_returning, sorted(s.slots))
frappe.db.rollback()\""
```
Expected: `CN Dĩ An Con em +84901234567 ['VP-EXCEL'] Excel từ cơ bản đến nâng cao`, then `True True ['branch', 'customer_name', 'learner', 'phone']`. If the products child DocType is not `CRM Products`, or a products field name differs, fix the name from `frappe.get_meta('CRM Lead').get_field('products').options` (ruling).

- [ ] **Step 6: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/engine/lead.py frappe-custom/mmm_custom/mmm_custom/engine/repo.py \
  frappe-custom/mmm_custom/mmm_custom/engine/effects.py frappe-custom/mmm_custom/mmm_custom/engine/pipeline.py \
  frappe-custom/mmm_custom/mmm_custom/setup.py frappe-custom/mmm_custom/mmm_custom/api.py \
  frappe-custom/mmm_custom/mmm_custom/tests/test_engine_lead.py frappe-custom/mmm_custom/mmm_custom/tests/test_engine_pipeline.py \
  frappe-custom/mmm_custom/mmm_custom/tests/test_api.py
git commit -m "feat(crm): write bot slots to Lead territory, products and slot fields; prefill returning customers"
```

---

### Task 5: C2.5 — AI Decision Log and learning signals

Implements layer **C2.5** (D-043, D-056, D-057). Out of scope: `confirm_rejected` capture (needs the C3.2 confirmation turn; the type exists), the review UI (C9.2), the log browser (C5.2).

**Files:**
- Create: `$APP/engine/log.py`, `$APP/engine/learning.py`
- Create DocTypes: `AI Decision Log`, `Bot Learning Signal`; add `log_retention_days` to `Lead Engine Settings`
- Modify: `$APP/engine/pipeline.py` (write log + signals), `$APP/engine/repo.py` (`write_log`, `write_signal`), `$APP/hooks.py` (CRM Lead `on_update`, daily purge)
- Modify tests: `$T/engine_fixtures.py` (FakeRepo logs), `$T/test_doctype_json.py` (expected list)
- Create tests: `$T/test_engine_log.py`

**Interfaces:**
- Consumes: `Turn` (Task 1: `event, state, understanding, decision, reply, slots_before, pending_before, status_before, turns_before, stuck_before, reason`), `Understanding.matches/unmatched`, `Reply.errors`.
- Produces:
  - `log.log_row(turn, jev=None) -> dict` (AI Decision Log field values; all JSON fields are JSON strings), `log.signals(turn) -> list[dict]` (Bot Learning Signal field values), `log.purge_old_logs()`.
  - `learning.corrections(before: {"territory", "products"}, after: same, bot_slots: dict, catalog) -> list[{"field", "bot_value", "new_value"}]`, `learning.on_lead_update(doc, method=None)`.
  - Repo methods `write_log(row)`, `write_signal(row)`.
  - AI Decision Log fields used later: `message_id`, `decision_type`, `asked_slot`, `reason`, `reply_text`, `reply_buttons`, `slots_before`, `pending_before`, `status_before`, `turns_before`, `stuck_before`, `jev_status`, `is_sandbox`, `bot_conversation`, `lead`.

- [ ] **Step 1: Write the failing tests**

In `$T/engine_fixtures.py`, `FakeRepo.__init__` gets `self.logs, self.signals = [], []`, and `FakeRepo` gets:

```python
    def write_log(self, row):
        self.logs.append(row)

    def write_signal(self, row):
        self.signals.append(row)
```

In `$T/test_doctype_json.py` add `"AI Decision Log", "Bot Learning Signal"` to the expected tuple.

`$T/test_engine_log.py`:

```python
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, fill, render

from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.learning import corrections
from mmm_custom.engine.log import log_row, signals
from mmm_custom.engine.pipeline import Event, run_turn
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding

CAT = demo_catalog()


def event(text="xin chào", message_id=5):
    return Event("customer_message", "7", message_id, text, {"id": 9})


class TestLogRow(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo(CAT)

    def test_one_row_per_processed_message_none_on_redelivery(self):
        run_turn(event(), self.repo, RecordingEffects(), render)
        run_turn(event(), self.repo, RecordingEffects(), render)
        self.assertEqual(len(self.repo.logs), 1)
        row = self.repo.logs[0]
        self.assertEqual((row["decision_type"], row["asked_slot"], row["jev_status"], row["message_id"]),
                         ("ask_slot", "course", "disabled", "5"))
        self.assertEqual(len(json.loads(row["reply_buttons"])), 8)
        self.assertEqual((json.loads(row["slots_before"]), row["status_before"], row["turns_before"]), ({}, "active", 0))
        self.assertIn("Trợ lý Sao Việt", row["reply_text"])
        self.assertEqual(json.loads(row["errors"]), [])

    def test_stuck_handoff_emits_stuck_and_unmatched_terms(self):
        self.repo.states["7"] = ConversationState("7", turns=3, stuck_turns=1)
        run_turn(event("abcxyz qwerty", 9), self.repo, RecordingEffects(), render)
        types = [(s["signal_type"], s.get("term")) for s in self.repo.signals]
        self.assertEqual(types, [("stuck", None), ("unmatched_term", "abcxyz"), ("unmatched_term", "qwerty")])

    def test_log_failure_never_raises(self):
        self.repo.write_log = MagicMock(side_effect=RuntimeError("db"))
        t = run_turn(event(), self.repo, RecordingEffects(), render)
        self.assertEqual(t.reply.errors[-1]["type"], "log_failed")


class TestSignalsPure(unittest.TestCase):
    def test_render_error_signal(self):
        from mmm_custom.engine.decide import Decision
        from mmm_custom.engine.pipeline import Turn
        from mmm_custom.engine.reply import Reply
        reply = Reply(errors=[{"type": "render_error", "source": "duration", "detail": "x"}])
        turn = Turn(event(), ConversationState("7"), Understanding(), Decision("answer"), reply)
        self.assertEqual([s["signal_type"] for s in signals(turn)], ["render_error"])
        self.assertEqual(log_row(turn)["decision_type"], "answer")


class TestCorrections(unittest.TestCase):
    def test_person_changes_branch_or_course_the_bot_set(self):
        bot = {"branch": fill("CN Dĩ An"), "course": fill("VP-EXCEL")}
        before = {"territory": "CN Dĩ An", "products": ["VP-EXCEL"]}
        after = {"territory": "CN Thuận An", "products": ["VP-WORD"]}
        self.assertEqual(corrections(before, after, bot, CAT), [
            {"field": "territory", "bot_value": "CN Dĩ An", "new_value": "CN Thuận An"},
            {"field": "products", "bot_value": "VP-EXCEL", "new_value": "VP-WORD"}])

    def test_no_signal_for_values_from_the_lead_or_unchanged(self):
        bot = {"branch": {"value": "CN Dĩ An", "source": "lead"}}
        self.assertEqual(corrections({"territory": "CN Dĩ An", "products": []},
                                     {"territory": "CN Thuận An", "products": []}, bot, CAT), [])
        bot = {"branch": fill("CN Dĩ An")}
        same = {"territory": "CN Dĩ An", "products": []}
        self.assertEqual(corrections(same, same, bot, CAT), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -p "test_engine_log.py" 2>&1 | tail -3`
Expected: ERROR — `No module named 'mmm_custom.engine.learning'`.

- [ ] **Step 3: Implement log, signals, learning and the DocTypes**

`$APP/engine/log.py`:

```python
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
        "reply_variants": _j(r.variants), "errors": _j(r.errors),
    }


def signals(turn):
    d, u, r, s = turn.decision, turn.understanding, turn.reply, turn.state
    base = {"bot_conversation": s.conversation_id, "lead": s.lead or None, "message_text": turn.event.text,
            "is_sandbox": int(s.is_sandbox), "status": "new"}
    out = []
    if d.type == "handoff" and d.handoff_reason == "stuck":
        out.append({**base, "signal_type": "stuck"})
        out += [{**base, "signal_type": "unmatched_term", "term": word} for word in u.unmatched]
    out += [{**base, "signal_type": "render_error", "details": _j(e)} for e in r.errors if e.get("type") == "render_error"]
    return out


def purge_old_logs():
    """Daily job (hooks.py): delete decision-log rows older than Lead Engine Settings.log_retention_days."""
    days = int(frappe.db.get_single_value("Lead Engine Settings", "log_retention_days") or 180)
    cutoff = frappe.utils.add_days(frappe.utils.now_datetime(), -days)
    frappe.db.delete("AI Decision Log", {"creation": ["<", cutoff]})
    frappe.db.commit()
```

`$APP/engine/learning.py`:

```python
"""`consultant_corrected` learning signals (D-057): a person changed a Lead's branch or course away from
what the bot set. Hooked on CRM Lead on_update; the engine's own saves carry doc.flags.lead_engine."""

import json

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

LEAD_FIELDS = (("branch", "territory"), ("course", "products"))


def corrections(before, after, bot_slots, catalog):
    out = []
    for source, field in LEAD_FIELDS:
        slot = catalog.slot_for(source)
        entry = (bot_slots.get(slot.key) or {}) if slot else {}
        bot_value = entry.get("value")
        if not bot_value or entry.get("source") == "lead":
            continue
        was, now = before.get(field), after.get(field)
        if field == "products":
            if bot_value in (was or []) and bot_value not in (now or []):
                out.append({"field": field, "bot_value": bot_value, "new_value": ", ".join(now or [])})
        elif was == bot_value and now != bot_value:
            out.append({"field": field, "bot_value": bot_value, "new_value": now or ""})
    return out


def _snapshot(doc):
    return {"territory": doc.get("territory"), "products": [p.product_code for p in doc.get("products") or []]}


def on_lead_update(doc, method=None):
    if doc.flags.get("lead_engine"):
        return
    before = doc.get_doc_before_save()
    if not before:
        return
    conv = frappe.get_all("Bot Conversation", filters={"lead": doc.name, "is_sandbox": 0}, fields=["name", "slots"],
                          order_by="modified desc", limit=1)
    if not conv:
        return
    from mmm_custom.engine.repo import load_catalog

    for change in corrections(_snapshot(before), _snapshot(doc), json.loads(conv[0].slots or "{}"), load_catalog()):
        frappe.get_doc({"doctype": "Bot Learning Signal", "signal_type": "consultant_corrected", "status": "new",
                        "bot_conversation": conv[0].name, "lead": doc.name,
                        "details": json.dumps(change, ensure_ascii=False)}).insert(ignore_permissions=True)
```

DocTypes:

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, "/tmp/claude-1000/-home-giabao-dev-dx-osd/035e8dd8-981c-46e8-98a7-2d3604765935/scratchpad")
from dt import *
write("AI Decision Log", [
    field("bot_conversation", "Link", options="Bot Conversation", in_list_view=1, in_standard_filter=1),
    field("lead", "Link", options="CRM Lead", in_standard_filter=1),
    field("message_id", "Data", "Message ID"),
    field("message_text", "Small Text", in_list_view=1),
    field("is_sandbox", "Check", in_standard_filter=1),
    field("understanding_section", "Section Break", "Understanding"),
    field("tapped", "Check", "Button Tap"),
    field("keyword_matches", "JSON"),
    field("jev_status", "Select", "Jev Status", options="disabled\nok\nunavailable\nskipped_cost_guard", default="disabled", in_standard_filter=1),
    field("model_version", "Data"),
    field("latency_ms", "Int", "Latency (ms)"),
    field("input_tokens", "Int"),
    field("jev_questions", "JSON"),
    field("jev_answers", "JSON"),
    field("decision_section", "Section Break", "Decision"),
    field("decision_type", "Select", options="answer\nconfirm\nask_slot\nhandoff\nsilent", in_list_view=1, in_standard_filter=1),
    field("reason", "Small Text", in_list_view=1),
    field("asked_slot", "Data"),
    field("handoff_reason", "Data"),
    field("skills_answered", "Data"),
    field("status_before", "Data"),
    field("turns_before", "Int"),
    field("stuck_before", "Int"),
    field("slots_before", "JSON"),
    field("pending_before", "JSON"),
    field("slots_after", "JSON"),
    field("reply_section", "Section Break", "Reply"),
    field("reply_text", "Long Text"),
    field("reply_buttons", "JSON"),
    field("reply_variants", "JSON"),
    field("errors", "JSON"),
], autoname="hash", permissions=MANAGERS_READ)
write("Bot Learning Signal", [
    field("signal_type", "Select", options="confirm_rejected\nconsultant_corrected\nunmatched_term\nstuck\nrender_error", reqd=1, in_list_view=1, in_standard_filter=1),
    field("status", "Select", options="new\naccepted_as_example\nalias_proposed\ndismissed", default="new", in_list_view=1, in_standard_filter=1),
    field("term", "Data", in_list_view=1),
    field("bot_conversation", "Link", options="Bot Conversation"),
    field("lead", "Link", options="CRM Lead"),
    field("message_text", "Small Text"),
    field("details", "JSON"),
    field("is_sandbox", "Check"),
], autoname="hash", permissions=MANAGERS)
add_fields("Lead Engine Settings", [
    field("log_retention_days", "Int", default="180", description="AI Decision Log rows older than this are deleted daily"),
])
EOF
```

Repo methods (`FrappeRepo`):

```python
    def write_log(self, row):
        frappe.get_doc({"doctype": "AI Decision Log", **row}).insert(ignore_permissions=True)

    def write_signal(self, row):
        frappe.get_doc({"doctype": "Bot Learning Signal", **row}).insert(ignore_permissions=True)
```

In `$APP/engine/pipeline.py` add `from mmm_custom.engine.log import log_row, signals` and, in `run_turn`, replace the final `emit_events(effects, state, turn.decision)` / `return turn` with:

```python
    emit_events(effects, state, turn.decision)
    try:
        repo.write_log(log_row(turn))
        for row in signals(turn):
            repo.write_signal(row)
    except Exception as e:  # the log must never break a customer's turn
        turn.reply.errors.append({"type": "log_failed", "detail": str(e)[:300]})
    return turn
```

In `$APP/hooks.py`, below the `doc_events = {...}` comprehension add:

```python
# Learning signal: a person corrected the branch/course the bot set on a Lead (D-057).
doc_events["CRM Lead"] = {"on_update": "mmm_custom.engine.learning.on_lead_update"}
```

and extend `scheduler_events` to:

```python
scheduler_events = {
	"cron": {
		"0 8 * * *": ["mmm_custom.followup.run_daily"],
	},
	# AI Decision Log retention (Lead Engine Settings.log_retention_days, default 180).
	"daily": ["mmm_custom.engine.log.purge_old_logs"],
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 5: Verify on the running bench**

```bash
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost migrate >/tmp/mig.log 2>&1; tail -1 /tmp/mig.log"
docker exec crm-frappe-1 bash -c "cd frappe-bench && ../env/bin/python -W ignore -c \"
import frappe; frappe.init(site='crm.localhost', sites_path='sites'); frappe.connect()
from mmm_custom.engine.repo import FrappeRepo
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import Event, run_turn
from mmm_custom.engine.render import frappe_renderer
from mmm_custom.engine.log import purge_old_logs
purge_old_logs(); print('purge ok')
t = run_turn(Event('customer_message', 'verify-c25', 1, 'xin chào', {'id': 'verify'}), FrappeRepo(sandbox=True), RecordingEffects(), frappe_renderer)
print(frappe.get_all('AI Decision Log', filters={'bot_conversation': 'verify-c25'}, fields=['decision_type', 'asked_slot', 'jev_status', 'is_sandbox']))
frappe.db.rollback()\""
```
Expected: `purge ok`, then `[{'decision_type': 'ask_slot', 'asked_slot': 'course', 'jev_status': 'disabled', 'is_sandbox': 1}]`; the rollback leaves no sandbox rows.

- [ ] **Step 6: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/engine/log.py frappe-custom/mmm_custom/mmm_custom/engine/learning.py \
  frappe-custom/mmm_custom/mmm_custom/engine/pipeline.py frappe-custom/mmm_custom/mmm_custom/engine/repo.py \
  frappe-custom/mmm_custom/mmm_custom/hooks.py frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/ai_decision_log \
  frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/bot_learning_signal \
  frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/lead_engine_settings/lead_engine_settings.json \
  frappe-custom/mmm_custom/mmm_custom/tests/engine_fixtures.py frappe-custom/mmm_custom/mmm_custom/tests/test_engine_log.py \
  frappe-custom/mmm_custom/mmm_custom/tests/test_doctype_json.py
git commit -m "feat(bot): add AI Decision Log, learning signals and log retention"
```

### Task 6: C2.6 — Handoff, summary note, Chatwoot labels/attributes, silence rules

Implements layer **C2.6** (D-021, D-026, D-027, D-058, D-059). Out of scope: full routing rule D with specialty and hotness (C4.1), working hours (C4.2), wants-human/hot triggers (C3.4).

**Files:**
- Create: `$APP/engine/routing.py`, `$APP/engine/handoff.py`, `$APP/engine/chatwoot_setup.py`
- Modify: `$APP/engine/pipeline.py` (`run_turn` handoff flow, `apply_decision` answered skills), `$APP/engine/state.py` (`answered`), `$APP/engine/repo.py` (consultants, load, owner, `set_lead_owner`, `mark_consultant_replied`, `close_conversation`, `answered_skills`), `$APP/engine/effects.py` (`handoff`), `$APP/engine/reply.py` (handoff paragraph), `$APP/bot_api.py` (silence rules), `$APP/chatwoot_client.py` (4 methods), `$APP/demo/chatwoot_seed.py` (team constants from routing)
- Modify data: DocType `Bot Conversation` (+`answered_skills`), `Lead Engine Settings` (+`max_stuck_turns`, `handoff_template`, `summary_template`), `$APP/demo/saoviet/settings.json`
- Modify tests: `$T/engine_fixtures.py`, `$T/test_engine_pipeline.py`, `$T/test_bot_api.py`, `$T/test_chatwoot_client.py`
- Create tests: `$T/test_engine_handoff.py`

**Interfaces:**
- Consumes: `base_context`, `find_schedules` (Task 3), `render_text`, `text.slug`, `Decision.handoff_reason/skills`, `ConversationState.is_returning/lead` (Task 4).
- Produces:
  - `routing.pick_consultant(branch, consultants: list[dict], load: dict, owner="") -> (dict | None, why: str)`; `routing.CENTRAL_TEAM = "Tổng đài"`, `routing.B2B_TEAM = "Doanh nghiệp (B2B)"`. Consultant dicts: `name` (= user email), `full_name`, `branch`, `chatwoot_agent_id`, `active`, `handles_b2b`, `level`.
  - `handoff.HandoffPlan` (`consultant, why, team, labels, attributes, summary, owner, errors`; properties `consultant_name`, `agent_id`, `consultant_ctx`), `handoff.plan_handoff(state, decision, catalog, repo, render) -> HandoffPlan`, `handoff.next_step(ctx, data, today) -> str`.
  - Effects method `handoff(conversation_id, plan, lead) -> list[errors]` (Recording records `("handoff", {...})`).
  - Repo read methods `consultants()`, `consultant_load() -> {consultant: open count}`, `lead_owner(lead) -> str`; module functions `set_lead_owner(lead, user)`, `mark_consultant_replied(conversation_id)`, `close_conversation(conversation_id)`.
  - `ChatwootClient.assign_team(conversation_id, team_id)`, `.set_conversation_attributes(conversation_id, attributes)`, `.list_custom_attributes(model="conversation_attribute")`, `.create_custom_attribute(key, display_name, model="conversation_attribute", display_type="text")`.
  - `chatwoot_setup.plan_attributes(slots, existing_keys) -> [(key, display_name)]`, `chatwoot_setup.ensure_conversation_attributes()`. Conversation attribute keys are `bot_<slot_key>`.

- [ ] **Step 1: Write the failing tests**

`$T/engine_fixtures.py`: in `FakeRepo.__init__` add `self.consultant_rows, self.load, self.owners = [], {}, {}`; add to `FakeRepo`:

```python
    def consultants(self):
        return list(self.consultant_rows)

    def consultant_load(self):
        return dict(self.load)

    def lead_owner(self, lead):
        return self.owners.get(lead, "")
```

and the module helper:

```python
def demo_consultants():
    return [{"name": c["email"], "full_name": c["full_name"], "branch": c["branch"], "chatwoot_agent_id": i + 1,
             "active": 1, "handles_b2b": c["handles_b2b"], "level": c["level"]}
            for i, c in enumerate(load_dataset()["consultants"])]
```

`$T/test_engine_handoff.py`:

```python
import sys
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, demo_consultants, fill, render, schedule

from mmm_custom.engine.chatwoot_setup import plan_attributes
from mmm_custom.engine.decide import Decision
from mmm_custom.engine.effects import ChatwootEffects
from mmm_custom.engine.handoff import HandoffPlan, plan_handoff
from mmm_custom.engine.routing import pick_consultant
from mmm_custom.engine.state import ConversationState

CAT = demo_catalog()
PEOPLE = [
    {"name": "mai@x", "full_name": "Mai", "branch": "CN Dĩ An", "chatwoot_agent_id": 11, "active": 1, "handles_b2b": 0},
    {"name": "lan@x", "full_name": "Lan", "branch": "CN Dĩ An", "chatwoot_agent_id": 12, "active": 1, "handles_b2b": 0},
    {"name": "an@x", "full_name": "An", "branch": "CN Dĩ An", "chatwoot_agent_id": None, "active": 1, "handles_b2b": 0},
    {"name": "hoa@x", "full_name": "Hoa", "branch": "", "chatwoot_agent_id": 20, "active": 1, "handles_b2b": 0},
    {"name": "b2b@x", "full_name": "B2B", "branch": "", "chatwoot_agent_id": 30, "active": 1, "handles_b2b": 1},
]


class TestRouting(unittest.TestCase):
    def test_least_loaded_in_branch_then_name(self):
        self.assertEqual(pick_consultant("CN Dĩ An", PEOPLE, {"mai@x": 3, "lan@x": 1})[0]["name"], "lan@x")
        self.assertEqual(pick_consultant("CN Dĩ An", PEOPLE, {"mai@x": 1, "lan@x": 1}),
                         (PEOPLE[1], "CN Dĩ An · ít khách nhất"))

    def test_consultant_without_chatwoot_agent_is_skipped(self):
        self.assertNotEqual(pick_consultant("CN Dĩ An", PEOPLE, {"mai@x": 5, "lan@x": 5})[0]["name"], "an@x")

    def test_returning_customer_goes_to_lead_owner(self):
        self.assertEqual(pick_consultant("CN Dĩ An", PEOPLE, {}, owner="hoa@x"),
                         (PEOPLE[3], "Khách quay lại · người phụ trách Lead"))
        self.assertEqual(pick_consultant("CN Dĩ An", PEOPLE, {}, owner="gone@x")[0]["name"], "lan@x")

    def test_central_team_when_branch_has_nobody(self):
        self.assertEqual(pick_consultant("CN Vũng Tàu", PEOPLE, {}), (PEOPLE[3], "Tổng đài · ít khách nhất"))
        self.assertEqual(pick_consultant("", [], {}), (None, "Chưa có tư vấn viên phù hợp"))


class TestPlan(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo(CAT)
        self.repo.consultant_rows = demo_consultants()
        self.repo.schedules = [schedule("VP-EXCEL", "CN Dĩ An", date(2026, 10, 6))]
        self.slots = {"course": {**fill("VP-EXCEL"), "parent": "Tin học văn phòng"}, "branch": fill("CN Dĩ An"),
                      "phone": fill("+84901234567"), "customer_name": fill("Lan"), "learner": fill("child"),
                      "learner_age": fill(9)}

    def plan(self, state=None, **settings):
        cat = demo_catalog(**settings) if settings else CAT
        decision = Decision("handoff", slots=self.slots, skills=["fee_quote"], handoff_reason="required_filled",
                            reason="Đã đủ thông tin bắt buộc")
        return plan_handoff(state or ConversationState("1", answered=["schedule_lookup"]), decision, cat, self.repo, render)

    def test_branch_consultant_team_labels_attributes(self):
        p = self.plan()
        self.assertEqual((p.consultant["branch"], p.team, p.why), ("CN Dĩ An", "CN Dĩ An", "CN Dĩ An · ít khách nhất"))
        self.assertEqual(p.labels, ["tin-hoc-van-phong", "cn-di-an"])
        self.assertEqual(p.attributes["bot_course"], "Excel từ cơ bản đến nâng cao")
        self.assertEqual(p.attributes["bot_learner"], "Con em")
        self.assertEqual(p.owner, p.consultant["name"])
        self.assertEqual(p.consultant_ctx, {"name": p.consultant["full_name"], "branch": "CN Dĩ An"})

    def test_summary_note_from_template_with_computed_next_step(self):
        s = self.plan().summary
        for part in ("Lan", "+84901234567", "Con em (9 tuổi)", "Excel từ cơ bản đến nâng cao (1.800.000đ)", "CN Dĩ An",
                     "lịch khai giảng", "học phí", "gọi xác nhận lớp Thứ 3, 06/10 (Tối 17:00–21:00) tại CN Dĩ An, còn 6 chỗ",
                     "CN Dĩ An · ít khách nhất"):
            self.assertIn(part, s)

    def test_returning_customer_goes_back_to_owner(self):
        owner = next(c for c in demo_consultants() if c["branch"] == "CN Biên Hòa")
        self.repo.owners = {"L1": owner["name"]}
        p = self.plan(ConversationState("1", lead="L1", is_returning=True))
        self.assertEqual((p.consultant["name"], p.team), (owner["name"], "CN Biên Hòa"))

    def test_broken_summary_template_falls_back(self):
        p = self.plan(summary_template="{{ nope.x }}")
        self.assertEqual(p.errors[0]["type"], "render_error")
        self.assertTrue(p.summary.startswith("🤖 Bot chuyển khách"))


class TestEffects(unittest.TestCase):
    def test_handoff_step_failure_does_not_stop_others(self):
        bot, user = MagicMock(), MagicMock()
        bot.assign_conversation.side_effect = RuntimeError("401")
        user.list_teams.return_value = [{"id": 4, "name": "cn dĩ an"}]
        plan = HandoffPlan({"name": "mai@x", "chatwoot_agent_id": 11, "branch": "CN Dĩ An"}, "why", "CN Dĩ An",
                           labels=["cn-di-an"], attributes={"bot_branch": "CN Dĩ An"}, summary="note", owner="mai@x")
        with patch("mmm_custom.engine.repo.set_lead_owner") as owner:
            errors = ChatwootEffects(bot, user).handoff(5, plan, "L1")
        self.assertEqual([e["step"] for e in errors], ["assign_agent"])
        bot.assign_team.assert_called_once_with(5, 4)
        bot.toggle_status.assert_called_once_with(5, "open")
        bot.add_labels.assert_called_once_with(5, ["cn-di-an"])
        bot.set_conversation_attributes.assert_called_once_with(5, {"bot_branch": "CN Dĩ An"})
        bot.send_private_note.assert_called_once_with(5, "note")
        owner.assert_called_once_with("L1", "mai@x")


class TestChatwootSetup(unittest.TestCase):
    def test_plan_attributes_skips_existing(self):
        self.assertEqual(plan_attributes(CAT.slots[:2], {"bot_course"}), [("bot_branch", "Bot · Chi nhánh")])


if __name__ == "__main__":
    unittest.main()
```

Add to `$T/test_engine_pipeline.py` (`from engine_fixtures import demo_consultants` at the top) inside `class TestRunTurn`:

```python
    def test_handoff_turn_assigns_and_tells_the_customer(self):
        self.repo.consultant_rows = demo_consultants()
        u = Understanding(fills={"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An"), "phone": fill("+84901234567")})
        with patch("mmm_custom.engine.pipeline.understand", return_value=u):
            t = self.turn("0901234567")
        handoff = self.fx.of("handoff")[0]
        self.assertTrue(handoff["agent_id"])
        self.assertEqual(handoff["team"], "CN Dĩ An")
        consultant = next(c for c in demo_consultants() if c["name"] == self.repo.states["7"].consultant)
        self.assertIn(f"tư vấn viên {consultant['full_name']} (CN Dĩ An)", self.fx.of("send")[0]["messages"][0])
        self.assertIn("CN Dĩ An · ít khách nhất", t.reason)
        self.assertEqual([e["consultant"] for e in self.fx.of("emit") if e["event"] == "handed_off"], [consultant["name"]])
```

Add to `$T/test_bot_api.py` (`from unittest.mock import MagicMock, patch`) inside the test class:

```python
    def test_human_agent_message_silences_the_bot(self):
        with patch.object(bot_api_mod, "mark_consultant_replied") as mark:
            self.assertEqual(self.post(incoming(message_type="outgoing", sender_type="user")),
                             {"status": "consultant_replied"})
        mark.assert_called_once_with("5")
        self.fr.enqueue.assert_not_called()

    def test_resolved_conversation_is_closed(self):
        with patch.object(bot_api_mod, "close_conversation") as close:
            self.assertEqual(self.post({"event": "conversation_resolved", "id": 5}), {"status": "closed"})
        close.assert_called_once_with("5")
```

Add to `$T/test_chatwoot_client.py` inside `TestChatwootClient`:

```python
    @patch("mmm_custom.chatwoot_client.requests")
    def test_assign_team(self, mock_requests):
        self._resp(mock_requests, "post", {})
        self.client.assign_team(5, 4)
        self.assertTrue(mock_requests.post.call_args[0][0].endswith("/conversations/5/assignments"))
        self.assertEqual(mock_requests.post.call_args[1]["json"], {"team_id": 4})

    @patch("mmm_custom.chatwoot_client.requests")
    def test_set_conversation_attributes(self, mock_requests):
        self._resp(mock_requests, "post", {})
        self.client.set_conversation_attributes(5, {"bot_branch": "CN Dĩ An"})
        self.assertTrue(mock_requests.post.call_args[0][0].endswith("/conversations/5/custom_attributes"))
        self.assertEqual(mock_requests.post.call_args[1]["json"], {"custom_attributes": {"bot_branch": "CN Dĩ An"}})

    @patch("mmm_custom.chatwoot_client.requests")
    def test_custom_attribute_definitions(self, mock_requests):
        self._resp(mock_requests, "get", [{"attribute_key": "bot_course"}])
        self.assertEqual(self.client.list_custom_attributes(), [{"attribute_key": "bot_course"}])
        self.assertEqual(mock_requests.get.call_args[1]["params"], {"attribute_model": "conversation_attribute"})
        self._resp(mock_requests, "post", {"id": 1})
        self.client.create_custom_attribute("bot_branch", "Bot · Chi nhánh")
        self.assertTrue(mock_requests.post.call_args[0][0].endswith("/custom_attribute_definitions"))
        self.assertEqual(mock_requests.post.call_args[1]["json"], {
            "attribute_display_name": "Bot · Chi nhánh", "attribute_key": "bot_branch",
            "attribute_model": "conversation_attribute", "attribute_display_type": "text"})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: ERROR — `No module named 'mmm_custom.engine.routing'` and friends.

- [ ] **Step 3: Implement routing, handoff plan, effects and client methods**

`$APP/engine/routing.py`:

```python
"""C2.6 consultant pick (D-058) — pure. C4.1 replaces it with full rule D (branch + specialty + hotness)."""

CENTRAL_TEAM = "Tổng đài"
B2B_TEAM = "Doanh nghiệp (B2B)"


def pick_consultant(branch, consultants, load, owner=""):
    """Returning customer → the Lead owner; else the least-loaded consultant of the branch; else the
    least-loaded central consultant. Only consultants linked to a Chatwoot agent can be assigned."""
    active = [c for c in consultants if c.get("active", 1) and c.get("chatwoot_agent_id")]
    if owner:
        for c in active:
            if c["name"] == owner:
                return c, "Khách quay lại · người phụ trách Lead"
    pool, why = [c for c in active if branch and c.get("branch") == branch], f"{branch} · ít khách nhất"
    if not pool:
        pool = [c for c in active if not c.get("branch") and not c.get("handles_b2b")]
        why = f"{CENTRAL_TEAM} · ít khách nhất"
    if not pool:
        return None, "Chưa có tư vấn viên phù hợp"
    return min(pool, key=lambda c: (load.get(c["name"], 0), c["name"])), why
```

`$APP/engine/handoff.py`:

```python
"""Handoff to a consultant (D-058): who gets the conversation, which Chatwoot team, labels, conversation
attributes (D-027) and the private summary note. Reads through the repo; the Chatwoot/CRM calls happen
in Effects.handoff."""

from dataclasses import dataclass, field

from mmm_custom.engine.actions import find_schedules
from mmm_custom.engine.context import base_context
from mmm_custom.engine.render import RenderError, date_vi, render_text
from mmm_custom.engine.routing import CENTRAL_TEAM, pick_consultant
from mmm_custom.engine.text import slug


@dataclass
class HandoffPlan:
    consultant: dict
    why: str
    team: str
    labels: list = field(default_factory=list)
    attributes: dict = field(default_factory=dict)
    summary: str = ""
    owner: str = ""
    errors: list = field(default_factory=list)

    @property
    def consultant_name(self):
        return (self.consultant or {}).get("name", "")

    @property
    def agent_id(self):
        return (self.consultant or {}).get("chatwoot_agent_id")

    @property
    def consultant_ctx(self):
        if not self.consultant:
            return {}
        return {"name": self.consultant.get("full_name") or self.consultant["name"],
                "branch": self.consultant.get("branch") or self.team}


def next_step(ctx, data, today):
    """The summary's suggestion for the consultant, computed from data — never Jev (D-058)."""
    if not ctx["course"]:
        return "hỏi nhu cầu khóa học của khách"
    rows = find_schedules(data, ctx, today, 1)
    if not rows:
        return f"gửi lịch khai giảng mới của {ctx['course']['name']}"
    s = rows[0]
    return f"gọi xác nhận lớp {date_vi(s['date'])} ({s['shift']}) tại {s['branch']}, còn {s['seats_left']} chỗ"


def plan_handoff(state, decision, catalog, repo, render):
    ctx = base_context(decision.slots, catalog, state)
    branch = ctx["branch"].get("name", "")
    owner = repo.lead_owner(state.lead) if state.is_returning and state.lead else ""
    consultant, why = pick_consultant(branch, repo.consultants(), repo.consultant_load(), owner)
    team = (consultant.get("branch") if consultant else branch) or CENTRAL_TEAM
    plan = HandoffPlan(consultant, why, team, owner=(consultant or {}).get("name", ""))
    course_slot = catalog.slot_for("course")
    group = ctx["course"].get("group") or ((decision.slots.get(course_slot.key) or {}).get("parent", "") if course_slot else "")
    plan.labels = [slug(x) for x in (group, branch) if x]
    plan.attributes = {f"bot_{key}": shown for key, shown in ctx["slots"].items()}
    answered = [catalog.skills[k].title for k in dict.fromkeys(state.answered + decision.skills) if k in catalog.skills]
    summary_ctx = {**ctx, "consultant": plan.consultant_ctx, "why": why, "reason": decision.reason,
                   "answered": answered, "next_step": next_step(ctx, repo, repo.today())}
    template = catalog.settings["summary_template"]
    try:
        plan.summary = render_text(template, summary_ctx, render) if template else ""
    except RenderError as e:
        plan.errors.append({"type": "render_error", "source": "summary", "detail": str(e)[:300]})
    if not plan.summary:
        plan.summary = f"🤖 Bot chuyển khách · {decision.reason} · {why}"
    return plan
```

`$APP/engine/chatwoot_setup.py`:

```python
"""Chatwoot conversation custom-attribute definitions for the bot's slots (D-027), so the values the bot
mirrors onto a conversation at handoff show in Chatwoot's sidebar. Idempotent; run after adding slots:

    bench --site crm.localhost execute mmm_custom.engine.chatwoot_setup.ensure_conversation_attributes
"""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.chatwoot_client import ChatwootClient


def plan_attributes(slots, existing_keys):
    return [(f"bot_{s.key}", f"Bot · {s.label}") for s in slots if f"bot_{s.key}" not in existing_keys]


def ensure_conversation_attributes():
    from mmm_custom.engine.repo import load_catalog

    conf = frappe.conf
    client = ChatwootClient(conf.get("chatwoot_api_url") or "http://chatwoot-rails:3000", conf.get("chatwoot_api_token"),
                            int(conf.get("chatwoot_account_id") or 1))
    existing = {a.get("attribute_key") for a in client.list_custom_attributes()}
    created = []
    for key, name in plan_attributes(load_catalog().slots, existing):
        client.create_custom_attribute(key, name)
        created.append(key)
    return {"created": created}
```

Append to `ChatwootClient` in `$APP/chatwoot_client.py`:

```python
    # Handoff (mmm_custom.engine.effects.ChatwootEffects.handoff).

    def assign_team(self, conversation_id: int, team_id: int) -> dict:
        resp = requests.post(f"{self._base}/conversations/{conversation_id}/assignments", headers=self._headers,
                             json={"team_id": team_id}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def set_conversation_attributes(self, conversation_id: int, attributes: dict) -> dict:
        resp = requests.post(f"{self._base}/conversations/{conversation_id}/custom_attributes", headers=self._headers,
                             json={"custom_attributes": attributes}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def list_custom_attributes(self, model: str = "conversation_attribute") -> list:
        resp = requests.get(f"{self._base}/custom_attribute_definitions", headers=self._headers,
                            params={"attribute_model": model}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def create_custom_attribute(self, key: str, display_name: str, model: str = "conversation_attribute",
                                display_type: str = "text") -> dict:
        resp = requests.post(f"{self._base}/custom_attribute_definitions", headers=self._headers, json={
            "attribute_display_name": display_name, "attribute_key": key, "attribute_model": model,
            "attribute_display_type": display_type}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
```

In `$APP/engine/effects.py`:

```python
    # RecordingEffects
    def handoff(self, conversation_id, plan, lead):
        self.calls.append(("handoff", {"agent_id": plan.agent_id, "team": plan.team, "labels": list(plan.labels),
                                       "attributes": dict(plan.attributes), "summary": plan.summary,
                                       "owner": plan.owner, "lead": lead}))
        return []
```

```python
    # ChatwootEffects
    def handoff(self, conversation_id, plan, lead):
        """D-058 steps 2–3; each step is independent so one failing call never blocks the rest."""
        from mmm_custom.engine import repo

        errors = []

        def step(name, fn, *args):
            try:
                fn(*args)
            except Exception as e:
                errors.append({"type": "handoff_step_failed", "step": name, "detail": str(e)[:300]})

        team_id = None
        try:
            team_id = next((t["id"] for t in self.user.list_teams() if t["name"].lower() == plan.team.lower()), None)
        except Exception as e:
            errors.append({"type": "handoff_step_failed", "step": "list_teams", "detail": str(e)[:300]})
        if team_id:  # team before agent: Chatwoot keeps the agent when they belong to the team
            step("assign_team", self.bot.assign_team, conversation_id, team_id)
        if plan.agent_id:
            step("assign_agent", self.bot.assign_conversation, conversation_id, plan.agent_id)
        step("open", self.bot.toggle_status, conversation_id, "open")
        if plan.labels:
            step("labels", self.bot.add_labels, conversation_id, plan.labels)
        if plan.attributes:
            step("attributes", self.bot.set_conversation_attributes, conversation_id, plan.attributes)
        if plan.summary:
            step("summary_note", self.bot.send_private_note, conversation_id, plan.summary)
        if plan.owner and lead:
            step("lead_owner", repo.set_lead_owner, lead, plan.owner)
        return errors
```

In `$APP/engine/reply.py`, in `compose`, directly after the `for key in decision.skills:` loop and before `ask_buttons = []`, add:

```python
    if decision.type == "handoff":
        say(settings["handoff_template"], ctx, "handoff")
```

`$APP/engine/state.py`: add the field `answered: list = field(default_factory=list)  # skill keys answered so far` after `turns`.

In `$APP/engine/repo.py`:
- `load_state` passes `answered=json.loads(d.answered_skills) if d.answered_skills else []`; `save_state` adds `"answered_skills": json.dumps(state.answered)` to `values`;
- add to `FrappeRepo`:

```python
    def consultants(self):
        return [dict(r) for r in frappe.get_all("Consultant", filters={"active": 1}, fields=[
            "name", "full_name", "branch", "chatwoot_agent_id", "level", "handles_b2b", "active"])]

    def consultant_load(self):
        rows = frappe.get_all("Bot Conversation", filters={"status": "handed_off", "is_sandbox": 0, "consultant": ["is", "set"]},
                              fields=["consultant", "count(name) as open"], group_by="consultant")
        return {r.consultant: r.open for r in rows}

    def lead_owner(self, lead):
        return frappe.db.get_value("CRM Lead", lead, "lead_owner") or ""
```

- add module functions:

```python
def set_lead_owner(lead, user):
    doc = frappe.get_doc("CRM Lead", lead)
    doc.lead_owner = user
    doc.flags.lead_engine = True
    doc.save(ignore_permissions=True)


def mark_consultant_replied(conversation_id):
    """D-059: a human answered — the bot stays silent in this conversation from now on. A conversation the
    bot never saw gets a row too, so the bot does not talk over an agent who is already chatting."""
    name = frappe.db.get_value("Bot Conversation", {"conversation_id": conversation_id})
    if name:
        frappe.db.set_value("Bot Conversation", name, "consultant_replied", 1)
    else:
        frappe.get_doc({"doctype": "Bot Conversation", "conversation_id": conversation_id, "status": "active",
                        "consultant_replied": 1, "slots": "{}", "pending": "{}"}).insert(ignore_permissions=True)


def close_conversation(conversation_id):
    name = frappe.db.get_value("Bot Conversation", {"conversation_id": conversation_id})
    if name:
        frappe.db.set_value("Bot Conversation", name, "status", "closed")
```

In `$APP/engine/pipeline.py`:
- imports: add `from mmm_custom.engine.handoff import plan_handoff`;
- `apply_decision`: add `state.answered = list(dict.fromkeys(state.answered + decision.skills))` after `state.pending_skill = …`;
- replace `run_turn` with:

```python
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

    plan, errors = None, []
    if turn.decision.type == "handoff":
        try:
            plan = plan_handoff(state, turn.decision, catalog, repo, render)
            turn.reason = f"{turn.reason} · {plan.why}"
            errors += plan.errors
        except Exception as e:
            errors.append({"type": "handoff_failed", "detail": str(e)[:300]})
    extra = {"consultant": plan.consultant_ctx} if plan else None
    turn.reply = compose(turn.decision, state, catalog, render, repo, repo.today(), extra)
    turn.reply.errors[:0] = errors
    if turn.reply.messages:
        try:
            effects.send(state.conversation_id, turn.reply)
        except Exception as e:  # never raise into RQ: a retry would answer twice
            turn.reply.errors.append({"type": "send_failed", "detail": str(e)[:300]})

    apply_decision(state, turn.decision, turn.reply, event)
    write_lead(turn, effects, catalog)
    if plan:
        state.consultant = plan.consultant_name
        try:
            turn.reply.errors += effects.handoff(state.conversation_id, plan, state.lead)
        except Exception as e:
            turn.reply.errors.append({"type": "handoff_failed", "detail": str(e)[:300]})
    repo.save_state(state)
    emit_events(effects, state, turn.decision)
    try:
        repo.write_log(log_row(turn))
        for row in signals(turn):
            repo.write_signal(row)
    except Exception as e:  # the log must never break a customer's turn
        turn.reply.errors.append({"type": "log_failed", "detail": str(e)[:300]})
    return turn
```

In `$APP/bot_api.py`: import `from mmm_custom.engine.repo import close_conversation, mark_consultant_replied`, and in `agent_bot_webhook` insert before the final `return {"status": "ignored", …}`:

```python
    if event.kind == "agent_message" and event.conversation_id:
        mark_consultant_replied(event.conversation_id)  # D-059: never talk over a person
        return {"status": "consultant_replied"}
    if event.kind == "resolved" and event.conversation_id:
        close_conversation(event.conversation_id)
        return {"status": "closed"}
```

In `$APP/demo/chatwoot_seed.py` replace the two constant lines `B2B_TEAM = …` / `CENTRAL_TEAM = …` with `from mmm_custom.engine.routing import B2B_TEAM, CENTRAL_TEAM`.

- [ ] **Step 4: Data: DocType fields and demo settings**

```bash
python3 - <<'EOF'
import sys; sys.path.insert(0, "/tmp/claude-1000/-home-giabao-dev-dx-osd/035e8dd8-981c-46e8-98a7-2d3604765935/scratchpad")
from dt import *
add_fields("Bot Conversation", [field("answered_skills", "JSON")])
add_fields("Lead Engine Settings", [
    field("handoff_section", "Section Break", "Handoff"),
    field("max_stuck_turns", "Int", default="2", description="Hand off after this many turns in a row with nothing understood"),
    field("handoff_template", "Small Text", description="Told to the customer at handoff; gets `consultant` (name, branch)"),
    field("summary_template", "Long Text", description="Private note for the consultant; gets answered, next_step, why, reason"),
])
EOF
python3 - <<'EOF'
import json
from pathlib import Path
p = Path("/home/giabao/dev/dx-osd/frappe-custom/mmm_custom/mmm_custom/demo/saoviet/settings.json")
s = json.loads(p.read_text(encoding="utf-8"))
s["max_stuck_turns"] = 2
s["handoff_template"] = ("Dạ {{ brand.me }} đã chuyển {{ brand.you }} cho {% if consultant %}tư vấn viên {{ consultant.name }} "
                         "({{ consultant.branch }}){% else %}tư vấn viên{% endif %}, bạn ấy sẽ nhắn {{ brand.you }} ngay ạ.")
s["summary_template"] = "\n".join([
    "🤖 Tóm tắt từ bot{% if customer.is_returning %} · khách QUAY LẠI{% endif %}",
    "👤 {{ customer.name or 'Khách' }}{% if slots.phone %} · {{ slots.phone }}{% endif %}{% if customer.learner %} · người học: {{ customer.learner }}{% if customer.learner_age %} ({{ customer.learner_age }} tuổi){% endif %}{% endif %}",
    "🎓 {{ course.name or 'chưa rõ khóa học' }}{% if course.fee %} ({{ course.fee | vnd }}){% endif %}{% if customer.shift %} · ca {{ customer.shift }}{% endif %} · {{ branch.name or 'chưa rõ chi nhánh' }}",
    "💬 Đã trả lời: {% if answered %}{{ answered | join(' ✓ · ') }} ✓{% else %}—{% endif %}",
    "➡️ Gợi ý: {{ next_step }}",
    "📌 Vì sao giao cho bạn: {{ why }}",
])
p.write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
EOF
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 6: Verify on the running stacks**

```bash
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost migrate >/tmp/mig.log 2>&1; tail -1 /tmp/mig.log; bench --site crm.localhost execute mmm_custom.demo.loader.load; bench --site crm.localhost execute mmm_custom.engine.chatwoot_setup.ensure_conversation_attributes"
docker exec crm-frappe-1 bash -c "cd frappe-bench && ../env/bin/python -W ignore -c \"
import frappe; frappe.init(site='crm.localhost', sites_path='sites'); frappe.connect()
from mmm_custom.engine.repo import FrappeRepo, clear_catalog_cache
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import Event, run_turn
from mmm_custom.engine.render import frappe_renderer
clear_catalog_cache(); fx = RecordingEffects(); repo = FrappeRepo(sandbox=True)
for i, text in enumerate(['học phí excel ở dĩ an', 'Cho tôi', 'Ca tối', '0901234567'], 1):
    t = run_turn(Event('customer_message', 'verify-c26', i, text, {'id': 'verify', 'name': 'Khách Kiểm Tra'}), repo, fx, frappe_renderer)
    print(t.decision.type, '|', t.reason)
h = fx.of('handoff')[0]; print(h['team'], h['agent_id'], h['labels']); print(h['summary']); print(t.reply.messages[-1])
frappe.db.rollback()\""
```
Expected: `answer | …`, `ask_slot | …`, `ask_slot | …`, `handoff | Đã đủ thông tin bắt buộc · CN Dĩ An · ít khách nhất`; then `CN Dĩ An <agent id> ['tin-hoc-van-phong', 'cn-di-an']`, the six-line summary with the Excel fee and a `gọi xác nhận lớp …` line, and the handoff sentence naming the consultant. The attribute command prints `{'created': [...7 keys]}` on the first run and `{'created': []}` on a second.

- [ ] **Step 7: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/engine/routing.py frappe-custom/mmm_custom/mmm_custom/engine/handoff.py \
  frappe-custom/mmm_custom/mmm_custom/engine/chatwoot_setup.py frappe-custom/mmm_custom/mmm_custom/engine/pipeline.py \
  frappe-custom/mmm_custom/mmm_custom/engine/state.py frappe-custom/mmm_custom/mmm_custom/engine/repo.py \
  frappe-custom/mmm_custom/mmm_custom/engine/effects.py frappe-custom/mmm_custom/mmm_custom/engine/reply.py \
  frappe-custom/mmm_custom/mmm_custom/bot_api.py frappe-custom/mmm_custom/mmm_custom/chatwoot_client.py \
  frappe-custom/mmm_custom/mmm_custom/demo/chatwoot_seed.py frappe-custom/mmm_custom/mmm_custom/demo/saoviet/settings.json \
  frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/bot_conversation/bot_conversation.json \
  frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/lead_engine_settings/lead_engine_settings.json \
  frappe-custom/mmm_custom/mmm_custom/tests/engine_fixtures.py frappe-custom/mmm_custom/mmm_custom/tests/test_engine_handoff.py \
  frappe-custom/mmm_custom/mmm_custom/tests/test_engine_pipeline.py frappe-custom/mmm_custom/mmm_custom/tests/test_bot_api.py \
  frappe-custom/mmm_custom/mmm_custom/tests/test_chatwoot_client.py
git commit -m "feat(bot): hand off to the branch consultant with summary note, labels, attributes and silence rules"
```

---

### Task 7: C2.7 — Playground: simulate a message, replay a logged decision

Implements layer **C2.7** (D-038, D-060). Out of scope: Jev on/off toggle and Jev columns (C3.2 adds them; the inspector already shows a `Jev` section reading `disabled`).

**Files:**
- Create: `$APP/engine/playground.py`, `$APP/mmm_custom/page/__init__.py`, `$APP/mmm_custom/page/bot_playground/__init__.py`, `bot_playground.json`, `bot_playground.js`
- Create tests: `$T/test_engine_playground.py`

**Interfaces:**
- Consumes: `run_turn`, `Event`, `RecordingEffects`, `FrappeRepo(sandbox=True, sandbox_lead=…)`, AI Decision Log fields (Task 5), `frappe_renderer`.
- Produces: whitelisted `mmm_custom.engine.playground.simulate(session, text, lead=None) -> dict`, `.reset(session)`, `.replay(log_name) -> {"then": dict, "now": dict}`; pure `playground.inspect(turn, effects) -> dict` (keys `understanding, jev, decision, reply, events, effects, state`), `playground.replay_state(log: dict, conv: dict) -> ConversationState`; desk page `/app/bot-playground` (roles System Manager, Sales Manager).

- [ ] **Step 1: Write the failing tests**

`$T/test_engine_playground.py`:

```python
import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, render

from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import Event, run_turn
from mmm_custom.engine.playground import inspect, replay_state

CAT = demo_catalog()
PAGE = Path(__file__).resolve().parent.parent / "mmm_custom" / "page" / "bot_playground"


class TestInspect(unittest.TestCase):
    def test_turn_is_shown_step_by_step(self):
        fx = RecordingEffects()
        turn = run_turn(Event("customer_message", "sandbox-x", 1, "học phí excel ở bình thạnh", {"id": "sandbox-x"}),
                        FakeRepo(CAT), fx, render)
        out = inspect(turn, fx)
        self.assertEqual(set(out), {"understanding", "jev", "decision", "reply", "events", "effects", "state"})
        self.assertEqual(out["understanding"]["fills"]["course"]["value"], "VP-EXCEL")
        self.assertEqual(out["jev"], {"status": "disabled"})
        self.assertEqual((out["decision"]["type"], out["decision"]["skills"]), ("answer", ["fee_quote"]))
        self.assertEqual(out["reply"]["buttons"], ["Cho tôi", "Cho con em", "Cho công ty"])
        self.assertIn("slot_filled", [e["event"] for e in out["events"]])
        self.assertEqual(out["effects"][0][0], "save_lead")
        json.dumps(out, default=str)  # must serialise for frappe.call

    def test_redelivery(self):
        self.assertEqual(inspect(None, RecordingEffects()), {"duplicate": True})


class TestReplayState(unittest.TestCase):
    def test_rebuilds_the_state_before_the_logged_turn(self):
        log = {"name": "abc", "lead": "L1", "status_before": "active", "turns_before": 2, "stuck_before": 1,
               "slots_before": json.dumps({"course": {"value": "VP-EXCEL"}}), "pending_before": json.dumps({"slot": "branch"})}
        s = replay_state(log, {"contact_id": "9", "is_returning": 1})
        self.assertEqual((s.conversation_id, s.lead, s.turns, s.stuck_turns, s.is_returning, s.is_sandbox),
                         ("replay-abc", "L1", 2, 1, True, True))
        self.assertEqual((s.slots["course"]["value"], s.pending["slot"]), ("VP-EXCEL", "branch"))


class TestPage(unittest.TestCase):
    def test_page_definition(self):
        data = json.loads((PAGE / "bot_playground.json").read_text(encoding="utf-8"))
        self.assertEqual((data["name"], data["module"], data["standard"]), ("bot-playground", "MMM Custom", "Yes"))
        self.assertEqual({r["role"] for r in data["roles"]}, {"System Manager", "Sales Manager"})
        js = (PAGE / "bot_playground.js").read_text(encoding="utf-8")
        for method in ("playground.simulate", "playground.reset", "playground.replay"):
            self.assertIn(method, js)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests -p "test_engine_playground.py" 2>&1 | tail -3`
Expected: ERROR — `No module named 'mmm_custom.engine.playground'`.

- [ ] **Step 3: Implement the Playground API**

`$APP/engine/playground.py`:

```python
"""Bot Playground (D-038, D-060): chat as a customer or replay a logged decision, and see every step.
Runs dry — RecordingEffects means nothing is sent to Chatwoot and no Lead is written; sandbox
conversations carry is_sandbox and are excluded from dashboards and consultant load."""

import copy
import json

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import Event, run_turn
from mmm_custom.engine.repo import FrappeRepo
from mmm_custom.engine.state import ConversationState

ROLES = ("System Manager", "Sales Manager")


def _loads(value):
    if isinstance(value, dict):
        return value
    return json.loads(value) if value else {}


def inspect(turn, effects):
    """One turn as the inspector shows it: keywords → Jev → decision → reply → events → side effects."""
    if turn is None:
        return {"duplicate": True}
    u, d, r, s = turn.understanding, turn.decision, turn.reply, turn.state
    return {
        "understanding": {"tapped": u.tapped, "fills": u.fills, "parents": u.parents, "ambiguous": u.ambiguous,
                          "skills": u.skills, "matches": u.matches, "unmatched": u.unmatched},
        "jev": {"status": "disabled"},
        "decision": {"type": d.type, "reason": turn.reason, "ask": d.ask, "skills": d.skills,
                     "pending_skill": d.pending_skill, "handoff_reason": d.handoff_reason, "stuck_turns": d.stuck_turns},
        "reply": {"messages": r.messages, "buttons": [b["title"] for b in r.buttons], "variants": r.variants,
                  "attachments": r.attachments, "errors": r.errors},
        "events": effects.of("emit"),
        "effects": [call for call in effects.calls if call[0] not in ("send", "emit")],
        "state": {"status": s.status, "slots": s.slots, "lead": s.lead, "consultant": s.consultant,
                  "is_returning": s.is_returning},
    }


def replay_state(log, conv):
    return ConversationState(
        conversation_id=f"replay-{log['name']}", contact_id=str(conv.get("contact_id") or ""), lead=log.get("lead") or "",
        status=log.get("status_before") or "active", slots=_loads(log.get("slots_before")),
        pending=_loads(log.get("pending_before")), turns=int(log.get("turns_before") or 0),
        stuck_turns=int(log.get("stuck_before") or 0), is_returning=bool(conv.get("is_returning")), is_sandbox=True)


class ReplayRepo(FrappeRepo):
    """Current catalog and data, the logged state, and no writes at all."""

    def __init__(self, state):
        super().__init__(sandbox=True)
        self.state = state

    def load_state(self, event):
        return copy.deepcopy(self.state)

    def save_state(self, state):
        pass

    def write_log(self, row):
        pass

    def write_signal(self, row):
        pass


def _renderer():
    from mmm_custom.engine.render import frappe_renderer

    return frappe_renderer


@frappe.whitelist() if frappe else (lambda f: f)
def simulate(session, text, lead=None):
    frappe.only_for(ROLES)
    cid = f"sandbox-{session}"
    last = frappe.db.get_value("Bot Conversation", {"conversation_id": cid}, "last_message_id") or 0
    event = Event("customer_message", cid, int(last) + 1, (text or "")[:1000], {"id": cid})
    effects = RecordingEffects()
    turn = run_turn(event, FrappeRepo(sandbox=True, sandbox_lead=lead or None), effects, _renderer())
    frappe.db.commit()
    return json.loads(json.dumps(inspect(turn, effects), default=str))


@frappe.whitelist() if frappe else (lambda f: f)
def reset(session):
    frappe.only_for(ROLES)
    frappe.db.delete("Bot Conversation", {"conversation_id": f"sandbox-{session}", "is_sandbox": 1})
    frappe.db.commit()


@frappe.whitelist() if frappe else (lambda f: f)
def replay(log_name):
    """Run a logged message again with today's data, templates and settings; show then vs now."""
    frappe.only_for(ROLES)
    log = frappe.get_doc("AI Decision Log", log_name).as_dict()
    conv = frappe.db.get_value("Bot Conversation", log.get("bot_conversation"), ["contact_id", "is_returning"],
                               as_dict=True) or {}
    state = replay_state(log, conv)
    effects = RecordingEffects()
    turn = run_turn(Event("customer_message", state.conversation_id, 0, log.get("message_text") or "",
                          {"id": state.contact_id}), ReplayRepo(state), effects, _renderer())
    then = {k: log.get(k) for k in ("creation", "decision_type", "reason", "skills_answered", "reply_text", "reply_buttons")}
    return json.loads(json.dumps({"then": then, "now": inspect(turn, effects)}, default=str))
```

- [ ] **Step 4: Create the desk page**

`$APP/mmm_custom/page/__init__.py` and `$APP/mmm_custom/page/bot_playground/__init__.py`: empty files.

`$APP/mmm_custom/page/bot_playground/bot_playground.json`:

```json
{
 "content": null,
 "creation": "2026-09-26 00:00:00.000000",
 "docstatus": 0,
 "doctype": "Page",
 "idx": 0,
 "modified": "2026-09-26 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "MMM Custom",
 "name": "bot-playground",
 "owner": "Administrator",
 "page_name": "bot-playground",
 "roles": [
  {"role": "System Manager"},
  {"role": "Sales Manager"}
 ],
 "script": null,
 "standard": "Yes",
 "style": null,
 "system_page": 0,
 "title": "Bot Playground"
}
```

`$APP/mmm_custom/page/bot_playground/bot_playground.js`:

```javascript
// Bot Playground (edu lead engine, D-038/D-060): chat as a customer and inspect every step of each turn.
// Runs dry: mmm_custom.engine.playground never sends to Chatwoot and never writes Leads.
frappe.pages["bot-playground"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Bot Playground"), single_column: true });
	new BotPlayground(page);
};

class BotPlayground {
	constructor(page) {
		this.page = page;
		this.session = frappe.utils.get_random(10);
		this.lead = page.add_field({
			fieldname: "lead", label: __("Returning customer (Lead)"), fieldtype: "Link", options: "CRM Lead",
			change: () => this.reset(),
		});
		page.set_primary_action(__("New conversation"), () => this.reset(), "refresh");
		page.add_inner_button(__("Replay a logged decision"), () => this.ask_replay());
		this.$root = $(`
			<div class="bot-pg">
				<div class="bot-pg-chat">
					<div class="bot-pg-log"></div>
					<form class="bot-pg-form">
						<input class="form-control" autocomplete="off" placeholder="${__("Type as the customer…")}">
						<button class="btn btn-primary btn-sm" type="submit">${__("Send")}</button>
					</form>
				</div>
				<div class="bot-pg-inspector">
					<p class="text-muted">${__("Send a message to see how the bot understands, decides and replies.")}</p>
				</div>
			</div>`).appendTo(page.main);
		$(`<style>
			.bot-pg { display: grid; grid-template-columns: minmax(280px, 2fr) 3fr; gap: 16px; }
			@media (max-width: 900px) { .bot-pg { grid-template-columns: 1fr; } }
			.bot-pg-chat, .bot-pg-inspector { border: 1px solid var(--border-color); border-radius: var(--border-radius-md);
				padding: 12px; background: var(--card-bg); }
			.bot-pg-log { height: 60vh; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; margin-bottom: 8px; }
			.bot-pg-msg { max-width: 85%; padding: 8px 12px; border-radius: 12px; white-space: pre-wrap; }
			.bot-pg-msg.customer { align-self: flex-end; background: var(--primary); color: var(--white); }
			.bot-pg-msg.bot { align-self: flex-start; background: var(--control-bg); }
			.bot-pg-chips { display: flex; flex-wrap: wrap; gap: 6px; }
			.bot-pg-form { display: flex; gap: 8px; }
			.bot-pg-inspector { max-height: 70vh; overflow-y: auto; }
			.bot-pg-inspector pre { white-space: pre-wrap; font-size: var(--text-xs); }
		</style>`).appendTo(this.$root);
		this.$log = this.$root.find(".bot-pg-log");
		this.$inspector = this.$root.find(".bot-pg-inspector");
		this.$root.find("form").on("submit", (e) => {
			e.preventDefault();
			const $input = this.$root.find("input");
			const text = $input.val().trim();
			if (text) {
				$input.val("");
				this.send(text);
			}
		});
	}

	bubble(text, who) {
		$(`<div class="bot-pg-msg ${who}"></div>`).text(text).appendTo(this.$log);
		this.$log.scrollTop(this.$log[0].scrollHeight);
	}

	chips(titles) {
		const $chips = $('<div class="bot-pg-chips"></div>').appendTo(this.$log);
		titles.forEach((title) => {
			$('<button class="btn btn-default btn-xs"></button>').text(title).on("click", () => this.send(title)).appendTo($chips);
		});
		this.$log.scrollTop(this.$log[0].scrollHeight);
	}

	async send(text) {
		this.bubble(text, "customer");
		const r = await frappe.call({
			method: "mmm_custom.engine.playground.simulate",
			args: { session: this.session, text, lead: this.lead.get_value() || null },
		});
		const out = r.message;
		if (out.duplicate) return;
		out.reply.messages.forEach((m) => this.bubble(m, "bot"));
		if (out.reply.buttons.length) this.chips(out.reply.buttons);
		this.show(out);
	}

	section(title, data) {
		return `<h5>${frappe.utils.escape_html(title)}</h5><pre>${frappe.utils.escape_html(JSON.stringify(data, null, 2))}</pre>`;
	}

	show(out) {
		this.$inspector.html([
			this.section(__("1 · Keyword matches"), out.understanding),
			this.section(__("2 · Jev"), out.jev),
			this.section(__("3 · Decision"), out.decision),
			this.section(__("4 · Reply and template variants"), out.reply),
			this.section(__("5 · Events that would fire"), out.events),
			this.section(__("6 · Side effects (not executed)"), out.effects),
			this.section(__("State after this turn"), out.state),
		].join(""));
	}

	async reset() {
		await frappe.call({ method: "mmm_custom.engine.playground.reset", args: { session: this.session } });
		this.session = frappe.utils.get_random(10);
		this.$log.empty();
		this.$inspector.html(`<p class="text-muted">${__("New conversation.")}</p>`);
	}

	ask_replay() {
		frappe.prompt(
			{ fieldname: "log", fieldtype: "Link", options: "AI Decision Log", label: __("AI Decision Log"), reqd: 1 },
			async (values) => {
				const r = await frappe.call({ method: "mmm_custom.engine.playground.replay", args: { log_name: values.log } });
				this.$inspector.html(
					this.section(__("Then (as logged)"), r.message.then) +
					this.section(__("Now (current data, templates and settings)"), r.message.now)
				);
			},
			__("Replay a decision"),
			__("Replay")
		);
	}
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 6: Verify on the running bench with screenshots**

```bash
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost migrate >/tmp/mig.log 2>&1; tail -1 /tmp/mig.log"
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: crm.localhost" http://127.0.0.1:8000/app/bot-playground
```
Expected: migrate clean; `200` (desk shell; the page itself loads after login).

With the Playwright MCP tools: open `http://127.0.0.1:8000/login`, log in as `Administrator` / `admin123`, open `/app/bot-playground`, send `học phí excel ở bình thạnh`, then tap chips until the bot hands off (enter `0901234567` when it asks for the phone). Take screenshots after the first turn (`$SCRATCH/c2-playground-1.png`) and at handoff (`$SCRATCH/c2-playground-handoff.png`). Then click **Replay a logged decision**, pick the newest AI Decision Log, and screenshot the then/now view (`$SCRATCH/c2-playground-replay.png`). Read each screenshot: chips visible, inspector sections 1–6 filled, no `{{` in bot bubbles. Finally click **New conversation** (removes the sandbox row).

- [ ] **Step 7: Commit**

```bash
git add frappe-custom/mmm_custom/mmm_custom/engine/playground.py frappe-custom/mmm_custom/mmm_custom/mmm_custom/page \
  frappe-custom/mmm_custom/mmm_custom/tests/test_engine_playground.py
git commit -m "feat(bot): add Bot Playground page to simulate conversations and replay logged decisions"
```

---

### Task 8: C2 verification (D-062) and docs

Runs the cluster's verification and records the result. No new product code except the integration script.

**Files:**
- Create: `scripts/test-bot-conversation.py`
- Modify docs: `docs/superpowers/specs/2026-09-26-edu-lead-engine-design.md` (§6.2 C2 rows ✅), `docs/superpowers/specs/2026-09-26-edu-lead-engine/decisions.md` (D-068…D-072), `current-state.md`, `README.md` (position), `AGENTS.md` (course-interest line)

- [ ] **Step 1: Write the integration script**

`scripts/test-bot-conversation.py`:

```python
#!/usr/bin/env python3
"""End-to-end check of the lead-engine bot (spec 2026-09-26-edu-lead-engine §7.2, D-062).

Sends signed Chatwoot Agent Bot webhooks to a CRM bench and reads back the AI Decision Log rows the
engine writes. Chatwoot does not have to be reachable: failed deliveries are recorded in each row's
`errors`, the decisions are still logged. Meant for a `-p crmverify` bench:

    python scripts/test-bot-conversation.py --url http://127.0.0.1:18000 --secret "$SECRET"
"""

import argparse
import hashlib
import hmac
import json
import sys
import time

import requests

DEFAULT_URL = "http://127.0.0.1:8000"
DEFAULT_HOST = "crm.localhost"


def sign(secret, ts, body):
    return "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


class Bench:
    def __init__(self, url, host, secret, user, password):
        self.url, self.host, self.secret = url.rstrip("/"), host, secret
        self.session = requests.Session()
        self.session.headers["Host"] = host
        self.session.post(f"{self.url}/api/method/login", json={"usr": user, "pwd": password}, timeout=15).raise_for_status()
        self.last_id = int(time.time() * 10) % 1_000_000_000
        self.rows = []

    def new_id(self):
        self.last_id += 1
        return self.last_id

    def post(self, conversation_id, contact_id, text, message_id=None, name="Khách Kiểm Thử"):
        message_id = message_id or self.new_id()
        contact = {"id": contact_id, "name": name, "custom_attributes": {}}
        payload = {"event": "message_created", "id": message_id, "content": text, "message_type": "incoming",
                   "private": False, "sender": {**contact, "type": "contact"},
                   "conversation": {"id": conversation_id, "inbox_id": 1, "meta": {"sender": contact}}}
        body, ts = json.dumps(payload).encode(), str(int(time.time()))
        requests.post(f"{self.url}/api/method/mmm_custom.bot_api.agent_bot_webhook", data=body, timeout=15, headers={
            "Host": self.host, "Content-Type": "application/json", "X-Chatwoot-Timestamp": ts,
            "X-Chatwoot-Signature": sign(self.secret, ts, body)}).raise_for_status()
        return message_id

    def logs(self, message_id):
        r = self.session.get(f"{self.url}/api/resource/AI Decision Log", timeout=15, params={
            "filters": json.dumps([["message_id", "=", str(message_id)]]), "fields": json.dumps(["*"]),
            "limit_page_length": 10})
        r.raise_for_status()
        return r.json()["data"]

    def wait(self, message_id, timeout=40):
        deadline = time.time() + timeout
        while time.time() < deadline:
            rows = self.logs(message_id)
            if rows:
                self.rows += rows
                return rows
            time.sleep(0.5)
        raise AssertionError(f"no AI Decision Log row for message {message_id} after {timeout}s — is the RQ worker running?")

    def turn(self, conversation_id, contact_id, text):
        return self.wait(self.post(conversation_id, contact_id, text))[0]

    def conversation(self, conversation_id):
        r = self.session.get(f"{self.url}/api/resource/Bot Conversation/{conversation_id}", timeout=15)
        r.raise_for_status()
        return r.json()["data"]


def check(name, ok, detail):
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  — {detail}"))
    return bool(ok)


def buttons_only(b, contact):
    """New customer answers only by tapping the first button (typing only what has no buttons)."""
    conv = b.new_id()
    row, turns = b.turn(conv, contact, "xin chào"), 1
    while row["decision_type"] != "handoff" and turns < 12:
        buttons, slot = json.loads(row["reply_buttons"] or "[]"), row["asked_slot"] or ""
        text = buttons[0] if buttons else ("0901 234 567" if "phone" in slot else "9" if "age" in slot else "Lan")
        row, turns = b.turn(conv, contact, text), turns + 1
    doc = b.conversation(conv)
    ok = row["handoff_reason"] == "required_filled" and doc["status"] == "handed_off" and doc.get("lead")
    return check("new customer, buttons only → handoff with a Lead", ok, f"{turns} turns, last: {row['decision_type']} {row['reason']}")


def free_text(b, contact):
    row = b.turn(b.new_id(), contact, "học phí excel ở bình thạnh")
    slots = json.loads(row["slots_after"])
    ok = (row["decision_type"] == "answer" and "fee_quote" in row["skills_answered"]
          and (slots.get("course") or {}).get("value") == "VP-EXCEL"
          and (slots.get("branch") or {}).get("value") == "CN Bình Thạnh" and "1.800.000đ" in row["reply_text"])
    return check("multi-slot free text → fee answer + both slots", ok, json.dumps(row, ensure_ascii=False)[:400])


def returning(b, contact):
    conv = b.new_id()
    row = b.turn(conv, contact, "chào em")
    before = json.loads(row["slots_before"])
    ok = ((before.get("branch") or {}).get("source") == "lead" and (before.get("phone") or {}).get("source") == "lead"
          and row["asked_slot"] == "course" and b.conversation(conv)["is_returning"] == 1)
    return check("returning customer → known facts prefilled, asks only the course", ok, json.dumps(before, ensure_ascii=False))


def duplicate(b, contact):
    conv, mid = b.new_id(), b.new_id()
    b.post(conv, contact, "excel", message_id=mid)
    b.post(conv, contact, "excel", message_id=mid)
    b.wait(mid)
    time.sleep(5)
    rows = b.logs(mid)
    return check("same webhook delivered twice → exactly one reply", len(rows) == 1, f"{len(rows)} log rows")


def jev_disabled(b):
    statuses = {r["jev_status"] for r in b.rows}
    return check("Jev disabled → every turn logged jev_status=disabled", statuses == {"disabled"}, str(statuses))


def main():
    p = argparse.ArgumentParser(description="Lead-engine bot end-to-end check (signed Agent Bot webhooks)")
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--secret", required=True, help="chatwoot_bot_webhook_secret from the site config")
    p.add_argument("--user", default="Administrator")
    p.add_argument("--password", default="admin123")
    a = p.parse_args()
    b = Bench(a.url, a.host, a.secret, a.user, a.password)
    base = b.new_id()
    results = [buttons_only(b, f"t{base}a"), free_text(b, f"t{base}b"), returning(b, f"t{base}a"),
               duplicate(b, f"t{base}c"), jev_disabled(b)]
    print(f"{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Full offline suite and live stacks**

Run: `python -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests 2>&1 | tail -3`
Expected: `OK`.

Run:
```bash
curl -s -o /dev/null -w "crm %{http_code}\n" http://127.0.0.1:8000; curl -s -o /dev/null -w "cw %{http_code}\n" http://127.0.0.1:3000
SECRET=$(docker exec crm-frappe-1 python3 -c "import json; print(json.load(open('/home/frappe/frappe-bench/sites/crm.localhost/site_config.json'))['chatwoot_webhook_secret'])")
python scripts/test-chatwoot-crm-sync.py --secret "$SECRET" 2>&1 | tail -3
```
Expected: `crm 200`, `cw 200` (or 302), and the sync test `5/5` passed. Never echo `$SECRET`.

- [ ] **Step 3: Fresh bench (`-p crmverify`) + integration script**

```bash
cd crm/docker
docker compose -p crmverify -f docker-compose.yml -f docker-compose.override.yml -f "$SCRATCH/crmverify-ports.yml" up -d
until [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18000)" = "200" ]; do sleep 10; done   # run via Monitor/background, ~10–15 min
docker compose -p crmverify exec -T frappe bash -c "cd frappe-bench && bench --site crm.localhost list-apps && bench --site crm.localhost set-config chatwoot_bot_webhook_secret verify-bot-secret && bench --site crm.localhost execute mmm_custom.demo.loader.load"
cd ../.. && python scripts/test-bot-conversation.py --url http://127.0.0.1:18000 --secret verify-bot-secret
```
Expected: `list-apps` shows `mmm_custom`; the loader prints the C1 counts; the script prints five `PASS` lines and `5/5 passed`. (`verify-bot-secret` exists only inside the throwaway bench.)

Tear down only the verify project:
```bash
cd crm/docker && docker compose -p crmverify -f docker-compose.yml -f docker-compose.override.yml -f "$SCRATCH/crmverify-ports.yml" down -v
docker volume ls --format '{{.Name}}' | grep -E '^crm'   # crm_frappe-bench-data and crm_mariadb-data must remain
```

- [ ] **Step 4: Update the docs**

1. Spec §6.2: set rows C2.1…C2.7 from `📝` to `✅` (`sed -i` on those seven lines only, like C1).
2. `decisions.md`: append rows D-068…D-072 exactly as listed in this plan's "Design decisions" section (date 2026-09-26, status approved — the user approved the C2 work without further questions).
3. `current-state.md`: header "as of 2026-09-26, C1 + C2 done"; module table rows — `bot_api.py` (verify → classify → enqueue; silence on agent messages; close on resolve), remove `bot_engine.py` rows (deleted), `api.py` detection now catalog-based and writes `products`, `bot_api.py:134 branch_owners` / `_find_best_agent` / `_create_or_update_lead` rows replaced by `engine/routing.py` (C4.1 replaces) and `engine/repo.py save_lead`; add one row per `engine/*.py` module (from this plan's file map), the three new DocTypes and the Playground page; config keys needed for the live bot: `chatwoot_bot_webhook_secret`, `chatwoot_bot_api_token` (still absent on the dev site → bot off until `scripts/setup-agent-bot.py` is run, a user decision since it answers real Messenger customers).
4. `README.md` position line: "C1 and C2 done (plans `…c01-data-foundation.md`, `…c02-conversation-engine.md`, verified on a fresh bench); C3 designed (spec §7.2), next is the C3 implementation plan. C4+ not designed."
5. `AGENTS.md` architecture note "Course Interest Detection": replace the hardcoded-course sentence with "incoming messages are matched against the CRM course catalog aliases (`mmm_custom.api.detect_courses`, using the lead engine's keyword matcher) and the courses are added to the Lead's standard `products` table, with `course_interest` kept as a readable summary."

- [ ] **Step 5: Commit**

```bash
git add scripts/test-bot-conversation.py docs/superpowers/specs/2026-09-26-edu-lead-engine-design.md \
  docs/superpowers/specs/2026-09-26-edu-lead-engine/decisions.md docs/superpowers/specs/2026-09-26-edu-lead-engine/current-state.md \
  docs/superpowers/specs/2026-09-26-edu-lead-engine/README.md AGENTS.md
git commit -m "docs(spec): mark edu lead engine C2 conversation engine done and add bot integration check"
```
