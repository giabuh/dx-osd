"""The bot leads a registration (D-118, D-121): class buttons, then the phone, then the handoff with a draft; Jev reads
a message that leaves the dialogue."""

import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeJev, FakeRepo, demo_catalog, demo_consultants, fill, incoming, render, schedule

from mmm_custom import catalog_rules
from mmm_custom.engine import decide, enrol_flow, offers
from mmm_custom.engine.actions import run_action
from mmm_custom.engine.context import base_context
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import enrol_drafts, parse_event, run_turn
from mmm_custom.engine.state import ConversationState

CAT = demo_catalog()
TODAY = date(2026, 9, 28)


def act(slots, repo, **extra):
    ctx = {**base_context(slots, CAT, ConversationState("1", slots=slots)), **extra}
    return run_action(CAT.skills["register"], ctx, slots, CAT, repo, TODAY)


def repo_with_classes():
    repo = FakeRepo(CAT, TODAY)
    repo.schedules = [schedule("VP-EXCEL", "CN Quận 7", date(2026, 10, 6)),
                      schedule("VP-EXCEL", "CN Quận 7", date(2026, 10, 11), shift="Sáng 8:00–11:00")]
    return repo


CLASS = "VP-EXCEL · CN Quận 7 · 06/10/2026 · Tối"


class TestEnrolAction(unittest.TestCase):
    def test_register_needs_only_the_course(self):
        self.assertEqual(CAT.skills["register"].params, ("course",))

    def test_register_leads_the_dialogue_instead_of_handing_off(self):
        skill = CAT.skills["register"]
        self.assertEqual((skill.action, skill.handoff_after), ("enrol", False))
        self.assertEqual(enrol_flow.skill_key(CAT), "register")
        self.assertEqual(enrol_flow.class_slot(CAT), "enrol_class")

    def test_action_is_known_everywhere_action_types_are_listed(self):
        self.assertIn("enrol", catalog_rules.ACTION_TYPES)
        self.assertIn("enrol", decide.LIVE_ACTIONS)
        self.assertIn("enrol", offers.BUTTON_ACTIONS)

    def test_next_classes_become_buttons_plus_one_to_let_the_consultant_choose(self):
        out = act({"course": fill("VP-EXCEL"), "branch": fill("CN Quận 7")}, repo_with_classes())
        self.assertEqual([b["title"] for b in out["_buttons"]],
                         ["06/10 Tối Quận 7", "11/10 Sáng Quận 7", "Nhờ tư vấn chọn lớp"])
        self.assertEqual(out["_buttons"][0]["action"], {"type": "slot", "slot": "enrol_class", "skill": "register",
                                                        "value": CLASS})
        self.assertEqual(out["_buttons"][-1]["action"], {"type": "skip", "slot": "enrol_class"})

    def test_classes_of_one_day_at_different_branches_get_different_buttons(self):
        repo = FakeRepo(CAT, TODAY)
        repo.schedules = [schedule("VP-EXCEL", "CN Quận 6", date(2026, 10, 5)),
                          schedule("VP-EXCEL", "CN Bình Thạnh", date(2026, 10, 5))]
        titles = [b["title"] for b in act({"course": fill("VP-EXCEL")}, repo)["_buttons"]]
        self.assertEqual(len(set(titles)), 3)
        self.assertTrue(all(len(t) <= 20 for t in titles))

    def test_a_chosen_class_is_echoed_and_offers_no_more_buttons(self):
        out = act({"course": fill("VP-EXCEL"), "enrol_class": fill(CLASS)}, repo_with_classes())
        self.assertEqual(out, {"enrol_class": CLASS})

    def test_no_open_class_skips_the_step_and_asks_the_phone(self):
        out = act({"course": fill("VP-EXCEL")}, FakeRepo(CAT, TODAY))
        self.assertEqual((out["schedules"], out["_skip_slot"], out["_then_ask"]), ([], "enrol_class", "phone"))
        self.assertNotIn("_buttons", out)
        out = act({"course": fill("VP-EXCEL"), "phone": fill("0901111222")}, FakeRepo(CAT, TODAY))
        self.assertNotIn("_then_ask", out)

    def test_an_ended_dialogue_answers_with_the_stop_variant(self):
        self.assertEqual(act({"course": fill("VP-EXCEL")}, repo_with_classes(), enrol_stop="later"),
                         {"enrol_stop": "later"})

    def test_the_class_list_breaks_lines_for_real(self):
        for t in CAT.skills["register"].templates:
            self.assertNotIn("\\n", t.text)

    def test_templates(self):
        variants = {t.key: t for t in CAT.skills["register"].templates}
        self.assertEqual(list(variants), ["stop", "chosen", "resumed", "default"])
        ctx = {"brand": {"me": "em", "you": "anh/chị"}, "course": {"name": "Excel"}}
        self.assertIn("Excel · 06/10", render(variants["chosen"].text, {**ctx, "enrol_class": "Excel · 06/10"}))
        self.assertIn("cân nhắc", render(variants["stop"].text, {**ctx, "enrol_stop": "later"}))
        self.assertNotIn("cân nhắc", render(variants["stop"].text, {**ctx, "enrol_stop": "cancel"}))
        default = render(variants["default"].text, {**ctx, "schedules": []})
        self.assertIn("chưa có lớp mở", default)
        self.assertNotIn("số điện thoại", default)  # the phone is the next step, asked on its own


