import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeJev, FakeRepo, demo_catalog, fill, render

from mmm_custom.engine import offers
from mmm_custom.engine.combine import combine
from mmm_custom.engine.decide import Decision, decide
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.jev_questions import build_questions
from mmm_custom.engine.pipeline import parse_event, run_turn
from mmm_custom.engine.reply import compose
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding, understand

CAT = demo_catalog()
KNOWN = {"course": {**fill("VP-EXCEL"), "parent": "Tin học văn phòng"}, "branch": fill("CN Dĩ An")}


def state(**kw):
    return ConversationState("1", **{"turns": 2, "slots": dict(KNOWN), **kw})


class TestWhenToOffer(unittest.TestCase):
    def test_known_course_without_level_gets_its_quiz(self):
        self.assertEqual(offers.quiz_offer(state(), Understanding(), KNOWN, CAT), "excel_quiz")

    def test_only_the_group_known_gets_the_group_quiz(self):
        slots = {"course": {"parent": "Thiết kế đồ họa"}}
        self.assertEqual(offers.quiz_offer(state(slots=slots), Understanding(), slots, CAT), "design_quiz")

    def test_no_offer(self):
        cases = {
            "first turn": (state(turns=0), KNOWN, ()),
            "handed off": (state(status="handed_off"), KNOWN, ()),
            "consultant replied": (state(consultant_replied=True), KNOWN, ()),
            "offered before": (state(offers={"excel_quiz": "declined"}), KNOWN, ()),
            "already placed": (state(), {**KNOWN, "placement": fill("Excel: 4/5")}, ()),
            "course unknown": (state(slots={}), {}, ()),
            "group without a quiz": (state(), {"course": fill("MKT-FB")}, ()),
            "quiz under way": (state(), KNOWN, ("excel_quiz",)),
        }
        for why, (s, slots, skills) in cases.items():
            self.assertEqual(offers.quiz_offer(s, Understanding(), slots, CAT, skills), "", why)

    def test_a_stated_level_needs_jev_to_read_doubt(self):
        slots = {**KNOWN, "level": fill("basic")}
        self.assertEqual(offers.quiz_offer(state(), Understanding(), slots, CAT), "")
        self.assertEqual(offers.quiz_offer(state(), Understanding(level_unsure=0.8), slots, CAT), "excel_quiz")


class TestDecideAndCompose(unittest.TestCase):
    def test_offer_replaces_an_optional_question(self):
        d = decide(state(), Understanding(), CAT)
        self.assertEqual((d.type, d.offer, d.ask), ("ask_slot", "excel_quiz", ""))
        self.assertEqual(d.reason, "Mời làm bài test Excel (chưa rõ trình độ)")
        self.assertNotIn("asked", d.slots.get("learner", {}))

    def test_required_branch_is_asked_first(self):
        s = state(slots={"course": KNOWN["course"]})
        d = decide(s, Understanding(), CAT)
        self.assertEqual((d.offer, d.ask), ("", "branch"))

    def test_handoff_and_confirm_come_first(self):
        d = decide(state(), Understanding(wants_human=0.9), CAT)
        self.assertEqual((d.type, d.offer), ("handoff", ""))
        confirm = {"kind": "slot", "slot": "learner", "value": "child", "label": "Con em"}
        d = decide(state(), Understanding(confirm=confirm), CAT)
        self.assertEqual((d.type, d.offer), ("confirm", ""))

    def test_offer_text_and_buttons(self):
        r = compose(Decision("ask_slot", slots=dict(KNOWN), offer="excel_quiz"), state(), CAT, render)
        self.assertEqual(r.messages, ["Dạ để em tư vấn đúng lớp hơn, anh/chị làm thử bài test Excel nhỏ 5 câu, chừng 1 phút "
                                      "thôi nhé ạ 😊 Làm xong em tặng anh/chị một buổi học thử miễn phí và mã ưu đãi ạ."])
        self.assertEqual(r.buttons, [{"title": "Làm bài test", "action": {"type": "skill", "skill": "excel_quiz"}},
                                     {"title": "Để sau", "action": {"type": "offer_decline", "skill": "excel_quiz"}}])

    def test_offer_follows_an_answer(self):
        u = Understanding(skills=["fee_quote"])
        d = decide(state(), u, CAT)
        self.assertEqual((d.type, d.skills, d.offer), ("answer", ["fee_quote"], "excel_quiz"))
        self.assertTrue(d.reason.startswith("Trả lời: "), d.reason)
        self.assertTrue(d.reason.endswith("; mời làm bài test Excel (chưa rõ trình độ)"), d.reason)

    def test_later_is_answered_kindly_and_the_talk_goes_on(self):
        s = state(offers={"excel_quiz": "offered"},
                  pending={"slot": "", "options": {b["title"]: b["action"] for b in offers.buttons("excel_quiz")}})
        u = understand("Để sau", s, CAT)
        self.assertEqual(u.declined, "excel_quiz")
        d = decide(s, u, CAT)
        self.assertEqual((d.declined, d.offer, d.ask, d.fallback), ("excel_quiz", "", "learner", False))
        r = compose(d, s, CAT, render)
        self.assertTrue(r.messages[0].startswith("Dạ không sao ạ, khi nào tiện anh/chị cứ nhắn em làm bài test nhé ạ."))
        self.assertEqual(offers.track(s.offers, d, CAT, d.declined), {"excel_quiz": "declined"})


