import sys
from datetime import date
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import render

from mmm_custom.engine.render import RenderError, condition, date_vi, render_text, vnd


class TestFilters(unittest.TestCase):
    def test_vnd(self):
        self.assertEqual(vnd(1200000), "1.200.000đ")
        self.assertEqual(vnd(1620000.0), "1.620.000đ")
        self.assertEqual(vnd(None), "0đ")

    def test_date_vi(self):
        self.assertEqual(date_vi(date(2026, 10, 4)), "Chủ nhật, 04/10")
        self.assertEqual(date_vi("2026-10-06"), "Thứ 3, 06/10")

    def test_filters_available_in_templates(self):
        self.assertEqual(render("{{ 1500000 | vnd }} · {{ d | date_vi }}", {"d": date(2026, 10, 3)}),
                         "1.500.000đ · Thứ 7, 03/10")


class TestGuard(unittest.TestCase):
    def test_renders(self):
        self.assertEqual(render_text("Chào {{ brand.you }}", {"brand": {"you": "anh/chị"}}, render), "Chào anh/chị")

    def test_missing_key_is_blocked(self):
        with self.assertRaises(RenderError):
            render_text("Chào {{ brand.you }}", {"brand": {}}, render)

    def test_undefined_object_is_blocked(self):
        with self.assertRaises(RenderError):
            render_text("Khóa {{ course.name }}", {}, render)

    def test_syntax_error_is_blocked(self):
        with self.assertRaises(RenderError):
            render_text("{% if %}x{% endif %}", {}, render)

    def test_condition(self):
        self.assertTrue(condition("not schedules", {"schedules": []}, render))
        self.assertFalse(condition("not schedules", {"schedules": [1]}, render))


if __name__ == "__main__":
    unittest.main()
