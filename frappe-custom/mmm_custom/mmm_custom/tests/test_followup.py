import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

if "requests" not in sys.modules:
    sys.modules["requests"] = MagicMock()

import mmm_custom.followup as followup
from mmm_custom.followup import DEFAULTS, payment_task, rule_task, settings

NOW = datetime(2026, 9, 25, 8, 0, 0)
CFG = settings({})


def lead(name, status="New", owner="sale@eduflow.vn", modified=datetime(2026, 9, 20, 8, 0, 0), **kw):
    return {"name": name, "lead_name": "Khách " + name, "status": status, "lead_owner": owner, "modified": modified, **kw}


def task(title, status="Todo", creation=datetime(2026, 9, 1)):
    return {"title": title, "status": status, "creation": creation}


class TestRules(unittest.TestCase):
    def test_qualified_lead_nobody_called_gets_a_call_task(self):
        self.assertEqual(rule_task(lead("L", "Qualified", modified=NOW - timedelta(hours=30)), NOW, CFG, [])["kind"],
                         "qualified_call")
        self.assertIsNone(rule_task(lead("L", "Qualified", modified=NOW - timedelta(hours=2)), NOW, CFG, []))

    def test_an_open_task_means_someone_is_on_it(self):
        self.assertIsNone(rule_task(lead("L", "Qualified"), NOW, CFG, [task("Gọi khách")]))
        self.assertIsNone(rule_task(lead("L", "Contacted"), NOW, CFG, [task("Gọi khách", "In Progress")]))

    def test_quiet_new_and_contacted_leads_are_stale(self):
        self.assertEqual(rule_task(lead("L", "Contacted"), NOW, CFG, [task("x", "Done")]), {"kind": "stale"})
        self.assertIsNone(rule_task(lead("L", "New", modified=NOW - timedelta(days=1)), NOW, CFG, []))

    def test_after_the_trial_date_even_with_the_trial_task_still_open(self):
        l = lead("L", "Trial Booked", trial_date=date(2026, 9, 23))
        rule = rule_task(l, NOW, CFG, [task("Học thử: Excel · 23/09")])
        self.assertEqual(rule["kind"], "after_trial")
        self.assertIn("23/09", rule["why"])

    def test_after_trial_task_once_and_not_before_the_date(self):
        l = lead("L", "Trial Booked", trial_date=date(2026, 9, 23))
        done = [task("Sau học thử: chốt đăng ký / hẹn lại: Khách L", creation=datetime(2026, 9, 24))]
        self.assertIsNone(rule_task(l, NOW, CFG, done))
        self.assertIsNone(rule_task(lead("L", "Trial Booked", trial_date=date(2026, 9, 26)), NOW, CFG, []))

    def test_nurture_every_two_weeks_with_the_next_class(self):
        l = lead("L", "Nurture", modified=NOW - timedelta(days=15))
        rule = rule_task(l, NOW, CFG, [], "Lớp VP-EXCEL gần nhất: Thứ 7 04/10.")
        self.assertEqual((rule["kind"], rule["n"]), ("nurture", 1))
        self.assertIn("VP-EXCEL", rule["why"])
        recent = [task("Chăm sóc định kỳ (lần 1): Khách L", "Done", NOW - timedelta(days=5))]
        self.assertIsNone(rule_task(l, NOW, CFG, recent))

    def test_nurture_stops_after_the_last_touch(self):
        l = lead("L", "Nurture", modified=NOW - timedelta(days=90))
        touches = [task(f"Chăm sóc định kỳ (lần {i}): Khách L", "Done", NOW - timedelta(days=80 - 15 * i)) for i in range(1, 5)]
        self.assertEqual(rule_task(l, NOW, CFG, touches)["kind"], "nurture_done")
        closed = touches + [task("Xem xét đóng khách nuôi dưỡng: Khách L", "Done")]
        self.assertIsNone(rule_task(l, NOW, CFG, closed))

    def test_settings_from_site_config(self):
        cfg = settings({"lead_nurture": {"nurture_every_days": 7}, "ai_followup_stale_days": 0,
                        "ai_followup_statuses": ["New"]})
        self.assertEqual((cfg["nurture_every_days"], cfg["stale_days"], cfg["stale_statuses"]), (7, 0, ["New"]))
        self.assertEqual(settings({})["qualified_call_hours"], DEFAULTS["qualified_call_hours"])


