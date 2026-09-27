import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom import staff_sync


class TestPlanTeams(unittest.TestCase):
    def test_team_names(self):
        consultants = [
            {"email": "a@demo.saoviet.invalid", "branch": "CN Dĩ An", "handles_b2b": 0},
            {"email": "b@demo.saoviet.invalid", "branch": "", "handles_b2b": 1},
            {"email": "c@demo.saoviet.invalid", "branch": "", "handles_b2b": 0},
            {"email": "d@demo.saoviet.invalid", "branch": "CN Dĩ An", "handles_b2b": 0, "active": 0},
        ]
        self.assertEqual(staff_sync.plan_teams(consultants), {
            "CN Dĩ An": ["a@demo.saoviet.invalid"],
            "Doanh nghiệp (B2B)": ["b@demo.saoviet.invalid"],
            "Tổng đài": ["c@demo.saoviet.invalid"],
        })


class TestEnsureAgents(unittest.TestCase):
    def test_existing_agents_are_reused_and_inactive_skipped(self):
        client = MagicMock()
        client.list_agents.return_value = [{"id": 7, "email": "a@demo.saoviet.invalid"}]
        client.create_agent.return_value = {"id": 9, "email": "b@demo.saoviet.invalid"}
        ids = staff_sync.ensure_agents(client, [
            {"full_name": "A", "email": "a@demo.saoviet.invalid"},
            {"full_name": "B", "email": "b@demo.saoviet.invalid"},
            {"full_name": "C", "email": "c@demo.saoviet.invalid", "active": 0},
        ])
        self.assertEqual(ids, {"a@demo.saoviet.invalid": 7, "b@demo.saoviet.invalid": 9})
        client.create_agent.assert_called_once_with("B", "b@demo.saoviet.invalid")


class TestSyncTeams(unittest.TestCase):
    def client(self, teams):
        client = MagicMock()
        client.list_teams.return_value = teams
        client.create_team.return_value = {"id": 30}
        return client

    def members(self, client):
        return {c.args[0]: c.args[1] for c in client.update_team_members.call_args_list}

    def test_branch_change_moves_the_consultant(self):
        client = self.client([{"id": 1, "name": "cn dĩ an"}, {"id": 2, "name": "cn thuận an"}])
        consultants = [{"email": "a@x", "branch": "CN Thuận An"}, {"email": "b@x", "branch": "CN Dĩ An"}]
        staff_sync.sync_teams(client, consultants, {"a@x": 11, "b@x": 12}, ["CN Dĩ An", "CN Thuận An"])
        self.assertEqual(self.members(client), {1: [12], 2: [11]})
        client.create_team.assert_not_called()

    def test_branch_without_active_consultant_is_emptied(self):
        client = self.client([{"id": 1, "name": "cn dĩ an"}])
        staff_sync.sync_teams(client, [{"email": "a@x", "branch": "CN Dĩ An", "active": 0}], {}, ["CN Dĩ An"])
        self.assertEqual(self.members(client), {1: []})

    def test_missing_team_is_created_and_unmanaged_teams_untouched(self):
        client = self.client([{"id": 5, "name": "marketing"}])
        staff_sync.sync_teams(client, [{"email": "a@x", "branch": "CN Dĩ An"}], {"a@x": 11}, ["CN Dĩ An"])
        client.create_team.assert_called_once_with("CN Dĩ An")
        self.assertEqual(self.members(client), {30: [11]})


class TestSyncInboxes(unittest.TestCase):
    def test_bot_is_attached_to_facebook_inboxes_only(self):
        client = MagicMock()
        client.list_agent_bots.return_value = [
            {"id": 1, "outgoing_url": "http://other/hook"},
            {"id": 4, "outgoing_url": "http://crm-frappe:8000/api/method/mmm_custom.bot_api.agent_bot_webhook"},
        ]
        client.list_inboxes.return_value = [
            {"id": 2, "channel_type": "Channel::FacebookPage"},
            {"id": 3, "channel_type": "Channel::WebWidget"},
            {"id": 6, "channel_type": "Channel::FacebookPage"},
        ]
        self.assertEqual(staff_sync.sync_inboxes(client), 2)
        self.assertEqual([c.args for c in client.set_agent_bot.call_args_list], [(2, 4), (6, 4)])

    def test_no_bot_means_no_change(self):
        client = MagicMock()
        client.list_agent_bots.return_value = []
        self.assertEqual(staff_sync.sync_inboxes(client), 0)
        client.set_agent_bot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
