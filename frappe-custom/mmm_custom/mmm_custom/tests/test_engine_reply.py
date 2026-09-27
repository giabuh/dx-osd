import sys
from datetime import date
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, fill, promo, render, schedule

from mmm_custom.engine.decide import Decision, decide
from mmm_custom.engine.reply import Reply, add_buttons, compose, split_messages
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding

CAT = demo_catalog()


class TestCompose(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo(CAT)

    def compose(self, decision, state=None):
        return compose(decision, state or ConversationState("1"), CAT, render, self.repo, self.repo.today())

    def test_fee_answer_with_promotion_then_next_question_and_its_buttons(self):
        self.repo.promotions = [promo("Tất cả -10%")]
        d = decide(ConversationState("1", turns=1),
                   Understanding(fills={"course": fill("VP-EXCEL")}, skills=["fee_quote"]), CAT)
        r = self.compose(d)
        self.assertEqual(len(r.messages), 1)
        self.assertIn("Dạ khóa Excel từ cơ bản đến nâng cao học phí 1.800.000đ, đang ưu đãi còn 1.620.000đ ạ.",
                      r.messages[0])
        self.assertTrue(r.messages[0].endswith("Anh/chị muốn học ở chi nhánh nào ạ?"))
        self.assertEqual([b["title"] for b in r.buttons], ["TP.HCM", "Bình Dương", "Đồng Nai", "Vũng Tàu"])
        self.assertEqual(r.variants, [{"skill": "fee_quote", "variant": "default"}])

    def test_course_content_answers_from_the_course_knowledge(self):
        d = Decision("answer", slots={"course": fill("VP-EXCEL")}, skills=["course_content"])
        r = self.compose(d)
        self.assertEqual(r.variants, [{"skill": "course_content", "variant": "knowledge"}])
        self.assertIn("Excel từ con số 0", r.messages[0])
        self.assertIn("\n• Hàm tra cứu: VLOOKUP, XLOOKUP, INDEX–MATCH", r.messages[0])

    def test_course_content_without_knowledge_keeps_the_short_answer(self):
        d = Decision("answer", slots={"course": fill("VP-WORD")}, skills=["course_content"])
        self.assertEqual(self.compose(d).variants, [{"skill": "course_content", "variant": "default"}])

    def test_schedule_variants(self):
        d = Decision("answer", slots={"course": fill("VP-EXCEL")}, skills=["schedule_lookup"])
        self.assertEqual(self.compose(d).variants[0]["variant"], "none")
        self.repo.schedules = [schedule("VP-EXCEL", "CN Dĩ An", date(2026, 10, 6))]
        r = self.compose(d)
        self.assertIn("• Thứ 3, 06/10 (T3, T5, T7, Tối 17:00–21:00) tại CN Dĩ An", r.messages[0])

    def test_follow_ups_when_nothing_is_asked(self):
        d = Decision("answer", slots={"course": fill("VP-EXCEL")}, skills=["fee_quote"])
        r = self.compose(d)
        self.assertEqual([b["title"] for b in r.buttons], ["Xem lịch khai giảng", "Đăng ký tư vấn"])
        self.assertEqual(r.options()["Đăng ký tư vấn"], {"type": "handoff"})

    def test_recommendation_buttons_win(self):
        d = Decision("answer", slots={"learner": fill("child")}, skills=["course_advisor"], ask="branch")
        r = self.compose(d)
        self.assertEqual([b["action"]["slot"] for b in r.buttons], ["course", "course", "course"])

    def test_missing_course_uses_fallback_and_records_error(self):
        d = Decision("answer", slots={}, skills=["duration"])
        r = self.compose(d)
        self.assertEqual(r.errors[0]["type"], "render_error")
        self.assertIn("chưa hiểu ý", r.messages[0])
        self.assertFalse(any("{{" in m or "{%" in m for m in r.messages))

    def test_greeting_first(self):
        d = decide(ConversationState("1"), Understanding(), CAT)
        self.assertIn("Trợ lý Sao Việt của Tin Học Sao Việt", self.compose(d).messages[0])

    def test_silent_sends_nothing(self):
        r = self.compose(Decision("silent"))
        self.assertEqual((r.messages, r.buttons), ([], []))


class TestLimits(unittest.TestCase):
    def test_buttons_are_unique_capped_and_truncated(self):
        r = Reply()
        many = [{"title": "Một tiêu đề rất rất dài quá mức", "action": {}}] * 2
        many += [{"title": f"Nút {i}", "action": {}} for i in range(20)]
        add_buttons(r, many)
        titles = [b["title"] for b in r.buttons]
        self.assertEqual(len(titles), 13)
        self.assertEqual(len(set(titles)), 13)
        self.assertTrue(all(len(t) <= 20 for t in titles))

    def test_long_reply_is_split(self):
        self.assertEqual([len(m) for m in split_messages(["a" * 1500, "b" * 1500])], [1500, 1500])
        self.assertEqual([len(m) for m in split_messages(["c" * 4500])], [2000, 2000, 500])
        self.assertEqual(split_messages(["x", "", "y"]), ["x\n\ny"])


if __name__ == "__main__":
    unittest.main()
