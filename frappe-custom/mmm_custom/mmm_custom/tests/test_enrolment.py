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
from mmm_custom.enrolment import (
    DEAL_DEFAULTS, RETIRED_FIELDS, compute, draft_plan, lead_after_deal_change, next_status, promotion_discount, schedule_title)


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

    def test_a_deposit_on_a_draft_moves_it_on_too(self):
        self.assertEqual(next_status("Awaiting Confirmation", 500_000, 0), "Deposit Paid")
        self.assertEqual(next_status("Awaiting Confirmation", 0, 0), "Awaiting Confirmation")

    def test_enrolment_and_cancellation_stay_a_person_s(self):
        self.assertEqual(next_status("Deposit Paid", 500_000, 2_000_000), "Deposit Paid")
        self.assertEqual(next_status("Lost", 500_000, 0), "Lost")


class TestLeadAfterDealChange(unittest.TestCase):
    def test_confirming_a_draft_registers_the_lead(self):
        for new in ("Pending Payment", "Deposit Paid", "Won"):
            self.assertEqual(lead_after_deal_change("Awaiting Confirmation", new, "", False),
                             {"status": "Converted", "converted": 1})

    def test_an_ordinary_change_leaves_the_lead(self):
        self.assertEqual(lead_after_deal_change("Pending Payment", "Deposit Paid", "", False), {})
        self.assertEqual(lead_after_deal_change(None, "Pending Payment", "", False), {})

    def test_postponed_goes_back_to_nurturing(self):
        for old in ("Pending Payment", "Awaiting Confirmation"):
            self.assertEqual(lead_after_deal_change(old, "Lost", "Postponed", False),
                             {"status": "Nurture", "converted": 0})

    def test_a_cancelled_registration_returns_the_lead_to_consulting(self):
        self.assertEqual(lead_after_deal_change("Pending Payment", "Lost", "Schedule Mismatch", False),
                         {"status": "Contacted", "converted": 0})
        self.assertEqual(lead_after_deal_change("Deposit Paid", "Lost", "", False),
                         {"status": "Contacted", "converted": 0})

    def test_a_cancelled_draft_never_moved_the_lead_so_it_stays(self):
        self.assertEqual(lead_after_deal_change("Awaiting Confirmation", "Lost", "Location Too Far", False), {})

    def test_another_live_registration_keeps_the_lead_registered(self):
        self.assertEqual(lead_after_deal_change("Pending Payment", "Lost", "Postponed", True), {})
        self.assertEqual(lead_after_deal_change("Pending Payment", "Lost", "Other", True), {})


class TestDraftPlan(unittest.TestCase):
    def test_a_customer_with_a_course_and_no_registration_gets_a_draft(self):
        self.assertEqual(draft_plan("Ongoing", None, "VP-EXCEL"), "create")
        self.assertEqual(draft_plan("Won", None, "VP-EXCEL"), "create")  # an existing student adding a course

    def test_nothing_without_a_course_or_for_a_lost_lead(self):
        self.assertEqual(draft_plan("Ongoing", None, ""), "")
        self.assertEqual(draft_plan("Lost", None, "VP-EXCEL"), "")

    def test_a_live_registration_is_never_doubled(self):
        for status in ("Awaiting Confirmation", "Pending Payment", "Deposit Paid"):
            self.assertEqual(draft_plan("Ongoing", {"status": status, "course_schedule": "abc"}, "VP-EXCEL", "x"), "")

    def test_a_class_chosen_later_goes_on_the_draft(self):
        live = {"status": "Awaiting Confirmation", "course_schedule": None}
        self.assertEqual(draft_plan("Ongoing", live, "VP-EXCEL", "abc"), "set_class")
        self.assertEqual(draft_plan("Ongoing", live, "VP-EXCEL", ""), "")


