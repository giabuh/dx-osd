import sys
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom import lead_chat

BOT = {"type": "agent_bot", "name": "Sao Việt Bot"}
AGENT = {"type": "user", "name": "Lạc Văn Bảo", "available_name": "Bảo"}


class TestMessages(unittest.TestCase):
    def test_kinds(self):
        cases = [
            ({"message_type": 0}, "customer"),
            ({"message_type": 1, "sender": AGENT}, "staff"),
            ({"message_type": 1, "sender": BOT}, "bot"),
            ({"message_type": 3}, "bot"),  # template
            ({"message_type": 1, "sender": AGENT, "private": True}, "note"),
            ({"message_type": 2, "content": "Assigned to Bảo"}, "activity"),
        ]
        for message, kind in cases:
            self.assertEqual(lead_chat.message_kind(message), kind, message)

    def test_to_message_keeps_quick_reply_buttons(self):
        out = lead_chat.to_message({"id": 7, "message_type": 1, "sender": BOT, "content": "Chi nhánh nào ạ?",
                                    "created_at": 1790000000,
                                    "content_attributes": {"items": [{"title": "Dĩ An"}, {"title": "Thuận An"}]}})
        self.assertEqual(out, {"id": 7, "kind": "bot", "text": "Chi nhánh nào ạ?", "sender": "Sao Việt Bot",
                               "at": 1790000000, "buttons": ["Dĩ An", "Thuận An"], "attachments": 0})

    def test_newest_conversation(self):
        self.assertEqual(lead_chat.newest_conversation([{"id": 3, "last_activity_at": 10},
                                                        {"id": 9, "last_activity_at": 50}, {"id": 5}]), 9)
        self.assertIsNone(lead_chat.newest_conversation([]))


def fake_frappe(readable=True, linked=(), contact_id=None, consultant=True, manager=False):
    frappe = MagicMock()
    frappe.session = SimpleNamespace(user="tv@x.vn")
    frappe.conf = {"chatwoot_api_token": "admin-token", "chatwoot_base_url": "https://chat.x", "chatwoot_account_id": 2}
    frappe.has_permission.return_value = readable
    frappe.get_all.return_value = list(linked)
    frappe.db.get_value.return_value = contact_id
    frappe.db.exists.return_value = consultant
    frappe.PermissionError = PermissionError
    frappe.throw.side_effect = lambda msg, exc=Exception: (_ for _ in ()).throw(exc(msg))
    return frappe


class TestChat(unittest.TestCase):
    def run_chat(self, frappe, token="", manager=False, messages=()):
        client = MagicMock()
        client.list_messages.return_value = {"payload": list(messages)}
        client.list_contact_conversations.return_value = [{"id": 41, "last_activity_at": 5}]
        with patch.object(lead_chat, "frappe", frappe), patch.object(lead_chat, "ChatwootClient", return_value=client), \
                patch.object(lead_chat, "own_token", return_value=token), \
                patch.object(lead_chat, "can_open_bot", return_value=manager):
            return lead_chat.chat("CRM-LEAD-1"), client

    def test_lead_outside_the_scope_is_refused(self):
        with self.assertRaises(PermissionError):
            self.run_chat(fake_frappe(readable=False))

    def test_bot_linked_conversation_first(self):
        out, client = self.run_chat(fake_frappe(linked=["123"]), token="tok",
                                    messages=[{"id": 1, "message_type": 0, "content": "Học excel"}])
        client.list_messages.assert_called_once_with(123)
        self.assertEqual(out["conversation"], 123)
        self.assertEqual(out["chatwoot_url"], "https://chat.x/app/accounts/2/conversations/123")
        self.assertTrue(out["can_reply"])
        self.assertEqual(out["messages"][0]["kind"], "customer")

    def test_falls_back_to_the_contacts_newest_conversation(self):
        out, client = self.run_chat(fake_frappe(contact_id="77"), token="tok")
        client.list_contact_conversations.assert_called_once_with(77)
        self.assertEqual(out["conversation"], 41)

    def test_no_conversation(self):
        out, _ = self.run_chat(fake_frappe(contact_id=None))
        self.assertEqual(out, {"conversation": None, "messages": [], "can_reply": False, "chatwoot_url": None})

    def test_consultant_without_token_reads_but_cannot_reply(self):
        out, _ = self.run_chat(fake_frappe(linked=["123"]), token="")
        self.assertFalse(out["can_reply"])


class TestSend(unittest.TestCase):
    def send(self, frappe, text="Dạ lớp tối T3 khai giảng 07/10 ạ", sender=True):
        admin, own = MagicMock(), MagicMock()
        own.send_message.return_value = {"id": 9, "message_type": 1, "sender": AGENT, "content": text}
        with patch.object(lead_chat, "frappe", frappe), patch.object(lead_chat, "admin_client", return_value=admin), \
                patch.object(lead_chat, "sender_client", return_value=own if sender else None):
            return lead_chat.send("CRM-LEAD-1", text), own

    def test_sends_as_the_consultant(self):
        out, own = self.send(fake_frappe(linked=["123"]))
        own.send_message.assert_called_once_with(123, "Dạ lớp tối T3 khai giảng 07/10 ạ")
        self.assertEqual(out["kind"], "staff")

    def test_conversation_not_yet_handed_to_the_team(self):
        own = MagicMock()
        own.send_message.side_effect = Exception("403")
        own.send_message.side_effect.response = SimpleNamespace(status_code=403)
        frappe = fake_frappe(linked=["123"])
        with patch.object(lead_chat, "frappe", frappe), patch.object(lead_chat, "admin_client"), \
                patch.object(lead_chat, "sender_client", return_value=own):
            with self.assertRaisesRegex(Exception, "chưa được giao"):
                lead_chat.send("CRM-LEAD-1", "Chào anh")

    def test_refusals(self):
        for frappe, kwargs in [(fake_frappe(readable=False, linked=["123"]), {}),
                               (fake_frappe(linked=["123"]), {"text": "   "}),
                               (fake_frappe(linked=["123"]), {"text": "x" * 2001}),
                               (fake_frappe(contact_id=None), {}),
                               (fake_frappe(linked=["123"]), {"sender": False})]:
            with self.assertRaises(Exception):
                self.send(frappe, **kwargs)


if __name__ == "__main__":
    unittest.main()
