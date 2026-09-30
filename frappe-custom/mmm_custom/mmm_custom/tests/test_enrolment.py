"""The registration record (D-117): fee maths, status on deposit, the page layouts and hooks."""

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

_real_frappe = sys.modules.get("frappe")
sys.modules["frappe"] = MagicMock()
try:
    import mmm_custom.setup as setup_mod
finally:
    if _real_frappe is None:
        del sys.modules["frappe"]
    else:
        sys.modules["frappe"] = _real_frappe

from mmm_custom import enrolment, hooks
from mmm_custom.enrolment import compute, next_status, promotion_discount, schedule_title


class TestFee(unittest.TestCase):
    def test_final_fee_and_balance(self):
        self.assertEqual(compute(2_000_000, 300_000, 500_000, 0),
                         {"discount_amount": 300_000, "final_fee": 1_700_000, "balance_due": 1_200_000})

    def test_paid_includes_the_deposit(self):
        self.assertEqual(compute(2_000_000, 0, 500_000, 2_000_000)["balance_due"], 0)

    def test_discount_never_exceeds_the_fee_and_empty_is_zero(self):
        self.assertEqual(compute(1_000_000, 5_000_000)["final_fee"], 0)
        self.assertEqual(compute(None, None, None, None),
                         {"discount_amount": 0, "final_fee": 0, "balance_due": 0})

    def test_promotion_discount(self):
        self.assertEqual(promotion_discount({"discount_type": "Percent", "discount_value": 10}, 2_000_000), 200_000)
        self.assertEqual(promotion_discount({"discount_type": "Amount", "discount_value": 300_000}, 2_000_000), 300_000)
        self.assertEqual(promotion_discount({"discount_type": "Amount", "discount_value": 9_000_000}, 2_000_000), 2_000_000)
        self.assertEqual(promotion_discount(None, 2_000_000), 0)


class TestStatus(unittest.TestCase):
    def test_a_deposit_moves_pending_payment_on(self):
        self.assertEqual(next_status("Pending Payment", 500_000, 0), "Deposit Paid")
        self.assertEqual(next_status("Pending Payment", 0, 2_000_000), "Deposit Paid")
        self.assertEqual(next_status("Pending Payment", 0, 0), "Pending Payment")

    def test_enrolment_and_cancellation_stay_a_person_s(self):
        self.assertEqual(next_status("Deposit Paid", 500_000, 2_000_000), "Deposit Paid")
        self.assertEqual(next_status("Lost", 500_000, 0), "Lost")


class TestSchedule(unittest.TestCase):
    def test_title_staff_pick_a_class_by(self):
        self.assertEqual(schedule_title("Excel cơ bản", "CN Quận 7", date(2026, 10, 4), "Tối 17:00–21:00"),
                         "Excel cơ bản · CN Quận 7 · 04/10/2026 · Tối")


class TestHooksOnADeal(unittest.TestCase):
    def deal(self, **values):
        doc = MagicMock()
        data = {"status": "Pending Payment", **values}
        doc.get.side_effect = data.get
        doc.status = data["status"]
        for k, v in data.items():
            setattr(doc, k, v)
        doc.update.side_effect = lambda d: [setattr(doc, k, v) for k, v in d.items()]
        return doc

    def test_validate_fills_fee_fields_and_moves_on_deposit(self):
        frappe = MagicMock()
        frappe.db.get_value.return_value = {"discount_type": "Percent", "discount_value": 10}
        doc = self.deal(tuition_fee=2_000_000, promotion="Ưu đãi tháng 10", deposit_amount=500_000)
        with patch.object(enrolment, "frappe", frappe):
            enrolment.validate(doc)
        self.assertEqual((doc.final_fee, doc.deal_value, doc.balance_due, doc.status),
                         (1_800_000, 1_800_000, 1_300_000, "Deposit Paid"))

    def test_class_of_another_course_is_refused(self):
        frappe = MagicMock()
        frappe.db.get_value.return_value = MagicMock(course="VP-WORD", start_date=date(2026, 10, 4), branch="CN Q7")
        frappe.throw.side_effect = Exception("refused")
        doc = self.deal(enrol_course="VP-EXCEL", course_schedule="abc123")
        with patch.object(enrolment, "frappe", frappe), self.assertRaisesRegex(Exception, "refused"):
            enrolment.validate(doc)

    def test_postponed_registration_sends_the_lead_back_to_nurturing(self):
        frappe = MagicMock()
        lead = frappe.get_doc.return_value
        doc = self.deal(status="Lost", lost_reason="Postponed", lead="CRM-LEAD-1")
        doc.has_value_changed.return_value = True
        with patch.object(enrolment, "frappe", frappe):
            enrolment.on_update(doc)
        lead.update.assert_called_once_with({"status": "Nurture", "converted": 0})
        lead.save.assert_called_once()

    def test_a_new_registration_tells_chatwoot_the_lead_is_registered(self):
        frappe = MagicMock()
        with patch.object(enrolment, "frappe", frappe):
            enrolment.after_insert(self.deal(lead="CRM-LEAD-1"))
        self.assertEqual(frappe.enqueue.call_args.args[0], "mmm_custom.lifecycle.push_status")
        self.assertEqual(frappe.enqueue.call_args.kwargs["lead"], "CRM-LEAD-1")

    def test_other_cancellations_leave_the_lead(self):
        frappe = MagicMock()
        doc = self.deal(status="Lost", lost_reason="Pricing", lead="CRM-LEAD-1")
        doc.has_value_changed.return_value = True
        with patch.object(enrolment, "frappe", frappe):
            enrolment.on_update(doc)
        frappe.get_doc.assert_not_called()


class TestPage(unittest.TestCase):
    DEAL_FIELDS = {f["fieldname"] for f in setup_mod.CATALOG_FIELDS["CRM Deal"]}
    STANDARD = {"territory", "deal_owner", "source", "lead", "organization", "next_step"}

    def fields(self, layout):
        return setup_mod.layout_fields(layout)

    def test_layouts_show_only_fields_the_deal_has(self):
        for layout in (enrolment.SIDE_PANEL, enrolment.DATA_FIELDS, enrolment.REQUIRED_FIELDS):
            self.assertEqual(self.fields(layout) - self.DEAL_FIELDS - self.STANDARD, set())

    def test_side_panel_is_a_registration_not_a_company(self):
        names = [s["name"] for s in enrolment.SIDE_PANEL]
        self.assertEqual(names, ["contacts_section", "enrolment_section", "fee_section", "source_section"])
        self.assertNotIn("organization", self.fields(enrolment.SIDE_PANEL))

    def test_fields_named_like_the_lead_s_are_copied_on_ghi_danh(self):
        lead = {f["fieldname"] for f in setup_mod.CATALOG_FIELDS["CRM Lead"]} | {"course_interest"}
        self.assertLessEqual({"course_interest", "placement_result", "voucher_code", "trial_date"}, lead & self.DEAL_FIELDS)

    def test_hooks(self):
        self.assertEqual(hooks.doc_events["CRM Deal"]["validate"], "mmm_custom.enrolment.validate")
        self.assertEqual(hooks.doc_events["CRM Deal"]["after_insert"], "mmm_custom.enrolment.after_insert")
        self.assertIn("mmm_custom.enrolment.update_deal_layouts", hooks.after_migrate)


if __name__ == "__main__":
    unittest.main()
