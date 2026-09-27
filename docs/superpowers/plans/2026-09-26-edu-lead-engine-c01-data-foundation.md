# Edu Lead Engine C1 — Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every piece of business data the lead engine needs — areas, branches, course groups, courses,
consultants, schedules, promotions, bot slots, bot skills, brand settings — exists as editable CRM data,
loaded with a large Tin Học Sao Việt demo dataset, with the matching Chatwoot agents and teams.

**Architecture:** Extend Frappe CRM first (custom fields on CRM Territory and CRM Product, created by
`setup.py` + a patch), and add new DocTypes to the `mmm_custom` app under module *MMM Custom*. Business
rules live in a pure module (`catalog_rules.py`) so they are unit-tested offline; DocType controllers
only call it. Demo data are JSON files loaded by an idempotent bench-executed loader; the Chatwoot side is
seeded from the bench through `ChatwootClient`.

**Tech Stack:** Frappe v15.121 (DocType JSON, Custom Field, patches, `bench execute`), Python 3.10+
stdlib `unittest` with `unittest.mock` (existing offline test style), Chatwoot REST API v1.

**Spec:** `docs/superpowers/specs/2026-09-26-edu-lead-engine-design.md` §7.1 (C1), with
`docs/superpowers/specs/2026-09-26-edu-lead-engine/decisions.md` (binding: D-013…D-016, D-053,
D-064…D-067). Read the agent briefing `docs/superpowers/specs/2026-09-26-edu-lead-engine/README.md` first.

## Global Constraints

- No edits to vendored `crm/` or `chatwoot/` in this cluster (spec §4; D-013).
- C1 **adds only**: `api.py`, `bot_api.py`, `bot_engine.py`, Activepieces keep working unchanged (spec §7.1).
- Module name is exactly `MMM Custom` (`frappe-custom/mmm_custom/mmm_custom/modules.txt`); DocType folders live in `frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/<snake_name>/`.
- `button_label` fields: `length: 20` (Messenger quick-reply limit, D-053).
- Demo consultant emails end in `@demo.saoviet.invalid` (D-066). Fees/promotions/schedules/consultants carry `is_demo_data = 1` where the DocType has the field.
- Never run `docker compose down -v`, `docker volume rm`, `docker system prune` on `crm`/`chatwoot`/`dx-osd` (AGENTS.md). Fresh-bench checks use project `crmverify` on ports 18000/19000.
- Code, identifiers, comments, commit messages in English; data labels and bot copy in Vietnamese.
- Commits: single line, conventional (`feat(scope): ...`), no trailer, explicit paths only. One commit per layer (C1.1 … C1.6).
- Offline tests: `python3 -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests` (baseline: 102 tests OK). Live checks run in container `crm-frappe-1`, bench dir `/home/frappe/frappe-bench`, site `crm.localhost`.

## Review Focus

1. **Re-running migrate/loader** on a site that already has the data must change nothing (no duplicate branches, schedules, users, Chatwoot agents or teams) — tested in Task 6 (`test_upsert_is_idempotent`, `test_generate_schedules_is_deterministic`) and verified live by running the loader twice.
2. **A consultant or schedule pointing at an area (group node) instead of a branch** must be rejected on save — tested in Task 3/4 via `catalog_rules.assert_leaf_branch`.
3. **Labels longer than 20 characters** in demo data (course, group, branch, follow-up buttons) must fail the data-integrity test before they reach Messenger — tested in Task 6 `test_button_labels_fit_messenger`.
4. **Dangling references in demo data** (course → unknown group, next course → unknown code, consultant → unknown branch, promotion → unknown course, skill parameter → unknown slot) must fail the integrity test — Task 6 `test_references_resolve`.
5. **Promotion with inverted dates or a percent outside 0–100** must be rejected on save — Task 4 `test_validate_promotion_*`.

---

## File Structure

| Path | Responsibility | Task |
|---|---|---|
| `frappe-custom/mmm_custom/mmm_custom/setup.py` (modify) | Add `CATALOG_FIELDS`, `ensure_custom_field()`, `create_catalog_fields()`; call from `setup()` | 1, 2 |
| `frappe-custom/mmm_custom/mmm_custom/patches/v1_1/__init__.py`, `create_catalog_fields.py` (create) | Patch that runs `create_catalog_fields()` on existing sites | 1 |
| `frappe-custom/mmm_custom/mmm_custom/patches.txt` (modify) | Register the patch | 1 |
| `frappe-custom/mmm_custom/mmm_custom/catalog_rules.py` (create) | Pure validation rules used by controllers | 3, 4, 5 |
| `frappe-custom/mmm_custom/mmm_custom/mmm_custom/doctype/*` (create) | New DocTypes (JSON + controller + `__init__.py`) | 2–5 |
| `frappe-custom/mmm_custom/mmm_custom/demo/__init__.py`, `loader.py`, `chatwoot_seed.py` (create) | Demo loader and Chatwoot seeding | 6 |
| `frappe-custom/mmm_custom/mmm_custom/demo/saoviet/*.json` (create) | Demo dataset | 6 |
| `frappe-custom/mmm_custom/mmm_custom/chatwoot_client.py` (modify) | Add inbox/agent/team methods | 6 |
| `frappe-custom/mmm_custom/mmm_custom/tests/test_catalog_setup.py`, `test_doctype_json.py`, `test_catalog_rules.py`, `test_demo_data.py`, `test_demo_loader.py`, `test_chatwoot_seed.py` (create); `test_chatwoot_client.py` (modify) | Offline tests | 1–6 |
| `docs/superpowers/specs/2026-09-26-edu-lead-engine-design.md`, companions (modify) | Status ✅, code map rows | 7 |

### Common DocType JSON envelope

Every new DocType JSON uses this envelope (fill `name`, `autoname`/`naming_rule`, `istable`/`issingle`,
`field_order`, `fields`, `permissions`). Child tables (`istable: 1`) have `"permissions": []`.

```json
{
 "actions": [],
 "doctype": "DocType",
 "engine": "InnoDB",
 "module": "MMM Custom",
 "name": "<DocType Name>",
 "owner": "Administrator",
 "modified": "2026-09-26 00:00:00.000000",
 "modified_by": "Administrator",
 "creation": "2026-09-26 00:00:00.000000",
 "row_format": "Dynamic",
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "links": [],
 "field_order": ["..."],
 "fields": ["..."],
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
  {"role": "Sales Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
  {"role": "Sales User", "read": 1, "report": 1}
 ]
}
```

Controller file `<snake>.py`:

```python
from frappe.model.document import Document


class <ClassName>(Document):
	pass
```

(Controllers that validate call `catalog_rules`, shown in their task.) Every folder also has an empty `__init__.py`.

---

## Phase C1.1 — Areas → branches on CRM Territory

### Task 1: Territory custom fields via a reusable custom-field helper

**Files:**
- Modify: `frappe-custom/mmm_custom/mmm_custom/setup.py`
- Create: `frappe-custom/mmm_custom/mmm_custom/patches/v1_1/__init__.py` (empty), `frappe-custom/mmm_custom/mmm_custom/patches/v1_1/create_catalog_fields.py`
- Modify: `frappe-custom/mmm_custom/mmm_custom/patches.txt`
- Test: `frappe-custom/mmm_custom/mmm_custom/tests/test_catalog_setup.py`

**Interfaces:**
- Produces: `setup.ensure_custom_field(dt: str, field: dict) -> None` (insert if missing, else update the listed properties); `setup.CATALOG_FIELDS: dict[str, list[dict]]` keyed by DocType; `setup.create_catalog_fields() -> None`.

- [ ] **Step 1: Write the failing test** — `tests/test_catalog_setup.py`

```python
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# setup.py imports frappe unconditionally; mock it only for this import so other modules keep
# their own ImportError fallbacks (e.g. bot_api's fake whitelist decorator).
with patch.dict(sys.modules, {"frappe": MagicMock()}):
    import mmm_custom.setup as setup_mod


class TestEnsureCustomField(unittest.TestCase):
    def setUp(self):
        self.frappe = MagicMock()

    def test_inserts_when_missing(self):
        self.frappe.db.exists.return_value = False
        field = {"fieldname": "branch_code", "label": "Branch Code", "fieldtype": "Data"}
        with patch.object(setup_mod, "frappe", self.frappe):
            setup_mod.ensure_custom_field("CRM Territory", field)
        self.frappe.db.exists.assert_called_with("Custom Field", "CRM Territory-branch_code")
        doc = self.frappe.get_doc.call_args[0][0]
        self.assertEqual(doc["doctype"], "Custom Field")
        self.assertEqual(doc["dt"], "CRM Territory")
        self.assertEqual(doc["fieldname"], "branch_code")

    def test_updates_when_present(self):
        self.frappe.db.exists.return_value = True
        existing = MagicMock()
        self.frappe.get_doc.return_value = existing
        field = {"fieldname": "branch_code", "label": "Mã chi nhánh", "fieldtype": "Data"}
        with patch.object(setup_mod, "frappe", self.frappe):
            setup_mod.ensure_custom_field("CRM Territory", field)
        self.frappe.get_doc.assert_called_with("Custom Field", "CRM Territory-branch_code")
        self.assertEqual(existing.label, "Mã chi nhánh")
        existing.save.assert_called_once()


class TestCatalogFields(unittest.TestCase):
    def test_territory_fields(self):
        names = [f["fieldname"] for f in setup_mod.CATALOG_FIELDS["CRM Territory"]]
        self.assertEqual(names, ["branch_code", "button_label", "branch_tier", "address", "hotline", "map_url", "aliases"])

    def test_button_labels_are_capped(self):
        for dt, fields in setup_mod.CATALOG_FIELDS.items():
            for f in fields:
                if f["fieldname"] == "button_label":
                    self.assertEqual(f.get("length"), 20, dt)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m unittest frappe-custom/mmm_custom/mmm_custom/tests/test_catalog_setup.py -v` (from repo root with `PYTHONPATH` unset; the test inserts the app dir itself)
Expected: FAIL — `AttributeError: module 'mmm_custom.setup' has no attribute 'ensure_custom_field'`.

- [ ] **Step 3: Implement** — append to `setup.py` (keep existing functions unchanged), and call `create_catalog_fields()` at the end of `setup()`:

```python
CATALOG_FIELDS = {
	"CRM Territory": [
		{"fieldname": "branch_code", "label": "Branch Code", "fieldtype": "Data", "unique": 1, "insert_after": "territory_name"},
		{"fieldname": "button_label", "label": "Button Label", "fieldtype": "Data", "length": 20, "insert_after": "branch_code"},
		{"fieldname": "branch_tier", "label": "Branch Tier", "fieldtype": "Select", "options": "\nfull\nstandard", "insert_after": "button_label"},
		{"fieldname": "address", "label": "Address", "fieldtype": "Small Text", "insert_after": "branch_tier"},
		{"fieldname": "hotline", "label": "Hotline", "fieldtype": "Data", "insert_after": "address"},
		{"fieldname": "map_url", "label": "Map URL", "fieldtype": "Data", "insert_after": "hotline"},
		{"fieldname": "aliases", "label": "Aliases", "fieldtype": "Small Text", "description": "Comma-separated names customers use, e.g. Dĩ An, Di An", "insert_after": "map_url"},
	],
}


def ensure_custom_field(dt, field):
	"""Create the Custom Field, or bring an existing one in line with `field`."""
	name = f"{dt}-{field['fieldname']}"
	if frappe.db.exists("Custom Field", name):
		doc = frappe.get_doc("Custom Field", name)
		for key, value in field.items():
			setattr(doc, key, value)
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc({"doctype": "Custom Field", "dt": dt, **field}).insert(ignore_permissions=True)


def create_catalog_fields():
	for dt, fields in CATALOG_FIELDS.items():
		for field in fields:
			ensure_custom_field(dt, field)
	frappe.db.commit()
```

`patches/v1_1/create_catalog_fields.py`:

```python
from mmm_custom.setup import create_catalog_fields


def execute():
	create_catalog_fields()
```

`patches.txt` — append under `[post_model_sync]`: `mmm_custom.patches.v1_1.create_catalog_fields`

- [ ] **Step 4: Run tests** — `python3 -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests` → Expected: `OK` (102 + 4 tests).

- [ ] **Step 5: Live check**

Run: `docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost migrate && bench --site crm.localhost execute frappe.db.exists --args \"['Custom Field','CRM Territory-branch_tier']\""`
Expected: migrate completes; prints `CRM Territory-branch_tier`.

- [ ] **Step 6: Commit** — `git add frappe-custom/mmm_custom/mmm_custom/setup.py frappe-custom/mmm_custom/mmm_custom/patches.txt frappe-custom/mmm_custom/mmm_custom/patches/v1_1/__init__.py frappe-custom/mmm_custom/mmm_custom/patches/v1_1/create_catalog_fields.py frappe-custom/mmm_custom/mmm_custom/tests/test_catalog_setup.py && git commit -m "feat(crm): add branch custom fields on CRM Territory for the lead engine catalog"`

---

## Phase C1.2 — Course groups → courses on CRM Product

### Task 2: `Course Group`, `Course Link`, `Course Group Link`, CRM Product fields, DocType JSON test

**Files:**
- Create: `mmm_custom/mmm_custom/doctype/course_group/{__init__.py,course_group.json,course_group.py}`
- Create: `mmm_custom/mmm_custom/doctype/course_link/{__init__.py,course_link.json,course_link.py}`
- Create: `mmm_custom/mmm_custom/doctype/course_group_link/{__init__.py,course_group_link.json,course_group_link.py}`
- Create: `mmm_custom/mmm_custom/doctype/__init__.py` (empty)
- Modify: `setup.py` (`CATALOG_FIELDS["CRM Product"]`)
- Test: `tests/test_doctype_json.py`; extend `tests/test_catalog_setup.py`

(All paths relative to `frappe-custom/mmm_custom/`.)

**Interfaces:**
- Produces DocTypes: `Course Group` (autoname `field:group_name`), `Course Link` (child, field `course` → CRM Product), `Course Group Link` (child, field `course_group` → Course Group). CRM Product custom fields listed below.

**DocType fields**

`Course Group` — `autoname: "field:group_name"`, `naming_rule: "By fieldname"`:

| fieldname | fieldtype | options / flags |
|---|---|---|
| group_name | Data | reqd, unique, in_list_view |
| button_label | Data | reqd, length 20, in_list_view |
| emoji | Data | |
| sort_order | Int | default 0 |
| aliases | Small Text | description "Comma-separated names customers use" |
| description | Small Text | |

`Course Link` — `istable: 1`, `editable_grid: 1`: `course` Link → `CRM Product`, reqd, in_list_view.
`Course Group Link` — `istable: 1`: `course_group` Link → `Course Group`, reqd, in_list_view.

`CATALOG_FIELDS["CRM Product"]` (in this order, each `insert_after` the previous; first after `product_name`):

```python
	"CRM Product": [
		{"fieldname": "course_group", "label": "Course Group", "fieldtype": "Link", "options": "Course Group", "in_standard_filter": 1, "insert_after": "product_name"},
		{"fieldname": "button_label", "label": "Button Label", "fieldtype": "Data", "length": 20, "insert_after": "course_group"},
		{"fieldname": "audience", "label": "Audience", "fieldtype": "Select", "options": "\nTrẻ em\nHọc sinh – Sinh viên\nNgười đi làm\nDoanh nghiệp", "insert_after": "button_label"},
		{"fieldname": "min_age", "label": "Min Age", "fieldtype": "Int", "insert_after": "audience"},
		{"fieldname": "max_age", "label": "Max Age", "fieldtype": "Int", "insert_after": "min_age"},
		{"fieldname": "duration_text", "label": "Duration", "fieldtype": "Data", "insert_after": "max_age"},
		{"fieldname": "certificate", "label": "Certificate", "fieldtype": "Data", "insert_after": "duration_text"},
		{"fieldname": "offer", "label": "Offered At", "fieldtype": "Select", "options": "all\nfull", "default": "all", "insert_after": "certificate"},
		{"fieldname": "aliases", "label": "Aliases", "fieldtype": "Small Text", "insert_after": "offer"},
		{"fieldname": "next_courses", "label": "Next Courses", "fieldtype": "Table MultiSelect", "options": "Course Link", "insert_after": "aliases"},
		{"fieldname": "is_demo_data", "label": "Demo Data", "fieldtype": "Check", "insert_after": "next_courses"},
	],
```

- [ ] **Step 1: Write the failing test** — `tests/test_doctype_json.py`

```python
import json
from pathlib import Path
import unittest

DOCTYPE_DIR = Path(__file__).resolve().parent.parent / "mmm_custom" / "doctype"
EXTERNAL = {"CRM Product", "CRM Territory", "User", "CRM Lead"}


def load_all():
    out = {}
    for folder in sorted(p for p in DOCTYPE_DIR.iterdir() if p.is_dir() and not p.name.startswith("__")):
        data = json.loads((folder / f"{folder.name}.json").read_text(encoding="utf-8"))
        out[data["name"]] = (folder, data)
    return out


class TestDocTypeJson(unittest.TestCase):
    def setUp(self):
        self.doctypes = load_all()

    def test_expected_doctypes_present(self):
        for name in ("Course Group", "Course Link", "Course Group Link"):
            self.assertIn(name, self.doctypes)

    def test_folder_names_and_module(self):
        for name, (folder, data) in self.doctypes.items():
            self.assertEqual(folder.name, name.lower().replace(" ", "_"), name)
            self.assertEqual(data["module"], "MMM Custom", name)
            self.assertTrue((folder / "__init__.py").exists(), name)
            self.assertTrue((folder / f"{folder.name}.py").exists(), name)

    def test_field_order_matches_fields(self):
        for name, (_, data) in self.doctypes.items():
            self.assertEqual(data["field_order"], [f["fieldname"] for f in data["fields"]], name)

    def test_links_resolve(self):
        known = set(self.doctypes) | EXTERNAL
        for name, (_, data) in self.doctypes.items():
            for f in data["fields"]:
                if f["fieldtype"] in ("Link", "Table", "Table MultiSelect"):
                    self.assertIn(f["options"], known, f"{name}.{f['fieldname']}")

    def test_table_multiselect_children_have_one_link(self):
        for name, (_, data) in self.doctypes.items():
            for f in data["fields"]:
                if f["fieldtype"] == "Table MultiSelect":
                    child = self.doctypes[f["options"]][1]
                    self.assertEqual(child.get("istable"), 1, f["options"])
                    self.assertEqual([c["fieldtype"] for c in child["fields"]], ["Link"], f["options"])

    def test_button_labels_capped(self):
        for name, (_, data) in self.doctypes.items():
            for f in data["fields"]:
                if f["fieldname"] in ("button_label", "title") and f.get("length"):
                    self.assertLessEqual(f["length"], 20, name)


if __name__ == "__main__":
    unittest.main()
```

Add to `TestCatalogFields` in `test_catalog_setup.py`:

```python
    def test_product_fields(self):
        names = [f["fieldname"] for f in setup_mod.CATALOG_FIELDS["CRM Product"]]
        self.assertEqual(names, ["course_group", "button_label", "audience", "min_age", "max_age",
                                 "duration_text", "certificate", "offer", "aliases", "next_courses", "is_demo_data"])
```

- [ ] **Step 2: Run to verify failure** — `python3 -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests` → Expected: FAIL (`FileNotFoundError` on `doctype` dir / `KeyError: 'CRM Product'`).

- [ ] **Step 3: Implement** — create the three DocType folders with the envelope + field tables above, and the `CRM Product` entry in `CATALOG_FIELDS`.

- [ ] **Step 4: Run tests** → Expected: `OK`.

- [ ] **Step 5: Live check** — `docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost migrate && bench --site crm.localhost execute frappe.db.exists --args \"['DocType','Course Group']\" && bench --site crm.localhost execute frappe.db.exists --args \"['Custom Field','CRM Product-next_courses']\""` → Expected: `Course Group`, `CRM Product-next_courses`.

- [ ] **Step 6: Commit** — explicit paths of the new doctype folders, `setup.py`, both tests: `git commit -m "feat(crm): add course groups and course custom fields on CRM Product"`

---

## Phase C1.3 — Consultants

### Task 3: `Consultant` DocType + `catalog_rules.assert_leaf_branch`

**Files:**
- Create: `mmm_custom/catalog_rules.py`
- Create: `mmm_custom/mmm_custom/doctype/consultant/{__init__.py,consultant.json,consultant.py}`
- Test: `tests/test_catalog_rules.py`; extend `tests/test_doctype_json.py` expected list with `"Consultant"`.

**Interfaces:**
- Produces: `catalog_rules.assert_leaf_branch(branch: str | None, is_group: callable[[str], bool | None]) -> None` — raises `ValueError("<branch> is an area, choose a branch")` when `is_group(branch)` is truthy; raises `ValueError("Unknown branch <branch>")` when it returns `None`; no-op when `branch` is empty.
- Produces DocType `Consultant` (autoname `field:user`).

`Consultant` fields:

| fieldname | fieldtype | options / flags |
|---|---|---|
| user | Link | User, reqd, unique, in_list_view |
| full_name | Data | fetch_from `user.full_name`, read_only, in_list_view |
| chatwoot_agent_id | Int | read_only |
| branch | Link | CRM Territory, in_list_view, in_standard_filter, description "Empty = central team" |
| level | Select | `Consultant\nTeam Lead`, default `Consultant`, in_list_view |
| specialties | Table MultiSelect | Course Group Link |
| handles_b2b | Check | |
| active | Check | default 1 |

Controller `consultant.py`:

```python
import frappe
from frappe.model.document import Document

from mmm_custom.catalog_rules import assert_leaf_branch


def territory_is_group(name):
	return frappe.db.get_value("CRM Territory", name, "is_group")


class Consultant(Document):
	def validate(self):
		try:
			assert_leaf_branch(self.branch, territory_is_group)
		except ValueError as e:
			frappe.throw(str(e))
```

- [ ] **Step 1: Failing test** — `tests/test_catalog_rules.py`

```python
import sys
from pathlib import Path
import unittest

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.catalog_rules import assert_leaf_branch

TREE = {"CN Dĩ An": 0, "Bình Dương": 1}


class TestAssertLeafBranch(unittest.TestCase):
    def test_empty_branch_is_allowed(self):
        assert_leaf_branch(None, TREE.get)
        assert_leaf_branch("", TREE.get)

    def test_leaf_branch_passes(self):
        assert_leaf_branch("CN Dĩ An", TREE.get)

    def test_area_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "is an area"):
            assert_leaf_branch("Bình Dương", TREE.get)

    def test_unknown_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown branch"):
            assert_leaf_branch("CN Mars", TREE.get)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run** → FAIL `ModuleNotFoundError: mmm_custom.catalog_rules`.
- [ ] **Step 3: Implement** `catalog_rules.py`:

```python
"""Pure validation rules for the lead-engine catalog DocTypes (no frappe import, unit-tested offline)."""


def assert_leaf_branch(branch, is_group):
	if not branch:
		return
	group = is_group(branch)
	if group is None:
		raise ValueError(f"Unknown branch {branch}")
	if group:
		raise ValueError(f"{branch} is an area, choose a branch")
```

and the `Consultant` DocType.
- [ ] **Step 4: Run tests** → `OK`.
- [ ] **Step 5: Live check** — migrate; then `bench --site crm.localhost execute frappe.db.exists --args "['DocType','Consultant']"` → `Consultant`.
- [ ] **Step 6: Commit** — `git commit -m "feat(crm): add Consultant doctype with branch validation"`

---

## Phase C1.4 — Course schedules + promotions

### Task 4: `Territory Link`, `Course Schedule`, `Course Promotion` + rules

**Files:**
- Modify: `mmm_custom/catalog_rules.py`
- Create: doctype folders `territory_link`, `course_schedule`, `course_promotion`
- Test: extend `tests/test_catalog_rules.py`, `tests/test_doctype_json.py` expected list.

**Interfaces:**
- Produces: `catalog_rules.validate_promotion(discount_type: str, discount_value: float, valid_from: date | None, valid_to: date | None) -> None` — `ValueError` when value ≤ 0, when Percent > 100, or when both dates set and `valid_to < valid_from`.
- Produces DocTypes: `Territory Link` (child: `branch` Link → CRM Territory), `Course Schedule` (autoname `hash`), `Course Promotion` (autoname `field:title`).

`Course Schedule` fields: `course` Link CRM Product reqd in_list_view in_standard_filter · `branch` Link CRM Territory reqd in_list_view in_standard_filter · `start_date` Date reqd in_list_view · `shift` Select `Sáng 8:30–11:00\nChiều 13:30–16:30\nTối 17:00–21:00` reqd in_list_view · `weekdays` Data (e.g. `T2, T4, T6`) · `seats` Int · `status` Select `Open\nFull\nStarted` default `Open` in_list_view · `is_demo_data` Check. Controller validates `assert_leaf_branch(self.branch, territory_is_group)` (same pattern as Consultant, importing `territory_is_group` from `mmm_custom.mmm_custom.doctype.consultant.consultant`).

`Course Promotion` fields: `title` Data reqd unique in_list_view · `discount_type` Select `Percent\nAmount` reqd · `discount_value` Float reqd in_list_view · `valid_from` Date · `valid_to` Date · `courses` Table MultiSelect Course Link · `course_groups` Table MultiSelect Course Group Link · `branches` Table MultiSelect Territory Link · `active` Check default 1 · `is_demo_data` Check. Controller:

```python
import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from mmm_custom.catalog_rules import validate_promotion


class CoursePromotion(Document):
	def validate(self):
		try:
			validate_promotion(
				self.discount_type, self.discount_value,
				getdate(self.valid_from) if self.valid_from else None,
				getdate(self.valid_to) if self.valid_to else None,
			)
		except ValueError as e:
			frappe.throw(str(e))
```

- [ ] **Step 1: Failing tests** — append to `tests/test_catalog_rules.py`:

```python
from datetime import date
from mmm_custom.catalog_rules import validate_promotion


class TestValidatePromotion(unittest.TestCase):
    def test_valid_percent(self):
        validate_promotion("Percent", 10, date(2026, 10, 1), date(2026, 11, 30))

    def test_validate_promotion_percent_over_100(self):
        with self.assertRaisesRegex(ValueError, "100"):
            validate_promotion("Percent", 120, None, None)

    def test_validate_promotion_non_positive(self):
        with self.assertRaisesRegex(ValueError, "greater than 0"):
            validate_promotion("Amount", 0, None, None)

    def test_validate_promotion_inverted_dates(self):
        with self.assertRaisesRegex(ValueError, "before"):
            validate_promotion("Amount", 500000, date(2026, 11, 1), date(2026, 10, 1))
```

- [ ] **Step 2: Run** → FAIL `ImportError: cannot import name 'validate_promotion'`.
- [ ] **Step 3: Implement**:

```python
def validate_promotion(discount_type, discount_value, valid_from, valid_to):
	if not discount_value or discount_value <= 0:
		raise ValueError("Discount must be greater than 0")
	if discount_type == "Percent" and discount_value > 100:
		raise ValueError("A percent discount cannot exceed 100")
	if valid_from and valid_to and valid_to < valid_from:
		raise ValueError("Valid to is before valid from")
```

plus the three DocTypes.
- [ ] **Step 4: Run tests** → `OK`.
- [ ] **Step 5: Live check** — migrate; `frappe.db.exists` for `Course Schedule` and `Course Promotion`.
- [ ] **Step 6: Commit** — `git commit -m "feat(crm): add course schedules and promotions doctypes"`

---

## Phase C1.5 — Bot data DocTypes and brand settings

### Task 5: `Bot Slot` (+ `Bot Slot Option`, `Bot Slot Link`), `Bot Skill` (+ `Bot Skill Template`, `Bot Skill Follow Up`), `Lead Engine Settings`

**Files:**
- Modify: `mmm_custom/catalog_rules.py` (constants + `validate_slot_dependency`)
- Create doctype folders: `bot_slot`, `bot_slot_option`, `bot_slot_link`, `bot_skill`, `bot_skill_template`, `bot_skill_follow_up`, `lead_engine_settings`
- Test: extend `tests/test_catalog_rules.py`, `tests/test_doctype_json.py`.

**Interfaces:**
- Produces constants in `catalog_rules`: `SLOT_TYPES = ("catalog", "choice", "phone", "number", "text")`, `CATALOG_SOURCES = ("course", "branch")`, `ACTION_TYPES = ("answer_template", "schedule_lookup", "fee_quote", "branch_info", "send_media", "recommend_courses", "handoff")`, `FOLLOW_UP_TARGETS = ("skill", "slot", "handoff")`.
- Produces: `catalog_rules.validate_slot_dependency(slot_type, catalog_source, depends_on_slot, depends_on_value) -> None` — `ValueError` if `slot_type == "catalog"` without a `catalog_source`, or exactly one of `depends_on_slot` / `depends_on_value` is set.
- The Select options in the JSON must equal these constants joined by `\n` (tested).

`Bot Slot` — autoname `field:slot_key`:

| fieldname | fieldtype | options / flags |
|---|---|---|
| slot_key | Data | reqd, unique, in_list_view |
| label | Data | reqd, in_list_view |
| slot_type | Select | `catalog\nchoice\nphone\nnumber\ntext`, reqd, in_list_view |
| catalog_source | Select | `\ncourse\nbranch` |
| required | Check | in_list_view |
| sort_order | Int | default 0 |
| ask_template | Small Text | reqd (Jinja) |
| options | Table | Bot Slot Option |
| depends_on_slot | Link | Bot Slot |
| depends_on_value | Data | |
| lead_field | Data | description "CRM Lead fieldname the value is written to" |
| active | Check | default 1 |

`Bot Slot Option` (child): `value` Data reqd in_list_view · `label` Data reqd in_list_view · `button_label` Data length 20 · `aliases` Small Text.
`Bot Slot Link` (child): `bot_slot` Link Bot Slot reqd in_list_view.

`Bot Skill` — autoname `field:skill_key`:

| fieldname | fieldtype | options / flags |
|---|---|---|
| skill_key | Data | reqd, unique, in_list_view |
| title | Data | reqd, in_list_view |
| jev_description | Small Text | reqd |
| examples | Small Text | one Vietnamese example per line |
| aliases | Small Text | |
| parameters | Table MultiSelect | Bot Slot Link |
| missing_policy | Select | `ask\ngeneric`, default `ask` |
| action_type | Select | `answer_template\nschedule_lookup\nfee_quote\nbranch_info\nsend_media\nrecommend_courses\nhandoff`, reqd, in_list_view |
| action_config | Code | options `JSON` |
| templates | Table | Bot Skill Template |
| follow_ups | Table | Bot Skill Follow Up |
| media | Attach Image | |
| creates_lead | Check | default 1 |
| handoff_after | Check | |
| sort_order | Int | default 0 |
| active | Check | default 1 |

`Bot Skill Template` (child): `variant_key` Data reqd in_list_view · `when` Data (Jinja expression, empty = always) · `template` Small Text reqd in_list_view.
`Bot Skill Follow Up` (child): `title` Data reqd length 20 in_list_view · `target_type` Select `skill\nslot\nhandoff` reqd · `target` Data (skill_key or slot_key; empty for handoff).

`Lead Engine Settings` — `issingle: 1`, permissions System Manager + Sales Manager (read/write):
`brand_name` Data reqd · `bot_name` Data · `address_customer` Data default `anh/chị` · `address_self` Data default `em` · `hotline` Data · `zalo` Data · `website` Data · `email` Data · `greeting_template` Small Text · `fallback_template` Small Text · `signoff` Data.

Controllers: `Bot Slot.validate` → `validate_slot_dependency(...)` (via `frappe.throw` on `ValueError`); others `pass`.

- [ ] **Step 1: Failing tests** — append to `tests/test_catalog_rules.py`:

```python
from mmm_custom.catalog_rules import validate_slot_dependency


