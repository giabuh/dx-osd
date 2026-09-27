import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom import crm_links, hooks


class TestUrls(unittest.TestCase):
    def test_lead_url(self):
        self.assertEqual(crm_links.lead_url("https://crm.example.vn/", "CRM-LEAD-2026-00001"),
                         "https://crm.example.vn/crm/leads/CRM-LEAD-2026-00001")

    def test_chatwoot_contact_url(self):
        self.assertEqual(crm_links.chatwoot_contact_url("http://127.0.0.1:3000/", "2", "41"),
                         "http://127.0.0.1:3000/app/accounts/2/contacts/41")

    def test_bases_default_and_drop_trailing_slash(self):
        self.assertEqual(crm_links.crm_base({}), "http://127.0.0.1:8000")
        self.assertEqual(crm_links.crm_base({"crm_public_url": "https://crm.x/"}), "https://crm.x")
        self.assertEqual(crm_links.chatwoot_base({}), "http://127.0.0.1:3000")


class TestOpenChatUrl(unittest.TestCase):
    def frappe(self, contact_id):
        frappe = MagicMock()
        frappe.has_permission.return_value = True
        frappe.db.get_value.return_value = contact_id
        frappe.conf = {"chatwoot_base_url": "https://chat.x", "chatwoot_account_id": 3}
        return frappe

    def test_lead_without_contact_returns_none(self):
        for contact_id in (None, "", "abc"):
            with patch.object(crm_links, "frappe", self.frappe(contact_id)):
                self.assertIsNone(crm_links.open_chat_url("CRM-LEAD-1"))

    def test_lead_with_contact_opens_chatwoot(self):
        with patch.object(crm_links, "frappe", self.frappe("41")):
            self.assertEqual(crm_links.open_chat_url("CRM-LEAD-1"), "https://chat.x/app/accounts/3/contacts/41")

    def test_needs_read_permission_on_the_lead(self):
        frappe = self.frappe("41")
        frappe.has_permission.return_value = False
        frappe.PermissionError = PermissionError
        frappe.throw.side_effect = lambda msg, exc=Exception: (_ for _ in ()).throw(exc(msg))
        with patch.object(crm_links, "frappe", frappe):
            with self.assertRaises(PermissionError):
                crm_links.open_chat_url("CRM-LEAD-1")
        frappe.db.get_value.assert_not_called()


class TestFormScript(unittest.TestCase):
    def test_old_open_chat_script_is_switched_off_once(self):
        frappe = MagicMock()
        frappe.db.get_value.side_effect = [1, 0]
        with patch.object(crm_links, "frappe", frappe):
            crm_links.retire_lead_form_script()
            crm_links.retire_lead_form_script()
        frappe.db.set_value.assert_called_once_with("CRM Form Script", crm_links.FORM_SCRIPT, "enabled", 0)
        self.assertIn("mmm_custom.crm_links.retire_lead_form_script", hooks.after_migrate)


class TestBackfill(unittest.TestCase):
    def test_continues_past_a_failing_contact(self):
        frappe = MagicMock()
        frappe.conf = {"crm_public_url": "https://crm.x"}
        frappe.get_all.return_value = [_row("L1", "5"), _row("L2", "bad"), _row("L3", "7")]
        client = MagicMock()
        with patch.object(crm_links, "frappe", frappe), \
                patch("mmm_custom.chatwoot_client.ChatwootClient", return_value=client):
            self.assertEqual(crm_links.backfill_contact_links(), {"updated": 2, "failed": 1})
        client.update_contact.assert_any_call(7, {"ho_so_crm": "https://crm.x/crm/leads/L3"})


def _row(name, contact_id):
    row = MagicMock(chatwoot_contact_id=contact_id)
    row.name = name
    return row


if __name__ == "__main__":
    unittest.main()
