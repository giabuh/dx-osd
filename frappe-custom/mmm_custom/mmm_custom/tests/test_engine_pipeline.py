import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeJev, FakeRepo, demo_catalog, demo_consultants, fill, render

from mmm_custom.engine import events
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import Event, parse_event, run_turn
from mmm_custom.engine.understand import Understanding

CAT = demo_catalog()


def incoming(text="xin chào", message_id=5, conversation_id=7, contact_id=9):
    return {"event": "message_created", "id": message_id, "content": text, "message_type": "incoming",
            "private": False, "sender": {"id": contact_id, "name": "Lan", "type": "contact"},
            "conversation": {"id": conversation_id, "inbox_id": 3,
                             "meta": {"sender": {"id": contact_id, "name": "Lan", "custom_attributes": {}}}}}


class TestParseEvent(unittest.TestCase):
    def test_customer_message(self):
        e = parse_event(incoming())
        self.assertEqual((e.kind, e.conversation_id, e.message_id, e.text, e.contact["id"], e.inbox_id),
                         ("customer_message", "7", 5, "xin chào", 9, "3"))

    def test_text_is_capped(self):
        self.assertEqual(len(parse_event(incoming("a" * 5000)).text), 1000)

    def test_agent_bot_and_private_and_activity_are_ignored(self):
        own = {**incoming(), "message_type": "outgoing", "sender": {"id": 1, "type": "agent_bot"}}
        note = {**incoming(), "message_type": "outgoing", "private": True, "sender": {"id": 2, "type": "user"}}
        activity = {**incoming(), "message_type": "activity"}
        for payload in (own, note, activity):
            self.assertEqual(parse_event(payload).kind, "ignore")

    def test_human_agent_message(self):
        e = parse_event({**incoming(), "message_type": "outgoing", "sender": {"id": 2, "type": "user"}})
        self.assertEqual((e.kind, e.conversation_id), ("agent_message", "7"))

    def test_resolved(self):
        self.assertEqual(parse_event({"event": "conversation_resolved", "id": 7}).kind, "resolved")
        self.assertEqual(parse_event({"event": "conversation_status_changed", "id": 7, "status": "resolved"}).kind, "resolved")
        self.assertEqual(parse_event({"event": "conversation_status_changed", "id": 7, "status": "open"}).kind, "ignore")


