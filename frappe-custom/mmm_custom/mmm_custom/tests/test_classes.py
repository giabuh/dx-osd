"""Classes page helpers (D-120): what a row shows and which values a save may carry."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mmm_custom.classes import clean_values, row_view

SHIFTS = ["Sáng 8:30–11:00", "Chiều 13:30–16:30", "Tối 17:00–21:00"]
STATUSES = ["Open", "Full", "Started"]


def clean(values, creating=True):
    return clean_values(values, SHIFTS, STATUSES, creating)


class TestRowView(unittest.TestCase):
    ROW = {"name": "abc", "title": "Excel · CN Q7 · 06/10/2026 · Tối", "course": "VP-EXCEL", "branch": "CN Q7",
           "start_date": "2026-10-06", "shift": "Tối 17:00–21:00", "weekdays": "T3, T5", "seats": 10, "status": "Open"}

    def test_seats_left_and_pending(self):
        view = row_view(self.ROW, {"VP-EXCEL": "Excel cơ bản"}, {"abc": 4}, {"abc": 2})
        self.assertEqual((view["course_name"], view["taken"], view["seats_left"], view["pending"]),
                         ("Excel cơ bản", 4, 6, 2))

    def test_seats_left_never_negative_and_unlimited_when_no_seats(self):
        self.assertEqual(row_view({**self.ROW}, {}, {"abc": 12}, {})["seats_left"], 0)
        unlimited = row_view({**self.ROW, "seats": 0}, {}, {"abc": 3}, {})
        self.assertIsNone(unlimited["seats_left"])
        self.assertEqual(unlimited["course_name"], "VP-EXCEL")


class TestCleanValues(unittest.TestCase):
    NEW = {"course": "VP-EXCEL", "branch": "CN Q7", "start_date": "2026-10-06", "shift": SHIFTS[2]}

    def test_a_new_class_needs_course_branch_date_and_shift(self):
        self.assertEqual(clean(self.NEW)["course"], "VP-EXCEL")
        for missing in ("course", "branch", "start_date", "shift"):
            with self.assertRaisesRegex(ValueError, "Chọn|Nhập"):
                clean({k: v for k, v in self.NEW.items() if k != missing})

    def test_an_edit_may_change_a_single_value(self):
        self.assertEqual(clean({"seats": "12"}, creating=False), {"seats": 12})

    def test_only_known_fields_pass(self):
        self.assertNotIn("owner", clean({**self.NEW, "owner": "x", "title": "y"}))

    def test_shift_and_status_must_be_options(self):
        with self.assertRaisesRegex(ValueError, "Ca học"):
            clean({**self.NEW, "shift": "Đêm"})
        with self.assertRaisesRegex(ValueError, "Trạng thái"):
            clean({**self.NEW, "status": "Closed"})

    def test_seats_is_a_non_negative_number(self):
        for bad in ("-1", "abc"):
            with self.assertRaisesRegex(ValueError, "Sĩ số"):
                clean({**self.NEW, "seats": bad})
        self.assertEqual(clean({**self.NEW, "seats": ""})["seats"], 0)


if __name__ == "__main__":
    unittest.main()
