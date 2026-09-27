import sys
from pathlib import Path
import json
import unittest
from unittest.mock import patch, MagicMock

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

if "requests" not in sys.modules:
    sys.modules["requests"] = MagicMock()

from mmm_custom.chatwoot_client import ChatwootClient


class TestChatwootClient(unittest.TestCase):
    def setUp(self):
        self.client = ChatwootClient(
            base_url="http://localhost:3000",
            api_token="test_token_123",
            account_id=1,
        )

    @patch("mmm_custom.chatwoot_client.requests")
    def test_send_message_plain_text(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": 1}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        result = self.client.send_message(42, "Hello world")

        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        self.assertIn("/conversations/42/messages", call_args[0][0])
        body = call_args[1]["json"]
        self.assertEqual(body["content"], "Hello world")
        self.assertEqual(body["message_type"], "outgoing")

    @patch("mmm_custom.chatwoot_client.requests")
    def test_send_quick_replies(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": 2}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        items = [{"title": "A", "value": "a"}, {"title": "B", "value": "b"}]
        result = self.client.send_quick_replies(42, "Pick one", items)

        call_args = mock_requests.post.call_args
        body = call_args[1]["json"]
        self.assertEqual(body["content_type"], "input_select")
        self.assertEqual(body["content_attributes"]["items"], items)

    @patch("mmm_custom.chatwoot_client.requests")
    def test_update_contact(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": 10}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.patch.return_value = mock_resp

        self.client.update_contact(10, {"bot_state": "await_course"})

        call_args = mock_requests.patch.call_args
        self.assertIn("/contacts/10", call_args[0][0])
        body = call_args[1]["json"]
        self.assertEqual(body["custom_attributes"]["bot_state"], "await_course")

    @patch("mmm_custom.chatwoot_client.requests")
    def test_update_contact_with_phone(self, mock_requests):
        mock_requests.patch.return_value = MagicMock()
        self.client.update_contact(10, {"crm_lead_id": "L1"}, phone_number="+84912345678")
        body = mock_requests.patch.call_args[1]["json"]
        self.assertEqual(body, {"custom_attributes": {"crm_lead_id": "L1"}, "phone_number": "+84912345678"})

    @patch("mmm_custom.chatwoot_client.requests")
    def test_toggle_status(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "open"}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        self.client.toggle_status(42, "open")

        call_args = mock_requests.post.call_args
        self.assertIn("/conversations/42/toggle_status", call_args[0][0])
        self.assertEqual(call_args[1]["json"]["status"], "open")

    @patch("mmm_custom.chatwoot_client.requests")
    def test_assign_conversation(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        self.client.assign_conversation(42, 7)

        call_args = mock_requests.post.call_args
        self.assertIn("/conversations/42/assignments", call_args[0][0])
        self.assertEqual(call_args[1]["json"]["assignee_id"], 7)

    @patch("mmm_custom.chatwoot_client.requests")
    def test_list_agents(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"id": 1, "name": "Agent A"}]
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        agents = self.client.list_agents()

        self.assertEqual(len(agents), 1)
        mock_requests.get.assert_called_once()

    @patch("mmm_custom.chatwoot_client.requests")
    def test_list_agent_conversations(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "payload": [
                    {"id": 101, "meta": {"assignee": {"id": 7}}},
                    {"id": 102, "meta": {"assignee": {"id": 8}}},
                ]
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        convos = self.client.list_agent_conversations(7)
        self.assertEqual(len(convos), 1)
        self.assertEqual(convos[0]["id"], 101)

    @patch("mmm_custom.chatwoot_client.requests")
    def test_auth_header_included(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        self.client.list_agents()

        call_args = mock_requests.get.call_args
        self.assertEqual(call_args[1]["headers"]["api_access_token"], "test_token_123")


    @patch("mmm_custom.chatwoot_client.requests")
    def test_add_labels_keeps_existing_labels(self, mock_requests):
        # Chatwoot's POST /labels replaces the whole list, so adding must merge with what is there.
        get_resp = MagicMock()
        get_resp.json.return_value = {"payload": ["ai-purchase", "vip"]}
        mock_requests.get.return_value = get_resp
        mock_requests.post.return_value = MagicMock()

        self.client.add_labels(42, ["Tiếng Anh", "vip"])

        self.assertIn("/conversations/42/labels", mock_requests.get.call_args[0][0])
        self.assertEqual(mock_requests.post.call_args[1]["json"], {"labels": ["ai-purchase", "vip", "Tiếng Anh"]})

    @patch("mmm_custom.chatwoot_client.requests")
    def test_add_labels_skips_the_write_when_nothing_is_new(self, mock_requests):
        get_resp = MagicMock()
        get_resp.json.return_value = {"payload": ["hot"]}
        mock_requests.get.return_value = get_resp

        self.client.add_labels(42, ["hot"])

        mock_requests.post.assert_not_called()

    @patch("mmm_custom.chatwoot_client.requests")
    def test_list_messages_returns_meta_and_payload(self, mock_requests):
        resp = MagicMock()
        resp.json.return_value = {"meta": {"labels": []}, "payload": [{"id": 1}]}
        mock_requests.get.return_value = resp

        data = self.client.list_messages(42)

        self.assertIn("/conversations/42/messages", mock_requests.get.call_args[0][0])
        self.assertEqual(data["payload"], [{"id": 1}])

    @patch("mmm_custom.chatwoot_client.requests")
    def test_send_private_note(self, mock_requests):
        mock_requests.post.return_value = MagicMock()

        self.client.send_private_note(42, "Gợi ý trả lời")

        body = mock_requests.post.call_args[1]["json"]
        self.assertEqual(body, {"content": "Gợi ý trả lời", "message_type": "outgoing", "private": True})


class TestChatwootClientAdmin(unittest.TestCase):
    """Inbox/agent/team methods used by the demo Chatwoot seeding (C1.6)."""

    def setUp(self):
        self.client = ChatwootClient("http://localhost:3000", "tok", 1)

    def _resp(self, mock_requests, verb, payload):
        resp = MagicMock()
        resp.json.return_value = payload
        getattr(mock_requests, verb).return_value = resp
        return resp

    @patch("mmm_custom.chatwoot_client.requests")
    def test_list_inboxes(self, mock_requests):
        self._resp(mock_requests, "get", {"payload": [{"id": 2}]})
        self.assertEqual(self.client.list_inboxes(), [{"id": 2}])
        self.assertTrue(mock_requests.get.call_args[0][0].endswith("/api/v1/accounts/1/inboxes"))

    @patch("mmm_custom.chatwoot_client.requests")
    def test_create_agent(self, mock_requests):
        self._resp(mock_requests, "post", {"id": 9})
        self.assertEqual(self.client.create_agent("B", "b@x.invalid"), {"id": 9})
        self.assertTrue(mock_requests.post.call_args[0][0].endswith("/agents"))
        self.assertEqual(mock_requests.post.call_args[1]["json"], {"name": "B", "email": "b@x.invalid", "role": "agent"})

    @patch("mmm_custom.chatwoot_client.requests")
    def test_list_teams(self, mock_requests):
        self._resp(mock_requests, "get", [{"id": 1, "name": "cn dĩ an"}])
        self.assertEqual(self.client.list_teams(), [{"id": 1, "name": "cn dĩ an"}])
        self.assertTrue(mock_requests.get.call_args[0][0].endswith("/teams"))

    @patch("mmm_custom.chatwoot_client.requests")
    def test_create_team(self, mock_requests):
        self._resp(mock_requests, "post", {"id": 3})
        self.client.create_team("CN Dĩ An")
        self.assertTrue(mock_requests.post.call_args[0][0].endswith("/teams"))
        self.assertEqual(mock_requests.post.call_args[1]["json"], {"name": "CN Dĩ An", "description": ""})

    @patch("mmm_custom.chatwoot_client.requests")
    def test_add_team_members(self, mock_requests):
        self._resp(mock_requests, "post", [])
        self.client.add_team_members(3, [7, 9])
        self.assertTrue(mock_requests.post.call_args[0][0].endswith("/teams/3/team_members"))
        self.assertEqual(mock_requests.post.call_args[1]["json"], {"user_ids": [7, 9]})

    @patch("mmm_custom.chatwoot_client.requests")
    def test_update_team_members_replaces_the_list(self, mock_requests):
        self._resp(mock_requests, "patch", [])
        self.client.update_team_members(3, [7])
        self.assertTrue(mock_requests.patch.call_args[0][0].endswith("/teams/3/team_members"))
        self.assertEqual(mock_requests.patch.call_args[1]["json"], {"user_ids": [7]})

    @patch("mmm_custom.chatwoot_client.requests")
    def test_list_agent_bots(self, mock_requests):
        self._resp(mock_requests, "get", [{"id": 4}])
        self.assertEqual(self.client.list_agent_bots(), [{"id": 4}])
        self.assertTrue(mock_requests.get.call_args[0][0].endswith("/agent_bots"))

    @patch("mmm_custom.chatwoot_client.requests")
    def test_set_agent_bot(self, mock_requests):
        self._resp(mock_requests, "post", None)
        self.client.set_agent_bot(2, 4)
        self.assertTrue(mock_requests.post.call_args[0][0].endswith("/inboxes/2/set_agent_bot"))
        self.assertEqual(mock_requests.post.call_args[1]["json"], {"agent_bot": 4})

    @patch("mmm_custom.chatwoot_client.requests")
    def test_add_inbox_members(self, mock_requests):
        self._resp(mock_requests, "post", [])
        self.client.add_inbox_members(2, [7])
        self.assertTrue(mock_requests.post.call_args[0][0].endswith("/inbox_members"))
        self.assertEqual(mock_requests.post.call_args[1]["json"], {"inbox_id": 2, "user_ids": [7]})

    @patch("mmm_custom.chatwoot_client.requests")
    def test_assign_team(self, mock_requests):
        self._resp(mock_requests, "post", {})
        self.client.assign_team(5, 4)
        self.assertTrue(mock_requests.post.call_args[0][0].endswith("/conversations/5/assignments"))
        self.assertEqual(mock_requests.post.call_args[1]["json"], {"team_id": 4})

    @patch("mmm_custom.chatwoot_client.requests")
    def test_set_conversation_attributes(self, mock_requests):
        self._resp(mock_requests, "post", {})
        self.client.set_conversation_attributes(5, {"bot_branch": "CN Dĩ An"})
        self.assertTrue(mock_requests.post.call_args[0][0].endswith("/conversations/5/custom_attributes"))
        self.assertEqual(mock_requests.post.call_args[1]["json"], {"custom_attributes": {"bot_branch": "CN Dĩ An"}})

    @patch("mmm_custom.chatwoot_client.requests")
    def test_custom_attribute_definitions(self, mock_requests):
        self._resp(mock_requests, "get", [{"attribute_key": "bot_course"}])
        self.assertEqual(self.client.list_custom_attributes(), [{"attribute_key": "bot_course"}])
        self.assertEqual(mock_requests.get.call_args[1]["params"], {"attribute_model": "conversation_attribute"})
        self._resp(mock_requests, "post", {"id": 1})
        self.client.create_custom_attribute("bot_branch", "Bot · Chi nhánh")
        self.assertTrue(mock_requests.post.call_args[0][0].endswith("/custom_attribute_definitions"))
        self.assertEqual(mock_requests.post.call_args[1]["json"], {
            "attribute_display_name": "Bot · Chi nhánh", "attribute_key": "bot_branch",
            "attribute_model": "conversation_attribute", "attribute_display_type": "text"})

if __name__ == "__main__":
    unittest.main()
