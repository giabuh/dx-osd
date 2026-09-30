"""D-114: the staff reply library — capture helpers, retrieval, Jev's choice, and the demo seed."""

import sys
from collections import Counter
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeJev, FakeRepo, demo_catalog, fill, render

from mmm_custom.demo.loader import load_dataset
from mmm_custom.engine import draft, staff_replies as sr
from mmm_custom.engine.combine import combine
from mmm_custom.engine.context import base_context
from mmm_custom.engine.decide import decide
from mmm_custom.engine.jev_questions import STAFF_REPLY, build_questions
from mmm_custom.engine.pipeline import Event
from mmm_custom.engine.render import render_text
from mmm_custom.engine.reply import compose
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.tone import problems
from mmm_custom.engine.understand import understand

CAT = demo_catalog()
SEED = load_dataset()["staff_replies"]
KT = {"course": {**fill("KT-MISA"), "parent": "Kế toán"}}


class TestCaptureHelpers(unittest.TestCase):
    def test_mask_hides_phones_and_emails(self):
        self.assertEqual(sr.mask("gọi 0901 234 567 hoặc lan@gmail.com nhé"), "gọi [SĐT] hoặc [email] nhé")

    def test_fee_name_and_duration_become_placeholders(self):
        course = CAT.courses["KT-MISA"]
        template, unknown = sr.templatize("Dạ khóa Kế toán phần mềm MISA học 1 tháng, học phí 2.000.000đ, "
                                          "đi 2 người còn 1tr8 ạ", course)
        self.assertEqual(template, "Dạ khóa {{ course.name }} học {{ course.duration }}, học phí {{ course.fee | vnd }}, "
                                   "đi 2 người còn 1tr8 ạ")
        self.assertEqual(unknown, ["1tr8"], "an amount the course data does not explain is for a manager to check")

    def test_money_formats(self):
        for text, value in (("2.000.000đ", 2_000_000), ("1,5 triệu", 1_500_000), ("1tr8", 1_800_000), ("900k", 900_000)):
            self.assertEqual(sr.money_value(sr.MONEY_RE.search(text)), value, text)

    def test_how_the_draft_was_used(self):
        self.assertEqual(sr.outcome("Dạ học phí 2.000.000đ ạ", "Dạ học phí 2.000.000đ ạ"), "used")
        self.assertEqual(sr.outcome("Dạ học phí 2.000.000đ ạ", "Dạ học phí 2.000.000đ, đang giảm 10% ạ"), "edited")
        self.assertEqual(sr.outcome("Dạ học phí 2.000.000đ ạ", "Chị cho em xin số điện thoại nha"), "ignored")
        self.assertEqual(sr.outcome("", "bất kỳ"), "")

    def test_customer_turn_is_what_the_staff_message_answered(self):
        messages = [{"id": 1, "message_type": 1, "content": "Dạ em chào chị"},
                    {"id": 2, "message_type": 0, "content": "học misa bao lâu"},
                    {"id": 3, "message_type": 0, "content": "có tối không em"},
                    {"id": 4, "message_type": 1, "private": True, "content": "💡 Jev gợi ý (khóa X):\n\nDạ 1 tháng ạ."},
                    {"id": 5, "message_type": 1, "content": "Dạ 1 tháng, có ca tối ạ"}]
        self.assertEqual(sr.customer_turn(messages, 5), ("học misa bao lâu\ncó tối không em", "Dạ 1 tháng ạ.", "bot"))


class TestRetrieval(unittest.TestCase):
    def test_customers_get_approved_replies_of_their_course_only(self):
        course = CAT.courses["KT-MISA"]
        found = sr.candidates(CAT, "học phí misa bao nhiêu", course)
        self.assertTrue(found)
        self.assertTrue(all(r.approved for r in found))
        self.assertTrue(all(r.course in ("KT-MISA", "") for r in found))
        self.assertLessEqual(len(found), sr.MAX_CANDIDATES)
        self.assertEqual(found[0].topic, "fee_quote")

    def test_drafts_may_use_new_replies(self):
        course = CAT.courses["KT-MISA"]
        approved = {r.name for r in sr.candidates(CAT, "học phí misa bao nhiêu", course, limit=100)}
        drafting = {r.name for r in sr.candidates(CAT, "học phí misa bao nhiêu", course, drafting=True, limit=100)}
        self.assertTrue(approved < drafting)

    def test_without_a_course_only_replies_that_need_none(self):
        found = sr.candidates(CAT, "trung tâm ở đâu vậy em", None, limit=100)
        self.assertTrue(found)
        self.assertTrue(all(not r.course and "course." not in r.reply for r in found))