class Chat:
    """A Messenger conversation through run_turn, with a Lead from the first message."""

    def __init__(self, jev=None, schedules=True):
        self.repo = repo_with_classes() if schedules else FakeRepo(CAT, TODAY)
        self.repo.consultant_rows = demo_consultants()
        self.repo.jev = jev
        self.fx = RecordingEffects()
        self.fx.save_lead = lambda state, fields, courses, contact: state.lead or "CRM-LEAD-1"
        self.n = 0

    def say(self, text):
        self.n += 1
        return run_turn(parse_event(incoming(text, self.n)), self.repo, self.fx, render)

    def sent(self):
        return " ".join(self.fx.of("send")[-1]["messages"])

    def buttons(self):
        return list(self.fx.of("send")[-1]["buttons"])

    def state(self):
        return self.repo.states["2"]


def step_jev(step):
    """Jev reads the message inside the registration dialogue as `step`; nothing else."""
    return FakeJev(lambda q: {enrol_flow.STEP: {"choice": step, "confidence": 0.95}} if enrol_flow.STEP in q else {})


class TestDialogue(unittest.TestCase):
    def test_register_shows_classes_and_does_not_hand_off(self):
        c = Chat()
        t = c.say("mình muốn đăng ký khóa excel")
        self.assertEqual((t.decision.type, t.decision.skills), ("answer", ["register"]))
        self.assertIn("06/10 Tối Quận 7", c.buttons())
        self.assertNotIn("số điện thoại", c.sent())
        self.assertEqual((c.state().status, enrol_flow.phase(c.state().slots, CAT)), ("active", "open"))
        self.assertEqual((c.fx.of("handoff"), c.fx.of("enrol")), ([], []))

    def test_the_dk_abbreviation_starts_the_dialogue(self):
        c = Chat()
        t = c.say("e muon dk khoa excel")
        self.assertEqual(t.decision.skills, ["register"])
        self.assertEqual(enrol_flow.phase(c.state().slots, CAT), "open")

    def test_a_hot_customer_is_not_handed_off_before_the_class_and_phone(self):
        jev = FakeJev(lambda q: {"hotness": {"score": 2, "confidence": 0.95},
                                 "skill:register": {"noul": 0.95}})
        c = Chat(jev)
        t = c.say("mình muốn đăng ký khóa excel nhé")
        self.assertEqual(t.decision.type, "answer")
        self.assertEqual(c.fx.of("handoff"), [])

    def test_class_then_phone_then_handoff_with_the_draft(self):
        c = Chat()
        c.say("mình muốn đăng ký khóa excel")
        t = c.say("06/10 Tối Quận 7")
        self.assertEqual((t.decision.type, t.decision.ask), ("answer", "phone"))
        self.assertIn("đã ghi lớp", c.sent())
        self.assertIn("số điện thoại", c.sent())
        self.assertEqual(c.fx.of("handoff"), [])
        t = c.say("0901111222")
        self.assertEqual((t.decision.type, t.decision.handoff_reason), ("handoff", "enrol_ready"))
        self.assertEqual(enrol_flow.phase(c.state().slots, CAT), "done")
        [draft] = c.fx.of("enrol")
        self.assertEqual((draft["course"], draft["class_title"]), ("VP-EXCEL", CLASS))
        self.assertEqual(draft["owner"], c.fx.of("handoff")[0]["owner"])

    def test_a_known_phone_hands_off_as_soon_as_the_class_is_chosen(self):
        c = Chat()
        c.say("đăng ký excel, sđt mình 0901111222")
        t = c.say("06/10 Tối Quận 7")
        self.assertEqual((t.decision.type, t.decision.handoff_reason), ("handoff", "enrol_ready"))
        self.assertIn("đã ghi lớp", c.sent())
        self.assertEqual(len(c.fx.of("enrol")), 1)

    def test_let_the_consultant_choose_skips_to_the_phone(self):
        c = Chat()
        c.say("mình muốn đăng ký khóa excel")
        t = c.say("Nhờ tư vấn chọn lớp")
        self.assertEqual((t.decision.type, t.decision.ask), ("ask_slot", "phone"))
        c.say("0901111222")
        self.assertEqual(c.fx.of("enrol")[0]["class_title"], "")

    def test_a_side_question_is_answered_then_the_classes_come_back(self):
        c = Chat()
        c.say("mình muốn đăng ký khóa excel")
        t = c.say("học phí bao nhiêu vậy")
        self.assertEqual(t.decision.type, "answer")
        self.assertEqual(t.decision.resume, "register")
        self.assertIn("fee_quote", t.decision.skills)
        self.assertIn("Nhờ tư vấn chọn lớp", c.buttons())
        self.assertIn("chọn lớp", t.reason)
        self.assertEqual(c.fx.of("handoff"), [])

    def test_a_class_typed_with_a_question_is_taken_and_the_question_answered(self):
        c = Chat()
        c.say("mình muốn đăng ký khóa excel")
        t = c.say("tối quận 7 ngày 6 tháng 10\nvậy học phí sao vậy")
        self.assertEqual(t.decision.slots["enrol_class"]["value"], CLASS)
        self.assertEqual((t.decision.ask, t.decision.resume), ("phone", ""))
        self.assertIn("fee_quote", t.decision.skills)
        self.assertIn("đã ghi lớp", c.sent())
        self.assertEqual(c.buttons(), [])  # no fee follow-ups under the phone question

    def test_after_two_side_questions_the_consultant_picks_the_class(self):
        c = Chat()
        c.say("mình muốn đăng ký khóa excel")
        c.say("học phí bao nhiêu vậy")
        c.say("học phí bao nhiêu vậy")
        t = c.say("học phí bao nhiêu vậy")
        self.assertEqual((t.decision.resume, t.decision.ask), ("", "phone"))

    def test_jev_later_ends_the_dialogue_without_handoff_or_draft(self):
        c = Chat(step_jev("later"))
        c.say("mình muốn đăng ký khóa excel")
        t = c.say("để mình về hỏi ý kiến vợ đã nhé")
        self.assertEqual((t.decision.type, t.decision.enrol_stop, t.decision.ask), ("answer", "later", ""))
        self.assertIn("cân nhắc", c.sent())
        self.assertEqual((c.fx.of("handoff"), c.fx.of("enrol")), ([], []))
        self.assertEqual(enrol_flow.phase(c.state().slots, CAT), "stopped")
        c.repo.jev = None
        t = c.say("mình muốn đăng ký khóa excel")  # ready again: the dialogue starts over
        self.assertEqual(enrol_flow.phase(c.state().slots, CAT), "open")
        self.assertIn("06/10 Tối Quận 7", c.buttons())

    def test_jev_no_phone_hands_off_to_chat_here(self):
        c = Chat(step_jev("no_phone"))
        c.say("mình muốn đăng ký khóa excel")
        c.say("06/10 Tối Quận 7")
        t = c.say("thôi nhắn ở đây được rồi, không cần gọi đâu")
        self.assertEqual((t.decision.type, t.decision.handoff_reason), ("handoff", "enrol_ready"))
        self.assertEqual(c.fx.of("enrol")[0]["class_title"], CLASS)

    def test_asking_for_a_person_hands_off_at_once_with_the_draft(self):
        c = Chat()
        c.say("mình muốn đăng ký khóa excel")
        c.repo.jev = FakeJev(lambda q: {"wants_human": {"noul": 0.95}} if "wants_human" in q else {})
        t = c.say("cho mình nói chuyện với nhân viên")
        self.assertEqual((t.decision.type, t.decision.handoff_reason), ("handoff", "wants_human"))
        self.assertEqual(len(c.fx.of("enrol")), 1)

    def test_jev_is_asked_where_a_message_leads_only_inside_the_dialogue(self):
        from mmm_custom.engine.jev_questions import build_questions
        from mmm_custom.engine.understand import understand

        s = ConversationState("1", slots={"course": fill("VP-EXCEL")})
        self.assertNotIn(enrol_flow.STEP, build_questions(s, understand("để mình suy nghĩ", s, CAT), CAT))
        s.slots["enrol_class"] = {"flow": "open"}
        self.assertIn(enrol_flow.STEP, build_questions(s, understand("để mình suy nghĩ", s, CAT), CAT))
        s.status = "handed_off"
        self.assertNotIn(enrol_flow.STEP, build_questions(s, understand("để mình suy nghĩ", s, CAT), CAT))

    def test_no_open_class_asks_the_phone_in_the_same_reply(self):
        c = Chat(schedules=False)
        c.say("mình muốn đăng ký khóa excel")
        self.assertIn("chưa có lớp mở", c.sent())
        self.assertIn("số điện thoại", c.sent())
        self.assertTrue(c.state().slots["enrol_class"].get("skipped"))
        t = c.say("0901111222")
        self.assertEqual(t.decision.handoff_reason, "enrol_ready")

    def test_after_a_handoff_register_drafts_at_once(self):
        c = Chat()
        c.repo.states["2"] = ConversationState("2", lead="CRM-LEAD-1", status="handed_off",
                                               slots={"course": fill("VP-EXCEL")}, turns=3)
        t = c.say("mình muốn đăng ký khóa excel")
        self.assertEqual(t.decision.type, "answer")
        self.assertEqual(len(c.fx.of("enrol")), 1)


