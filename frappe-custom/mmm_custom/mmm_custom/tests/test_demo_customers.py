import sys
import unittest
from datetime import date, datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom import seed_demo
from mmm_custom.demo import customers, loader

DATA = customers.load_data()
CATALOG = customers.catalog_of(loader.load_dataset())
TODAY = date(2026, 10, 1)


def count(rows, key):
    out = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return out


class TestSampleData(unittest.TestCase):
    def test_is_consistent_with_the_catalog(self):
        self.assertEqual(customers.validate_data(DATA, CATALOG), [])

    def test_lead_numbers_match_the_spec(self):
        leads = DATA["leads"]
        self.assertEqual(len(leads), 52)
        self.assertEqual(count(leads, "status"), {
            "New": 9, "Qualified": 9, "Contacted": 7, "Trial Booked": 5, "Nurture": 4, "Converted": 12,
            "Unqualified": 3, "Junk": 3})
        self.assertEqual(count(leads, "source"), {
            "Messenger Bot": 20, "Facebook Messenger": 12, "Zalo OA": 5, "Hotline": 5, "Giới thiệu": 4,
            "Đến trực tiếp": 3, "TikTok": 3})
        self.assertEqual(set(count(leads, "branch").values()), {4})
        self.assertEqual(len(count(leads, "branch")), 13)
        self.assertTrue(all(0 <= l["days_ago"] <= 30 for l in leads))
        self.assertTrue(any(l["days_ago"] == 0 for l in leads))

    def test_no_developer_test_leads(self):
        names = {f"{l['first_name']} {l['last_name']}" for l in DATA["leads"]}
        self.assertFalse(names & {"Bảo Gia", "Hoàng Thành", "Gia Bảo", "Thành Hoàng"})
        self.assertFalse([t for t in seed_demo.TASKS if "Hoàng Thành" in t["title"] + t["description"]])

    def test_registrations(self):
        deals = DATA["deals"]
        self.assertEqual(len(deals), 15)
        self.assertEqual(count(deals, "final"), {"awaiting": 2, "pending": 3, "deposit": 4, "won": 5, "lost": 1})
        converted = {l["email"] for l in DATA["leads"] if l["status"] == "Converted"}
        confirmed = {d["lead"] for d in deals if d["final"] in ("pending", "deposit", "won")}
        self.assertEqual(confirmed, converted)

    def test_other_counts(self):
        self.assertEqual(len(DATA["tasks"]), 8)
        self.assertEqual(len(DATA["tasks"]) + len(seed_demo.TASKS), 14)
        self.assertEqual(len(DATA["quiz_attempts"]), 10)
        self.assertEqual(count(DATA["quiz_attempts"], "quiz"),
                         {"excel_quiz": 4, "word_quiz": 2, "design_quiz": 2, "kids_quiz": 2})
        self.assertEqual(len(DATA["posts"]), 8)
        self.assertEqual(count(DATA["posts"], "status"), {"Posted": 5, "Pending Approval": 2, "Draft": 1})
        self.assertEqual(len(DATA["comment_replies"]), 8)
        self.assertEqual(sum(1 for r in DATA["comment_replies"] if r.get("lead")), 3)
        self.assertTrue(38 <= len(DATA["notes"]) <= 42)

    def test_dispatch_has_something_to_propose(self):
        odd = [t for t in DATA["tasks"]
               if not t["assigned_to"] or CATALOG["consultants"][t["assigned_to"]] != next(
                   l["branch"] for l in DATA["leads"] if l["email"] == t["lead"])]
        self.assertGreaterEqual(len(odd), 3)

    def test_existing_tasks_point_at_the_sample(self):
        emails = {l["email"] for l in DATA["leads"]}
        for t in seed_demo.TASKS:
            self.assertTrue(t["lead"] is None or t["lead"] in emails, t["title"])
            self.assertTrue(t["assigned_to"] == "Administrator" or t["assigned_to"] in CATALOG["consultants"], t["title"])

    def test_validation_catches_problems(self):
        bad = {**DATA, "leads": [{**DATA["leads"][0], "courses": ["NOPE"], "lead_owner": "x@demo.saoviet.invalid"}]
               + DATA["leads"][1:]}
        errors = customers.validate_data(bad, CATALOG)
        self.assertTrue(any("unknown course NOPE" in e for e in errors))
        self.assertTrue(any("not a consultant" in e for e in errors))

    def test_full_only_course_needs_a_full_branch(self):
        lead = {**DATA["leads"][1], "courses": ["VKT-REVIT"]}  # second Lead sits at a standard branch
        errors = customers.validate_data({**DATA, "leads": [DATA["leads"][0], lead] + DATA["leads"][2:]}, CATALOG)
        self.assertTrue(any("not offered at" in e for e in errors))