class TestJevChoosesAStaffReply(unittest.TestCase):
    def setUp(self):
        self.state = ConversationState("1", turns=2, slots=dict(KT))
        self.text = "học misa thì trả góp được không em"
        self.u = understand(self.text, self.state, CAT)
        self.questions = build_questions(self.state, self.u, CAT, text=self.text)

    def pick(self, topic):
        return next(k for k in self.questions[STAFF_REPLY]["criteria"] if k.startswith(f"kt-misa-{topic}"))

    def test_asked_with_the_similar_replies(self):
        criteria = self.questions[STAFF_REPLY]["criteria"]
        self.assertIn("none", criteria)
        self.assertIn("staff answered", criteria[self.pick("payment")])

    def test_confident_pick_is_answered_with_the_staff_wording(self):
        name = self.pick("payment")
        out = combine(self.u, {STAFF_REPLY: {"choice": name, "confidence": 0.93}}, self.questions, self.state, CAT)
        self.assertEqual(out.staff_reply["name"], name)
        d = decide(self.state, out, CAT)
        self.assertEqual((d.type, d.staff_reply["name"]), ("answer", name))
        text = " ".join(compose(d, self.state, CAT, render).messages)
        self.assertIn("2 đợt", text)

    def test_an_unsure_pick_is_ignored(self):
        out = combine(self.u, {STAFF_REPLY: {"choice": self.pick("payment"), "confidence": 0.7}}, self.questions,
                      self.state, CAT)
        self.assertEqual(out.staff_reply, {})

    def test_the_draft_names_its_source(self):
        repo = FakeRepo(CAT)
        repo.save_state(ConversationState("2", turns=2, slots=dict(KT)))
        repo.jev = FakeJev(lambda q: {STAFF_REPLY: {"choice": next(k for k in q[STAFF_REPLY]["criteria"]
                                                                   if k.startswith("kt-misa-fee_quote")),
                                                    "confidence": 0.95}})
        turn = draft.draft_turn(Event("customer_message", "2", 9, "học phí misa bao nhiêu vậy em", {"id": 1}), repo, render)
        note = draft.note(turn, CAT)
        self.assertIn("câu trả lời NV", note)
        self.assertIn("2.000.000", note)


class TestSeed(unittest.TestCase):
    def test_large_and_about_the_asked_groups(self):
        groups = Counter(r["course_group"] for r in SEED)
        self.assertGreaterEqual(len(SEED), 350)
        for group in ("Kế toán", "Tin học trẻ em", "Tin học văn phòng"):
            self.assertGreaterEqual(groups[group], 80, group)
        self.assertGreaterEqual(sum("ROBO" in r["course"] for r in SEED), 30)
        self.assertEqual(len({r["seed_id"] for r in SEED}), len(SEED))
        self.assertTrue(any(r["status"] == "new" for r in SEED), "a review queue to try the approval screen")

    def test_every_reply_renders_with_the_course_data_in_the_house_tone(self):
        for r in SEED:
            course = CAT.courses.get(r["course"]) if r["course"] else next(
                (c for c in CAT.courses.values() if c.group == r["course_group"]), None) if r["course_group"] else None
            if r["course"]:
                self.assertIsNotNone(course, r["seed_id"])
            slots = {"course": fill(course.code)} if course else {}
            text = render_text(r["reply"], base_context(slots, CAT, ConversationState("1")), render)
            self.assertNotIn("{", text, r["seed_id"])
            self.assertEqual(problems(r["reply"]), [], r["seed_id"])
            self.assertEqual(sr.templatize(text, course)[1] if course else [], [], f"{r['seed_id']}: hard-coded fee")


if __name__ == "__main__":
    unittest.main()
