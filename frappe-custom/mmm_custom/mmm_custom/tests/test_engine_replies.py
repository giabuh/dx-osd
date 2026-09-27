"""D-107: typed answers to the bot's own question, names, phone numbers with a digit missing, a quiz that
survives side questions, and one focus per reply."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, fill, render

from mmm_custom.engine import offers, quiz
from mmm_custom.engine.combine import combine
from mmm_custom.engine.decide import decide
from mmm_custom.engine.jev_questions import REPLY_TO_BOT, build_questions
from mmm_custom.engine.reply import compose
from mmm_custom.engine.reply_match import match_pending, yes_no
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.text import extract_name, find_phone_candidate
from mmm_custom.engine.understand import Understanding, understand

CAT = demo_catalog()
KNOWN = {"course": {**fill("VP-EXCEL"), "parent": "Tin học văn phòng"}, "branch": fill("CN Dĩ An")}


def quiz_buttons(answers=()):
    ctx_slots = {"quiz_progress": fill(quiz.encode("excel_quiz", list(answers)))}
    _, q = quiz.next_question(CAT.skills["excel_quiz"].config, list(answers))
    return {o: {"type": "slot", "slot": "quiz_progress", "skill": "excel_quiz",
                "value": quiz.encode("excel_quiz", list(answers) + [i])} for i, o in enumerate(q["options"])}, ctx_slots


def quiz_state(answers=(0,), **kw):
    options, slots = quiz_buttons(answers)
    return ConversationState("1", turns=4, slots={**KNOWN, **slots}, offers={"excel_quiz": "started"},
                             pending={"slot": "", "options": options, **kw})


TRIAL = {"T7 03/10 Tối": {"type": "slot", "slot": "trial_class", "value": "Excel · Thứ 7, 03/10 · Tối", "skill": "trial_booked"},
         "T3 06/10 Tối": {"type": "slot", "slot": "trial_class", "value": "Excel · Thứ 3, 06/10 · Tối", "skill": "trial_booked"},
         "T3 06/10 Sáng": {"type": "slot", "slot": "trial_class", "value": "Excel · Thứ 3, 06/10 · Sáng", "skill": "trial_booked"}}


class TestMatchPending(unittest.TestCase):
    def test_quiz_answers_typed_any_way(self):
        options, _ = quiz_buttons([0, 1, 0])
        for text, value in (("countif", "excel_quiz:0,1,0,0"), ("SUMIF", "excel_quiz:0,1,0,1"), ("b", "excel_quiz:0,1,0,1"),
                            ("câu C", "excel_quiz:0,1,0,2"), ("đáp án 4", "excel_quiz:0,1,0,3"),
                            ("chắc là countif", "excel_quiz:0,1,0,0")):
            self.assertEqual(match_pending(text, {"options": options})["value"], value, text)
        self.assertIsNone(match_pending("học buổi tối được không", {"options": options}))
        self.assertIsNone(match_pending("e", {"options": options}))
        self.assertEqual(match_pending("thôi không làm nữa", {"options": options}),
                         {"type": "offer_decline", "skill": "excel_quiz"})

    def test_offer_answered_in_words(self):
        options = {b["title"]: b["action"] for b in offers.buttons("excel_quiz")}
        for text in ("ok", "Ok em", "được", "làm thử", "làm luôn nhé"):
            self.assertEqual(match_pending(text, {"options": options})["type"], "skill", text)
        for text in ("thôi", "để sau nhé", "không", "chưa cần"):
            self.assertEqual(match_pending(text, {"options": options})["type"], "offer_decline", text)
        self.assertIsNone(match_pending("học phí bao nhiêu", {"options": options}))

    def test_trial_date_typed(self):
        pending = {"options": TRIAL}
        self.assertEqual(match_pending("học thử thứ 7 ngày 3/10", pending)["value"], "Excel · Thứ 7, 03/10 · Tối")
        self.assertEqual(match_pending("t3 buổi sáng", pending)["value"], "Excel · Thứ 3, 06/10 · Sáng")
        self.assertEqual(match_pending("thứ bảy", pending)["value"], "Excel · Thứ 7, 03/10 · Tối")
        self.assertIsNone(match_pending("ngày 6", pending))  # two classes that day: let the customer choose
        self.assertIsNone(match_pending("chủ nhật được không", pending))

    def test_yes_no(self):
        self.assertTrue(yes_no("ok a"))
        self.assertFalse(yes_no("thoi de sau"))
        self.assertIsNone(yes_no("hoc phi bao nhieu"))


class TestNamesAndPhones(unittest.TestCase):
    def test_names(self):
        cases = [("mình tên Hùng", False, "Hùng"), ("tên em là nguyễn văn an ạ", False, "Nguyễn Văn An"),
                 ("anh tên Bảo, sđt 0901234567", False, "Bảo"), ("Hùng", True, "Hùng"), ("dạ chị Mai", True, "Mai"),
                 ("em là Lan nhé", True, "Lan"), ("$A$1", True, None), ("0901234567", True, None), ("ok", True, None),
                 ("học buổi tối được không", True, None), ("con tên là Bin", False, None), ("Hùng", False, None)]
        for text, asked, name in cases:
            self.assertEqual(extract_name(text, asked), name, text)

    def test_name_is_heard_anywhere(self):
        u = understand("mình tên Hùng nhé", ConversationState("1", slots=KNOWN, pending={"slot": "learner"}), CAT)
        self.assertEqual(u.fills["customer_name"]["value"], "Hùng")

    def test_phone_with_a_digit_missing(self):
        self.assertEqual(find_phone_candidate("ok số điện thoại tôi là 039182384"), "039182384")
        self.assertIsNone(find_phone_candidate("0391823845"))
        self.assertIsNone(find_phone_candidate("học phí 180000000 đồng"))
        s = ConversationState("1", turns=3, slots=KNOWN, pending={"slot": "phone"})
        u = understand("ok số điện thoại tôi là 039182384", s, CAT)
        d = decide(s, u, CAT)
        self.assertEqual((d.phone_check, d.ask, d.skills, d.fallback), ("039182384", "phone", [], False))
        r = compose(d, s, CAT, render)
        self.assertEqual(r.messages, ["Dạ số 039182384 hình như chưa đủ 10 số, anh/chị kiểm tra lại giúp em nhé ạ."])

    def test_the_customers_number_is_not_a_hotline_question(self):
        s = ConversationState("1", turns=3, slots=KNOWN)
        self.assertNotIn("hotline", decide(s, understand("sđt của em là 0901234567", s, CAT), CAT).skills)
        self.assertIn("hotline", decide(s, understand("cho em xin số điện thoại trung tâm", s, CAT), CAT).skills)

    def test_ok_to_a_question_asks_it_again_kindly(self):
        s = ConversationState("1", turns=3, slots=KNOWN, pending={"slot": "phone"}, stuck_turns=1)
        d = decide(s, understand("ok", s, CAT), CAT)
        self.assertEqual((d.type, d.ask, d.fallback, d.stuck_turns), ("ask_slot", "phone", False, 0))


class TestQuizSurvivesSideQuestions(unittest.TestCase):
    def test_side_question_then_back_to_the_same_question(self):
        s = quiz_state()
        u = understand("học buổi tối được không", s, CAT)
        d = decide(s, u, CAT)
        self.assertEqual((d.resume, d.skills[-1], d.ask, d.unclear), ("excel_quiz", "excel_quiz", "", False))
        r = compose(d, s, CAT, render, FakeRepo(CAT))
        self.assertTrue(r.messages[-1].startswith("Dạ em ghi nhận rồi ạ, anh/chị làm tiếp bài test giúp em nhé. Câu 2/5 ạ:"),
                        r.messages)
        self.assertNotIn("chính xác", " ".join(r.messages))
        self.assertEqual([b["title"] for b in r.buttons], ["A1", "$A$1", "#A1", "A:1"])

    def test_an_answer_that_is_not_a_button(self):
        s = quiz_state()
        d = decide(s, understand("không biết nữa", s, CAT), CAT)
        self.assertTrue(d.unclear)
        r = compose(d, s, CAT, render, FakeRepo(CAT))
        self.assertTrue(r.messages[-1].startswith("Dạ anh/chị chọn giúp em một đáp án bên dưới nhé ạ. Câu 2/5"))

    def test_let_go_after_two_side_questions(self):
        s = quiz_state(resumes=2)
        d = decide(s, understand("học buổi tối được không", s, CAT), CAT)
        self.assertEqual(d.resume, "")

    def test_praise_only_for_an_answer_given_now(self):
        s = quiz_state()
        d = decide(s, understand("$A$1", s, CAT), CAT)
        r = compose(d, s, CAT, render, FakeRepo(CAT))
        self.assertTrue(r.messages[-1].startswith("Dạ chính xác rồi ạ 👏 Câu 3/5"), r.messages)


class TestOneFocus(unittest.TestCase):
    def test_parent_question_that_jev_reads_as_three_skills(self):
        s = ConversationState("1", turns=1)
        u = Understanding(skills=["kids_courses", "course_advisor", "kids_quiz"], fills={"learner": fill("child")},
                          parents={"course": "Tin học trẻ em"})
        d = decide(s, u, CAT)
        self.assertEqual((d.skills, d.offer), (["kids_courses"], ""))
        r = compose(d, s, CAT, render, FakeRepo(CAT))
        self.assertEqual(sum("các khóa phù hợp" in m.lower() for m in r.messages), 1)
        self.assertEqual([b["title"] for b in r.buttons], ["Tin học cho bé", "Scratch", "Python cho bé"])

    def test_a_test_asked_with_another_question_is_offered_after_the_answer(self):
        s = ConversationState("1", turns=1, slots=KNOWN)
        d = decide(s, Understanding(skills=["fee_quote", "excel_quiz"]), CAT)
        self.assertEqual((d.skills, d.offer), (["fee_quote"], "excel_quiz"))

    def test_no_offer_over_trial_buttons(self):
        s = ConversationState("1", turns=2, slots=KNOWN)
        d = decide(s, Understanding(skills=["trial_class"]), CAT)
        self.assertEqual(d.offer, "")


class TestJevReplyToBot(unittest.TestCase):
    def test_asked_only_with_buttons_and_applied_when_confident(self):
        s = ConversationState("1", turns=2, slots=KNOWN, pending={"slot": "", "options": TRIAL})
        u = understand("cho em buổi đầu tiên nha", s, CAT)
        questions = build_questions(s, u, CAT)
        self.assertEqual(list(questions[REPLY_TO_BOT]["criteria"])[:3], ["0", "1", "2"])
        out = combine(u, {REPLY_TO_BOT: {"choice": "0", "confidence": 0.9}}, questions, s, CAT)
        self.assertEqual(out.fills["trial_class"]["value"], "Excel · Thứ 7, 03/10 · Tối")
        low = combine(u, {REPLY_TO_BOT: {"choice": "0", "confidence": 0.4}}, questions, s, CAT)
        self.assertNotIn("trial_class", low.fills)
        self.assertNotIn(REPLY_TO_BOT, build_questions(ConversationState("1", slots=KNOWN), Understanding(), CAT))


class TestLessonFor(unittest.TestCase):
    def test_where_the_course_teaches_a_missed_topic(self):
        syllabus = CAT.courses["VP-EXCEL-NC"].syllabus
        self.assertEqual(quiz.lesson_for(["Pivot Table"], syllabus), {"topic": "Pivot Table", "lesson": "Pivot Table nâng cao, Slicer"})
        self.assertIsNone(quiz.lesson_for(["Hàm SUM"], ()))


if __name__ == "__main__":
    unittest.main()
