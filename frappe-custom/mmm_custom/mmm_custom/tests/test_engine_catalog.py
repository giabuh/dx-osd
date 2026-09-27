import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog

from mmm_custom.engine.catalog import build_catalog


class TestBuildCatalog(unittest.TestCase):
    def setUp(self):
        self.cat = demo_catalog()

    def test_counts_match_demo_dataset(self):
        self.assertEqual((len(self.cat.groups), len(self.cat.courses), len(self.cat.areas), len(self.cat.branches)),
                         (8, 46, 4, 13))
        self.assertEqual(len(self.cat.skills), 30)

    def test_slots_sorted_with_dependency(self):
        self.assertEqual([s.key for s in self.cat.slots],
                         ["course", "branch", "learner", "goal", "level", "learner_age", "preferred_shift", "customer_name", "phone"])
        self.assertEqual(self.cat.slot("learner_age").depends_on, ("learner", "child"))
        self.assertEqual(self.cat.slot("learner").option("child").button, "Cho con em")

    def test_branch_fields_and_map_url(self):
        b = self.cat.branches["CN Dĩ An"]
        self.assertEqual((b.area, b.button, b.tier), ("Bình Dương", "Dĩ An", "standard"))
        self.assertTrue(b.map_url.startswith("https://www.google.com/maps/search/"))
        self.assertIn("di an", b.aliases)

    def test_course_and_parent_lookup(self):
        c = self.cat.courses["VP-EXCEL"]
        self.assertEqual((c.group, c.fee, c.button), ("Tin học văn phòng", 1800000.0, "Excel"))
        self.assertEqual(c.next_courses, ("VP-EXCEL-NC", "VP-MOS"))
        self.assertEqual(self.cat.parent_of(self.cat.slot("course"), "VP-EXCEL"), "Tin học văn phòng")
        self.assertEqual(self.cat.parent_of(self.cat.slot("branch"), "CN Dĩ An"), "Bình Dương")
        self.assertEqual(self.cat.slot_for("branch").key, "branch")
        self.assertEqual(len(self.cat.courses_in("Kế toán")), 5)
        self.assertEqual(len(self.cat.branches_in("Bình Dương")), 4)

    def test_skill_fields(self):
        s = self.cat.skills["schedule_lookup"]
        self.assertEqual((s.action, s.params, s.config), ("schedule_lookup", ("course",), {"limit": 3}))
        self.assertEqual([t.key for t in s.templates], ["default", "none"])
        self.assertEqual(s.follow_ups[0].target, "fee_quote")

    def test_settings_defaults_fill_gaps_but_zero_and_empty_do_not_override(self):
        self.assertEqual(self.cat.settings["max_skills_per_reply"], 3)
        self.assertEqual(demo_catalog(max_skills_per_reply=0).settings["max_skills_per_reply"], 3)
        self.assertEqual(demo_catalog(max_skills_per_reply=2).settings["max_skills_per_reply"], 2)
        self.assertEqual(self.cat.settings["brand_name"], "Tin Học Sao Việt")

    def test_inactive_rows_are_left_out(self):
        cat = build_catalog({"bot_slots": [
            {"slot_key": "a", "label": "A", "slot_type": "text", "active": 0},
            {"slot_key": "b", "label": "B", "slot_type": "text"}]})
        self.assertEqual([s.key for s in cat.slots], ["b"])


if __name__ == "__main__":
    unittest.main()
