import sys
from pathlib import Path
import unittest

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom import seed_demo


class TestDemoTasks(unittest.TestCase):
    def test_dates_follow_the_demo_day(self):
        tasks = {t["title"][:20]: t for t in seed_demo.demo_tasks("2026-10-02")}
        first = tasks["Gọi điện tư vấn lộ t"]
        self.assertEqual((first["start_date"], first["due_date"]), ("2026-10-01", "2026-10-02 17:00:00"))
        self.assertTrue(all("start" not in t and "due" not in t for t in tasks.values()))

    def test_only_the_finished_task_is_in_the_past(self):
        past = [t["title"] for t in seed_demo.demo_tasks("2026-10-02") if t["due_date"][:10] < "2026-10-02"]
        self.assertEqual(past, [t["title"] for t in seed_demo.TASKS if t["status"] == "Done"])


if __name__ == "__main__":
    unittest.main()
