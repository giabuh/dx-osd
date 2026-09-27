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


if __name__ == "__main__":
    unittest.main()