class TestTrack(unittest.TestCase):
    def test_offered_started_done(self):
        self.assertEqual(offers.track({}, Decision("ask_slot", offer="excel_quiz"), CAT), {"excel_quiz": "offered"})
        started = Decision("answer", skills=["excel_quiz"], slots={"quiz_progress": fill("excel_quiz:0")})
        self.assertEqual(offers.track({"excel_quiz": "offered"}, started, CAT), {"excel_quiz": "started"})
        done = Decision("answer", skills=["excel_quiz"], slots={"quiz_progress": fill("excel_quiz:3,3")})
        self.assertEqual(offers.track({"excel_quiz": "reminded"}, done, CAT), {"excel_quiz": "done"})
        self.assertEqual(offers.track({"excel_quiz": "reminded"}, started, CAT), {"excel_quiz": "reminded"})


class TestJev(unittest.TestCase):
    def test_level_unsure_is_asked_only_while_an_offer_is_possible(self):
        self.assertIn("level_unsure", build_questions(state(), Understanding(), CAT))
        self.assertNotIn("level_unsure", build_questions(state(offers={"excel_quiz": "done"}), Understanding(), CAT))
        self.assertNotIn("level_unsure", build_questions(state(slots={}), Understanding(), CAT))

    def test_combine_reads_the_noul(self):
        s = state()
        questions = build_questions(s, Understanding(), CAT)
        u = combine(Understanding(), {"level_unsure": {"noul": 0.83}}, questions, s, CAT)
        self.assertEqual(u.level_unsure, 0.83)


def incoming(text, message_id):
    return {"event": "message_created", "id": message_id, "content": text, "message_type": "incoming",
            "private": False, "sender": {"id": 9, "name": "Lan", "type": "contact"},
            "conversation": {"id": 7, "inbox_id": 3, "meta": {"sender": {"id": 9, "name": "Lan", "custom_attributes": {}}}}}


class TestConversation(unittest.TestCase):
    """Customer asks about Excel, is offered the test, takes it and gets placed."""

    def test_offer_then_quiz_then_result(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        n = iter(range(10, 100))

        def say(text):
            run_turn(parse_event(incoming(text, next(n))), repo, fx, render)
            return fx.of("send")[-1]

        say("học excel ở dĩ an")
        sent = say("em tự học")
        self.assertIn("bài test Excel nhỏ 5 câu", sent["messages"][-1])
        self.assertEqual(sent["buttons"], ["Làm bài test", "Để sau"])
        self.assertEqual(repo.states["7"].offers, {"excel_quiz": "offered"})

        sent = say("Làm bài test")
        self.assertIn("Câu 1/5", sent["messages"][-1])
        self.assertEqual(repo.states["7"].offers, {"excel_quiz": "started"})
        for pick in ("SUM", "$A$1", "Dò tìm theo mã", "COUNTIF"):
            sent = say(pick)
        self.assertEqual(sent["buttons"], ["Pivot Table", "Lọc thủ công", "Copy – dán", "Format Painter"])
        sent = say("Lọc thủ công")
        self.assertIn("đúng 4/5 câu", sent["messages"][0])
        saved = repo.states["7"]
        self.assertEqual(saved.offers, {"excel_quiz": "done"})
        self.assertEqual((saved.slots["level"]["value"], saved.slots["course"]["value"]), ("basic", "VP-EXCEL-NC"))


if __name__ == "__main__":
    unittest.main()
