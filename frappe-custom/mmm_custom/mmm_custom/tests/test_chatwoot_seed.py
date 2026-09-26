import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.demo import chatwoot_seed


class TestPlanTeams(unittest.TestCase):
    def test_team_names(self):
        consultants = [
            {"email": "a@demo.saoviet.invalid", "branch": "CN Dĩ An", "handles_b2b": 0},
            {"email": "b@demo.saoviet.invalid", "branch": "", "handles_b2b": 1},
            {"email": "c@demo.saoviet.invalid", "branch": "", "handles_b2b": 0},
        ]
        self.assertEqual(chatwoot_seed.plan_teams(consultants), {
            "CN Dĩ An": ["a@demo.saoviet.invalid"],
            "Doanh nghiệp (B2B)": ["b@demo.saoviet.invalid"],
            "Tổng đài": ["c@demo.saoviet.invalid"],
        })


class TestEnsureAgents(unittest.TestCase):
    def test_existing_agents_are_reused(self):
        client = MagicMock()
        client.list_agents.return_value = [{"id": 7, "email": "a@demo.saoviet.invalid"}]
        client.create_agent.return_value = {"id": 9, "email": "b@demo.saoviet.invalid"}
        ids = chatwoot_seed.ensure_agents(client, [
            {"full_name": "A", "email": "a@demo.saoviet.invalid"},
            {"full_name": "B", "email": "b@demo.saoviet.invalid"},
        ])
        self.assertEqual(ids, {"a@demo.saoviet.invalid": 7, "b@demo.saoviet.invalid": 9})
        client.create_agent.assert_called_once_with("B", "b@demo.saoviet.invalid")


if __name__ == "__main__":
    unittest.main()