class TestRunTurn(unittest.TestCase):
    def setUp(self):
        self.repo, self.fx = FakeRepo(CAT), RecordingEffects()

    def turn(self, text="alo", message_id=5):
        return run_turn(parse_event(incoming(text, message_id)), self.repo, self.fx, render)

    def test_first_message_greets_asks_and_saves_state(self):
        t = self.turn()
        sent = self.fx.of("send")
        self.assertEqual(len(sent), 1)
        self.assertIn("Trợ lý Sao Việt", sent[0]["messages"][0])
        self.assertIn("Anh/chị quan tâm khóa học nào ạ?", sent[0]["messages"][0])
        saved = self.repo.states["7"]
        self.assertEqual((saved.last_message_id, saved.turns, saved.pending["slot"]), (5, 1, "course"))
        self.assertEqual(t.decision.type, "ask_slot")

    def test_redelivered_message_is_ignored(self):
        self.turn()
        self.assertIsNone(self.turn())
        self.assertEqual(len(self.fx.of("send")), 1)

    def test_send_failure_is_recorded_and_state_saved(self):
        fx = RecordingEffects()
        fx.send = MagicMock(side_effect=RuntimeError("chatwoot down"))
        t = run_turn(parse_event(incoming()), self.repo, fx, render)
        self.assertEqual(t.reply.errors[0]["type"], "send_failed")
        self.assertEqual(self.repo.states["7"].last_message_id, 5)

    def test_events_for_filled_slots(self):
        with patch("mmm_custom.engine.pipeline.understand", return_value=Understanding(fills={"course": fill("VP-EXCEL")})):
            self.turn("excel")
        filled = [e for e in self.fx.of("emit") if e["event"] == "slot_filled"]
        self.assertEqual([(e["slot"], e["value"]) for e in filled], [("course", "VP-EXCEL")])

    def test_handoff_changes_status_and_emits(self):
        with patch("mmm_custom.engine.pipeline.understand", return_value=Understanding(handoff=True)):
            self.turn("gặp tư vấn viên")
        self.assertEqual(self.repo.states["7"].status, "handed_off")
        self.assertIn("handed_off", [e["event"] for e in self.fx.of("emit")])

    def test_lead_saved_when_a_lead_field_slot_is_filled(self):
        with patch("mmm_custom.engine.pipeline.understand", return_value=Understanding(fills={"course": fill("VP-EXCEL")})):
            self.turn("excel")
        self.assertEqual(self.fx.of("save_lead")[0]["courses"], ["VP-EXCEL"])
        self.assertIn("lead_updated", [e["event"] for e in self.fx.of("emit")])

    def test_no_lead_write_for_greeting_or_no_lead_skill(self):
        self.turn("xin chào")
        with patch("mmm_custom.engine.pipeline.understand", return_value=Understanding(skills=["certificate_lookup"])):
            self.turn("tra cứu chứng nhận", message_id=6)
        self.assertEqual(self.fx.of("save_lead"), [])
        with patch("mmm_custom.engine.pipeline.understand", return_value=Understanding(skills=["hotline"])):
            self.turn("hotline", message_id=7)
        self.assertEqual(len(self.fx.of("save_lead")), 1)

    def test_lead_failure_is_recorded(self):
        fx = RecordingEffects()
        fx.save_lead = MagicMock(side_effect=RuntimeError("db"))
        with patch("mmm_custom.engine.pipeline.understand", return_value=Understanding(fills={"course": fill("VP-EXCEL")})):
            t = run_turn(parse_event(incoming("excel")), self.repo, fx, render)
        self.assertEqual(t.reply.errors[-1]["type"], "lead_failed")
        self.assertEqual(self.repo.states["7"].slots["course"]["value"], "VP-EXCEL")
    def test_handoff_turn_assigns_and_tells_the_customer(self):
        self.repo.consultant_rows = demo_consultants()
        u = Understanding(fills={"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An"), "phone": fill("+84901234567")})
        with patch("mmm_custom.engine.pipeline.understand", return_value=u):
            t = self.turn("0901234567")
        handoff = self.fx.of("handoff")[0]
        self.assertTrue(handoff["agent_id"])
        self.assertEqual(handoff["team"], "CN Dĩ An")
        consultant = next(c for c in demo_consultants() if c["name"] == self.repo.states["7"].consultant)
        self.assertIn(f"tư vấn viên {consultant['full_name']} (CN Dĩ An)", self.fx.of("send")[0]["messages"][0])
        self.assertIn("CN Dĩ An · ít khách nhất", t.reason)
        self.assertEqual([e["consultant"] for e in self.fx.of("emit") if e["event"] == "handed_off"], [consultant["name"]])

