import json
import sys
from pathlib import Path
import unittest

DATA = Path(__file__).resolve().parent.parent / "demo" / "saoviet"


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


class TestDemoData(unittest.TestCase):
    def setUp(self):
        self.areas = load("areas")
        self.groups = load("course_groups")
        self.courses = load("courses")
        self.consultants = load("consultants")
        self.promotions = load("promotions")
        self.slots = load("bot_slots")
        self.skills = load("bot_skills")
        self.branches = [b for a in self.areas["areas"] for b in a["branches"]]

    def test_counts(self):
        self.assertEqual(len(self.areas["areas"]), 4)
        self.assertEqual(len(self.branches), 13)
        self.assertEqual(len(self.groups), 8)
        self.assertEqual(len(self.courses), 46)
        self.assertEqual(len(self.consultants), 44)
        self.assertEqual(len(self.promotions), 10)
        self.assertEqual(len(self.slots), 7)
        self.assertEqual(len(self.skills), 30)

    def test_unique_keys(self):
        for rows, key in ((self.branches, "branch_code"), (self.branches, "territory_name"),
                          (self.courses, "product_code"), (self.consultants, "email"),
                          (self.groups, "group_name"), (self.skills, "skill_key"), (self.slots, "slot_key")):
            values = [r[key] for r in rows]
            self.assertEqual(len(values), len(set(values)), key)

    def test_button_labels_fit_messenger(self):
        labels = [a["button_label"] for a in self.areas["areas"]]
        labels += [r["button_label"] for r in self.branches + self.groups + self.courses]
        labels += [o["button_label"] for s in self.slots for o in s.get("options", [])]
        labels += [f["title"] for s in self.skills for f in s.get("follow_ups", [])]
        for label in labels:
            self.assertLessEqual(len(label), 20, label)

    def test_references_resolve(self):
        groups = {g["group_name"] for g in self.groups}
        codes = {c["product_code"] for c in self.courses}
        branches = {b["territory_name"] for b in self.branches}
        slots = {s["slot_key"] for s in self.slots}
        skills = {s["skill_key"] for s in self.skills}
        for c in self.courses:
            self.assertIn(c["course_group"], groups, c["product_code"])
            for n in c.get("next_courses", []):
                self.assertIn(n, codes, c["product_code"])
        for p in self.consultants:
            if p["branch"]:
                self.assertIn(p["branch"], branches, p["email"])
            for g in p["specialties"]:
                self.assertIn(g, groups, p["email"])
        for pr in self.promotions:
            for c in pr.get("courses", []):
                self.assertIn(c, codes, pr["title"])
            for g in pr.get("course_groups", []):
                self.assertIn(g, groups, pr["title"])
            for b in pr.get("branches", []):
                self.assertIn(b, branches, pr["title"])
        for s in self.skills:
            for p in s.get("parameters", []):
                self.assertIn(p, slots, s["skill_key"])
            for f in s.get("follow_ups", []):
                if f["target_type"] == "skill":
                    self.assertIn(f["target"], skills, s["skill_key"])
            self.assertTrue(any(t["variant_key"] == "default" for t in s["templates"]), s["skill_key"])
        for s in self.slots:
            if s.get("depends_on_slot"):
                self.assertIn(s["depends_on_slot"], slots)

    def test_consultants_per_branch(self):
        for b in self.branches:
            staff = [p for p in self.consultants if p["branch"] == b["territory_name"]]
            self.assertEqual(len(staff), 3, b["territory_name"])
            self.assertEqual(sum(p["level"] == "Team Lead" for p in staff), 1, b["territory_name"])

    def test_demo_emails_are_unroutable(self):
        for p in self.consultants:
            self.assertTrue(p["email"].endswith("@demo.saoviet.invalid"), p["email"])

    def test_age_ranges_ordered(self):
        for c in self.courses:
            self.assertLessEqual(c["min_age"], c["max_age"], c["product_code"])


if __name__ == "__main__":
    unittest.main()