def turn(slots, lead="CRM-LEAD-1", skills=("register",), kind="handoff", before="active"):
    state = ConversationState("7", lead=lead, slots=slots)
    return SimpleNamespace(state=state, status_before=before,
                           decision=SimpleNamespace(skills=list(skills), type=kind, slots=slots),
                           reply=SimpleNamespace(errors=[]))


DONE = {"flow": "done"}


class TestEnrolDrafts(unittest.TestCase):
    def run_it(self, t, plan=None):
        fx = RecordingEffects()
        enrol_drafts(t, fx, CAT, plan)
        return fx, fx.of("enrol")

    def test_the_dialogue_ending_in_a_handoff_drafts_with_the_class(self):
        _, calls = self.run_it(turn({"course": fill("VP-EXCEL"), "enrol_class": {**fill(CLASS), **DONE}}),
                               SimpleNamespace(owner="mai@x.vn"))
        self.assertEqual(calls, [{"lead": "CRM-LEAD-1", "course": "VP-EXCEL", "class_title": CLASS, "owner": "mai@x.vn"}])

    def test_no_draft_while_the_dialogue_runs_or_after_it_stopped(self):
        for entry, kind in (({"flow": "open"}, "answer"), ({"flow": "stopped"}, "answer"), ({}, "handoff")):
            self.assertEqual(self.run_it(turn({"course": fill("VP-EXCEL"), "enrol_class": entry}, kind=kind))[1], [])

    def test_after_a_handoff_the_register_answer_drafts(self):
        _, calls = self.run_it(turn({"course": fill("VP-EXCEL")}, kind="answer", before="handed_off"))
        self.assertEqual(len(calls), 1)
        t = turn({"course": fill("VP-EXCEL")}, kind="answer", before="handed_off", skills=("hotline",))
        self.assertEqual(self.run_it(t)[1], [])

    def test_no_course_or_no_lead_no_draft(self):
        for slots, lead in (({"enrol_class": DONE}, "CRM-LEAD-1"), ({"course": fill("VP-EXCEL"), "enrol_class": DONE}, "")):
            self.assertEqual(self.run_it(turn(slots, lead))[1], [])

    def test_a_failing_effect_is_recorded_not_raised(self):
        t = turn({"course": fill("VP-EXCEL"), "enrol_class": DONE})
        fx = RecordingEffects()

        def boom(*a, **k):
            raise PermissionError()

        fx.enrol = boom
        enrol_drafts(t, fx, CAT, None)
        self.assertEqual(t.reply.errors[0], {"type": "enrol_failed", "detail": "PermissionError: "})



