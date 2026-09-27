import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom import bot_admin


def row(name, parent, is_group=0):
    return {"name": name, "parent_crm_territory": parent, "is_group": is_group}


class TestSplitTree(unittest.TestCase):
    def test_root_areas_and_branches(self):
        rows = [row("Sao Việt", None, 1), row("Bình Dương", "Sao Việt", 1), row("Đồng Nai", "Sao Việt", 1),
                row("CN Thuận An", "Bình Dương"), row("CN Dĩ An", "Bình Dương"), row("CN Biên Hòa", "Đồng Nai")]
        root, areas, branches = bot_admin.split_tree(rows)
        self.assertEqual(root, "Sao Việt")
        self.assertEqual(areas, ["Bình Dương", "Đồng Nai"])
        self.assertEqual([b["name"] for b in branches], ["CN Dĩ An", "CN Thuận An", "CN Biên Hòa"])

    def test_leaf_directly_under_root_is_not_a_branch(self):
        rows = [row("Sao Việt", None, 1), row("Lẻ", "Sao Việt")]
        self.assertEqual(bot_admin.split_tree(rows), ("Sao Việt", [], []))


class TestCourseValues(unittest.TestCase):
    def base(self, **extra):
        return {"product_name": " SQL cho phân tích dữ liệu ", "product_code": "lt-sql", "course_group": "Lập trình",
                **extra}

    def test_minimal_course_gets_defaults(self):
        values = bot_admin.course_values(self.base())
        self.assertEqual(values["product_name"], "SQL cho phân tích dữ liệu")
        self.assertEqual(values["product_code"], "LT-SQL")
        self.assertEqual(values["button_label"], "SQL cho phân tích dữ")  # cut to the 20-char button limit
        self.assertEqual(values["offer"], "all")
        self.assertEqual(values["standard_rate"], 0)
        self.assertEqual(values["faqs"], [])

    def test_missing_required_field_is_rejected(self):
        for key in ("product_name", "product_code", "course_group"):
            with self.assertRaises(ValueError):
                bot_admin.course_values(self.base(**{key: "  "}))

    def test_fee_accepts_vietnamese_thousands_separators(self):
        self.assertEqual(bot_admin.course_values(self.base(standard_rate="2.500.000đ"))["standard_rate"], 2500000)
        self.assertEqual(bot_admin.course_values(self.base(standard_rate=1800000))["standard_rate"], 1800000)

    def test_bad_ages_and_audience_are_rejected(self):
        with self.assertRaises(ValueError):
            bot_admin.course_values(self.base(min_age=40, max_age=18))
        with self.assertRaises(ValueError):
            bot_admin.course_values(self.base(audience="Người ngoài hành tinh"))

    def test_plain_description_becomes_escaped_paragraphs(self):
        values = bot_admin.course_values(self.base(description="Dòng một <b>\n\nDòng hai"))
        self.assertEqual(values["description"], "<p>Dòng một &lt;b&gt;</p><p>Dòng hai</p>")
        html = "<p>Đã là HTML</p>"
        self.assertEqual(bot_admin.course_values(self.base(description=html))["description"], html)

    def test_syllabus_and_faq_examples_accept_lists(self):
        values = bot_admin.course_values(self.base(
            syllabus=["SELECT", " JOIN ", ""],
            faqs=[{"question": "Cần biết lập trình không?", "examples": ["chưa biết code", "dân kế toán học được không"],
                   "answer": "Dạ không cần ạ."},
                  {"question": "", "answer": ""}]))
        self.assertEqual(values["syllabus"], "SELECT\nJOIN")
        self.assertEqual(values["faqs"], [{"question": "Cần biết lập trình không?",
                                           "examples": "chưa biết code\ndân kế toán học được không",
                                           "answer": "Dạ không cần ạ."}])

    def test_faq_without_answer_is_rejected(self):
        with self.assertRaises(ValueError):
            bot_admin.course_values(self.base(faqs=[{"question": "Học mấy buổi?", "answer": " "}]))


class TestImportSamples(unittest.TestCase):
    """The files shipped for demoing “Nhập từ file” are valid, new to the seeded catalog, and link real courses."""

    def test_samples_import_cleanly_on_top_of_the_seed(self):
        import json
        demo = APP_DIR / "mmm_custom" / "demo"
        seed = json.loads((demo / "saoviet" / "courses.json").read_text(encoding="utf-8"))
        groups = {g["group_name"] for g in json.loads((demo / "saoviet" / "course_groups.json").read_text(encoding="utf-8"))}
        seeded = {c["product_code"] for c in seed}
        samples = sorted((demo / "import-samples").glob("*.json"))
        self.assertEqual(len(samples), 2)
        for path in samples:
            data = json.loads(path.read_text(encoding="utf-8"))
            values = bot_admin.course_values(data)
            self.assertNotIn(values["product_code"], seeded, path.name)
            self.assertIn(values["course_group"], groups, path.name)
            self.assertTrue(set(data["next_courses"]) <= seeded, path.name)
            self.assertGreaterEqual(len(values["faqs"]), 2, path.name)


class TestAppLinks(unittest.TestCase):
    def test_chatwoot_url_for_managers_only(self):
        frappe = MagicMock()
        frappe.conf = {"chatwoot_base_url": "https://chat.example.vn/"}
        frappe.PermissionError = PermissionError
        frappe.throw.side_effect = lambda msg, exc=Exception: (_ for _ in ()).throw(exc(msg))
        with patch.object(bot_admin, "frappe", frappe):
            with patch.object(bot_admin, "can_open_bot", return_value=True):
                self.assertEqual(bot_admin.app_links(), {"chatwoot_url": "https://chat.example.vn"})
            with patch.object(bot_admin, "can_open_bot", return_value=False):
                with self.assertRaises(PermissionError):
                    bot_admin.app_links()


if __name__ == "__main__":
    unittest.main()
