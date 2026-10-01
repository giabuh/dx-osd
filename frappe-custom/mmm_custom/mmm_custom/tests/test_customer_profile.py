import json
import sys
import unittest
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

from mmm_custom import customer_profile, hooks

SLOTS = json.loads((APP_DIR / "mmm_custom" / "demo" / "saoviet" / "bot_slots.json").read_text(encoding="utf-8"))


class TestCards(unittest.TestCase):
    def test_registration_card(self):
        deal = {"name": "CRM-DEAL-1", "status": "Pending Payment", "enrol_course": "EXCEL-NC",
                "course_schedule": "CS-9", "class_start_date": "2026-10-04", "final_fee": 1800000,
                "paid_amount": 500000, "balance_due": 1300000}
        out = customer_profile.registration_view(deal, {"EXCEL-NC": "Excel nâng cao"},
                                                 {"CS-9": "Excel nâng cao · CN Dĩ An · 04/10/2026 · Tối"})
        self.assertEqual(out["label"], "Chờ đóng phí")
        self.assertEqual(out["colour"], "orange")
        self.assertTrue(out["live"])
        self.assertEqual((out["course"], out["paid"], out["balance"]), ("Excel nâng cao", 500000, 1300000))

    def test_a_registration_without_class_or_fee(self):
        out = customer_profile.registration_view({"name": "D", "status": "Won", "enrol_course": "X"}, {}, {})
        self.assertEqual((out["course"], out["class_title"], out["final_fee"], out["live"]), ("X", "", 0, False))

    def test_bot_card_counts_quiz_offers(self):
        out = customer_profile.bot_view({"status": "handed_off", "turns": 7, "is_returning": 1,
                                         "quiz_offers": json.dumps({"excel": "done", "word": "declined"})}, "Bảo")
        self.assertEqual(out, {"status": "handed_off", "label": "Đã chuyển tư vấn viên", "consultant": "Bảo",
                               "turns": 7, "returning": True, "quiz_offers": 2})
        self.assertIsNone(customer_profile.bot_view(None))
        self.assertEqual(customer_profile.bot_view({"status": "active", "quiz_offers": "not json"})["quiz_offers"], 0)

    def test_quiz_score_only_when_done(self):
        done = customer_profile.quiz_view({"quiz": "q1", "status": "done", "score": 8, "total": 10, "level": "Khá",
                                           "voucher_code": "SV-1"}, {"q1": "Test Excel"})
        self.assertEqual((done["quiz"], done["score"], done["label"], done["voucher"]),
                         ("Test Excel", "8/10", "Đã làm xong", "SV-1"))
        self.assertEqual(customer_profile.quiz_view({"quiz": "q1", "status": "started", "score": 3, "total": 10},
                                                    {})["score"], "")

    def test_class_seats_left(self):
        row = {"name": "CS-9", "seats": 20, "start_date": "2026-10-04"}
        self.assertEqual(customer_profile.class_view(row, "Excel", 18)["seats_left"], 2)
        self.assertEqual(customer_profile.class_view(row, "Excel", 25)["seats_left"], 0)
        self.assertIsNone(customer_profile.class_view({"name": "CS-1", "seats": 0}, "Excel", 3)["seats_left"])


class Row(dict):
    """frappe._dict: a row read by key and by attribute."""
    __getattr__ = dict.get


class TestAccess(unittest.TestCase):
    def test_profile_needs_the_lead(self):
        frappe = MagicMock()
        frappe.has_permission.return_value = False
        frappe.PermissionError = PermissionError
        frappe.throw.side_effect = lambda msg, exc=Exception: (_ for _ in ()).throw(exc(msg))
        with patch.object(customer_profile, "frappe", frappe):
            with self.assertRaises(PermissionError):
                customer_profile.profile("CRM-LEAD-1")
        frappe.get_all.assert_not_called()

    def test_profile_reads_the_leads_records(self):
        frappe = MagicMock()
        frappe.has_permission.return_value = True
        rows = {
            "CRM Deal": [Row(name="D1", status="Awaiting Confirmation", enrol_course="EX", course_schedule="")],
            "Bot Conversation": [], "Quiz Attempt": [], "CRM Lead": [],
        }
        frappe.get_all.side_effect = lambda doctype, **kw: rows.get(doctype, [])
        with patch.object(customer_profile, "frappe", frappe):
            out = customer_profile.profile("CRM-LEAD-1")
        self.assertEqual([r["label"] for r in out["registrations"]], ["Chờ xác nhận"])
        self.assertIsNone(out["bot"])
        deal_call = next(c for c in frappe.get_all.call_args_list if c.args[0] == "CRM Deal")
        self.assertEqual(deal_call.kwargs["filters"], {"lead": "CRM-LEAD-1"})


class TestSidePanel(unittest.TestCase):
    def test_every_panel_field_is_a_lead_field_or_a_known_custom_one(self):
        custom = {f["fieldname"] for f in setup_mod.CATALOG_FIELDS["CRM Lead"]} | \
                 {f["fieldname"] for f in setup_mod.AI_FIELDS} | {"course_interest", "data_quality"}
        standard = {"first_name", "mobile_no", "email", "gender", "lead_owner", "territory", "source"}
        fields = {f for s in setup_mod.LEAD_SIDE_PANEL for c in s["columns"] for f in c["fields"]}
        self.assertEqual(fields - custom - standard, set())
        self.assertNotIn("organization", fields)

    def test_panel_drops_fields_the_site_lacks(self):
        out = setup_mod.lead_side_panel(lambda f: f != "learning_goal")
        needs = next(s for s in out if s["name"] == "needs_section")
        self.assertNotIn("learning_goal", needs["columns"][0]["fields"])
        self.assertIn("learning_goal", setup_mod.LEAD_SIDE_PANEL[1]["columns"][0]["fields"])  # constant untouched

    def test_custom_sections_are_flagged(self):
        custom = [s["name"] for s in setup_mod.LEAD_SIDE_PANEL if s.get("custom")]
        self.assertEqual(custom, ["registrations_section"])
        self.assertIn(setup_mod.LEAD_PANEL_SENTINEL, [s["name"] for s in setup_mod.LEAD_SIDE_PANEL])

    def test_hooks_write_the_panel(self):
        self.assertIn("mmm_custom.setup.update_lead_side_panel", hooks.after_migrate)

    def test_goal_and_level_land_on_the_lead(self):
        by_key = {s["slot_key"]: s for s in SLOTS}
        for key, field in setup_mod.SLOT_LEAD_FIELDS.items():
            self.assertEqual(by_key[key]["lead_field"], field)
        labels = {"goal": {"office": "Công việc văn phòng"}}
        out = setup_mod.slot_backfill({"goal": {"value": "office"}, "level": {"value": "basic"},
                                       "course": {"value": "EX"}}, labels)
        self.assertEqual(out, {"learning_goal": "Công việc văn phòng", "current_level": "basic"})
        self.assertEqual(setup_mod.slot_backfill({"goal": {"value": ""}}, labels), {})


if __name__ == "__main__":
    unittest.main()