class TestValidateSlotDependency(unittest.TestCase):
    def test_catalog_needs_source(self):
        with self.assertRaisesRegex(ValueError, "catalog_source"):
            validate_slot_dependency("catalog", None, None, None)

    def test_dependency_needs_both_parts(self):
        with self.assertRaisesRegex(ValueError, "depends_on"):
            validate_slot_dependency("number", None, "learner", None)

    def test_valid(self):
        validate_slot_dependency("number", None, "learner", "child")
        validate_slot_dependency("catalog", "course", None, None)
```

and to `tests/test_doctype_json.py`:

```python
    def test_select_options_match_rules(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from mmm_custom import catalog_rules as r
        def opts(dt, field):
            return [f for f in self.doctypes[dt][1]["fields"] if f["fieldname"] == field][0]["options"]
        self.assertEqual(opts("Bot Slot", "slot_type"), "\n".join(r.SLOT_TYPES))
        self.assertEqual(opts("Bot Skill", "action_type"), "\n".join(r.ACTION_TYPES))
        self.assertEqual(opts("Bot Skill Follow Up", "target_type"), "\n".join(r.FOLLOW_UP_TARGETS))
        self.assertEqual(opts("Bot Slot", "catalog_source"), "\n" + "\n".join(r.CATALOG_SOURCES))

    def test_settings_is_single(self):
        self.assertEqual(self.doctypes["Lead Engine Settings"][1].get("issingle"), 1)
```

- [ ] **Step 2: Run** → FAIL (`ImportError`, `KeyError: 'Bot Slot'`).
- [ ] **Step 3: Implement**:

```python
SLOT_TYPES = ("catalog", "choice", "phone", "number", "text")
CATALOG_SOURCES = ("course", "branch")
ACTION_TYPES = ("answer_template", "schedule_lookup", "fee_quote", "branch_info", "send_media", "recommend_courses", "handoff")
FOLLOW_UP_TARGETS = ("skill", "slot", "handoff")


def validate_slot_dependency(slot_type, catalog_source, depends_on_slot, depends_on_value):
	if slot_type == "catalog" and not catalog_source:
		raise ValueError("A catalog slot needs a catalog_source")
	if bool(depends_on_slot) != bool(depends_on_value):
		raise ValueError("Set both depends_on_slot and depends_on_value, or neither")
```

plus the seven DocTypes.
- [ ] **Step 4: Run tests** → `OK`.
- [ ] **Step 5: Live check** — migrate; `frappe.db.exists` for `Bot Skill`, `Bot Slot`, `Lead Engine Settings`.
- [ ] **Step 6: Commit** — `git commit -m "feat(bot): add bot slot, bot skill and lead engine settings doctypes"`

---

## Phase C1.6 — Sao Việt demo dataset, loader, Chatwoot seeding

### Task 6: Demo data files + integrity test + loader + Chatwoot seed

**Files:**
- Create: `mmm_custom/demo/__init__.py`, `mmm_custom/demo/loader.py`, `mmm_custom/demo/chatwoot_seed.py`
- Create: `mmm_custom/demo/saoviet/{areas.json,course_groups.json,courses.json,consultants.json,promotions.json,bot_slots.json,bot_skills.json,settings.json}`
- Modify: `mmm_custom/chatwoot_client.py`
- Test: `tests/test_demo_data.py`, `tests/test_demo_loader.py`, `tests/test_chatwoot_seed.py`, extend `tests/test_chatwoot_client.py`

**Interfaces:**
- Produces `loader.load_dataset(root: Path = DATA_DIR) -> dict[str, Any]` (parsed JSON by file stem).
- Produces `loader.generate_schedules(courses: list[dict], branches: list[dict], anchor: date, weeks: int = 8, cadence: int = 4) -> list[dict]` — pure; each row `{"course", "branch", "start_date", "shift", "weekdays", "seats", "status": "Open", "is_demo_data": 1}`; a course with `offer == "full"` only at branches with `tier == "full"`.
- Produces `loader.map_url(address: str) -> str` = `"https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(address)`.
- Produces `loader.upsert(doctype: str, filters: dict, values: dict, db=frappe) -> tuple[str, bool]` — returns `(name, created)`; updates only when a value differs.
- Produces `loader.load(anchor: str | None = None) -> dict[str, int]` (bench entry point; returns counts by DocType) and `loader.purge_demo() -> dict[str, int]`.
- Produces `chatwoot_seed.run() -> dict[str, int]` (bench entry point) using new `ChatwootClient` methods: `list_inboxes() -> list[dict]`, `create_agent(name: str, email: str, role: str = "agent") -> dict`, `list_teams() -> list[dict]`, `create_team(name: str, description: str = "") -> dict`, `add_team_members(team_id: int, user_ids: list[int]) -> list`, `add_inbox_members(inbox_id: int, user_ids: list[int]) -> list`.

**Dataset content** (D-005, D-066; all Vietnamese labels exactly as below)

`areas.json` — root `Sao Việt` (group) → 4 areas (groups) → 13 branches. Hotline for every branch `0931 144 858`. `map_url` is computed by the loader from `address`.

| area | territory_name | branch_code | button_label | tier | address | aliases |
|---|---|---|---|---|---|---|
| TP. Hồ Chí Minh | CN Bình Thạnh | HCM-BT | Bình Thạnh | full | 21/8 Lê Trực, Phường 7, Bình Thạnh, TP.HCM | binh thanh, bthanh, le truc |
| TP. Hồ Chí Minh | CN Quận 7 | HCM-Q7 | Quận 7 | standard | 515 B2/12 Lê Văn Lương, Tân Phong, Quận 7, TP.HCM | quan 7, q7, q.7, le van luong |
| TP. Hồ Chí Minh | CN Quận 6 | HCM-Q6 | Quận 6 | standard | 189 Kinh Dương Vương, Phường 12, Quận 6, TP.HCM | quan 6, q6, kinh duong vuong |
| TP. Hồ Chí Minh | CN Quận 12 | HCM-Q12 | Quận 12 | standard | A23 Lê Thị Riêng, Thới An, Quận 12, TP.HCM | quan 12, q12, le thi rieng |
| TP. Hồ Chí Minh | CN Thủ Đức | HCM-TD | Thủ Đức | full | 133/2 Đỗ Xuân Hợp, Phước Long, TP. Thủ Đức | thu duc, tp thu duc, do xuan hop |
| TP. Hồ Chí Minh | CN Tân Bình | HCM-TB | Tân Bình | standard | 180 Phạm Văn Bạch, Phường 15, Tân Bình, TP.HCM | tan binh, pham van bach |
| Bình Dương | CN Thủ Dầu Một | BD-TDM | Thủ Dầu Một | full | 107 D5, Phú Hòa 1, Thủ Dầu Một, Bình Dương | thu dau mot, tdm, phu hoa |
| Bình Dương | CN Thuận An | BD-TA | Thuận An | standard | Đường NA8, KDC Việt Sing, Thuận An, Bình Dương | thuan an, viet sing |
| Bình Dương | CN Dĩ An | BD-DA | Dĩ An | standard | 184/19/11 Đặng Văn Mây, Dĩ An, Bình Dương | di an, dang van may |
| Bình Dương | CN Tân Uyên | BD-TU | Tân Uyên | standard | 30 Tổ 3, Tân Hóa, Tân Uyên, Bình Dương | tan uyen, tan hoa |
| Đồng Nai | CN Biên Hòa | DN-BH | Biên Hòa | full | 91 Đoàn Văn Cự, Tam Hiệp, Biên Hòa, Đồng Nai | bien hoa, tam hiep |
| Đồng Nai | CN Long Thành | DN-LT | Long Thành | standard | 72 Đinh Bộ Lĩnh, Long Thành, Đồng Nai | long thanh, dinh bo linh |
| Bà Rịa - Vũng Tàu | CN Vũng Tàu | VT-VT | Vũng Tàu | standard | 293 Bình Giã, Phường 8, Vũng Tàu | vung tau, binh gia |

Area aliases: TP. Hồ Chí Minh `tphcm, hcm, sai gon, saigon, ho chi minh`; Bình Dương `binh duong, bd`; Đồng Nai `dong nai`; Bà Rịa - Vũng Tàu `vung tau, ba ria, brvt`. Area button labels: `TP.HCM`, `Bình Dương`, `Đồng Nai`, `Vũng Tàu`.

`course_groups.json` — 8 groups (`group_name`, `button_label`, `emoji`, `sort_order`, `aliases`):

| group_name | button_label | emoji | aliases |
|---|---|---|---|
| Tin học văn phòng | Tin học văn phòng | 💼 | tin hoc van phong, thvp, office, word, excel |
| Thiết kế đồ họa | Đồ họa | 🎨 | do hoa, thiet ke, design, graphic |
| Vẽ kỹ thuật | Vẽ kỹ thuật | 📐 | ve ky thuat, cad, 3d, kien truc |
| Kế toán | Kế toán | 📊 | ke toan, accounting, thue, misa |
| Lập trình | Lập trình | 💻 | lap trinh, code, coding, developer |
| Tin học trẻ em | Trẻ em & Robotics | 🤖 | tre em, cho be, thieu nhi, robotics, robot |
| Digital Marketing | Marketing online | 📣 | marketing, quang cao, ads, seo |
| AI & Tự động hóa | AI & Tự động hóa | ✨ | ai, tri tue nhan tao, automation, tu dong hoa |

`courses.json` — 46 courses (`product_code`, `product_name`, `button_label`, `course_group`, `audience`, `min_age`, `max_age`, `standard_rate` VND, `duration_text`, `certificate`, `offer`, `aliases`, `next_courses`). Audience `Người đi làm` and ages 15–60 unless stated; `offer` `all` unless marked **full**.

| code | name | button_label | fee | duration | next | notes |
|---|---|---|---|---|---|---|
| VP-CB | Tin học cơ bản | Tin học cơ bản | 1200000 | 1 tháng | VP-WORD, VP-EXCEL | aliases `tin hoc co ban, may tinh co ban` |
| VP-WORD | Word từ cơ bản đến nâng cao | Word | 1500000 | 1 tháng | VP-MOS | `word, soan thao` |
| VP-EXCEL | Excel từ cơ bản đến nâng cao | Excel | 1800000 | 1–1,5 tháng | VP-EXCEL-NC, VP-MOS | `excel, bang tinh` |
| VP-EXCEL-NC | Excel nâng cao & Dashboard | Excel nâng cao | 2200000 | 1 tháng | LT-VBA | `excel nang cao, dashboard, pivot` |
| VP-PPT | PowerPoint chuyên nghiệp | PowerPoint | 1300000 | 3 tuần | VP-MOS | `powerpoint, ppt, trinh chieu` |
| VP-AI | Ứng dụng AI trong văn phòng | AI văn phòng | 1900000 | 1 tháng | AI-N8N | `ai van phong, chatgpt van phong` |
| VP-MOS | Luyện thi MOS quốc tế | Chứng chỉ MOS | 3500000 | 1,5–2 tháng | — | certificate `MOS (Microsoft)`, `mos, chung chi mos` |
| VP-IC3 | Luyện thi IC3 | Chứng chỉ IC3 | 3200000 | 1,5–2 tháng | — | certificate `IC3 (Certiport)`, audience `Học sinh – Sinh viên`, `ic3` |
| VP-TRONGOI | Tin học văn phòng trọn gói | VP trọn gói | 3900000 | 2–3 tháng | VP-MOS | `tron goi van phong, word excel powerpoint` |
| DH-PTS | Photoshop cơ bản | Photoshop | 1800000 | 1 tháng | DH-PTS-NC | `photoshop, ps, chinh anh` |
| DH-PTS-NC | Photoshop nâng cao | Photoshop nâng cao | 2300000 | 1 tháng | DH-AI | `photoshop nang cao` |
| DH-AI | Illustrator | Illustrator | 2000000 | 1 tháng | DH-CRD | `illustrator, ai design, vector` |
| DH-CRD | CorelDraw | CorelDraw | 1900000 | 1 tháng | — | `corel, coreldraw` |
| DH-PR | Premiere dựng video | Premiere | 2500000 | 1 tháng | DH-AE | `premiere, dung video, edit video` |
| DH-AE | After Effects | After Effects | 2800000 | 1 tháng | — | `after effects, ae, hieu ung` |
| DH-TRONGOI | Đồ họa trọn gói | Đồ họa trọn gói | 6500000 | 3 tháng | DH-PR | `tron goi do hoa` |
| VKT-CAD2D | AutoCAD 2D | AutoCAD 2D | 1800000 | 1 tháng | VKT-CAD3D | `autocad, cad 2d, autocad 2d` |
| VKT-CAD3D | AutoCAD 3D | AutoCAD 3D | 2200000 | 1 tháng | VKT-REVIT | `autocad 3d, cad 3d` |
| VKT-SW | SolidWorks | SolidWorks | 3200000 | 1,5 tháng | VKT-INV | `solidworks, solid` |
| VKT-SKP | SketchUp | SketchUp | 2200000 | 1 tháng | VKT-VRAY | `sketchup, sketch up` |
| VKT-3DS | 3DS Max | 3DS Max | 3500000 | 1,5 tháng | VKT-VRAY | **full**, `3ds max, 3dsmax` |
| VKT-REVIT | Revit kiến trúc | Revit | 3800000 | 2 tháng | — | **full**, `revit, bim` |
| VKT-INV | Inventor | Inventor | 3300000 | 1,5 tháng | — | **full**, `inventor` |
| VKT-VRAY | Vray & Enscape render | Vray & Enscape | 2900000 | 1 tháng | — | **full**, `vray, enscape, render` |
| KT-CB | Nguyên lý kế toán cho người mới | Kế toán cơ bản | 1800000 | 1 tháng | KT-TH | `ke toan co ban, nguyen ly ke toan` |
| KT-TH | Kế toán tổng hợp thực hành | Kế toán tổng hợp | 3500000 | 2 tháng | KT-THUE | `ke toan tong hop` |
| KT-THUE | Khai báo & quyết toán thuế | Kế toán thuế | 2800000 | 1,5 tháng | — | `thue, quyet toan thue, khai bao thue` |
| KT-EXCEL | Kế toán trên Excel | Kế toán Excel | 2200000 | 1 tháng | KT-MISA | `ke toan excel` |
| KT-MISA | Kế toán phần mềm MISA | Phần mềm MISA | 2000000 | 1 tháng | — | `misa` |
| LT-PY | Python cơ bản | Python | 2500000 | 1,5 tháng | LT-WEB | `python` |
| LT-VBA | VBA Excel | VBA Excel | 2300000 | 1 tháng | — | `vba, macro` |
| LT-WEB | Lập trình Web | Lập trình Web | 4500000 | 3 tháng | LT-MOBILE | **full**, `web, html, lap trinh web` |
| LT-MOBILE | Lập trình Mobile | Lập trình Mobile | 4900000 | 3 tháng | — | **full**, `mobile, app, android, ios` |
| TE-THUD | Tin học ứng dụng cho trẻ | Tin học cho bé | 1200000 | 1 tháng | TE-SCRATCH | audience `Trẻ em`, ages 6–12, `tin hoc cho be, tin hoc tre em` |
| TE-SCRATCH | Lập trình Scratch | Scratch | 1500000 | 1,5 tháng | TE-PY | `Trẻ em`, 7–12, `scratch` |
| TE-PY | Python cho trẻ | Python cho bé | 1900000 | 2 tháng | LT-PY | `Trẻ em`, 10–15, `python cho be, python tre em` |
| TE-ROBO | Robotics cơ bản | Robotics | 2400000 | 2 tháng | TE-ROBO-NC | `Trẻ em`, 7–12, `robotics, robot, lap rap robot` |
| TE-ROBO-NC | Robotics nâng cao | Robotics nâng cao | 2900000 | 2 tháng | — | **full**, `Trẻ em`, 10–15, `robotics nang cao` |
| MKT-FB | Quảng cáo Facebook Ads | Facebook Ads | 2500000 | 1 tháng | MKT-TT | `facebook ads, chay quang cao facebook` |
| MKT-GG | Quảng cáo Google Ads | Google Ads | 2500000 | 1 tháng | MKT-SEO | `google ads` |
| MKT-TT | Quảng cáo TikTok Ads | TikTok Ads | 2300000 | 1 tháng | — | `tiktok ads, tiktok` |
| MKT-SEO | SEO website | SEO | 2800000 | 1,5 tháng | — | `seo, len top google` |
| MKT-WEB | Thiết kế website không cần code | Thiết kế website | 2600000 | 1 tháng | MKT-SEO | `thiet ke website, lam web` |
| AI-BASIC | AI cho người mới bắt đầu | AI cho người mới | 1500000 | 3 tuần | AI-VIBE | `ai co ban, hoc ai` |
| AI-VIBE | Vibe Coding | Vibe Coding | 2900000 | 1 tháng | AI-N8N | `vibe coding` |
| AI-N8N | Tự động hóa với n8n | Tự động hóa n8n | 2700000 | 1 tháng | — | `n8n, automation` |

`consultants.json` — 44 rows (`full_name`, `email`, `branch` = territory_name or empty, `level`, `specialties`, `handles_b2b`). Per branch three consultants; specialties by tier:
- `full` branch: Team Lead [Tin học văn phòng, Kế toán] · Consultant [Thiết kế đồ họa, Vẽ kỹ thuật] · Consultant [Lập trình, Tin học trẻ em, Digital Marketing, AI & Tự động hóa]
- `standard` branch: Team Lead [Tin học văn phòng, Kế toán, Tin học trẻ em] · Consultant [Thiết kế đồ họa, Vẽ kỹ thuật, Digital Marketing] · Consultant [Lập trình, AI & Tự động hóa, Tin học văn phòng]
- B2B team (branch empty, `handles_b2b: 1`, all 8 groups): Team Lead + 2 Consultants. Central team (branch empty, all 8 groups): 2 Consultants.

Names (in branch order of the areas table, TL first; then B2B ×3, central ×2), email = unaccented lowercase given name + `.` + lowercase branch code (B2B `b2b`, central `tongdai`) + `@demo.saoviet.invalid`:
Nguyễn Thị Mai, Trần Văn Nam, Lê Thị Hoa · Phạm Minh Tuấn, Võ Thị Lan, Đặng Quốc Huy · Bùi Thị Ngọc, Hoàng Văn Long, Đỗ Thị Thảo · Ngô Thị Hạnh, Dương Văn Khoa, Lý Thị Vy · Trịnh Văn Phúc, Mai Thị Trang, Hồ Văn Đức · Phan Thị Yến, Lâm Văn Tài, Tạ Thị Nhung · Châu Văn Hải, Quách Thị My, Vương Văn Sơn · Lưu Thị Diễm, Tô Văn Thành, Kiều Thị Loan · Đinh Văn Hùng, Cao Thị Kim, Lạc Văn Bảo · Mạc Thị Oanh, Thái Văn Lộc, Từ Thị Hằng · La Văn Kiệt, Âu Thị Xuân, Hà Văn Tùng · Giang Thị Nhi, Khổng Văn Toàn, Lục Thị Tuyết · Tăng Văn Vinh, Ông Thị Liên, Sầm Văn Hiếu · Nguyễn Hoàng Anh, Trần Thu Hà, Lê Minh Khang · Phạm Thị Thu, Võ Văn Quang.
If two emails collide, append a digit (`mai2.hcm-bt@…`); the integrity test asserts uniqueness.

`promotions.json` — 10 rows; `valid_from` = anchor, `valid_to` = anchor + 60 days (loader computes; JSON stores `"days": 60`):

| title | type | value | applies to |
|---|---|---|---|
| Ưu đãi khai giảng tháng này | Percent | 10 | all |
| Giảm 500.000đ Kế toán tổng hợp | Amount | 500000 | course KT-TH |
| Tin học cho bé giảm 20% | Percent | 20 | group Tin học trẻ em |
| Đồ họa trọn gói giảm 1.000.000đ | Amount | 1000000 | course DH-TRONGOI |
| Chi nhánh Long Thành giảm 15% | Percent | 15 | branch CN Long Thành |
| Tặng phí thi thử MOS/IC3 | Amount | 300000 | courses VP-MOS, VP-IC3 |
| Excel nâng cao giảm 10% | Percent | 10 | course VP-EXCEL-NC |
| AI & Tự động hóa giảm 12% | Percent | 12 | group AI & Tự động hóa |
| AutoCAD 2D giảm 300.000đ | Amount | 300000 | course VKT-CAD2D |
| Lập trình Web giảm 8% | Percent | 8 | course LT-WEB |

`bot_slots.json` — 7 rows (`slot_key`, `label`, `slot_type`, `catalog_source`, `required`, `sort_order`, `ask_template`, `options`, `depends_on_slot`, `depends_on_value`, `lead_field`):

| slot_key | type | req | order | ask_template | options (value:label:button) | depends | lead_field |
|---|---|---|---|---|---|---|---|
| course | catalog/course | ✓ | 10 | `{{ brand.you \| capitalize }} quan tâm khóa học nào ạ?` | — | — | products |
| branch | catalog/branch | ✓ | 20 | `{{ brand.you \| capitalize }} muốn học ở chi nhánh nào ạ?` | — | — | territory |
| learner | choice | | 30 | `Khóa học này dành cho ai ạ?` | self:Bản thân:Cho tôi · child:Con em:Cho con em · staff:Nhân viên công ty:Cho công ty | — | learner_type |
| learner_age | number | | 40 | `Bé nhà mình năm nay mấy tuổi ạ?` | — | learner = child | learner_age |
| preferred_shift | choice | | 50 | `{{ brand.you \| capitalize }} tiện học ca nào ạ?` | morning:Sáng:Ca sáng · afternoon:Chiều:Ca chiều · evening:Tối:Ca tối | — | preferred_shift |
| customer_name | text | | 60 | `Cho {{ brand.me }} xin tên {{ brand.you }} để tiện xưng hô ạ?` | — | — | first_name |
| phone | phone | ✓ | 70 | `Để tư vấn viên liên hệ nhanh, {{ brand.you }} cho {{ brand.me }} xin số điện thoại nhé ạ?` | — | — | mobile_no |

Option aliases: self `minh, ban than, toi hoc`; child `con, be, con em, cho con`; staff `cong ty, nhan vien, doanh nghiep`; morning `sang, buoi sang`; afternoon `chieu, buoi chieu`; evening `toi, buoi toi, ca toi`.

`bot_skills.json` — 30 rows (`skill_key`, `title`, `jev_description`, `examples`, `aliases`, `parameters`, `missing_policy`, `action_type`, `action_config`, `templates[]`, `follow_ups[]`, `creates_lead`, `handoff_after`, `sort_order`). Each skill has at least a `default` template; templates use only the D-050 context names.

| skill_key | title | action_type | params | aliases | default template |
|---|---|---|---|---|---|
| fee_quote | học phí | fee_quote | course | hoc phi, bao nhieu tien, bn tien, gia, chi phi | `Dạ khóa {{ course.name }} học phí {{ course.fee \| vnd }}{% if promotions %}, đang ưu đãi còn {{ final_fee \| vnd }}{% endif %} ạ.` |
| schedule_lookup | lịch khai giảng | schedule_lookup | course | lich khai giang, khi nao hoc, bao gio khai giang, lop moi | `Lịch khai giảng gần nhất khóa {{ course.name }}:{% for s in schedules %}\n• {{ s.date \| date_vi }} ({{ s.weekdays }}, {{ s.shift }}) tại {{ s.branch }}{% endfor %}` (+ variant `none` with `when: "not schedules"`: `Hiện khóa {{ course.name }} chưa có lịch mới, {{ brand.me }} sẽ báo {{ brand.you }} ngay khi mở lớp ạ.`) |
| branch_info | địa chỉ chi nhánh | branch_info | — | dia chi, o dau, chi nhanh, co so, gan nhat | `Dạ {{ branch.name }} ở {{ branch.address }} ạ. Bản đồ: {{ branch.map_url }}` |
| duration | thời lượng khóa học | answer_template | course | hoc bao lau, may thang, thoi luong, bao nhieu buoi | `Khóa {{ course.name }} thường học khoảng {{ course.duration }} ạ.` |
| unlimited_sessions | học đến khi thành thạo | answer_template | — | hoc lai, khong gioi han, hoc den khi thanh thao | `Dạ bên {{ brand.me }} học không giới hạn số buổi đến khi thành thạo, học chưa vững được học lại miễn phí ạ.` |
| certificate_info | chứng chỉ | answer_template | course | chung chi, bang cap, chung nhan | `{% if course.certificate %}Khóa {{ course.name }} có chứng chỉ {{ course.certificate }} ạ.{% else %}Học viên hoàn thành khóa được cấp chứng nhận của trung tâm ạ.{% endif %}` |
| certificate_lookup | tra cứu chứng nhận | answer_template | — | tra cuu chung nhan, tra chung chi, kiem tra bang | `Dạ {{ brand.you }} tra cứu chứng nhận tại https://chungnhan.tinhocsaoviet.com/ ạ.` (`creates_lead: 0`) |
| trial_class | học thử | answer_template | course | hoc thu, hoc thu mien phi, du thinh | `Dạ {{ brand.you }} được học thử miễn phí 1 buổi ạ, {{ brand.me }} xếp lịch cho {{ brand.you }} nhé?` |
| promotions | khuyến mãi | fee_quote | course | khuyen mai, uu dai, giam gia | `{% if promotions %}Ưu đãi đang áp dụng: {% for p in promotions %}{{ p.title }}{% if not loop.last %}; {% endif %}{% endfor %} ạ.{% else %}Hiện chưa có ưu đãi cho khóa này ạ.{% endif %}` |
| payment | cách đóng học phí | answer_template | — | dong hoc phi, chuyen khoan, tra gop | `Dạ {{ brand.you }} có thể đóng tiền mặt tại chi nhánh hoặc chuyển khoản ạ.` |
| shifts | ca học | answer_template | — | ca hoc, gio hoc, hoc buoi nao | `Bên {{ brand.me }} có ca sáng 8:30–11:00, chiều 13:30–16:30, tối 17:00–21:00, thứ 2 đến thứ 7 ạ.` |
| career | đầu ra, việc làm | answer_template | course | viec lam, dau ra, xin viec, ra truong | `Khóa {{ course.name }} học thực hành trên bài tập thực tế, học xong làm việc được ngay ạ.` |
| laptop | cần mang laptop không | answer_template | — | mang laptop, may tinh rieng, can laptop | `Dạ trung tâm có sẵn máy thực hành, {{ brand.you }} mang laptop riêng cũng được ạ.` |
| kids_courses | khóa cho trẻ em | recommend_courses | — | cho be, tre em, thieu nhi | `Các khóa phù hợp cho bé:{% for r in recommendations %}\n• {{ r.course }} – {{ r.fee \| vnd }}{% endfor %}` |
| corporate_training | đào tạo doanh nghiệp | handoff | — | dao tao doanh nghiep, cho nhan vien, cong ty | `Dạ {{ brand.me }} chuyển {{ brand.you }} sang bộ phận đào tạo doanh nghiệp ngay ạ.` (`handoff_after: 1`) |
| complaint | khiếu nại | handoff | — | khieu nai, phan nan, khong hai long, te qua | `Dạ {{ brand.me }} rất xin lỗi, {{ brand.me }} chuyển ngay cho quản lý hỗ trợ {{ brand.you }} ạ.` (`handoff_after: 1`) |
| talk_to_human | gặp tư vấn viên | handoff | — | gap nguoi, tu van vien, goi cho toi, nhan vien | `Dạ {{ brand.me }} chuyển {{ brand.you }} cho tư vấn viên ngay ạ.` |
| course_advisor | tư vấn chọn khóa | recommend_courses | learner | nen hoc gi, chua biet hoc gi, tu van khoa | `{{ brand.me \| capitalize }} gợi ý {{ brand.you }}:{% for r in recommendations %}\n• {{ r.course }} – {{ r.fee \| vnd }}{% endfor %}` |
| hotline | hotline, Zalo | answer_template | — | hotline, so dien thoai, zalo, lien he | `Hotline/Zalo: {{ brand.hotline }} ạ.` |
| opening_hours | giờ làm việc | answer_template | — | may gio, gio lam viec, mo cua | `Trung tâm làm việc từ 8:00 đến 21:00, thứ 2 đến thứ 7 ạ.` |
| online_learning | học online | answer_template | course | hoc online, truc tuyen, hoc tu xa | `Dạ hiện khóa {{ course.name }} học trực tiếp tại chi nhánh để được hướng dẫn cầm tay chỉ việc ạ.` |
| course_content | nội dung khóa học | send_media | course | noi dung, hoc nhung gi, giao trinh, lo trinh | `Dạ {{ brand.me }} gửi {{ brand.you }} nội dung khóa {{ course.name }} ạ.` |
| next_course | học tiếp khóa nào | answer_template | course | hoc tiep, khoa tiep theo, nang cao | `{% if course.next_courses %}Sau {{ course.name }}, {{ brand.you }} có thể học tiếp: {{ course.next_courses \| join(", ") }} ạ.{% else %}Đây là khóa chuyên sâu nhất của nhóm này ạ.{% endif %}` |
| class_size | sĩ số lớp | answer_template | — | si so, lop bao nhieu nguoi, lop dong khong | `Lớp nhỏ 12–20 học viên để giảng viên kèm sát ạ.` |
| teachers | giảng viên | answer_template | — | giang vien, giao vien, thay co | `Giảng viên là người đi làm thực tế trong ngành, kèm từng học viên ạ.` |
| age_fit | độ tuổi phù hợp | answer_template | course | may tuoi, do tuoi, be may tuoi hoc duoc | `Khóa {{ course.name }} phù hợp từ {{ course.min_age }} đến {{ course.max_age }} tuổi ạ.` |
| beginner_ok | người mới học được không | answer_template | course | chua biet gi, nguoi moi, mat goc | `Dạ khóa {{ course.name }} học từ căn bản, người mới hoàn toàn học được ạ.` |
| register | đăng ký học | handoff | course | dang ky, ghi danh, giu cho | `Dạ {{ brand.me }} ghi nhận đăng ký, tư vấn viên sẽ liên hệ giữ chỗ cho {{ brand.you }} ngay ạ.` |
| refund | bảo lưu, hoàn phí | handoff | — | bao luu, hoan tien, hoan phi, nghi hoc | `Dạ {{ brand.me }} chuyển {{ brand.you }} cho tư vấn viên để hỗ trợ bảo lưu ạ.` |
| greeting | chào hỏi | answer_template | — | xin chao, hello, hi, chao shop | `{{ brand.me \| capitalize }} chào {{ brand.you }}! {{ brand.you \| capitalize }} đang quan tâm khóa học nào ạ?` (`creates_lead: 0`) |

`jev_description` per skill: one English sentence describing what the customer asks (e.g. fee_quote: "The customer asks how much a course costs or about tuition fees"). `examples`: 2–3 Vietnamese lines per skill (e.g. fee_quote: "khóa excel bao nhiêu tiền", "học phí autocad sao ạ", "hp bn vậy"). `follow_ups`: fee_quote → [Xem lịch khai giảng → skill schedule_lookup, Đăng ký tư vấn → handoff]; schedule_lookup → [Xem học phí → skill fee_quote, Đăng ký giữ chỗ → skill register]; course_advisor → [Gặp tư vấn viên → handoff]; others none. `action_config`: schedule_lookup `{"limit": 3}`, course_advisor/kids_courses `{"top": 3}`.

`settings.json` — `brand_name: "Tin Học Sao Việt"`, `bot_name: "Trợ lý Sao Việt"`, `address_customer: "anh/chị"`, `address_self: "em"`, `hotline: "0931 144 858"`, `zalo: "0931144858"`, `website: "https://tinhocsaoviet.com"`, `email: "trungtamtinhocsaoviet@gmail.com"`, `greeting_template: "Dạ {{ brand.me }} là {{ brand.bot_name }}, {{ brand.me }} có thể giúp gì cho {{ brand.you }} ạ?"`, `fallback_template: "Dạ {{ brand.me }} chưa hiểu ý {{ brand.you }}, {{ brand.you }} chọn giúp {{ brand.me }} một mục bên dưới hoặc gọi {{ brand.hotline }} nhé ạ."`, `signoff: "Sao Việt"`.

- [ ] **Step 1: Failing tests** — `tests/test_demo_data.py`:

```python
import json
import sys
from pathlib import Path
import unittest

DATA = Path(__file__).resolve().parent.parent / "demo" / "saoviet"


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


class TestDemoData(unittest.TestCase):
    def setUp(self):
        self.areas = load("areas")
        self.groups = load("course_groups")
        self.courses = load("courses")
        self.consultants = load("consultants")
        self.promotions = load("promotions")
        self.slots = load("bot_slots")
        self.skills = load("bot_skills")
        self.branches = [b for a in self.areas["areas"] for b in a["branches"]]

    def test_counts(self):
        self.assertEqual(len(self.areas["areas"]), 4)
        self.assertEqual(len(self.branches), 13)
        self.assertEqual(len(self.groups), 8)
        self.assertEqual(len(self.courses), 46)
        self.assertEqual(len(self.consultants), 44)
        self.assertEqual(len(self.promotions), 10)
        self.assertEqual(len(self.slots), 7)
        self.assertEqual(len(self.skills), 30)

    def test_unique_keys(self):
        for rows, key in ((self.branches, "branch_code"), (self.branches, "territory_name"),
                          (self.courses, "product_code"), (self.consultants, "email"),
                          (self.groups, "group_name"), (self.skills, "skill_key"), (self.slots, "slot_key")):
            values = [r[key] for r in rows]
            self.assertEqual(len(values), len(set(values)), key)

    def test_button_labels_fit_messenger(self):
        labels = [a["button_label"] for a in self.areas["areas"]]
        labels += [r["button_label"] for r in self.branches + self.groups + self.courses]
        labels += [o["button_label"] for s in self.slots for o in s.get("options", [])]
        labels += [f["title"] for s in self.skills for f in s.get("follow_ups", [])]
        for label in labels:
            self.assertLessEqual(len(label), 20, label)

    def test_references_resolve(self):
        groups = {g["group_name"] for g in self.groups}
        codes = {c["product_code"] for c in self.courses}
        branches = {b["territory_name"] for b in self.branches}
        slots = {s["slot_key"] for s in self.slots}
        skills = {s["skill_key"] for s in self.skills}
        for c in self.courses:
            self.assertIn(c["course_group"], groups, c["product_code"])
            for n in c.get("next_courses", []):
                self.assertIn(n, codes, c["product_code"])
        for p in self.consultants:
            if p["branch"]:
                self.assertIn(p["branch"], branches, p["email"])
            for g in p["specialties"]:
                self.assertIn(g, groups, p["email"])
        for pr in self.promotions:
            for c in pr.get("courses", []):
                self.assertIn(c, codes, pr["title"])
            for g in pr.get("course_groups", []):
                self.assertIn(g, groups, pr["title"])
            for b in pr.get("branches", []):
                self.assertIn(b, branches, pr["title"])
        for s in self.skills:
            for p in s.get("parameters", []):
                self.assertIn(p, slots, s["skill_key"])
            for f in s.get("follow_ups", []):
                if f["target_type"] == "skill":
                    self.assertIn(f["target"], skills, s["skill_key"])
            self.assertTrue(any(t["variant_key"] == "default" for t in s["templates"]), s["skill_key"])
        for s in self.slots:
            if s.get("depends_on_slot"):
                self.assertIn(s["depends_on_slot"], slots)

    def test_consultants_per_branch(self):
        for b in self.branches:
            staff = [p for p in self.consultants if p["branch"] == b["territory_name"]]
            self.assertEqual(len(staff), 3, b["territory_name"])
            self.assertEqual(sum(p["level"] == "Team Lead" for p in staff), 1, b["territory_name"])

    def test_demo_emails_are_unroutable(self):
        for p in self.consultants:
            self.assertTrue(p["email"].endswith("@demo.saoviet.invalid"), p["email"])

    def test_age_ranges_ordered(self):
        for c in self.courses:
            self.assertLessEqual(c["min_age"], c["max_age"], c["product_code"])


if __name__ == "__main__":
    unittest.main()
```

`tests/test_demo_loader.py`:

```python
import sys
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import MagicMock

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.demo import loader

BRANCHES = [{"territory_name": "CN A", "tier": "full"}, {"territory_name": "CN B", "tier": "standard"}]
COURSES = [{"product_code": "X", "offer": "all", "weekdays": "T2, T4, T6", "shifts": ["evening"]},
           {"product_code": "Y", "offer": "full", "weekdays": "T7, CN", "shifts": ["morning", "afternoon"]}]


class FakeDb:
    def __init__(self):
        self.rows = {}

    def get_value(self, doctype, filters, fieldname="name"):
        for (dt, name), row in self.rows.items():
            if dt == doctype and all(row.get(k) == v for k, v in filters.items()):
                return name
        return None

    def insert(self, doctype, values):
        name = f"{doctype}-{len(self.rows)}"
        self.rows[(doctype, name)] = dict(values)
        return name

    def get(self, doctype, name):
        return self.rows[(doctype, name)]

    def update(self, doctype, name, values):
        self.rows[(doctype, name)].update(values)


class TestGenerateSchedules(unittest.TestCase):
    def test_full_courses_only_at_full_branches(self):
        rows = loader.generate_schedules(COURSES, BRANCHES, date(2026, 9, 28))
        self.assertTrue(all(r["branch"] == "CN A" for r in rows if r["course"] == "Y"))
        self.assertTrue({r["branch"] for r in rows if r["course"] == "X"} == {"CN A", "CN B"})

    def test_generate_schedules_is_deterministic(self):
        a = loader.generate_schedules(COURSES, BRANCHES, date(2026, 9, 28))
        b = loader.generate_schedules(COURSES, BRANCHES, date(2026, 9, 28))
        self.assertEqual(a, b)

    def test_two_classes_per_pair_in_eight_weeks(self):
        rows = loader.generate_schedules(COURSES, BRANCHES, date(2026, 9, 28), weeks=8, cadence=4)
        self.assertEqual(len(rows), 3 * 2)  # pairs: X@A, X@B, Y@A

    def test_rows_fall_inside_window_and_match_weekday(self):
        anchor = date(2026, 9, 28)
        for r in loader.generate_schedules(COURSES, BRANCHES, anchor):
            self.assertGreaterEqual(r["start_date"], anchor)
            self.assertLess((r["start_date"] - anchor).days, 56)
            first = r["weekdays"].split(",")[0].strip()
            self.assertEqual(loader.WEEKDAY_INDEX[first], r["start_date"].weekday())
            self.assertIn(r["seats"], range(12, 21))


class TestUpsert(unittest.TestCase):
    def test_upsert_is_idempotent(self):
        db = FakeDb()
        name1, created1 = loader.upsert("Course Group", {"group_name": "Kế toán"}, {"button_label": "Kế toán"}, db=db)
        name2, created2 = loader.upsert("Course Group", {"group_name": "Kế toán"}, {"button_label": "Kế toán"}, db=db)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(name1, name2)
        self.assertEqual(len(db.rows), 1)

    def test_upsert_updates_changed_values(self):
        db = FakeDb()
        name, _ = loader.upsert("Course Group", {"group_name": "Kế toán"}, {"button_label": "KT"}, db=db)
        loader.upsert("Course Group", {"group_name": "Kế toán"}, {"button_label": "Kế toán"}, db=db)
        self.assertEqual(db.get("Course Group", name)["button_label"], "Kế toán")


class TestMapUrl(unittest.TestCase):
    def test_encodes_address(self):
        self.assertEqual(loader.map_url("21/8 Lê Trực"),
                         "https://www.google.com/maps/search/?api=1&query=21/8%20L%C3%AA%20Tr%E1%BB%B1c")


if __name__ == "__main__":
    unittest.main()
```

(`courses.json` rows therefore also carry `weekdays` and `shifts`: office/accounting/programming/marketing/AI courses `"T2, T4, T6"` with `["evening", "morning"]` alternating by code, design/technical-drawing `"T3, T5, T7"` with `["evening", "afternoon"]`, kids `"T7, CN"` with `["morning", "afternoon"]`.)

`tests/test_chatwoot_seed.py`:

```python
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.demo import chatwoot_seed


class TestPlanTeams(unittest.TestCase):
    def test_team_names(self):
        consultants = [
            {"email": "a@demo.saoviet.invalid", "branch": "CN Dĩ An", "handles_b2b": 0},
            {"email": "b@demo.saoviet.invalid", "branch": "", "handles_b2b": 1},
            {"email": "c@demo.saoviet.invalid", "branch": "", "handles_b2b": 0},
        ]
        self.assertEqual(chatwoot_seed.plan_teams(consultants), {
            "CN Dĩ An": ["a@demo.saoviet.invalid"],
            "Doanh nghiệp (B2B)": ["b@demo.saoviet.invalid"],
            "Tổng đài": ["c@demo.saoviet.invalid"],
        })


class TestEnsureAgents(unittest.TestCase):
    def test_existing_agents_are_reused(self):
        client = MagicMock()
        client.list_agents.return_value = [{"id": 7, "email": "a@demo.saoviet.invalid"}]
        client.create_agent.return_value = {"id": 9, "email": "b@demo.saoviet.invalid"}
        ids = chatwoot_seed.ensure_agents(client, [
            {"full_name": "A", "email": "a@demo.saoviet.invalid"},
            {"full_name": "B", "email": "b@demo.saoviet.invalid"},
        ])
        self.assertEqual(ids, {"a@demo.saoviet.invalid": 7, "b@demo.saoviet.invalid": 9})
        client.create_agent.assert_called_once_with("B", "b@demo.saoviet.invalid")


if __name__ == "__main__":
    unittest.main()
```

Append to `tests/test_chatwoot_client.py` (follow its existing `requests` mocking style) tests for `create_team` (POST `/teams` with `{"name": ..., "description": ...}`), `add_team_members` (POST `/teams/{id}/team_members` with `{"user_ids": [...]}`), `add_inbox_members` (POST `/inbox_members` with `{"inbox_id": ..., "user_ids": [...]}`), `create_agent` (POST `/agents` with `{"name", "email", "role": "agent"}`), `list_inboxes` (GET `/inboxes` → `payload`), `list_teams` (GET `/teams`).

- [ ] **Step 2: Run** → FAIL (missing data files / `ModuleNotFoundError: mmm_custom.demo`).

- [ ] **Step 3: Implement data files** exactly per the tables above.

- [ ] **Step 4: Implement `loader.py`**:

```python
"""Idempotent loader for the Tin Học Sao Việt demo dataset (bench execute mmm_custom.demo.loader.load)."""

import json
import urllib.parse
import zlib
from datetime import date, timedelta
from pathlib import Path

try:
	import frappe
except ImportError:  # offline tests
	frappe = None

DATA_DIR = Path(__file__).resolve().parent / "saoviet"
WEEKDAY_INDEX = {"T2": 0, "T3": 1, "T4": 2, "T5": 3, "T6": 4, "T7": 5, "CN": 6}
SHIFT_LABELS = {"morning": "Sáng 8:30–11:00", "afternoon": "Chiều 13:30–16:30", "evening": "Tối 17:00–21:00"}


def load_dataset(root=DATA_DIR):
	return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(root.glob("*.json"))}


def map_url(address):
	return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(address)


def generate_schedules(courses, branches, anchor, weeks=8, cadence=4):
	rows = []
	for course in courses:
		first_day = WEEKDAY_INDEX[course["weekdays"].split(",")[0].strip()]
		for branch in branches:
			if course["offer"] == "full" and branch["tier"] != "full":
				continue
			seed = zlib.crc32(f"{course['product_code']}|{branch['territory_name']}".encode())
			for i, week in enumerate(range(seed % cadence, weeks, cadence)):
				rows.append({
					"course": course["product_code"],
					"branch": branch["territory_name"],
					"start_date": anchor + timedelta(weeks=week, days=first_day),
					"shift": SHIFT_LABELS[course["shifts"][(seed + i) % len(course["shifts"])]],
					"weekdays": course["weekdays"],
					"seats": 12 + (seed + i) % 9,
					"status": "Open",
					"is_demo_data": 1,
				})
	return rows


class FrappeDb:
	"""The small slice of frappe the loader needs; tests pass a fake with the same methods."""

	def get_value(self, doctype, filters, fieldname="name"):
		return frappe.db.get_value(doctype, filters, fieldname)

	def insert(self, doctype, values):
		return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name

	def get(self, doctype, name):
		return frappe.get_doc(doctype, name).as_dict()

	def update(self, doctype, name, values):
		doc = frappe.get_doc(doctype, name)
		doc.update(values)
		doc.save(ignore_permissions=True)


def upsert(doctype, filters, values, db=None):
	db = db or FrappeDb()
	name = db.get_value(doctype, filters)
	if not name:
		return db.insert(doctype, {**filters, **values}), True
	current = db.get(doctype, name)
	changed = {k: v for k, v in values.items() if current.get(k) != v}
	if changed:
		db.update(doctype, name, changed)
	return name, False
```

Then `load(anchor=None)`, in this order, each via `upsert`, counting created rows per DocType:
1. Territories: root `Sao Việt` (`is_group: 1`), each area (`is_group: 1`, `parent_crm_territory: "Sao Việt"`, `button_label`, `aliases`), each branch (`is_group: 0`, parent = area, `branch_code`, `button_label`, `branch_tier`, `address`, `hotline`, `map_url(address)`, `aliases`); filter key `territory_name`.
2. Course Groups (key `group_name`).
3. CRM Products (key `product_code`), `standard_rate`, custom fields, `is_demo_data: 1`, first pass without `next_courses`; second pass sets `next_courses` as `[{"course": code}]` once all products exist. `weekdays`/`shifts` are loader-only (not stored).
4. Users: for each consultant, `upsert("User", {"email": e}, {"first_name": full_name, "send_welcome_email": 0, "enabled": 1})`, then add role `Sales User` if missing (`frappe.get_doc("User", e).add_roles("Sales User")`).
5. Consultants (key `user`), `branch` or empty, `level`, `specialties` as `[{"course_group": g}]`, `handles_b2b`, `active: 1`.
6. Course Schedules: `generate_schedules(courses, branches, anchor_monday)` where `anchor_monday` = `anchor` parsed (`YYYY-MM-DD`) or this week's Monday (`frappe.utils.getdate()` minus weekday); key = course+branch+start_date+shift.
7. Course Promotions (key `title`), `valid_from = anchor_monday`, `valid_to = anchor_monday + days`, children rows, `is_demo_data: 1`.
8. Bot Slots (key `slot_key`), `options` rows; second pass for `depends_on_slot`.
9. Bot Skills (key `skill_key`), `parameters` as `[{"bot_slot": k}]`, `templates`, `follow_ups`, `action_config` as JSON string.
10. `Lead Engine Settings`: `frappe.get_single`, set fields from `settings.json`, save.
Finish with `frappe.db.commit()` and return the counts dict. `purge_demo()` deletes `Course Schedule`, `Course Promotion` and `CRM Product` rows where `is_demo_data = 1` (in that order) and returns counts.

- [ ] **Step 5: Implement `ChatwootClient` additions** (same style as existing methods: `requests.<verb>(f"{self._base}/…", headers=self._headers, json=…, timeout=REQUEST_TIMEOUT)`, `raise_for_status()`, return JSON; `list_inboxes` returns `resp.json()["payload"]`).

- [ ] **Step 6: Implement `chatwoot_seed.py`**:

```python
"""Create the demo consultants as Chatwoot agents, one team per branch + B2B + central, and link ids back."""

try:
	import frappe
except ImportError:  # offline tests
	frappe = None

from mmm_custom.chatwoot_client import ChatwootClient
from mmm_custom.demo.loader import load_dataset

B2B_TEAM = "Doanh nghiệp (B2B)"
CENTRAL_TEAM = "Tổng đài"


def plan_teams(consultants):
	teams = {}
	for c in consultants:
		team = c["branch"] or (B2B_TEAM if c.get("handles_b2b") else CENTRAL_TEAM)
		teams.setdefault(team, []).append(c["email"])
	return teams


def ensure_agents(client, consultants):
	existing = {a["email"]: a["id"] for a in client.list_agents()}
	ids = {}
	for c in consultants:
		if c["email"] not in existing:
			existing[c["email"]] = client.create_agent(c["full_name"], c["email"])["id"]
		ids[c["email"]] = existing[c["email"]]
	return ids


def run():
	conf = frappe.conf
	client = ChatwootClient(conf.get("chatwoot_api_url") or "http://chatwoot-rails:3000",
	                        conf.get("chatwoot_api_token"), int(conf.get("chatwoot_account_id") or 1))
	consultants = load_dataset()["consultants"]
	ids = ensure_agents(client, consultants)
	teams = {t["name"]: t["id"] for t in client.list_teams()}
	for name, emails in plan_teams(consultants).items():
		if name not in teams:
			teams[name] = client.create_team(name)["id"]
		client.add_team_members(teams[name], [ids[e] for e in emails])
	for inbox in client.list_inboxes():
		if inbox.get("channel_type") == "Channel::FacebookPage":
			client.add_inbox_members(inbox["id"], list(ids.values()))
	for email, agent_id in ids.items():
		frappe.db.set_value("Consultant", email, "chatwoot_agent_id", agent_id)
	frappe.db.commit()
	return {"agents": len(ids), "teams": len(plan_teams(consultants))}
```

Note: Chatwoot team names are stored lowercased; compare with `name.lower()` when matching `list_teams()` results (adjust `teams` dict keys to `t["name"].lower()` and look up `name.lower()`).

- [ ] **Step 7: Run all tests** — `python3 -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests` → `OK`.

- [ ] **Step 8: Live load, twice**

```bash
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost execute mmm_custom.demo.loader.load"
docker exec crm-frappe-1 bash -c "cd frappe-bench && bench --site crm.localhost execute mmm_custom.demo.loader.load"
```

Expected: first run prints non-zero created counts (Territory 18, Course Group 8, CRM Product 46, User 44, Consultant 44, Course Schedule = generator count, Course Promotion 10, Bot Slot 7, Bot Skill 30); second run prints all zeros.

- [ ] **Step 9: Live Chatwoot seed, twice** — `bench --site crm.localhost execute mmm_custom.demo.chatwoot_seed.run` twice → both print `{"agents": 44, "teams": 15}`; Chatwoot `GET /api/v1/accounts/1/teams` lists 15 teams; `Consultant` rows have `chatwoot_agent_id` set (`frappe.db.count("Consultant", {"chatwoot_agent_id": [">", 0]})` → 44).

- [ ] **Step 10: Existing suites still pass** — offline suite OK and `python3 scripts/test-chatwoot-crm-sync.py --secret "$SECRET"` 5/5 (secret per AGENTS.md).

- [ ] **Step 11: Commit** — explicit paths: `demo/` files, `chatwoot_client.py`, the four test files: `git commit -m "feat(demo): add Tin Hoc Sao Viet demo dataset, idempotent loader and Chatwoot seeding"`

---

## Task 7: Fresh-bench verification and docs

**Files:**
- Modify: `docs/superpowers/specs/2026-09-26-edu-lead-engine-design.md` (§6.2 C1 rows → ✅; C1.6 schedule count)
- Modify: `docs/superpowers/specs/2026-09-26-edu-lead-engine/current-state.md` (new DocTypes, custom fields, demo loader rows)
- Modify: `docs/superpowers/specs/2026-09-26-edu-lead-engine/README.md` (current position → C2 plan next)

- [ ] **Step 1: Fresh bench** — create `/tmp/…/scratchpad/crmverify-ports.yml`:

```yaml
services:
  frappe:
    ports: !override
      - "127.0.0.1:18000:8000"
      - "127.0.0.1:19000:9000"
```

Run from `crm/docker`: `docker compose -p crmverify -f docker-compose.yml -f docker-compose.override.yml -f <scratchpad>/crmverify-ports.yml up -d`, wait until `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18000` returns `200` (first init takes several minutes; poll).

- [ ] **Step 2: Checks on the fresh bench** — `docker compose -p crmverify exec frappe bash -c "cd frappe-bench && bench --site crm.localhost list-apps && bench --site crm.localhost execute mmm_custom.demo.loader.load"` → `mmm_custom` listed; loader counts as in Task 6 Step 8.

- [ ] **Step 3: Tear down only the verify project** — `docker compose -p crmverify -f docker-compose.yml -f docker-compose.override.yml -f <scratchpad>/crmverify-ports.yml down -v` (project `crmverify` only).

- [ ] **Step 4: Update docs** per Files above; commit `git commit -m "docs(spec): mark edu lead engine C1 data foundation done"`.
