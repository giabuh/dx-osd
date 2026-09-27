import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom import hooks, scope


class TestRule(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(scope.rule({"branch": "CN Dĩ An", "handles_b2b": 0}), ("branch", "CN Dĩ An"))
        self.assertEqual(scope.rule({"branch": None, "handles_b2b": 1}), ("b2b", None))
        self.assertEqual(scope.rule({"branch": "", "handles_b2b": 0}), ("central", None))
        self.assertIsNone(scope.rule(None))  # managers and non-consultants: the CRM's own rules only


class Field:
    """Stands in for a pypika field: records comparisons as tuples."""

    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return ("=", self.name, other)

    def isin(self, values):
        return ("in", self.name, values)

    def isnull(self):
        return ("null", self.name)


class Table:
    territory = Field("territory")

    def __getitem__(self, name):
        return Field(name)


class TestRecordScope(unittest.TestCase):
    def scope_for(self, consultant, doctype="CRM Lead"):
        frappe, DT = MagicMock(), Table()
        frappe.db.get_value.return_value = consultant
        frappe.get_all.return_value = ["b2b1@x.vn", "b2b2@x.vn"]
        with patch.object(scope, "frappe", frappe):
            return scope.record_scope("tv@x.vn", doctype, DT), DT

    def test_branch_consultant_sees_the_branch(self):
        self.assertEqual(self.scope_for({"branch": "CN Dĩ An", "handles_b2b": 0})[0], ("=", "territory", "CN Dĩ An"))

    def test_b2b_consultant_sees_the_b2b_team(self):
        self.assertEqual(self.scope_for({"branch": None, "handles_b2b": 1}, "CRM Deal")[0],
                         ("in", "deal_owner", ["b2b1@x.vn", "b2b2@x.vn"]))

    def test_other_doctypes_and_non_consultants_are_untouched(self):
        self.assertIsNone(self.scope_for({"branch": "CN Dĩ An"}, "CRM Task")[0])
        self.assertIsNone(self.scope_for(None)[0])

    def test_hooked_into_the_crm(self):
        self.assertEqual(hooks.crm_record_scope, ["mmm_custom.scope.record_scope"])


if __name__ == "__main__":
    unittest.main()