class TestJevTurn(unittest.TestCase):
    def setUp(self):
        self.repo, self.fx = FakeRepo(CAT), RecordingEffects()

    def turn(self, text, message_id=5):
        return run_turn(parse_event(incoming(text, message_id)), self.repo, self.fx, render)

    def test_without_a_client_jev_is_disabled(self):
        t = self.turn("alo")
        self.assertEqual((t.jev.status, self.repo.logs[0]["jev_status"]), ("disabled", "disabled"))

    def test_two_topics_in_one_message_are_both_answered(self):
        self.repo.jev = FakeJev({"skill:opening_hours": {"noul": 0.92}, "skill:hotline": {"noul": 0.9}})
        t = self.turn("trung tâm nghỉ lúc nào, liên lạc bằng cách nào")
        self.assertEqual(sorted(t.decision.skills), ["hotline", "opening_hours"])
        self.assertEqual(t.decision.type, "answer")

    def test_jev_answer_fills_a_slot_and_is_logged(self):
        self.repo.jev = FakeJev({"slot:course": {"choice": "VKT-REVIT", "confidence": 0.96}})
        t = self.turn("mình muốn học vẽ nhà nha bạn")
        self.assertEqual(self.repo.states["7"].slots["course"]["source"], "jev")
        self.assertEqual(t.decision.ask, "branch")
        log = self.repo.logs[0]
        self.assertEqual((log["jev_status"], log["input_tokens"], log["model_version"]), ("ok", 120, "jev-test"))
        self.assertIn("slot:course", log["jev_questions"])

    def test_jev_unavailable_falls_back_to_keywords(self):
        self.repo.jev = FakeJev(status="unavailable")
        t = self.turn("excel bạn ơi")  # a leftover word keeps the Task 5 cost guard from skipping Jev
        self.assertEqual((t.jev.status, self.repo.states["7"].slots["course"]["value"]), ("unavailable", "VP-EXCEL"))
        self.assertEqual(self.repo.logs[0]["jev_status"], "unavailable")

    def test_confirm_no_asks_with_buttons_and_records_signal(self):
        self.repo.jev = FakeJev({"slot:course": {"choice": "VKT-REVIT", "confidence": 0.7}})
        t1 = self.turn("mình muốn học vẽ nhà nha bạn")
        self.assertEqual(t1.decision.type, "confirm")
        self.assertEqual([b["title"] for b in t1.reply.buttons], ["Đúng ạ", "Không phải"])
        self.assertEqual(self.repo.states["7"].pending["confirm"]["value"], "VKT-REVIT")
        t2 = self.turn("Không phải", message_id=6)
        self.assertEqual((t2.decision.type, t2.decision.ask), ("ask_slot", "course"))
        self.assertTrue(t2.reply.buttons)
        self.assertNotIn("value", self.repo.states["7"].slots.get("course", {}))
        self.assertEqual(len(self.repo.jev.calls), 1)  # the tap needed no Jev call
        self.assertEqual([s["signal_type"] for s in self.repo.signals], ["confirm_rejected"])

    def test_confirm_yes_fills(self):
        self.repo.jev = FakeJev({"slot:course": {"choice": "VKT-REVIT", "confidence": 0.7}})
        self.turn("mình muốn học vẽ nhà nha bạn")
        self.turn("Đúng ạ", message_id=6)
        self.assertEqual(self.repo.states["7"].slots["course"]["value"], "VKT-REVIT")

    def test_history_is_kept_and_capped(self):
        self.turn("alo")
        self.assertEqual([h["from"] for h in self.repo.states["7"].history], ["customer", "bot"])
        for i in range(1, 30):  # after the stuck handoff the bot is silent: customer lines only
            self.turn(f"alo {i}", message_id=5 + i)
        history = self.repo.states["7"].history
        self.assertEqual(len(history), 20)
        self.assertEqual(history[-1], {"from": "customer", "text": "alo 29"})

class TestEvents(unittest.TestCase):
    def test_handlers_receive_payload_and_failures_are_logged(self):
        got, log = [], MagicMock()

        def boom(payload):
            raise RuntimeError("x")

        attrs = {"a.ok": got.append, "a.boom": boom}
        events.emit("handed_off", {"lead": "L1"}, get_hooks=lambda name: {"handed_off": ["a.boom", "a.ok"]},
                    get_attr=attrs.__getitem__, log_error=log)
        self.assertEqual(got, [{"event": "handed_off", "lead": "L1"}])
        log.assert_called_once()

    def test_no_hooks_registered(self):
        events.emit("slot_filled", {}, get_hooks=lambda name: [], get_attr=None, log_error=None)


if __name__ == "__main__":
    unittest.main()
