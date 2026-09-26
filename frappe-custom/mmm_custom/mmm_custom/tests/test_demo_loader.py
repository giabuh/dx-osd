import sys
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import MagicMock

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.demo import loader

BRANCHES = [{"territory_name": "CN A", "tier": "full"}, {"territory_name": "CN B", "tier": "standard"}]
COURSES = [{"product_code": "X", "offer": "all", "weekdays": "T2, T4, T6", "shifts": ["evening"]},
           {"product_code": "Y", "offer": "full", "weekdays": "T7, CN", "shifts": ["morning", "afternoon"]}]


class FakeDb:
    def __init__(self):
        self.rows = {}

    def get_value(self, doctype, filters, fieldname="name"):
        for (dt, name), row in self.rows.items():
            if dt == doctype and all(row.get(k) == v for k, v in filters.items()):
                return name
        return None

    def insert(self, doctype, values):
        name = f"{doctype}-{len(self.rows)}"
        self.rows[(doctype, name)] = dict(values)
        return name

    def get(self, doctype, name):
        return self.rows[(doctype, name)]

    def update(self, doctype, name, values):
        self.rows[(doctype, name)].update(values)


class TestGenerateSchedules(unittest.TestCase):
    def test_full_courses_only_at_full_branches(self):
        rows = loader.generate_schedules(COURSES, BRANCHES, date(2026, 9, 28))
        self.assertTrue(all(r["branch"] == "CN A" for r in rows if r["course"] == "Y"))
        self.assertTrue({r["branch"] for r in rows if r["course"] == "X"} == {"CN A", "CN B"})

    def test_generate_schedules_is_deterministic(self):
        a = loader.generate_schedules(COURSES, BRANCHES, date(2026, 9, 28))
        b = loader.generate_schedules(COURSES, BRANCHES, date(2026, 9, 28))
        self.assertEqual(a, b)

    def test_two_classes_per_pair_in_eight_weeks(self):
        rows = loader.generate_schedules(COURSES, BRANCHES, date(2026, 9, 28), weeks=8, cadence=4)
        self.assertEqual(len(rows), 3 * 2)  # pairs: X@A, X@B, Y@A

    def test_rows_fall_inside_window_and_match_weekday(self):
        anchor = date(2026, 9, 28)
        for r in loader.generate_schedules(COURSES, BRANCHES, anchor):
            self.assertGreaterEqual(r["start_date"], anchor)
            self.assertLess((r["start_date"] - anchor).days, 56)
            first = r["weekdays"].split(",")[0].strip()
            self.assertEqual(loader.WEEKDAY_INDEX[first], r["start_date"].weekday())
            self.assertIn(r["seats"], range(12, 21))


class TestUpsert(unittest.TestCase):
    def test_upsert_is_idempotent(self):
        db = FakeDb()
        name1, created1 = loader.upsert("Course Group", {"group_name": "Kế toán"}, {"button_label": "Kế toán"}, db=db)
        name2, created2 = loader.upsert("Course Group", {"group_name": "Kế toán"}, {"button_label": "Kế toán"}, db=db)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(name1, name2)
        self.assertEqual(len(db.rows), 1)

    def test_upsert_updates_changed_values(self):
        db = FakeDb()
        name, _ = loader.upsert("Course Group", {"group_name": "Kế toán"}, {"button_label": "KT"}, db=db)
        loader.upsert("Course Group", {"group_name": "Kế toán"}, {"button_label": "Kế toán"}, db=db)
        self.assertEqual(db.get("Course Group", name)["button_label"], "Kế toán")


class TestMapUrl(unittest.TestCase):
    def test_encodes_address(self):
        self.assertEqual(loader.map_url("21/8 Lê Trực"),
                         "https://www.google.com/maps/search/?api=1&query=21/8%20L%C3%AA%20Tr%E1%BB%B1c")


if __name__ == "__main__":
    unittest.main()