class TestPaymentReminder(unittest.TestCase):
    def deal(self, **kw):
        return {"name": "D1", "status": "Pending Payment", "modified": NOW - timedelta(days=4), **kw}

    def test_quiet_registration_gets_a_reminder(self):
        self.assertEqual(payment_task(self.deal(), NOW, CFG, [])["kind"], "payment")
        self.assertIsNone(payment_task(self.deal(modified=NOW - timedelta(days=1)), NOW, CFG, []))

    def test_past_due_date_reminds_at_once(self):
        rule = payment_task(self.deal(modified=NOW, payment_due_date=date(2026, 9, 24)), NOW, CFG, [])
        self.assertIn("24/09", rule["why"])

    def test_paid_or_already_followed_is_left_alone(self):
        self.assertIsNone(payment_task(self.deal(status="Deposit Paid"), NOW, CFG, []))
        self.assertIsNone(payment_task(self.deal(), NOW, CFG, [task("Nhắc đóng phí: Lan")]))


class TestPlanFollowups(unittest.TestCase):
    def setUp(self):
        self.frappe = MagicMock()
        self.frappe.conf = {"typesafe_api_key": "jev"}
        self.leads = []
        self.tasks = {}

        def get_all(doctype, filters=None, **kwargs):
            if doctype == "CRM Lead":
                return self.leads
            if doctype == "CRM Task":
                return self.tasks.get(filters["reference_docname"], [])
            return []

        self.frappe.get_all.side_effect = get_all

    def run_plan(self, answers):
        def ask(api_key, state, questions, model="jev-latest", url=None):
            return {"next_action": answers[state["lead"]["name"]]}

        with patch.object(followup, "frappe", self.frappe), patch.object(followup, "ask_jev", side_effect=ask) as jev, \
                patch.object(followup, "_next_class", return_value=""):
            return followup.plan_followups(now=NOW), jev

    def created(self):
        return [c[0][0] for c in self.frappe.get_doc.call_args_list]

    def test_queries_every_open_status_oldest_first(self):
        result, _ = self.run_plan({})
        self.assertEqual(result["checked"], 0)
        call = self.frappe.get_all.call_args_list[0]
        self.assertEqual(call[1]["filters"], {"status": ["in", ["New", "Qualified", "Contacted", "Trial Booked", "Nurture"]],
                                              "converted": 0})
        self.assertEqual(call[1]["order_by"], "modified asc")

    def test_confident_call_creates_a_high_priority_task_for_the_owner_due_tomorrow(self):
        self.leads = [lead("L1")]
        result, jev = self.run_plan({"L1": {"choice": "call", "confidence": 0.9}})
        self.assertEqual(result["results"], [{"lead": "L1", "action": "task_created", "choice": "call"}])
        self.assertEqual(jev.call_args[0][1]["lead"]["days_since_update"], 5)
        t = self.created()[0]
        self.assertEqual((t["doctype"], t["priority"], t["assigned_to"], t["reference_docname"], t["due_date"]),
                         ("CRM Task", "High", "sale@eduflow.vn", "L1", datetime(2026, 9, 26, 8, 0, 0)))
        self.assertIn("Khách L1", t["title"])

    def test_no_task_when_unsure_or_wait_and_leads_with_an_open_task_are_skipped(self):
        self.leads = [lead("L1"), lead("L2"), lead("L3")]
        self.tasks = {"L3": [task("T1")]}
        result, _ = self.run_plan({"L1": {"choice": "call", "confidence": 0.5}, "L2": {"choice": "wait", "confidence": 0.95}})
        self.assertEqual([r["action"] for r in result["results"]], ["none", "none"])
        self.frappe.get_doc.assert_not_called()
        self.frappe.db.set_value.assert_not_called()

    def test_rules_run_without_an_ai_key(self):
        self.frappe.conf = {}
        self.leads = [lead("L1", "Contacted"), lead("L2", "Qualified"), lead("L3", "Nurture", modified=NOW - timedelta(days=20))]
        result, jev = self.run_plan({})
        jev.assert_not_called()
        self.assertEqual([r["choice"] for r in result["results"]], ["message", "qualified_call", "nurture"])
        titles = [t["title"] for t in self.created()]
        self.assertTrue(titles[0].startswith("Nhắn tin chăm sóc lại khách"))
        self.assertTrue(titles[2].startswith("Chăm sóc định kỳ (lần 1)"))

    def test_jev_is_asked_for_at_most_the_configured_number(self):
        self.frappe.conf["ai_followup_max_leads"] = 1
        self.leads = [lead("L1"), lead("L2")]
        result, jev = self.run_plan({"L1": {"choice": "call", "confidence": 0.9}})
        self.assertEqual(jev.call_count, 1)
        self.assertEqual([r["choice"] for r in result["results"]], ["call", "message"])


class TestSchedulerHook(unittest.TestCase):
    def test_hooks_run_the_followup_daily(self):
        hooks = (APP_DIR / "mmm_custom" / "hooks.py").read_text(encoding="utf-8")
        self.assertIn('"mmm_custom.followup.run_daily"', hooks)


if __name__ == "__main__":
    unittest.main()
