import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.engine import dashboard


class TestDashboard(unittest.TestCase):
    def test_counts_today_bot_leads_and_latest_qualified(self):
        leads = [
            {"name": "L1", "source": "Messenger Bot", "status": "Qualified", "creation": "2026-09-27 09:00:00", "status_since": "2026-09-27 10:00:00"},
            {"name": "L2", "source": "Messenger Bot", "status": "Unqualified", "creation": "2026-09-26 09:00:00", "status_since": "2026-09-27 11:00:00"},
            {"name": "L3", "source": "Facebook", "status": "Qualified", "creation": "2026-09-27 12:00:00", "status_since": "2026-09-27 12:00:00"},
            {"name": "L4", "source": "Messenger Bot", "status": "Qualified", "creation": "2026-09-26 12:00:00", "status_since": "2026-09-26 13:00:00"},
        ]
        result = dashboard.summarize(leads, [{"bot_conversation": "C1"}, {"bot_conversation": "C1"}, {"bot_conversation": "C2"}], [50, 100], "2026-09-27")
        self.assertEqual((result["new_today"], result["qualified_today"], result["unqualified_today"], result["handed_off_today"], result["coverage"]), (1, 1, 1, 2, 75))
        self.assertEqual([r["name"] for r in result["latest_leads"]], ["L1", "L4"])

    def test_leads_the_bot_talked_to_count_whatever_their_source(self):
        # the Chatwoot sync often creates the Lead first (source "Messenger"); the bot then continues it
        leads = [{"name": "L9", "source": "Messenger", "status": "Qualified", "creation": "2026-09-27 08:00:00",
                  "status_since": "2026-09-27 08:30:00"}]
        result = dashboard.summarize(leads, [], [], "2026-09-27", bot_leads={"L9"})
        self.assertEqual((result["new_today"], result["qualified_today"], [r["name"] for r in result["latest_leads"]]), (1, 1, ["L9"]))

    def test_playground_handoffs_are_not_counted(self):
        handoffs = [{"bot_conversation": "sandbox-a", "is_sandbox": 1}, {"bot_conversation": "C1", "is_sandbox": 0}]
        self.assertEqual(dashboard.summarize([], handoffs, [], "2026-09-27")["handed_off_today"], 1)

    def test_latest_leads_limited_to_ten(self):
        leads = [{"name": str(i), "source": "Messenger Bot", "status": "Qualified", "creation": f"2026-09-{i + 1:02d} 10:00:00"} for i in range(12)]
        result = dashboard.summarize(leads, [], [], "2026-09-27")
        self.assertEqual(len(result["latest_leads"]), 10)
        self.assertEqual(result["latest_leads"][0]["name"], "11")

    def test_summary_requires_manager(self):
        frappe = MagicMock()
        with patch.object(dashboard, "frappe", frappe), patch.object(dashboard, "can_open_bot", return_value=False):
            frappe.PermissionError = PermissionError
            frappe.throw.side_effect = PermissionError
            with self.assertRaises(PermissionError):
                dashboard.summary()


class TestOverview(unittest.TestCase):
    def test_period_starts_counting_today_and_falls_back_to_seven_days(self):
        self.assertEqual(dashboard.period_since("today", "2026-10-02"), "2026-10-02")
        self.assertEqual(dashboard.period_since("7", "2026-10-02"), "2026-09-26")
        self.assertEqual(dashboard.period_since(30, "2026-10-02 08:00:00"), "2026-09-03")
        self.assertEqual(dashboard.period_since("365", "2026-10-02"), "2026-09-26")

    def test_fees_count_only_confirmed_registrations(self):
        deals = [
            {"status": "Pending Payment", "deposit_amount": 0, "paid_amount": 0, "balance_due": 1800000},
            {"status": "Deposit Paid", "deposit_amount": 500000, "paid_amount": 0, "balance_due": 1300000},
            {"status": "Won", "deposit_amount": 500000, "paid_amount": 1530000, "balance_due": 0},
            {"status": "Awaiting Confirmation", "deposit_amount": 0, "paid_amount": 0, "balance_due": 1800000},  # bot draft
            {"status": "Lost", "deposit_amount": 300000, "paid_amount": 300000, "balance_due": 1500000},  # cancelled
        ]
        self.assertEqual(dashboard.fees(deals), {"paid": 2030000.0, "due": 3100000.0, "registrations": 3,
                                                 "pending_payment": 1})
        self.assertEqual(dashboard.fees([]), {"paid": 0, "due": 0, "registrations": 0, "pending_payment": 0})

    def test_overview_requires_manager(self):
        frappe = MagicMock()
        with patch.object(dashboard, "frappe", frappe), patch.object(dashboard, "can_open_bot", return_value=False):
            frappe.PermissionError = PermissionError
            frappe.throw.side_effect = PermissionError
            with self.assertRaises(PermissionError):
                dashboard.overview("7")


if __name__ == "__main__":
    unittest.main()
