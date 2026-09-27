import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import mmm_custom.bot_api as bot_api_mod
from mmm_custom.bot_api import agent_bot_webhook

SECRET = "bot-secret"


def sign(secret, ts, body):
    return "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


def incoming(message_type="incoming", sender_type="contact", private=False, message_id=77):
    return {"event": "message_created", "id": message_id, "content": "xin chào", "message_type": message_type,
            "private": private, "sender": {"id": 9, "type": sender_type},
            "conversation": {"id": 5, "meta": {"sender": {"id": 9, "name": "Lan"}}}}


class TestAgentBotWebhook(unittest.TestCase):
    def setUp(self):
        self.fr = bot_api_mod.frappe
        self.fr.conf = {"chatwoot_bot_webhook_secret": SECRET}
        self.fr.enqueue = MagicMock()

    def post(self, payload, secret=SECRET, ts=None, raw=None):
        body = raw if raw is not None else json.dumps(payload).encode()
        ts = ts or str(int(time.time()))
        req = MagicMock()
        req.headers = {"X-Chatwoot-Timestamp": ts, "X-Chatwoot-Signature": sign(secret, ts, body)}
        req.get_data.return_value = body
        self.fr.request = req
        return agent_bot_webhook()

    def test_missing_secret_is_rejected(self):
        self.fr.conf = {}
        with self.assertRaises(self.fr.AuthenticationError):
            self.post(incoming())

    def test_bad_signature_is_rejected(self):
        with self.assertRaises(self.fr.AuthenticationError):
            self.post(incoming(), secret="wrong")

    def test_stale_timestamp_is_rejected(self):
        with self.assertRaises(self.fr.AuthenticationError):
            self.post(incoming(), ts=str(int(time.time()) - 600))

    def test_customer_message_is_enqueued_once_per_message_id(self):
        payload = incoming()
        self.assertEqual(self.post(payload), {"status": "queued"})
        self.fr.enqueue.assert_called_once_with("mmm_custom.engine.pipeline.process_event", queue="short",
                                                job_id="lead_engine_msg_77", deduplicate=True, payload=payload)

    def test_bot_own_message_and_private_note_are_not_enqueued(self):
        self.post(incoming(message_type="outgoing", sender_type="agent_bot"))
        self.post(incoming(message_type="outgoing", sender_type="user", private=True))
        self.fr.enqueue.assert_not_called()

    def test_invalid_json(self):
        self.assertEqual(self.post(None, raw=b"{not json")["status"], "error")

    def test_human_agent_message_silences_the_bot(self):
        with patch.object(bot_api_mod, "mark_consultant_replied") as mark:
            self.assertEqual(self.post(incoming(message_type="outgoing", sender_type="user")),
                             {"status": "consultant_replied"})
        mark.assert_called_once_with("5")
        self.fr.enqueue.assert_not_called()

    def test_resolved_conversation_is_closed(self):
        with patch.object(bot_api_mod, "close_conversation") as close:
            self.assertEqual(self.post({"event": "conversation_resolved", "id": 5}), {"status": "closed"})
        close.assert_called_once_with("5")

if __name__ == "__main__":
    unittest.main()
