"""One Lead writer for a Chatwoot contact (D-116): repo.ensure_lead, used by the Chatwoot webhook."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine_fixtures import demo_catalog
from test_lead_status_moves import FakeLead

from mmm_custom.engine import repo

EXCEL = demo_catalog().courses["VP-EXCEL"]


class Lead(FakeLead):
    def append(self, table, row):
        self.setdefault(table, []).append(MagicMock(**row))


def run(contact, found=None, courses=(), claimed=True, doc=None):
    doc = doc or Lead()
    frappe = MagicMock()
    frappe.get_doc.return_value = doc
    frappe.new_doc.return_value = doc
    frappe.cache().set.return_value = claimed
    frappe.db.get_value.return_value = None
    with patch.object(repo, "frappe", frappe), patch.object(repo, "find_lead", side_effect=found or [None]) as find, \
            patch.object(repo.time, "sleep") as sleep:
        out = repo.ensure_lead(contact, "Facebook Messenger", list(courses))
    return out, doc, frappe, find, sleep


class TestEnsureLead(unittest.TestCase):
    def test_a_lead_that_no_longer_validates_still_gets_linked(self):
        class Broken(Lead):
            def save(self, **kw):
                raise ValueError("Please specify a reason for losing the lead.")

        doc = Broken(chatwoot_contact_id="")
        (name, created), _, frappe, _, _ = run({"id": 5, "name": "Lan"}, found=["CRM-LEAD-1"], doc=doc)
        self.assertEqual((name, created), ("CRM-LEAD-1", False))
        frappe.log_error.assert_called_once()
        frappe.db.set_value.assert_called_once_with("CRM Lead", "CRM-LEAD-1", "chatwoot_contact_id", "5")

    def test_existing_lead_is_linked_named_and_given_the_course(self):
        doc = Lead(first_name="Khách Messenger", mobile_no="")
        (name, created), doc, frappe, _, _ = run({"id": 456, "name": "Trần Văn B", "phone_number": "0912345678"},
                                                 found=["CRM-LEAD-1"], courses=[EXCEL], doc=doc)
        self.assertEqual((name, created), ("CRM-LEAD-1", False))
        self.assertEqual((doc["chatwoot_contact_id"], doc["first_name"], doc["lead_name"], doc["mobile_no"]),
                         ("456", "Trần Văn B", "Trần Văn B", "+84912345678"))
        self.assertEqual([p.product_code for p in doc["products"]], ["VP-EXCEL"])
        self.assertEqual(doc.saved, 1)
        frappe.new_doc.assert_not_called()

    def test_a_real_name_or_phone_a_person_entered_stays(self):
        doc = Lead(first_name="Lan", mobile_no="+84900000000", chatwoot_contact_id="1")
        run({"id": 2, "name": "Facebook User", "phone_number": "0912345678"}, found=["CRM-LEAD-1"], doc=doc)
        self.assertEqual((doc["first_name"], doc["mobile_no"], doc["chatwoot_contact_id"]), ("Lan", "+84900000000", "1"))

    def test_new_contact_becomes_a_new_lead_from_its_channel(self):
        doc = Lead(first_name="", status="")
        (_, created), doc, frappe, _, _ = run({"id": 9, "name": "", "email": "a@b.vn"}, doc=doc)
        self.assertTrue(created)
        frappe.new_doc.assert_called_once_with("CRM Lead")
        self.assertEqual((doc["first_name"], doc["email"], doc["source"], doc["chatwoot_contact_id"]),
                         ("Khách Messenger", "a@b.vn", "Facebook Messenger", "9"))
        self.assertEqual(doc["status"], "")  # the CRM default (New) applies

    def test_the_second_of_two_simultaneous_events_waits_and_finds_the_lead(self):
        (name, created), _, frappe, find, sleep = run({"id": 9, "name": "Lan"}, found=[None, "CRM-LEAD-7"], claimed=False)
        self.assertEqual((name, created), ("CRM-LEAD-7", False))
        frappe.get_doc.assert_called_once_with("CRM Lead", "CRM-LEAD-7")
        sleep.assert_called_once()
        self.assertEqual(find.call_count, 2)


if __name__ == "__main__":
    unittest.main()
