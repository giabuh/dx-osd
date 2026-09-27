import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom import lead_ads


def field(fieldname, fieldtype="Data", label=None, hidden=0, read_only=0):
    return {"fieldname": fieldname, "fieldtype": fieldtype, "label": label or fieldname.title(), "hidden": hidden,
            "read_only": read_only}


class TestLeadFieldChoices(unittest.TestCase):
    def test_name_email_phone_first_then_editable_data_fields(self):
        meta = [field("status", "Select"), field("email", label="Email"), field("notes", "Table"),
                field("secret", hidden=1), field("lead_name", read_only=1), field("city"), field("first_name", label="Tên"),
                field("facebook_lead_id"), field("source", "Link"), field("course_interest")]
        choices = lead_ads.lead_field_choices(meta)
        self.assertEqual([c["value"] for c in choices],
                         ["first_name", "email", "mobile_no", "status", "city", "course_interest"])
        self.assertEqual(choices[0]["label"], "Tên")  # the site's own label wins
        self.assertEqual(choices[2]["label"], "Mobile No")

    def test_meta_objects_work_like_dicts(self):
        meta = [MagicMock(fieldname="city", fieldtype="Data", label="City", hidden=0, read_only=0)]
        self.assertEqual(lead_ads.lead_field_choices(meta)[-1], {"value": "city", "label": "City"})


class TestCleanSourceValues(unittest.TestCase):
    NEW = {"access_token": " tok ", "facebook_page": "P1", "facebook_lead_form": "F1", "owner": "x", "type": "Other"}

    def test_new_source_gets_defaults_and_only_whitelisted_fields(self):
        self.assertEqual(lead_ads.clean_source_values(self.NEW, True), {
            "access_token": "tok", "facebook_page": "P1", "facebook_lead_form": "F1",
            "background_sync_frequency": "Hourly", "enabled": 1})

    def test_new_source_requires_token_page_and_form(self):
        for key in ("access_token", "facebook_page", "facebook_lead_form"):
            with self.assertRaises(ValueError):
                lead_ads.clean_source_values({**self.NEW, key: " "}, True)

    def test_blank_token_on_update_keeps_the_stored_one(self):
        out = lead_ads.clean_source_values({"access_token": "", "background_sync_frequency": "Daily", "enabled": "0"},
                                           False)
        self.assertEqual(out, {"background_sync_frequency": "Daily", "enabled": 0})

    def test_unknown_frequency_is_rejected(self):
        with self.assertRaises(ValueError):
            lead_ads.clean_source_values({**self.NEW, "background_sync_frequency": "Every second"}, True)


class TestHelpers(unittest.TestCase):
    def test_mapping_rejects_unknown_fields_and_allows_clearing(self):
        self.assertEqual(lead_ads.clean_mapping('{"full_name": "first_name", "city": ""}', {"first_name"}),
                         {"full_name": "first_name", "city": ""})
        with self.assertRaises(ValueError):
            lead_ads.clean_mapping({"q": "owner"}, {"first_name"})

    def test_page_choices_drop_facebook_tokens(self):
        pages = [{"id": "1", "name": "Sao Việt", "access_token": "secret", "category": "Edu",
                  "forms": [{"id": "9", "name": "Form hè", "questions": []}]}]
        self.assertEqual(lead_ads.page_choices(pages),
                         [{"id": "1", "name": "Sao Việt", "forms": [{"id": "9", "name": "Form hè"}]}])

    def test_short_error_is_the_last_line(self):
        self.assertEqual(lead_ads.short_error("Traceback:\n  File x\nValueError: bad phone\n\n"), "ValueError: bad phone")
        self.assertEqual(lead_ads.short_error(None), "")


class TestAccess(unittest.TestCase):
    def test_non_manager_is_refused_before_any_read(self):
        frappe = MagicMock()
        frappe.PermissionError = PermissionError
        frappe.throw.side_effect = lambda msg, exc=Exception: (_ for _ in ()).throw(exc(msg))
        with patch.object(lead_ads, "frappe", frappe), patch.object(lead_ads, "can_open_bot", return_value=False):
            for call in (lead_ads.list_sources, lead_ads.pages, lambda: lead_ads.retry("LOG-1"),
                         lambda: lead_ads.save_source({"name": "x"})):
                with self.assertRaises(PermissionError):
                    call()
        frappe.get_all.assert_not_called()
        frappe.get_doc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
