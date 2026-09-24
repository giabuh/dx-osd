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


if __name__ == "__main__":
    unittest.main()