class TestMatchClass(unittest.TestCase):
    PENDING = {"options": {
        "05/10 Sáng Quận 6": {"type": "slot", "slot": "enrol_class", "value": "A", "skill": "register"},
        "05/10 Sáng Bình Thạn": {"type": "slot", "slot": "enrol_class", "value": "B", "skill": "register"},
        "12/10 Tối Quận 6": {"type": "slot", "slot": "enrol_class", "value": "C", "skill": "register"},
        "Nhờ tư vấn chọn lớp": {"type": "skip", "slot": "enrol_class"}}}

    def pick(self, text):
        from mmm_custom.engine.reply_match import match_class

        action = match_class(text, self.PENDING, "enrol_class")
        return action["value"] if action else None

    def test_day_shift_and_branch_in_any_words(self):
        self.assertEqual(self.pick("sáng quận 6 ngày 5 tháng 10\nvậy học phí sao vậy"), "A")
        self.assertEqual(self.pick("lớp 5/10 ở bình thạnh nhé"), "B")
        self.assertEqual(self.pick("cho mình lớp tối quận 6"), "C")

    def test_nothing_or_several_fitting_picks_none(self):
        self.assertIsNone(self.pick("ngày 5 nhé"))  # Quận 6 and Bình Thạnh
        self.assertIsNone(self.pick("học phí bao nhiêu"))
        self.assertIsNone(self.pick("sáng"))
        self.assertIsNone(self.pick("trung tâm ở quận 6 nằm đâu vậy"))  # asks about the branch, picks no class


if __name__ == "__main__":
    unittest.main()
