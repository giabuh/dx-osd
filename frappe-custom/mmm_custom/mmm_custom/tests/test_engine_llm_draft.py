"""D-115: a Gemini draft for staff only when the bot has no answer, checked by Jev and by code against the course
data, never sent to a customer."""

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import ROBO, FakeJev, FakeRepo, demo_catalog, fill, render

from mmm_custom import llm
from mmm_custom.engine import copilot, llm_draft
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import Event
from mmm_custom.engine.state import ConversationState

CAT = demo_catalog()
GOOD = {"answers_question": {"noul": 0.93}, "supported": {"noul": 0.9}, "unapproved_promise": {"noul": 0.05}}
DRAFT = "Dạ khóa Robotics cơ bản học trong 2 tháng, học phí 2.400.000đ ạ. Em kiểm tra thêm và báo ba mẹ ngay ạ."


def state(**kw):
    return ConversationState("2", turns=3, slots=dict(ROBO), **kw)


class TestChecks(unittest.TestCase):
    def setUp(self):
        self.facts = llm_draft.facts(state(), CAT)

    def test_facts_are_the_course_data(self):
        self.assertIn("Học phí: 2.400.000đ", self.facts)
        self.assertIn("Độ tuổi: 7–12 tuổi", self.facts)

    def test_numbers_must_come_from_the_data(self):
        self.assertTrue(llm_draft.numbers_ok(DRAFT, self.facts))
        self.assertFalse(llm_draft.numbers_ok("Dạ học phí chỉ 1.900.000đ ạ", self.facts), "an invented fee")
        self.assertFalse(llm_draft.numbers_ok("Dạ lớp học 3 buổi mỗi tuần ạ", self.facts), "an invented count")
        self.assertTrue(llm_draft.numbers_ok("Dạ bé 7 tuổi học được ạ", self.facts))

    def test_jev_must_accept_all_three(self):
        self.assertTrue(llm_draft.accepted(GOOD))
        self.assertFalse(llm_draft.accepted({**GOOD, "supported": {"noul": 0.6}}))
        self.assertFalse(llm_draft.accepted({**GOOD, "unapproved_promise": {"noul": 0.5}}))
        self.assertFalse(llm_draft.accepted({}))


class TestMake(unittest.TestCase):
    def test_a_checked_draft_becomes_a_note(self):
        generate, jev, s = MagicMock(return_value=DRAFT), FakeJev(GOOD), state()
        text, why, calls = llm_draft.make("bé học robot có cần mang máy không", s, CAT, jev, generate, now=100.0)
        self.assertEqual(why, "ok")
        self.assertTrue(text.startswith(llm_draft.HEADER))
        prompt, system = generate.call_args[0]
        self.assertIn("DỮ LIỆU KHÓA HỌC", prompt)
        self.assertIn("Robotics cơ bản", prompt)
        self.assertIn("không bịa", system)
        self.assertEqual(calls, [100.0])

    def test_rejected_by_jev_or_by_the_numbers(self):
        self.assertEqual(llm_draft.make("?", state(), CAT, FakeJev({**GOOD, "supported": {"noul": 0.2}}),
                                        lambda p, s: DRAFT)[1], "jev_rejected")
        jev = FakeJev(GOOD)
        self.assertEqual(llm_draft.make("?", state(), CAT, jev, lambda p, s: "Dạ giảm còn 999.000đ ạ")[1], "numbers")
        self.assertEqual(jev.calls, [], "Jev is not asked about a draft the numbers already rule out")
        self.assertEqual(llm_draft.make("?", state(), CAT, None, lambda p, s: DRAFT)[1], "no_jev")

    def test_budget_per_conversation_and_switch(self):
        self.assertEqual(llm_draft.make("?", state(), CAT, FakeJev(GOOD), lambda p, x: DRAFT, now=100.0,
                                        calls=[float(t) for t in range(6)])[1], "budget")
        self.assertEqual(llm_draft.make("?", state(), demo_catalog(llm_draft_disabled=1), FakeJev(GOOD),
                                        lambda p, x: DRAFT)[1], "budget")


class TestInAssistMode(unittest.TestCase):
    def setUp(self):
        self.repo, self.fx = FakeRepo(CAT), RecordingEffects()
        self.repo.jev = FakeJev(GOOD)
        self.repo.save_state(ConversationState("2", turns=3, slots=dict(ROBO), last_message_id=10, consultant_replied=True))

    def ask(self):
        with patch.object(llm, "api_key", return_value="k"), patch.object(llm, "generate", return_value=DRAFT):
            copilot.handle(Event("customer_message", "2", 11, "bên mình có gửi xe máy không em", {"id": 9}),
                           self.repo, self.fx, render)

    def test_staff_get_the_checked_draft_when_the_bot_has_no_answer(self):
        self.ask()
        self.assertTrue(self.fx.of("note")[0]["text"].startswith(llm_draft.HEADER))
        self.assertEqual(len(self.repo.states["2"].assist["llm_calls"]), 1)

    def test_also_once_everything_required_is_known(self):
        full = {**ROBO, "branch": fill("CN Dĩ An"), "phone": fill("+84399981234")}
        self.repo.save_state(ConversationState("2", turns=3, slots=full, last_message_id=10, consultant_replied=True))
        self.ask()
        self.assertTrue(self.fx.of("note")[0]["text"].startswith(llm_draft.HEADER),
                        "a question after the hand-off still gets a draft, not silence")

    def test_no_note_for_a_plain_ok_once_everything_required_is_known(self):
        full = {**ROBO, "branch": fill("CN Dĩ An"), "phone": fill("+84399981234")}
        self.repo.save_state(ConversationState("2", turns=3, slots=full, last_message_id=10, consultant_replied=True))
        copilot.handle(Event("customer_message", "2", 11, "ok em", {"id": 9}), self.repo, self.fx, render)
        self.assertEqual(self.fx.of("note"), [])

    def test_the_customer_never_gets_it(self):
        self.ask()
        self.repo.jev = FakeJev({})
        self.repo.clock += 5 * 60
        copilot.answer("2", self.repo, self.fx, render)
        sent = " ".join(m for s in self.fx.of("send") for m in s["messages"])
        self.assertNotIn("2.400.000", sent)
        self.assertIn("đã báo tư vấn viên", sent)


class TestGenerate(unittest.TestCase):
    def test_no_key_no_call(self):
        post = MagicMock()
        with patch.object(llm, "api_key", return_value=""):
            self.assertIsNone(llm.generate("x", post=post))
        post.assert_not_called()

    def test_text_of_the_first_candidate(self):
        resp = MagicMock()
        resp.json.return_value = {"candidates": [{"content": {"parts": [{"text": " Dạ vâng ạ \n"}]}}]}
        post = MagicMock(return_value=resp)
        with patch.object(llm, "api_key", return_value="k"):
            self.assertEqual(llm.generate("x", system="s", post=post), "Dạ vâng ạ")
        body = post.call_args.kwargs["json"]
        self.assertEqual((body["systemInstruction"]["parts"][0]["text"], post.call_args.kwargs["params"]), ("s", {"key": "k"}))


if __name__ == "__main__":
    unittest.main()
