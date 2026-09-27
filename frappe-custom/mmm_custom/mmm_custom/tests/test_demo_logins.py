import sys
from pathlib import Path
import unittest

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.demo import logins


class TestStaffEmails(unittest.TestCase):
    def test_keeps_active_consultants_sorted(self):
        rows = [{"user": "b@x.vn", "active": 1}, {"user": "a@x.vn", "active": 1}]
        self.assertEqual(logins.staff_emails(rows), ["a@x.vn", "b@x.vn"])

    def test_skips_inactive_and_userless(self):
        rows = [{"user": "a@x.vn", "active": 0}, {"user": None, "active": 1}, {"user": "c@x.vn"}]
        self.assertEqual(logins.staff_emails(rows), ["c@x.vn"])


if __name__ == "__main__":
    unittest.main()
