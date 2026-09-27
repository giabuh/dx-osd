import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from datetime import date

from engine_fixtures import FakeRepo, demo_catalog, fill, render

from mmm_custom.engine.actions import run_action
from mmm_custom.engine.context import base_context
from mmm_custom.engine.render import render_text
from mmm_custom.engine.reply import choose_template
from mmm_custom.engine.state import ConversationState

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
        self.assertEqual(quiz.result(CFG, [0, 1, 0, 0, 0]), {"score": 5, "total": 5, "level": "advanced",
                                                             "course": "QT-MOS-EXCEL", "missed": [], "stopped_early": False})
        res = quiz.result(CFG, [0, 1, 0, 0, 1])
        self.assertEqual((res["level"], res["missed"]), ("basic", ["Pivot Table"]))

    def test_easy_to_hard_and_filtered_by_goal(self):
        self.assertEqual([CFG["questions"][i]["level"] for i in quiz.order(CFG)[:5]],
                         ["basic", "basic", "intermediate", "intermediate", "advanced"])
        self.assertEqual(quiz.next_question(CFG, [0, 1, 0, 0])[1]["topic"], "Pivot Table")
        self.assertEqual(quiz.next_question(CFG, [0, 1, 0, 0], "certificate")[1]["topic"], "Data Validation")
        res = quiz.result(CFG, [0, 1, 0, 0, 1], "certificate")
        self.assertEqual(res["missed"], ["Data Validation"])

    def test_too_few_questions_for_a_goal_uses_them_all(self):
        cfg = {"max_questions": 2, "questions": [{"q": "a", "goals": ["hobby"]}, {"q": "b", "goals": ["office"]}]}
        self.assertEqual(quiz.order(cfg, "office"), [0, 1])

    def test_two_basic_questions_wrong_end_early(self):
        self.assertFalse(quiz.finished(CFG, [3]))
        res = quiz.result(CFG, [3, 3])
        self.assertEqual((res["score"], res["total"], res["level"], res["course"], res["stopped_early"]),
                         (0, 2, "beginner", "VP-EXCEL", True))
        self.assertEqual(res["missed"], ["Hàm SUM", "Địa chỉ tuyệt đối"])

    def test_praise_or_encouragement_follows_the_last_answer(self):
        self.assertIsNone(quiz.last_correct(CFG, []))
        self.assertTrue(quiz.last_correct(CFG, [0]))
        self.assertFalse(quiz.last_correct(CFG, [0, 0]))

    def test_d104_config_without_levels_keeps_its_order(self):
        cfg = {"questions": [{"q": "x", "options": ["a", "b"], "answer": 1},
                             {"q": "y", "options": ["a", "b"], "answer": 0}],
               "bands": [{"max": 1, "level": "basic"}, {"max": 2, "level": "advanced"}]}
        self.assertEqual(quiz.next_question(cfg, [1])[1]["q"], "y")
        self.assertEqual(quiz.result(cfg, [1, 0])["level"], "advanced")

    def test_survey_mode_adds_points(self):
        kids = CAT.skills["kids_quiz"].config
        self.assertIsNone(quiz.last_correct(kids, [2]))
        res = quiz.result(kids, [2, 1, 1, 2])
        self.assertEqual((res["score"], res["total"], res["course"], res["missed"]), (6, 8, "TE-ROBO", []))
        self.assertEqual(quiz.result(kids, [0, 0, 1, 0])["course"], "TE-THUD")

    def test_quiz_for_course_then_group(self):
        self.assertEqual(quiz.quiz_for(CAT.skills, course="KT-EXCEL"), "excel_quiz")
        self.assertEqual(quiz.quiz_for(CAT.skills, course="VP-WORD", group="Tin học văn phòng"), "word_quiz")
        self.assertEqual(quiz.quiz_for(CAT.skills, course="VP-CB", group="Tin học văn phòng"), "excel_quiz")
        self.assertEqual(quiz.quiz_for(CAT.skills, course="TE-PY", group="Tin học trẻ em"), "kids_quiz")
        self.assertEqual(quiz.quiz_for(CAT.skills, course="MKT-FB", group="Digital Marketing"), "")

    def test_every_demo_quiz_is_valid(self):
        codes, levels = set(CAT.courses), {"beginner", "basic", "advanced"}
        quizzes = [s for s in CAT.skills.values() if s.action == "level_quiz"]
        self.assertGreaterEqual(len(quizzes), 6)
        for s in quizzes:
            self.assertEqual(quiz.validate(s.config, codes, levels), [], s.key)

    def test_validate_reports_problems(self):
        bad = {"mode": "quiz", "questions": [{"q": "", "options": ["Một lựa chọn rất rất dài quá mức"], "answer": 3,
                                              "level": "hard"}],
               "bands": [{"max": 1, "level": "expert", "course": "NOPE"}]}
        errors = quiz.validate(bad, {"VP-EXCEL"}, {"basic"})
        self.assertEqual(len(errors), 7, errors)
        self.assertIn("Câu 1: mức độ không hợp lệ (hard).", errors)
        self.assertEqual(quiz.validate({"mode": "survey", "questions": [{"q": "a", "options": ["x", "y"], "points": [1]}],
                                        "bands": [{"max": 1, "level": "basic"}]}), ["Câu 1: cần điểm cho từng lựa chọn."])

    def test_finished_quiz_fills_level_placement_and_course_of_the_same_group(self):
        d = Decision("answer", skills=["excel_quiz"],
                     slots={"quiz_progress": fill("excel_quiz:0,1,0,0,1"), "course": fill("VP-EXCEL")})
        apply_quiz_results(d, CAT)
        self.assertEqual((d.slots["level"]["value"], d.slots["placement"]["value"], d.slots["course"]["value"]),
                         ("basic", "Excel: 4/5 · Biết cơ bản", "VP-EXCEL-NC"))
        self.assertEqual(sorted(d.new_slots), ["course", "level", "placement", "quiz_detail"])
        self.assertEqual((d.slots["quiz_detail"]["value"], d.quiz_done), ("Pivot Table", "excel_quiz"))

    def test_a_course_of_another_group_is_kept(self):
        d = Decision("answer", skills=["excel_quiz"],
                     slots={"quiz_progress": fill("excel_quiz:0,1,0,0,1"), "course": fill("DH-PTS")})
        apply_quiz_results(d, CAT)
        self.assertEqual(d.slots["course"]["value"], "DH-PTS")

    def test_unfinished_quiz_changes_nothing(self):
        d = Decision("answer", skills=["excel_quiz"], slots={"quiz_progress": fill("excel_quiz:0")})
        apply_quiz_results(d, CAT)
        self.assertEqual(set(d.slots), {"quiz_progress"})


