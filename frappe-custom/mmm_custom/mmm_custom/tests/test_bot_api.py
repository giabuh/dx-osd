import hashlib
import hmac
import json
import sys
from pathlib import Path
import time
import unittest
from unittest.mock import MagicMock, patch, call

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

if "requests" not in sys.modules:
    sys.modules["requests"] = MagicMock()

import mmm_custom.bot_api as bot_api_mod
from mmm_custom.bot_api import agent_bot_webhook


def compute_sig(secret: str, ts: str, body: bytes) -> str:
    msg = f"{ts}.".encode("utf-8") + body
    return "sha256=" + hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def make_message_created_payload(
    content="hello",
    message_type=0,
    conversation_id=1,
    contact_id=10,
    contact_name="Test User",
    custom_attributes=None,
):
    """Build a minimal Agent Bot webhook payload for message_created."""
    return {
        "event": "message_created",
        "content_type": "text",
        "content": content,
        "message_type": message_type,
        "conversation": {
            "id": conversation_id,
            "status": "pending",
            "contact_inbox": {
                "contact": {
                    "id": contact_id,
                    "name": contact_name,
                    "email": "test@example.com",
                    "phone_number": "0901234567",
                    "custom_attributes": custom_attributes or {},
                }
            },
        },
        "sender": {"id": contact_id, "name": contact_name, "type": "contact"},
    }


