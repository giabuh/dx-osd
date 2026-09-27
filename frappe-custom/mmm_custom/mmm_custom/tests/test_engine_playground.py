import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeJev, FakeRepo, demo_catalog, render

from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import Event, run_turn
from mmm_custom.engine.playground import inspect, replay_state

CAT = demo_catalog()
PAGE = Path(__file__).resolve().parent.parent / "mmm_custom" / "page" / "bot_playground"


class TestInspect(unittest.TestCase):
    def test_inspect_shows_the_jev_result(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        repo.jev = FakeJev({"slot:course": {"choice": "VKT-REVIT", "confidence": 0.7}})
        out = inspect(run_turn(Event("customer_message", "7", 5, "học vẽ nhà", {"id": 9}), repo, fx, render), fx)
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

    def test_redelivery(self):
        self.assertEqual(inspect(None, RecordingEffects()), {"duplicate": True})


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
