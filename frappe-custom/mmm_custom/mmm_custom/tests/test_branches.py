import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

_real_frappe = sys.modules.get("frappe")
sys.modules["frappe"] = MagicMock()
try:
    import mmm_custom.setup as setup_mod
finally:
    if _real_frappe is None:
        del sys.modules["frappe"]
    else:
        sys.modules["frappe"] = _real_frappe

from mmm_custom import hooks
from mmm_custom.branches import fill_territory, territory_for_branch

TERRITORIES = [{"name": "CN Bình Thạnh", "aliases": "binh thanh, bthanh"}, {"name": "CN Quận 7", "aliases": "quan 7, q7"},
               {"name": "CN Thủ Đức", "aliases": "thu duc"}]


class TestLegacyBranch(unittest.TestCase):
    def test_legacy_values_find_their_territory(self):
        self.assertEqual(territory_for_branch("CS1 Bình Thạnh", TERRITORIES), "CN Bình Thạnh")
        self.assertEqual(territory_for_branch("CS3 Thủ Đức", TERRITORIES), "CN Thủ Đức")
        self.assertEqual(territory_for_branch("Q7", TERRITORIES), "CN Quận 7")

    def test_unknown_branch_stays_empty(self):
        self.assertIsNone(territory_for_branch("CS2 Quận 1", TERRITORIES))
        self.assertIsNone(territory_for_branch("", TERRITORIES))

    def test_a_territory_already_set_wins(self):
        doc = MagicMock()
        doc.get.side_effect = {"branch": "CS1 Bình Thạnh", "territory": "CN Quận 7"}.get
        fill_territory(doc)
        self.assertNotEqual(doc.territory, "CN Bình Thạnh")

    def test_hooks(self):
        self.assertIn("mmm_custom.branches.migrate", hooks.after_migrate)
        self.assertIn("mmm_custom.branches.fill_territory", hooks.doc_events["CRM Lead"]["validate"])


class TestLeadLayout(unittest.TestCase):
    def test_b2b_fields_leave_every_lead_layout(self):
        side = [{"name": "details_section", "columns": [{"name": "c", "fields": [
            "organization", "website", "territory", "industry", "job_title", "source", "lead_owner", "branch"]}]}]
        tabs = [{"name": "t", "sections": [{"name": "s", "columns": [{"name": "c", "fields": [
            "organization", "annual_revenue", "no_of_employees", "territory"]}]}]}]
        self.assertEqual(setup_mod.remove_fields(side, setup_mod.REMOVE_FROM_LEAD)[0]["columns"][0]["fields"],
                         ["territory", "source", "lead_owner"])  # a customer is a person: no organization (D-122)
        self.assertEqual(setup_mod.remove_fields(tabs, setup_mod.REMOVE_FROM_LEAD)[0]["sections"][0]["columns"][0]["fields"],
                         ["territory"])

    def test_layout_fields_sees_every_section(self):
        tabs = [{"sections": [{"columns": [{"fields": ["a", "territory"]}]}, {"columns": [{"fields": ["b"]}]}]}]
        self.assertEqual(setup_mod.layout_fields(tabs), {"a", "territory", "b"})

    def test_upstream_quick_entry_keeps_its_shape(self):
        quick = json.loads('[{"name": "organization_section", "columns": [{"name": "a", "fields": ["organization", "territory"]},'
                           ' {"name": "b", "fields": ["website", "annual_revenue"]}]}]')
        out = setup_mod.remove_fields(quick, setup_mod.REMOVE_FROM_LEAD)
        self.assertEqual([c["fields"] for c in out[0]["columns"]], [["territory"], []])


if __name__ == "__main__":
    unittest.main()
