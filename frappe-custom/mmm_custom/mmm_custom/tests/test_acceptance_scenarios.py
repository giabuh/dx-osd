"""The acceptance scenarios (engine/eval/scenarios.json, D-098) on the demo catalog, keyword tier."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, demo_consultants, render

from mmm_custom.engine.scenarios import load_scenarios, run_scenario

CAT = demo_catalog()


class TestAcceptanceScenarios(unittest.TestCase):
    def test_every_scenario_passes_on_the_demo_dataset(self):
        for scenario in load_scenarios():
            with self.subTest(scenario["id"], title=scenario["title"]):
                repo = FakeRepo(CAT)
                repo.consultant_rows = demo_consultants()
                result = run_scenario(scenario, repo, render)
                failed = [f"{c['check']}: expected {c['expected']!r}, got {c['actual']!r}" for c in result["checks"] if not c["ok"]]
                self.assertTrue(result["checks"], "a scenario must check something")
                self.assertEqual(failed, [])

    def test_ids_are_unique_and_every_scenario_states_why(self):
        scenarios = load_scenarios()
        self.assertEqual(len({s["id"] for s in scenarios}), len(scenarios))
        self.assertTrue(all(s.get("why") and s.get("messages") and s.get("expect") for s in scenarios))

    def test_a_failing_expectation_is_reported(self):
        repo = FakeRepo(CAT)
        repo.consultant_rows = demo_consultants()
        wrong = {"id": "X", "title": "sai", "messages": ["Mình ở Bình Thạnh muốn học Excel", "0901234567"],
                 "expect": {"consultant": {"branch": "CN Quận 7"}}}
        result = run_scenario(wrong, repo, render)
        self.assertFalse(result["passed"])
        self.assertEqual(result["checks"][0]["actual"], "CN Bình Thạnh")
        self.assertEqual(len(result["transcript"]), 2)


if __name__ == "__main__":
    unittest.main()