class TestCreateDraft(unittest.TestCase):
    def frappe(self, live=None, task_exists=False, status_type="Ongoing"):
        frappe = MagicMock()
        frappe.get_cached_value.return_value = status_type
        frappe.get_all.return_value = live or []
        frappe.db.exists.return_value = task_exists
        frappe.db.get_value.return_value = "sched-1"
        lead = frappe.get_doc.return_value
        lead.status, lead.lead_name, lead.lead_owner = "Contacted", "Lan", "mai@x.vn"
        lead.create_deal.return_value = "CRM-DEAL-1"
        return frappe, lead

    def run_it(self, frappe, *args, **kw):
        with patch.object(enrolment, "frappe", frappe):
            return enrolment.create_draft(*args, **kw)

    def test_creates_the_draft_and_a_task_and_leaves_the_lead(self):
        frappe, lead = self.frappe()
        self.assertEqual(self.run_it(frappe, "CRM-LEAD-1", "VP-EXCEL", "T", "", "bot"), "CRM-DEAL-1")
        self.assertEqual(lead.create_deal.call_args.args[2],
                         {"status": "Awaiting Confirmation", "enrol_course": "VP-EXCEL", "course_schedule": "sched-1"})
        lead.db_set.assert_not_called()
        task = frappe.get_doc.call_args_list[-1].args[0]
        self.assertEqual((task["title"], task["priority"], task["assigned_to"], task["reference_doctype"]),
                         ("Xác nhận ghi danh: Lan", "High", "mai@x.vn", "CRM Deal"))

    def test_a_live_registration_gets_no_second_draft_or_task(self):
        frappe, lead = self.frappe(live=[{"name": "CRM-DEAL-9", "status": "Pending Payment", "course_schedule": "s"}])
        self.assertEqual(self.run_it(frappe, "CRM-LEAD-1", "VP-EXCEL"), "CRM-DEAL-9")
        lead.create_deal.assert_not_called()

    def test_the_task_is_made_once(self):
        frappe, _ = self.frappe(task_exists=True)
        self.run_it(frappe, "CRM-LEAD-1", "VP-EXCEL")
        self.assertFalse([c for c in frappe.get_doc.call_args_list if isinstance(c.args[0], dict)])

    def test_a_class_chosen_later_is_set_on_the_draft(self):
        frappe, _ = self.frappe(live=[{"name": "CRM-DEAL-9", "status": "Awaiting Confirmation", "course_schedule": None}])
        deal = frappe.get_doc.return_value
        self.assertEqual(self.run_it(frappe, "CRM-LEAD-1", "VP-EXCEL", "T"), "CRM-DEAL-9")
        self.assertEqual(deal.course_schedule, "sched-1")
        deal.save.assert_called_once()

    def test_no_lead_or_course_is_nothing(self):
        frappe, _ = self.frappe()
        self.assertEqual(self.run_it(frappe, "", "VP-EXCEL"), "")
        self.assertEqual(self.run_it(frappe, "CRM-LEAD-1", ""), "")


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
        frappe.db.count.return_value = 0
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

    def cancel(self, before, others=0, **values):
        frappe = MagicMock()
        frappe.db.count.return_value = others
        lead = frappe.get_doc.return_value
        doc = self.deal(status="Lost", lead="CRM-LEAD-1", **values)
        doc.has_value_changed.return_value = True
        doc.get_doc_before_save.return_value = MagicMock(status=before)
        with patch.object(enrolment, "frappe", frappe):
            enrolment.on_update(doc)
        return frappe, lead

    def test_other_cancellations_send_the_lead_back_to_consulting(self):
        frappe, lead = self.cancel("Pending Payment", lost_reason="Pricing")
        lead.update.assert_called_once_with({"status": "Contacted", "converted": 0})
        lead.save.assert_called_once()

    def test_a_cancelled_draft_leaves_the_lead(self):
        frappe, lead = self.cancel("Awaiting Confirmation", lost_reason="Pricing")
        frappe.get_doc.assert_not_called()

    def test_another_live_registration_leaves_the_lead(self):
        frappe, lead = self.cancel("Pending Payment", others=1, lost_reason="Pricing")
        frappe.get_doc.assert_not_called()

    def test_confirming_a_draft_registers_the_lead(self):
        frappe = MagicMock()
        lead = frappe.get_doc.return_value
        doc = self.deal(status="Pending Payment", lead="CRM-LEAD-1")
        doc.has_value_changed.return_value = True
        doc.get_doc_before_save.return_value = MagicMock(status="Awaiting Confirmation")
        with patch.object(enrolment, "frappe", frappe):
            enrolment.on_update(doc)
        lead.update.assert_called_once_with({"status": "Converted", "converted": 1})
        self.assertTrue(lead.flags.registered)


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
        self.assertEqual(names, ["contacts_section", "learner_section", "enrolment_section", "fee_section",
                                 "source_section"])
        self.assertEqual(enrolment.LAYOUT_SENTINELS["Side Panel"], "learner_section")
        self.assertNotIn("organization", self.fields(enrolment.SIDE_PANEL))

    def test_fields_named_like_the_lead_s_are_copied_on_ghi_danh(self):
        lead = {f["fieldname"] for f in setup_mod.CATALOG_FIELDS["CRM Lead"]} | {"course_interest"}
        self.assertLessEqual({"course_interest", "placement_result", "voucher_code", "trial_date", "learner_type",
                              "learner_name", "learner_age"}, lead & self.DEAL_FIELDS)

    def test_a_site_without_the_learner_fields_still_gets_a_valid_panel(self):
        out = setup_mod.keep_fields(enrolment.SIDE_PANEL, lambda f: not f.startswith("learner_"))
        learner = next(s for s in out if s["name"] == "learner_section")
        self.assertEqual(learner["columns"][0]["fields"], [])
        self.assertIn("contacts", out[0])
        self.assertIn("learner_name", self.fields(enrolment.SIDE_PANEL))  # the constant is untouched

    def test_payment_due_date_is_gone(self):
        self.assertEqual(RETIRED_FIELDS, ("payment_due_date",))
        self.assertNotIn("payment_due_date", self.DEAL_FIELDS)
        for layout in (enrolment.SIDE_PANEL, enrolment.DATA_FIELDS, enrolment.REQUIRED_FIELDS):
            self.assertNotIn("payment_due_date", self.fields(layout))

    def test_the_modal_asks_course_class_branch_and_deposit_only(self):
        self.assertEqual(self.fields(enrolment.REQUIRED_FIELDS),
                         {"enrol_course", "course_schedule", "territory", "deposit_amount"})

    def test_class_choices_follow_the_deal_s_branch(self):
        flt = next(f for f in setup_mod.CATALOG_FIELDS["CRM Deal"] if f["fieldname"] == "course_schedule")["link_filters"]
        self.assertIn("eval: doc.territory", flt)

    def test_deal_defaults_hide_status_and_use_vnd(self):
        self.assertEqual(DEAL_DEFAULTS, {"status": "Pending Payment", "currency": "VND"})

    def test_rewrite_removes_retired_fields_in_place_and_adds_the_branch(self):
        import json
        old = json.dumps([{"name": "first_tab", "sections": [{"name": "enrolment_section", "columns": [
            {"name": "column_r1", "fields": ["enrol_course", "course_schedule"]},
            {"name": "column_r2", "fields": ["deposit_amount", "payment_due_date"]}]}]}])
        self.assertEqual(json.loads(enrolment.rewrite_layout(old, "Required Fields"))[0]["sections"][0]["columns"][1]["fields"],
                         ["territory", "deposit_amount"])
        side = json.dumps(enrolment.SIDE_PANEL).replace('"deposit_date"', '"deposit_date", "payment_due_date"')
        self.assertNotIn("payment_due_date", enrolment.rewrite_layout(side, "Side Panel"))

    def test_hooks(self):
        self.assertEqual(hooks.doc_events["CRM Deal"]["validate"], "mmm_custom.enrolment.validate")
        self.assertEqual(hooks.doc_events["CRM Deal"]["after_insert"], "mmm_custom.enrolment.after_insert")
        self.assertIn("mmm_custom.enrolment.update_deal_layouts", hooks.after_migrate)
        for hook in ("mmm_custom.enrolment.ensure_deal_defaults", "mmm_custom.setup.ensure_vnd"):
            self.assertIn(hook, hooks.after_migrate)
            self.assertIn(hook, hooks.after_install)


if __name__ == "__main__":
    unittest.main()
