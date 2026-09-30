"""D-110: questions about a course's own data (content, length, audience, next course) are answered from that
data, and the staff suggestion is the bot's own draft, never a canned template."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import ROBO, FakeJev, FakeRepo, demo_catalog, event, fill, render

from mmm_custom.engine import draft
from mmm_custom.engine.combine import combine
from mmm_custom.engine.decide import decide
from mmm_custom.engine.jev_questions import COURSE_FACT, COURSE_FAQ, NONE, build_questions
from mmm_custom.engine.pipeline import parse_event, run_turn
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.reply import compose
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding, understand

CAT = demo_catalog()



class TestQuestion(unittest.TestCase):
    def test_asked_with_the_parts_the_course_has_data_for(self):
        q = build_questions(ConversationState("1", slots=ROBO), Understanding(), CAT)[COURSE_FACT]
        self.assertIn("Robotics cơ bản", q["instructions"])
        self.assertEqual(list(q["criteria"]), ["summary", "syllabus", "duration", "audience", "next", NONE])

    def test_not_asked_without_a_course(self):
        self.assertNotIn(COURSE_FACT, build_questions(ConversationState("1"), Understanding(), CAT))


class TestCombineAndDecide(unittest.TestCase):
    def setUp(self):
        self.state = ConversationState("1", turns=2, slots=ROBO)
        self.u = understand("bé học bao lâu vậy em", self.state, CAT)
        self.questions = build_questions(self.state, self.u, CAT)

    def test_confident_fact_is_answered_from_the_course_data(self):
        out = combine(self.u, {COURSE_FACT: {"choice": "duration", "confidence": 0.93}}, self.questions, self.state, CAT)
        self.assertEqual(out.fact, {"course": "TE-ROBO", "fact": "duration", "confidence": 0.93})
        d = decide(self.state, out, CAT)
        self.assertEqual((d.type, d.fact["fact"], d.fallback, d.stuck_turns), ("answer", "duration", False, 0))
        self.assertIn("thời lượng khóa Robotics cơ bản", d.reason)
        text = " ".join(compose(d, self.state, CAT, render).messages)
        self.assertIn("Robotics cơ bản học trong 2 tháng", text)

    def test_unsure_fact_is_ignored(self):
        out = combine(self.u, {COURSE_FACT: {"choice": "duration", "confidence": 0.6}}, self.questions, self.state, CAT)
        self.assertEqual(out.fact, {})

    def test_a_matching_faq_wins_over_a_fact(self):
        excel = ConversationState("1", turns=2, slots={"course": fill("VP-EXCEL")})
        questions = build_questions(excel, Understanding(), CAT)
        out = combine(Understanding(), {COURSE_FAQ: {"choice": "1", "confidence": 0.95},
                                        COURSE_FACT: {"choice": "syllabus", "confidence": 0.95}}, questions, excel, CAT)
        d = decide(excel, out, CAT)
        self.assertEqual((d.faq["index"], d.fact), (1, {}))

    def test_syllabus_lists_the_lessons(self):
        d = decide(self.state, Understanding(fact={"course": "TE-ROBO", "fact": "syllabus", "confidence": 0.95}), CAT)
        text = " ".join(compose(d, self.state, CAT, render).messages)
        self.assertIn("• " + CAT.courses["TE-ROBO"].syllabus[0], text)


class TestDraft(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo(CAT)
        state = ConversationState("2", turns=4, status="handed_off", consultant_replied=True, slots=dict(ROBO),
                                  last_message_id=10)
        self.repo.save_state(state)

    def test_drafts_from_the_course_data_after_a_person_wrote_and_writes_nothing(self):
        self.repo.jev = FakeJev({COURSE_FACT: {"choice": "duration", "confidence": 0.95}})
        turn = draft.draft_turn(event("khóa này kéo dài mấy tuần vậy em"), self.repo, render)
        text = draft.note(turn, CAT)
        self.assertTrue(text.startswith("💡 Jev gợi ý (khóa Robotics cơ bản; dựa trên: thời lượng khóa Robotics cơ bản, "
                                        "hỏi chi nhánh)"))
        self.assertIn("học trong 2 tháng", text)
        self.assertIn("Nút gợi ý: TP.HCM", text)
        saved = self.repo.states["2"]
        self.assertEqual((saved.turns, saved.consultant_replied, saved.last_message_id), (4, True, 10))
        self.assertEqual(self.repo.logs, [])

    def test_a_draft_never_hands_off(self):
        self.repo.states["2"].status = "active"
        self.repo.jev = FakeJev({"wants_human": {"noul": 0.95}})
        turn = draft.draft_turn(event("cho mình nói chuyện với tư vấn viên đi"), self.repo, render)
        self.assertNotEqual(turn.decision.type, "handoff")
        self.assertEqual(draft.note(turn, CAT), "👤 Khách cần tư vấn viên (gặp tư vấn viên). Bạn trả lời giúp nhé.")

    def test_a_question_the_bot_cannot_answer_says_so(self):
        self.repo.jev = FakeJev({})
        turn = draft.draft_turn(event("bên mình có gửi xe máy không"), self.repo, render)
        self.assertEqual(draft.note(turn, CAT), draft.NO_KNOWLEDGE)

    def test_a_closed_conversation_gives_no_note(self):
        self.repo.states["2"].status = "closed"
        turn = draft.draft_turn(event("học phí bao nhiêu"), self.repo, render)
        self.assertIsNone(draft.note(turn, CAT))


class TestLiveTurnUnchanged(unittest.TestCase):
    def test_bot_stays_silent_after_a_person_wrote(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        repo.jev = FakeJev({COURSE_FACT: {"choice": "duration", "confidence": 0.95}})
        repo.save_state(ConversationState("7", consultant_replied=True, slots=dict(ROBO), turns=3))
        payload = {"event": "message_created", "id": 11, "content": "bé học bao lâu", "message_type": "incoming",
                   "private": False, "sender": {"id": 9, "type": "contact"},
                   "conversation": {"id": 7, "inbox_id": 3, "meta": {"sender": {"id": 9}}}}
        turn = run_turn(parse_event(payload), repo, fx, render)
        self.assertEqual(turn.decision.type, "silent")
        self.assertEqual(fx.of("send"), [])


if __name__ == "__main__":
    unittest.main()
