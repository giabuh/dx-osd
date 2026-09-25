import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

if "requests" not in sys.modules:
    sys.modules["requests"] = MagicMock()

import mmm_custom.followup as followup

NOW = datetime(2026, 9, 25, 8, 0, 0)


def lead(name, owner="sale@eduflow.vn"):
    return {"name": name, "lead_name": "Khách " + name, "status": "New", "lead_owner": owner, "modified": datetime(2026, 9, 20, 8, 0, 0)}


class TestPlanFollowups(unittest.TestCase):
    def setUp(self):
        self.frappe = MagicMock()
        self.frappe.conf = {"typesafe_api_key": "jev"}
        self.leads = []
        self.open_tasks = {}

        def get_all(doctype, filters=None, **kwargs):
            if doctype == "CRM Lead":
                return self.leads
            if doctype == "CRM Task":
                return self.open_tasks.get(filters["reference_docname"], [])
            return []

        self.frappe.get_all.side_effect = get_all

    def run_plan(self, answers):
        def ask(api_key, state, questions, model="jev-latest", url=None):
            return {"next_action": answers[state["lead"]["name"]]}

        with patch.object(followup, "frappe", self.frappe), patch.object(followup, "ask_jev", side_effect=ask) as jev:
            return followup.plan_followups(now=NOW), jev

    def test_does_nothing_without_an_api_key(self):
        self.frappe.conf = {}
        with patch.object(followup, "frappe", self.frappe):
            self.assertEqual(followup.plan_followups(now=NOW), {"status": "ai_disabled"})
        self.frappe.get_all.assert_not_called()

    def test_queries_only_open_leads_unchanged_for_stale_days_oldest_first(self):
        result, _ = self.run_plan({})
        self.assertEqual(result["checked"], 0)
        call = self.frappe.get_all.call_args_list[0]
        self.assertEqual(call[1]["filters"], {"status": ["in", ["New", "Contacted", "Nurture"]], "modified": ["<", datetime(2026, 9, 22, 8, 0, 0)]})
        self.assertEqual(call[1]["order_by"], "modified asc")

    def test_stale_days_zero_is_honoured_not_replaced_by_the_default(self):
        self.frappe.conf["ai_followup_stale_days"] = 0
        self.run_plan({})
        self.assertEqual(self.frappe.get_all.call_args_list[0][1]["filters"]["modified"], ["<", NOW])

    def test_confident_call_creates_a_high_priority_task_for_the_owner_due_tomorrow(self):
        self.leads = [lead("L1")]
        result, jev = self.run_plan({"L1": {"choice": "call", "confidence": 0.9}})
        self.assertEqual(result["results"], [{"lead": "L1", "action": "task_created", "choice": "call", "confidence": 0.9}])
        self.assertEqual(jev.call_args[0][1]["lead"]["days_since_update"], 5)
        task = self.frappe.get_doc.call_args[0][0]
        self.assertEqual(task["doctype"], "CRM Task")
        self.assertEqual(task["priority"], "High")
        self.assertEqual(task["assigned_to"], "sale@eduflow.vn")
        self.assertEqual(task["reference_docname"], "L1")
        self.assertEqual(task["due_date"], datetime(2026, 9, 26, 8, 0, 0))
        self.assertIn("Khách L1", task["title"])

    def test_no_task_when_unsure_or_wait_and_leads_with_an_open_task_are_skipped(self):
        self.leads = [lead("L1"), lead("L2"), lead("L3")]
        self.open_tasks = {"L3": ["T1"]}
        result, _ = self.run_plan({"L1": {"choice": "call", "confidence": 0.5}, "L2": {"choice": "wait", "confidence": 0.95}})
        self.assertEqual([r["action"] for r in result["results"]], ["none", "none", "skipped"])
        self.frappe.get_doc.assert_not_called()
        self.frappe.db.set_value.assert_not_called()


class TestSchedulerHook(unittest.TestCase):
    def test_hooks_run_the_followup_daily(self):
        hooks = (APP_DIR / "mmm_custom" / "hooks.py").read_text(encoding="utf-8")
        self.assertIn('"mmm_custom.followup.run_daily"', hooks)


if __name__ == "__main__":
    unittest.main()