class TestBotApiWebhook(unittest.TestCase):
    def setUp(self):
        self.secret = "bot_webhook_secret_test"
        self.conf = {
            "chatwoot_bot_webhook_secret": self.secret,
            "chatwoot_bot_api_token": "mock_bot_token",
            "chatwoot_bot_account_id": 1,
            "chatwoot_base_url": "http://localhost:3000",
        }
        self.mock_frappe = MagicMock()
        self.mock_frappe.conf = self.conf
        self.mock_frappe.AuthenticationError = bot_api_mod.frappe.AuthenticationError
        self.mock_frappe.throw = bot_api_mod.frappe.throw

    def _setup_request(self, payload_dict, ts=None, sig=None):
        body = json.dumps(payload_dict).encode("utf-8")
        ts = ts or str(int(time.time()))
        sig = sig or compute_sig(self.secret, ts, body)
        mock_req = MagicMock()
        mock_req.headers = {
            "X-Chatwoot-Signature": sig,
            "X-Chatwoot-Timestamp": ts,
        }
        mock_req.get_data.return_value = body
        mock_req.data = body
        self.mock_frappe.request = mock_req
        return body

    def test_invalid_hmac_rejected(self):
        payload = make_message_created_payload()
        self._setup_request(payload, sig="sha256=invalid")
        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            with self.assertRaises(self.mock_frappe.AuthenticationError):
                agent_bot_webhook()

    def test_unconfigured_secret_rejects_even_the_old_public_default(self):
        # A site without chatwoot_bot_webhook_secret must not fall back to a secret anyone can read in the repo.
        self.conf.pop("chatwoot_bot_webhook_secret")
        ts = str(int(time.time()))
        payload = {"event": "message_created", "message_type": "incoming"}
        body = json.dumps(payload).encode("utf-8")
        self._setup_request(payload, ts=ts, sig=compute_sig("dx_osd_bot_webhook_secret_2026", ts, body))
        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            with self.assertRaises(self.mock_frappe.AuthenticationError):
                bot_api_mod.agent_bot_webhook()

    def test_outgoing_message_ignored(self):
        payload = make_message_created_payload(message_type=1)
        self._setup_request(payload)
        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            with patch.object(bot_api_mod, "ChatwootClient"):
                result = agent_bot_webhook()
                self.assertEqual(result["status"], "ignored")

    def test_non_message_created_event_ignored(self):
        payload = {"event": "conversation_resolved"}
        self._setup_request(payload)
        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            result = agent_bot_webhook()
            self.assertEqual(result["status"], "ignored")

    def test_greeting_sends_course_quick_replies(self):
        payload = make_message_created_payload(content="xin chào")
        self._setup_request(payload)
        mock_client = MagicMock()
        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            with patch.object(bot_api_mod, "ChatwootClient", return_value=mock_client):
                result = agent_bot_webhook()
                self.assertEqual(result["status"], "ok")
                mock_client.send_quick_replies.assert_called_once()
                call_args = mock_client.send_quick_replies.call_args
                self.assertIn("EduFlow", call_args[0][1])
                mock_client.update_contact.assert_called_once()

    def test_completed_state_is_noop(self):
        payload = make_message_created_payload(
            content="any",
            custom_attributes={"bot_state": "completed"},
        )
        self._setup_request(payload)
        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            with patch.object(bot_api_mod, "ChatwootClient") as MockClient:
                result = agent_bot_webhook()
                self.assertEqual(result["status"], "ignored")
                MockClient.return_value.send_message.assert_not_called()
                MockClient.return_value.send_quick_replies.assert_not_called()

    def test_branch_selection_asks_for_phone(self):
        """Branch selection now transitions to await_phone."""
        payload = make_message_created_payload(
            content="binh_thanh",
            custom_attributes={
                "bot_state": "await_branch",
                "bot_courses": ["tieng_anh"],
            },
        )
        self._setup_request(payload)
        mock_client = MagicMock()

        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            with patch.object(bot_api_mod, "ChatwootClient", return_value=mock_client):
                result = agent_bot_webhook()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["next_state"], "await_phone")
        mock_client.send_quick_replies.assert_called_once()  # skip button

    def test_phone_input_completes_handoff(self):
        """Providing a valid phone in await_phone triggers full handoff."""
        payload = make_message_created_payload(
            content="0901234567",
            custom_attributes={
                "bot_state": "await_phone",
                "bot_courses": ["tieng_anh"],
                "bot_branch": "binh_thanh",
            },
        )
        self._setup_request(payload)
        mock_client = MagicMock()
        mock_client.list_agents.return_value = [
            {"id": 1, "name": "Agent A", "custom_attributes": {"branch": "binh_thanh"}},
            {"id": 2, "name": "Agent B", "custom_attributes": {"branch": "quan_1"}},
        ]
        mock_client.list_agent_conversations.return_value = []

        self.mock_frappe.db.exists.return_value = False
        mock_lead = MagicMock()
        mock_lead.name = "CRM-LEAD-BOT-001"
        mock_lead.insert.return_value = mock_lead
        self.mock_frappe.get_doc.return_value = mock_lead

        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            with patch.object(bot_api_mod, "ChatwootClient", return_value=mock_client):
                with patch("mmm_custom.bot_api.find_matching_lead", return_value=None):
                    result = agent_bot_webhook()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["next_state"], "completed")
        mock_client.send_message.assert_called_once()  # confirmation message
        mock_client.assign_conversation.assert_called_once_with(1, 1)
        mock_client.toggle_status.assert_called_once_with(1, "open")

    def test_contact_and_agent_calls_use_the_user_token_messages_use_the_bot_token(self):
        # Chatwoot answers 401 to an Agent Bot token on /contacts and /agents (verified live), so the bot
        # could never save its state or pick a branch agent with its own token.
        self.conf["chatwoot_api_token"] = "user_token"
        payload = make_message_created_payload(
            content="0901234567",
            custom_attributes={
                "bot_state": "await_phone",
                "bot_courses": ["tieng_anh"],
                "bot_branch": "binh_thanh",
            },
        )
        self._setup_request(payload)
        clients = {"mock_bot_token": MagicMock(), "user_token": MagicMock()}
        clients["user_token"].list_agents.return_value = [{"id": 1, "custom_attributes": {"branch": "binh_thanh"}}]
        clients["user_token"].list_agent_conversations.return_value = []
        self.mock_frappe.db.exists.return_value = False
        mock_lead = MagicMock()
        mock_lead.name = "CRM-LEAD-BOT-002"
        mock_lead.insert.return_value = mock_lead
        self.mock_frappe.get_doc.return_value = mock_lead

        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            with patch.object(bot_api_mod, "ChatwootClient", side_effect=lambda url, token, account: clients[token]):
                with patch("mmm_custom.bot_api.find_matching_lead", return_value=None):
                    agent_bot_webhook()

        bot, user = clients["mock_bot_token"], clients["user_token"]
        bot.send_message.assert_called_once()
        bot.assign_conversation.assert_called_once_with(1, 1)
        bot.toggle_status.assert_called_once_with(1, "open")
        bot.update_contact.assert_not_called()
        bot.list_agents.assert_not_called()
        self.assertTrue(user.update_contact.called)
        user.list_agents.assert_called_once()

    def test_handoff_fixes_placeholder_name_on_existing_lead(self):
        """When a lead already exists with placeholder name, bot handoff
        should fix first_name and lead_name to the real contact name."""
        payload = make_message_created_payload(
            content="0901234567",
            contact_name="Hoàng Thành",
            custom_attributes={
                "bot_state": "await_phone",
                "bot_courses": ["tieng_anh"],
                "bot_branch": "binh_thanh",
                "crm_lead_id": "CRM-LEAD-PLACEHOLDER",
            },
        )
        self._setup_request(payload)
        mock_client = MagicMock()
        mock_client.list_agents.return_value = [
            {"id": 1, "name": "Agent A", "custom_attributes": {"branch": "binh_thanh"}},
        ]
        mock_client.list_agent_conversations.return_value = []

        self.mock_frappe.db.exists.return_value = True
        # Simulate stored lead has old placeholder name
        self.mock_frappe.db.get_value.return_value = {
            "first_name": "EduFlow Student",
            "lead_name": "EduFlow Student",
        }

        with patch.object(bot_api_mod, "frappe", self.mock_frappe):
            with patch.object(bot_api_mod, "ChatwootClient", return_value=mock_client):
                result = agent_bot_webhook()

        self.assertEqual(result["status"], "ok")
        # Verify name was fixed
        self.mock_frappe.db.set_value.assert_any_call(
            "CRM Lead", "CRM-LEAD-PLACEHOLDER", "first_name", "Hoàng Thành"
        )
        self.mock_frappe.db.set_value.assert_any_call(
            "CRM Lead", "CRM-LEAD-PLACEHOLDER", "lead_name", "Hoàng Thành"
        )


if __name__ == "__main__":
    unittest.main()
