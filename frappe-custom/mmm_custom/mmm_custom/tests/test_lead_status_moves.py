"""D-116: status moves the engine and events make on a real CRM Lead (repo + lifecycle hooks, frappe mocked)."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mmm_custom import lifecycle
from mmm_custom.engine import repo
from mmm_custom.engine.state import ConversationState


class FakeLead(dict):
    def __init__(self, **values):
        super().__init__({"name": "CRM-LEAD-1", "status": "New", "lost_reason": "", "lead_owner": "", "first_name": "Lan",
                          **values})
        self.flags = MagicMock()
        self.meta = MagicMock()
        self.meta.has_field = lambda f: f not in ("not_a_field",)
        self.saved = 0

    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        if key in ("flags", "meta", "saved"):
            object.__setattr__(self, key, value)
        else:
            self[key] = value

    def set(self, key, value):
        self[key] = value

    def save(self, **kw):
        self.saved += 1

    insert = save


def fake_frappe(doc):
    frappe = MagicMock()
    frappe.get_doc.return_value = doc
    frappe.db.exists.return_value = True
    return frappe


class TestHandoffAndReply(unittest.TestCase):
    def test_handoff_makes_a_new_or_qualified_lead_contacted(self):
        for start in ("New", "Qualified", "Nurture"):
            doc = FakeLead(status=start)
            with patch.object(repo, "frappe", fake_frappe(doc)):
                repo.set_lead_owner("CRM-LEAD-1", "mai@crm")
            self.assertEqual((doc["lead_owner"], doc["status"]), ("mai@crm", "Contacted"), start)

    def test_handoff_never_undoes_a_later_step(self):
        for start in ("Trial Booked", "Converted"):
            doc = FakeLead(status=start)
            with patch.object(repo, "frappe", fake_frappe(doc)):
                repo.set_lead_owner("CRM-LEAD-1", "mai@crm")
            self.assertEqual(doc["status"], start)

    def test_first_reply_marks_contacted_once(self):
        doc = FakeLead(status="Qualified")
        with patch.object(repo, "frappe", fake_frappe(doc)):
            repo.lead_contacted("CRM-LEAD-1")
            repo.lead_contacted("CRM-LEAD-1")
        self.assertEqual((doc["status"], doc.saved), ("Contacted", 1))

    def test_a_failing_status_write_never_breaks_the_webhook(self):
        frappe = MagicMock()
        frappe.get_doc.side_effect = RuntimeError("db")
        with patch.object(repo, "frappe", frappe):
            repo.lead_contacted("CRM-LEAD-1")
        frappe.log_error.assert_called_once()


class TestTrialBooking(unittest.TestCase):
    def test_trial_sets_status_and_date(self):
        from datetime import date

        doc = FakeLead(status="Contacted")
        frappe = fake_frappe(doc)
        frappe.db.exists.return_value = False  # no task yet
        frappe.utils.getdate.return_value = date(2026, 10, 1)
        with patch.object(repo, "frappe", frappe):
            repo.create_trial_task("CRM-LEAD-1", "Excel · Thứ ba, 06/10 · Tối · CN Q7")
        self.assertEqual(doc["status"], "Trial Booked")
        self.assertEqual(doc["trial_date"], date(2026, 10, 6))


class TestBotStatusOnSave(unittest.TestCase):
    def save(self, doc, status):
        state = ConversationState("7", contact_id="9", lead="CRM-LEAD-1")
        with patch.object(repo, "frappe", fake_frappe(doc)):
            repo.save_lead(state, {"status": status}, [], {"id": 9})

    def test_unqualified_is_saved_with_its_reason(self):
        doc = FakeLead()
        self.save(doc, "Unqualified")
        self.assertEqual((doc["status"], doc["lost_reason"]), ("Unqualified", "Existing Student"))

    def test_spam_is_junk_with_its_reason(self):
        doc = FakeLead()
        self.save(doc, "Junk")
        self.assertEqual((doc["status"], doc["lost_reason"]), ("Junk", "Spam"))

    def test_a_status_a_person_set_stays(self):
        doc = FakeLead(status="Nurture")
        self.save(doc, "Qualified")
        self.assertEqual(doc["status"], "Nurture")

    def test_a_real_customer_leaves_the_bot_s_lost_status(self):
        doc = FakeLead(status="Unqualified", lost_reason="Existing Student")
        self.save(doc, "Qualified")
        self.assertEqual((doc["status"], doc["lost_reason"]), ("Qualified", ""))


class TestChatwootStatus(unittest.TestCase):
    def hook(self, changed=True, contact="9"):
        doc = MagicMock()
        doc.name, doc.status = "CRM-LEAD-1", "Contacted"
        doc.get.side_effect = lambda k: {"chatwoot_contact_id": contact}.get(k)
        doc.has_value_changed.return_value = changed
        frappe = MagicMock()
        with patch.object(lifecycle, "frappe", frappe):
            lifecycle.on_lead_update(doc)
        return frappe.enqueue

    def test_status_change_is_pushed_to_the_contact(self):
        enqueue = self.hook()
        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.kwargs["lead"], "CRM-LEAD-1")

    def test_other_edits_or_no_contact_push_nothing(self):
        self.hook(changed=False).assert_not_called()
        self.hook(contact=None).assert_not_called()

    def test_push_writes_the_vietnamese_label(self):
        frappe = MagicMock()
        frappe.db.get_value.return_value = MagicMock(chatwoot_contact_id="9", status="Trial Booked")
        client = MagicMock()
        with patch.object(lifecycle, "frappe", frappe), patch("mmm_custom.lead_chat.admin_client", return_value=client):
            lifecycle.push_status("CRM-LEAD-1")
        client.update_contact.assert_called_once_with(9, {"trang_thai_lead": "Hẹn học thử / test"})


if __name__ == "__main__":
    unittest.main()
