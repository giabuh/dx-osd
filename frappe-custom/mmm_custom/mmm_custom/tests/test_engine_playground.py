import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from datetime import date

from engine_fixtures import FakeJev, FakeRepo, demo_catalog, demo_consultants, render, schedule

from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import Event, run_turn
from mmm_custom.engine.playground import actions, inspect, load_demo_scripts, replay_state
from mmm_custom.engine.scenarios import run_scenario

CAT = demo_catalog()
PAGE = Path(__file__).resolve().parent.parent / "mmm_custom" / "page" / "bot_playground"


class TestInspect(unittest.TestCase):
    def test_inspect_shows_the_jev_result(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        repo.jev = FakeJev({"slot:course": {"choice": "VKT-REVIT", "confidence": 0.7}})
        out = inspect(run_turn(Event("customer_message", "7", 5, "học vẽ nhà nha bạn", {"id": 9}), repo, fx, render), fx)
        self.assertEqual((out["jev"]["status"], out["jev"]["input_tokens"]), ("ok", 120))
        self.assertEqual(out["understanding"]["confirm"]["value"], "VKT-REVIT")

    def test_turn_is_shown_step_by_step(self):
        fx = RecordingEffects()
        turn = run_turn(Event("customer_message", "sandbox-x", 1, "học phí excel ở bình thạnh", {"id": "sandbox-x"}),
                        FakeRepo(CAT), fx, render)
        out = inspect(turn, fx)
        self.assertEqual(set(out), {"understanding", "jev", "decision", "reply", "events", "effects", "state"})
        self.assertEqual(out["understanding"]["fills"]["course"]["value"], "VP-EXCEL")
        self.assertEqual(out["jev"]["status"], "disabled")
        self.assertEqual((out["decision"]["type"], out["decision"]["skills"]), ("answer", ["fee_quote"]))
        self.assertEqual(out["reply"]["buttons"], ["Cho tôi", "Cho con em", "Cho công ty"])
        self.assertIn("slot_filled", [e["event"] for e in out["events"]])
        self.assertEqual(out["effects"][0][0], "save_lead")
        json.dumps(out, default=str)  # must serialise for frappe.call

    def test_state_keeps_the_conversation_signals_on_a_turn_without_jev(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        repo.jev = FakeJev({"intent": {"choice": "purchase", "confidence": 0.9}, "hotness": {"score": 1.8, "confidence": 0.9}})
        run_turn(Event("customer_message", "sandbox-x", 1, "học phí excel ở bình thạnh", {"id": "sandbox-x"}), repo, fx, render)
        out = inspect(run_turn(Event("customer_message", "sandbox-x", 2, "Cho tôi", {"id": "sandbox-x"}), repo, fx, render), fx)
        self.assertEqual(out["understanding"]["hotness"], {})  # a button reply skips Jev
        self.assertEqual((out["state"]["ai"]["ai_hotness"], out["state"]["ai"]["ai_intent"]), ("hot", "purchase"))

    def test_redelivery(self):
        self.assertEqual(inspect(None, RecordingEffects()), {"duplicate": True})

    def test_summary_tells_a_manager_what_the_bot_understood_and_would_do(self):
        fx = RecordingEffects()
        turn = run_turn(Event("customer_message", "sandbox-x", 1, "học phí excel ở bình thạnh", {"id": "sandbox-x"}),
                        FakeRepo(CAT), fx, render)
        summary = inspect(turn, fx, CAT)["summary"]
        self.assertEqual((summary["skills"], summary["decision"]), (["học phí"], "Trả lời"))
        self.assertEqual((summary["keywords"], summary["tapped"]), (["Khóa học", "Chi nhánh", "Câu hỏi: học phí"], False))
        facts = {f["key"]: f for f in summary["facts"]}
        self.assertEqual((facts["course"]["value"], facts["course"]["new"]), ("Excel từ cơ bản đến nâng cao", True))
        self.assertEqual((facts["branch"]["value"], facts["phone"]["value"], facts["phone"]["required"]), ("CN Bình Thạnh", "", True))
        self.assertNotIn("learner", facts)  # optional and still empty: not listed
        self.assertEqual(summary["actions"], ["Ghi vào Lead: Khóa học, Chi nhánh"])
        json.dumps(summary, default=str)

    def test_handoff_actions_name_the_consultant_team_and_status(self):
        calls = [("save_lead", {"fields": {"mobile_no": "+84901234567", "status": "Qualified"}, "courses": []}),
                 ("emit", {"event": "handed_off"}),
                 ("handoff", {"team": "CN Dĩ An", "labels": ["cn-di-an"], "summary": "…", "owner": "bao@x"}),
                 ("enrol", {"course": "VP-EXCEL", "class_title": "VP-EXCEL · CN Dĩ An · 06/10/2030 · Tối"})]
        self.assertEqual(actions(calls, ["phone"], CAT, "Lạc Văn Bảo"), [
            "Ghi vào Lead: Số điện thoại", "Trạng thái Lead → Đủ thông tin",
            "Giao cho tư vấn viên Lạc Văn Bảo · nhóm CN Dĩ An", "Gắn nhãn Chatwoot: cn-di-an",
            "Ghi chú tóm tắt hội thoại cho tư vấn viên", "Tạo phiếu ghi danh nháp: VP-EXCEL · CN Dĩ An · 06/10/2030 · Tối"])


class TestDemoScripts(unittest.TestCase):
    """The Playground's sample chats are played live at demos: each must reach a consultant on the demo data."""

    def test_every_demo_script_ends_with_a_handoff(self):
        classes = [schedule("VP-EXCEL", branch, date(2030, 10, day), shift=shift)
                   for branch in ("CN Bình Thạnh", "CN Dĩ An")
                   for day, shift in ((6, "Tối 18:00–20:00"), (8, "Sáng 8:00–10:00"))]
        scripts = load_demo_scripts()
        self.assertEqual([s["id"] for s in scripts], ["fee", "quiz", "enrol"])
        for script in scripts:
            with self.subTest(script["id"]):
                repo = FakeRepo(CAT)
                repo.consultant_rows, repo.schedules = demo_consultants(), classes
                result = run_scenario({**script, "expect": {}}, repo, render)
                self.assertTrue(script["title"])
                self.assertEqual(result["transcript"][-1]["decision"], "handoff", result["transcript"][-1])
                self.assertTrue(result["assigned"]["owner"])


class TestReplayState(unittest.TestCase):
    def test_rebuilds_the_state_before_the_logged_turn(self):
        log = {"name": "abc", "lead": "L1", "status_before": "active", "turns_before": 2, "stuck_before": 1,
               "slots_before": json.dumps({"course": {"value": "VP-EXCEL"}}), "pending_before": json.dumps({"slot": "branch"})}
        s = replay_state(log, {"contact_id": "9", "is_returning": 1})
        self.assertEqual((s.conversation_id, s.lead, s.turns, s.stuck_turns, s.is_returning, s.is_sandbox),
                         ("replay-abc", "L1", 2, 1, True, True))
        self.assertEqual((s.slots["course"]["value"], s.pending["slot"]), ("VP-EXCEL", "branch"))


class TestPage(unittest.TestCase):
    def test_page_definition(self):
        data = json.loads((PAGE / "bot_playground.json").read_text(encoding="utf-8"))
        self.assertEqual((data["name"], data["module"], data["standard"]), ("bot-playground", "MMM Custom", "Yes"))
        self.assertEqual({r["role"] for r in data["roles"]}, {"System Manager", "Sales Manager"})
        js = (PAGE / "bot_playground.js").read_text(encoding="utf-8")
        for method in ("playground.simulate", "playground.reset", "playground.replay"):
            self.assertIn(method, js)


if __name__ == "__main__":
    unittest.main()