class TestHelpers(unittest.TestCase):
    def test_stamp_is_stable_and_moves_with_the_day(self):
        a = customers.stamp(TODAY, 3, "k")
        self.assertEqual(a, customers.stamp(TODAY, 3, "k"))
        self.assertEqual(a.date(), date(2026, 9, 28))
        self.assertEqual(customers.stamp(date(2026, 10, 2), 3, "k").date(), date(2026, 9, 29))
        self.assertEqual(customers.stamp(TODAY, 3, "k").time(), customers.stamp(date(2026, 10, 2), 3, "k").time())
        self.assertLessEqual(customers.stamp(TODAY, 0, "k").hour, 9)

    def test_pick_class_takes_the_first_upcoming_open_class(self):
        rows = [{"name": "old", "start_date": date(2026, 9, 28), "status": "Open"},
                {"name": "later", "start_date": "2026-10-20", "status": "Open"},
                {"name": "soon", "start_date": date(2026, 10, 5), "status": "Open"},
                {"name": "full", "start_date": date(2026, 10, 2), "status": "Closed"}]
        self.assertEqual(customers.pick_class(rows, TODAY), "soon")
        self.assertEqual(customers.pick_class(rows[:1], TODAY), "old")
        self.assertEqual(customers.pick_class([], TODAY), "")

    def test_branch_consultants(self):
        people = [{"email": "a", "branch": "X"}, {"email": "b", "branch": "Y"}, {"email": "c", "branch": "X"}]
        self.assertEqual(customers.branch_consultants(people, "X"), ["a", "c"])
        self.assertEqual(customers.branch_consultants(people, "Z"), [])

    def test_deposit_and_dates(self):
        self.assertEqual(customers.deposit_for(1500000), 450000)
        self.assertEqual(customers.day_of_week(date(2026, 10, 1)), "Thứ Năm")
        self.assertEqual(customers.day_from(TODAY, -2), date(2026, 9, 29))
        self.assertEqual(customers.conversation_id("a.b@demo.saoviet.invalid"), "demo-a.b")

    def test_differs_ignores_representation(self):
        self.assertFalse(customers.differs(datetime(2026, 10, 1, 9, 5), "2026-10-01 09:05:00"))
        self.assertFalse(customers.differs(1500000.0, 1500000))
        self.assertFalse(customers.differs(None, ""))
        self.assertTrue(customers.differs("a", "b"))
        self.assertFalse(customers.differs([{"product_code": "X", "qty": 1}], [{"product_code": "X"}]))
        self.assertTrue(customers.differs([{"product_code": "X"}], [{"product_code": "Y"}]))
        self.assertTrue(customers.differs([], [{"product_code": "Y"}]))


class TestTaskReferences(unittest.TestCase):
    def test_resolves_a_lead_or_its_registration(self):
        leads, deals = {"a@x": "CRM-LEAD-1"}, {"CRM-LEAD-1": "CRM-DEAL-1"}
        self.assertEqual(seed_demo.resolve_reference({"lead": "a@x", "reference_doctype": "CRM Lead"}, leads, deals),
                         ("CRM Lead", "CRM-LEAD-1"))
        self.assertEqual(seed_demo.resolve_reference({"lead": "a@x", "reference_doctype": "CRM Deal"}, leads, deals),
                         ("CRM Deal", "CRM-DEAL-1"))
        self.assertEqual(seed_demo.resolve_reference({"lead": "a@x", "reference_doctype": "CRM Deal"}, leads, {}),
                         ("", ""))
        self.assertEqual(seed_demo.resolve_reference({"lead": None}, leads, deals), ("", ""))
        self.assertEqual(seed_demo.resolve_reference({"lead": "zzz"}, leads, deals), ("", ""))


if __name__ == "__main__":
    unittest.main()
