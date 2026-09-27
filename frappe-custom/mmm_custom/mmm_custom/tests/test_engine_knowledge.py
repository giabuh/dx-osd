import sys
from datetime import date
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, promo, render, schedule, without_knowledge

from mmm_custom.engine.catalog import build_catalog
from mmm_custom.engine.knowledge import CHECKS, course_overview, knowledge_table

CAT = demo_catalog()
SCHEDULES = [schedule("VP-EXCEL", "CN Dĩ An", date(2026, 10, 6))]


class TestCourseOverview(unittest.TestCase):
    def test_a_complete_course(self):
        o = course_overview(CAT.courses["VP-EXCEL"], CAT, SCHEDULES, [promo("Tất cả -10%")], render)
        self.assertEqual((o["coverage"], o["gaps"]), (100, []))
        self.assertEqual((o["fee"], o["final_fee"], o["promotions"]), (1800000.0, 1620000.0, ["Tất cả -10%"]))
        self.assertEqual(len(o["faqs"]), 4)
        self.assertIn("Khóa Excel từ cơ bản đến nâng cao học từ đầu", o["faqs"][0]["reply"])
        self.assertIn("excel", o["jev_reads"])
        self.assertIn("Pivot Table", " ".join(o["syllabus"]))

    def test_gaps_tell_what_to_fill_in(self):
        cat = without_knowledge(CAT, "VP-WORD")
        o = course_overview(cat.courses["VP-WORD"], cat, [], [], render)
        self.assertEqual(len(o["gaps"]), 4)
        for text in ("mô tả", "nội dung học", "câu hỏi thường gặp", "lịch khai giảng"):
            self.assertTrue(any(text in g for g in o["gaps"]), text)
        self.assertEqual(o["coverage"], round(100 * (len(CHECKS) - 4) / len(CHECKS)))

    def test_a_broken_faq_answer_is_flagged(self):
        cat = build_catalog({"courses": [{"product_code": "X", "product_name": "X", "course_group": "G",
                                          "faqs": [{"question": "Q", "answer": "Dạ {{ course.name "}]}]})
        o = course_overview(cat.courses["X"], cat, [], [], render)
        self.assertTrue(o["faqs"][0]["error"])
        self.assertTrue(any("câu trả lời 1" in g for g in o["gaps"]))

    def test_promotions_limited_to_other_courses_are_left_out(self):
        o = course_overview(CAT.courses["VP-EXCEL"], CAT, [], [promo("Robot -20%", courses=["TE-ROBO"])], render)
        self.assertEqual((o["promotions"], o["final_fee"]), ([], 1800000.0))

    def test_branch_only_promotions_do_not_set_the_fee_everyone_sees(self):
        o = course_overview(CAT.courses["VP-EXCEL"], CAT, [], [promo("Long Thành -15%", amount=15, branches=["CN Long Thành"])], render)
        self.assertEqual((o["promotions"], o["final_fee"]), ([], 1800000.0))


class TestDemoKnowledge(unittest.TestCase):
    def test_every_demo_course_is_covered_and_its_replies_render(self):
        for course in CAT.courses.values():
            o = course_overview(course, CAT, SCHEDULES, [], render)
            self.assertEqual(o["gaps"], [], course.code)
            self.assertTrue(all(f["reply"] and "{" not in f["reply"] for f in o["faqs"]), course.code)


class TestKnowledgeTable(unittest.TestCase):
    def test_every_course_least_covered_first(self):
        rows = knowledge_table(CAT, {"VP-EXCEL": 3})
        self.assertEqual(len(rows), 51)
        self.assertEqual([r["coverage"] for r in rows], sorted(r["coverage"] for r in rows))
        excel = next(r for r in rows if r["code"] == "VP-EXCEL")
        self.assertEqual((excel["coverage"], excel["faqs"], excel["schedules"]), (100, 4, 3))


if __name__ == "__main__":
    unittest.main()
