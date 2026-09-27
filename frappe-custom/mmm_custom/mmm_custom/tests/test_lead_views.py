import sys
from pathlib import Path
import unittest

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom import hooks, lead_views


class TestQuickFilters(unittest.TestCase):
    def test_site_filters_kept_and_missing_ones_appended(self):
        self.assertEqual(lead_views.merge_filters(["lead_name", "status", "territory"]),
                         ["lead_name", "status", "territory", "ai_hotness", "course_interest"])

    def test_nothing_to_add_is_unchanged(self):
        current = ["territory", "ai_hotness", "course_interest", "status"]
        self.assertEqual(lead_views.merge_filters(current), current)

    def test_runs_on_migrate(self):
        self.assertIn("mmm_custom.lead_views.ensure_lead_quick_filters", hooks.after_migrate)


if __name__ == "__main__":
    unittest.main()