def say(skill_key, progress, goal=""):
    """The quiz action's buttons and the customer-facing text for this progress."""
    slots = {"quiz_progress": fill(progress)}
    if goal:
        slots["goal"] = fill(goal)
    skill = CAT.skills[skill_key]
    ctx = base_context(slots, CAT, ConversationState("1", slots=slots))
    ctx.update(run_action(skill, ctx, slots, CAT, FakeRepo(CAT), date(2026, 9, 28)))
    return render_text(choose_template(skill, ctx, render).text, ctx, render), ctx


class TestQuizMessages(unittest.TestCase):
    def test_first_question_invites_gently(self):
        text, ctx = say("excel_quiz", "")
        self.assertTrue(text.startswith("Dạ em gửi anh/chị bài test Excel nhỏ 5 câu nhé ạ"), text)
        self.assertIn("Câu 1/5: Hàm nào tính tổng", text)
        self.assertEqual([b["title"] for b in ctx["_buttons"]], ["SUM", "COUNT", "AVERAGE", "MAX"])
        self.assertEqual(ctx["_buttons"][1]["action"]["value"], "excel_quiz:1")

    def test_praise_after_a_right_answer_and_comfort_after_a_wrong_one(self):
        text, ctx = say("excel_quiz", "excel_quiz:0")
        self.assertTrue(text.startswith("Dạ chính xác rồi ạ 👏 Câu 2/5 ạ:"), text)
        self.assertEqual(ctx["quiz"]["left"], 4)
        text, _ = say("excel_quiz", "excel_quiz:0,0")
        self.assertTrue(text.startswith("Dạ câu vừa rồi hơi khó, không sao đâu ạ. Câu 3/5 ạ:"), text)

    def test_result(self):
        text, ctx = say("excel_quiz", "excel_quiz:0,1,0,0,1")
        self.assertTrue(text.startswith("Dạ anh/chị làm đúng 4/5 câu, giỏi quá ạ 🎉"), text)
        self.assertIn("Biết cơ bản", text)
        self.assertIn("Excel nâng cao & Dashboard", text)
        self.assertEqual(ctx["quiz"]["missed_text"], "Pivot Table")
        text, _ = say("excel_quiz", "excel_quiz:3,3")
        self.assertIn("đúng 0/2 câu rồi ạ, em đã biết nên bắt đầu từ đâu", text)

    def test_every_demo_quiz_renders_without_banned_pronouns(self):
        from mmm_custom.engine import tone

        for key in [s.key for s in CAT.skills.values() if s.action == "level_quiz"]:
            cfg = CAT.skills[key].config
            answers = []
            while True:
                text, ctx = say(key, quiz.encode(key, answers))
                self.assertFalse(tone.BANNED.search(text), (key, text))
                if ctx["quiz"]["done"]:
                    break
                answers.append(0)
            self.assertLessEqual(len(answers), cfg["max_questions"], key)


if __name__ == "__main__":
    unittest.main()
