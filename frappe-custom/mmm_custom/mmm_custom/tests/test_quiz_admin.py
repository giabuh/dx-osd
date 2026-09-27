import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog

from mmm_custom import quiz_admin

CAT = demo_catalog()
CODES = set(CAT.courses)
LEVELS = ("beginner", "basic", "advanced")


def editor_config(**kw):
    return {"subject": " Word ", "mode": "test", "courses": ["VP-WORD", ""], "groups": [], "max_questions": "3",
            "stop_after_wrong": "2",
            "questions": [{"q": " Phím in đậm? ", "options": ["Ctrl + B", "", "Ctrl + I"], "answer": "2",
                           "level": "basic", "topic": "", "goals": ["office", ""]},
                          {"q": "Mục lục?", "options": ["Heading", "Tô màu"], "answer": 0, "level": "intermediate"}],
            "bands": [{"max": "2", "level": "advanced", "course": "QT-MOS-WORD"},
                      {"max": 1, "level": "basic", "course": "VP-WORD"}], **kw}


class TestNormalize(unittest.TestCase):
    def test_cleans_what_the_editor_sends(self):
        cfg = quiz_admin.normalize(editor_config())
        self.assertEqual(cfg["subject"], "Word")
        self.assertEqual(cfg["courses"], ["VP-WORD"])
        self.assertEqual((cfg["max_questions"], cfg["stop_after_wrong"]), (3, 2))
        self.assertEqual(cfg["questions"][0], {"q": "Phím in đậm?", "options": ["Ctrl + B", "Ctrl + I"], "answer": 1,
                                               "level": "basic", "goals": ["office"]})
        self.assertEqual([b["max"] for b in cfg["bands"]], [1, 2])

    def test_the_answer_on_an_empty_option_is_lost(self):
        cfg = quiz_admin.normalize(editor_config(questions=[{"q": "x", "options": ["a", "", "c"], "answer": 1}]))
        self.assertEqual(cfg["questions"][0]["answer"], -1)
        self.assertIn("Câu 1: chọn đáp án đúng.", quiz_admin.problems(cfg, {}, CODES, LEVELS))

    def test_survey_keeps_points_and_no_early_stop(self):
        cfg = quiz_admin.normalize(editor_config(mode="survey", questions=[
            {"q": "Bé dùng chuột?", "options": ["Chưa", "", "Rồi"], "points": ["0", "5", "2"]}]))
        self.assertEqual(cfg["questions"][0], {"q": "Bé dùng chuột?", "options": ["Chưa", "Rồi"], "points": [0, 2]})
        self.assertNotIn("stop_after_wrong", cfg)

    def test_demo_quizzes_survive_a_round_trip(self):
        for skill in (s for s in CAT.skills.values() if s.action == "level_quiz"):
            again = quiz_admin.normalize(skill.config)
            for key in ("questions", "bands", "mode", "courses", "groups"):
                self.assertEqual(again[key], {**{"mode": "test"}, **skill.config}[key], (skill.key, key))


class TestProblems(unittest.TestCase):
    def test_fine(self):
        cfg = quiz_admin.normalize(editor_config())
        self.assertEqual(quiz_admin.problems(cfg, quiz_admin.DEFAULT_TEMPLATES, CODES, LEVELS), [])

    def test_reports_subject_scope_and_tone(self):
        cfg = quiz_admin.normalize(editor_config(subject="", courses=[]))
        errors = quiz_admin.problems(cfg, {"start": "Bạn làm bài test nhé", "result": "Dạ xong rồi ạ"}, CODES, LEVELS)
        self.assertIn("Nhập tên môn của bài test (ví dụ Excel).", errors)
        self.assertTrue(any(e.startswith("Chọn ít nhất một khóa") for e in errors))
        self.assertTrue(any(e.startswith("Câu mở đầu (câu 1): ") for e in errors), errors)
        self.assertFalse(any(e.startswith("Báo kết quả") for e in errors), errors)

    def test_default_templates_keep_the_house_tone(self):
        from mmm_custom.engine import tone

        for key, text in quiz_admin.DEFAULT_TEMPLATES.items():
            self.assertEqual(tone.problems(text), [], key)


class TestKeysAndFunnel(unittest.TestCase):
    def test_new_key(self):
        self.assertEqual(quiz_admin.new_key("Tin học cho bé", set()), "tin_hoc_cho_be_quiz")
        self.assertEqual(quiz_admin.new_key("Excel", {"excel_quiz"}), "excel_quiz_2")
        self.assertEqual(quiz_admin.new_key("!!", set()), "level_quiz")

    def test_funnel(self):
        rows = [
            {"quiz": "excel_quiz", "lead": "L1", "status": "done", "offered_at": 1, "started_at": 1, "phone_after": 1},
            {"quiz": "excel_quiz", "lead": "L2", "status": "done", "offered_at": None, "started_at": 1,
             "phone_after": 0, "reminded_at": 1},
            {"quiz": "excel_quiz", "lead": "L3", "status": "declined", "offered_at": 1},
            {"quiz": "excel_quiz", "lead": "", "status": "started", "offered_at": 1, "started_at": 1, "reminded_at": 1},
            {"quiz": "kids_quiz", "lead": "L4", "status": "offered", "offered_at": 1},
        ]
        out = quiz_admin.funnel(rows, {"L1"})
        self.assertEqual(out["excel_quiz"], {"offered": 3, "started": 3, "done": 2, "phone": 1, "enrolled": 1,
                                             "declined": 1, "reminded": 2, "recovered": 1})
        self.assertEqual(out["kids_quiz"]["offered"], 1)


if __name__ == "__main__":
    unittest.main()
