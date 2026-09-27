import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeJev, FakeRepo, demo_catalog, fill, render

from mmm_custom.engine.combine import combine
from mmm_custom.engine.decide import Decision, decide
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.jev_questions import COURSE_FAQ, NONE, build_questions
from mmm_custom.engine.pipeline import parse_event, run_turn
from mmm_custom.engine.reply import compose
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding, understand

CAT = demo_catalog()
EXCEL = {"course": fill("VP-EXCEL")}


def incoming(text, message_id=5):
    return {"event": "message_created", "id": message_id, "content": text, "message_type": "incoming",
            "private": False, "sender": {"id": 9, "name": "Lan", "type": "contact"},
            "conversation": {"id": 7, "inbox_id": 3, "meta": {"sender": {"id": 9, "name": "Lan", "custom_attributes": {}}}}}


class TestQuestion(unittest.TestCase):
    def test_asked_for_the_known_course(self):
        q = build_questions(ConversationState("1", slots=EXCEL), Understanding(), CAT)[COURSE_FAQ]
        self.assertEqual(q["type"], "choice")
        self.assertIn("Excel từ cơ bản đến nâng cao", q["instructions"])
        self.assertEqual(list(q["criteria"]), ["0", "1", "2", "3", NONE])
        self.assertIn("VLOOKUP", q["criteria"]["1"])
        self.assertIn("có học vlookup không", q["criteria"]["1"])

    def test_asked_for_the_course_named_in_this_message(self):
        u = understand("excel có dạy vlookup không", ConversationState("1"), CAT)
        self.assertIn(COURSE_FAQ, build_questions(ConversationState("1"), u, CAT))

    def test_not_asked_without_a_course_or_without_faqs(self):
        self.assertNotIn(COURSE_FAQ, build_questions(ConversationState("1"), Understanding(), CAT))
        word = ConversationState("1", slots={"course": fill("VP-WORD")})
        self.assertNotIn(COURSE_FAQ, build_questions(word, Understanding(), CAT))


class TestCombine(unittest.TestCase):
    def setUp(self):
        self.state = ConversationState("1", slots=EXCEL)
        self.questions = build_questions(self.state, Understanding(), CAT)

    def test_confident_pick_is_answered(self):
        out = combine(Understanding(), {COURSE_FAQ: {"choice": "1", "confidence": 0.93}}, self.questions, self.state, CAT)
        self.assertEqual((out.faq["course"], out.faq["index"]), ("VP-EXCEL", 1))

    def test_unsure_pick_or_none_is_ignored(self):
        for answer in ({"choice": "1", "confidence": 0.7}, {"choice": NONE, "confidence": 0.99}):
            out = combine(Understanding(), {COURSE_FAQ: answer}, self.questions, self.state, CAT)
            self.assertEqual(out.faq, {})


class TestDecideAndCompose(unittest.TestCase):
    FAQ = {"course": "VP-EXCEL", "index": 1, "confidence": 0.93}

    def test_a_faq_alone_is_an_answer(self):
        d = decide(ConversationState("1", turns=1, slots=EXCEL), Understanding(faq=self.FAQ), CAT)
        self.assertEqual((d.type, d.faq, d.fallback), ("answer", self.FAQ, False))
        self.assertIn("VLOOKUP", d.reason)

    def test_the_course_answer_replaces_generic_template_answers(self):
        u = Understanding(faq=self.FAQ, skills=["beginner_ok", "fee_quote"])
        d = decide(ConversationState("1", turns=1, slots=EXCEL), u, CAT)
        self.assertEqual(d.skills, ["fee_quote"])

    def test_answered_after_handoff_too(self):
        state = ConversationState("1", turns=3, slots=EXCEL, status="handed_off")
        self.assertEqual(decide(state, Understanding(faq=self.FAQ), CAT).type, "answer")

    def test_reply_starts_with_the_stored_answer(self):
        d = Decision("answer", slots=EXCEL, faq=self.FAQ)
        r = compose(d, ConversationState("1"), CAT, render, FakeRepo(CAT))
        self.assertTrue(r.messages[0].startswith("Dạ có ạ. Khóa có riêng buổi hàm tra cứu"))
        self.assertIn({"skill": COURSE_FAQ, "variant": "1"}, r.variants)

    def test_answer_templates_see_the_course(self):
        d = Decision("answer", slots={"course": fill("VP-CB")}, faq={"course": "VP-CB", "index": 1, "confidence": 0.9})
        r = compose(d, ConversationState("1"), CAT, render, FakeRepo(CAT))
        self.assertIn("Word từ cơ bản đến nâng cao, Excel từ cơ bản đến nâng cao", r.messages[0])


class TestInTheTurn(unittest.TestCase):
    def test_customer_gets_the_course_answer(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        repo.jev = FakeJev({COURSE_FAQ: {"choice": "1", "confidence": 0.95}})
        repo.states["7"] = ConversationState("7", contact_id="9", turns=1, slots=EXCEL, pending={"slot": "branch"})
        run_turn(parse_event(incoming("khóa này có dạy hàm dò tìm không bạn")), repo, fx, render)
        self.assertIn("Khóa có riêng buổi hàm tra cứu", fx.of("send")[0]["messages"][0])
        self.assertIn("VLOOKUP", repo.logs[0]["reason"])


if __name__ == "__main__":
    unittest.main()
