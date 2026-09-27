import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, fill

from mmm_custom.engine import quiz
from mmm_custom.engine.decide import Decision
from mmm_custom.engine.pipeline import apply_quiz_results

CAT = demo_catalog()
CFG = CAT.skills["excel_quiz"].config


class TestQuiz(unittest.TestCase):
    def test_progress_round_trip_and_other_quiz(self):
        self.assertEqual(quiz.progress(quiz.encode("excel_quiz", [0, 3]), "excel_quiz"), [0, 3])
        self.assertEqual(quiz.progress("word_quiz:1", "excel_quiz"), [])
        self.assertEqual(quiz.progress("excel_quiz:x", "excel_quiz"), [])
        self.assertEqual(quiz.progress(None, "excel_quiz"), [])

    def test_score_and_bands(self):
        self.assertIsNone(quiz.result(CFG, [0, 1]))
        self.assertEqual(quiz.result(CFG, [0, 1, 0, 0, 0]), {"score": 5, "total": 5, "level": "advanced", "course": "QT-MOS-EXCEL"})
        self.assertEqual(quiz.result(CFG, [0, 1, 0, 0, 1])["level"], "basic")
        self.assertEqual(quiz.result(CFG, [3, 3, 3, 3, 3])["course"], "VP-EXCEL")

    def test_finished_quiz_fills_level_placement_and_course_of_the_same_group(self):
        d = Decision("answer", skills=["excel_quiz"],
                     slots={"quiz_progress": fill("excel_quiz:0,1,0,0,1"), "course": fill("VP-EXCEL")})
        apply_quiz_results(d, CAT)
        self.assertEqual((d.slots["level"]["value"], d.slots["placement"]["value"], d.slots["course"]["value"]),
                         ("basic", "Excel: 4/5 · Biết cơ bản", "VP-EXCEL-NC"))
        self.assertEqual(sorted(d.new_slots), ["course", "level", "placement"])

    def test_a_course_of_another_group_is_kept(self):
        d = Decision("answer", skills=["excel_quiz"],
                     slots={"quiz_progress": fill("excel_quiz:0,1,0,0,1"), "course": fill("DH-PTS")})
        apply_quiz_results(d, CAT)
        self.assertEqual(d.slots["course"]["value"], "DH-PTS")

    def test_unfinished_quiz_changes_nothing(self):
        d = Decision("answer", skills=["excel_quiz"], slots={"quiz_progress": fill("excel_quiz:0")})
        apply_quiz_results(d, CAT)
        self.assertEqual(set(d.slots), {"quiz_progress"})


if __name__ == "__main__":
    unittest.main()
