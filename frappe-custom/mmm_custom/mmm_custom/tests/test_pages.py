import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom import pages


class TestMergePages(unittest.TestCase):
    def test_first_page(self):
        self.assertEqual(pages.merge_pages("", "Ngôi Sao Sáng"), "Ngôi Sao Sáng")

    def test_second_page_is_appended_once(self):
        both = pages.merge_pages("Ngôi Sao Sáng", "Tin học Ngôi Sao")
        self.assertEqual(both, "Ngôi Sao Sáng, Tin học Ngôi Sao")
        self.assertEqual(pages.merge_pages(both, "Ngôi Sao Sáng"), both)

    def test_no_page_keeps_current(self):
        self.assertEqual(pages.merge_pages("A", ""), "A")
        self.assertEqual(pages.merge_pages(None, None), "")


class TestListColumn(unittest.TestCase):
    def test_inserted_after_the_name(self):
        cols = [{"key": "lead_name"}, {"key": "status"}]
        self.assertEqual([c["key"] for c in pages.add_column(cols)], ["lead_name", "facebook_page", "status"])

    def test_already_there(self):
        self.assertIsNone(pages.add_column([{"key": "lead_name"}, {"key": "facebook_page"}]))

    def test_appended_without_a_name_column(self):
        self.assertEqual(pages.add_column([{"key": "status"}])[-1]["key"], "facebook_page")


class TestPageOfInbox(unittest.TestCase):
    def test_looks_up_the_channel_connection(self):
        frappe = MagicMock()
        frappe.db.get_value.return_value = "Ngôi Sao Sáng "
        with patch.object(pages, "frappe", frappe):
            self.assertEqual(pages.page_of_inbox("3"), "Ngôi Sao Sáng")
        frappe.db.get_value.assert_called_once_with("Channel Connection", {"chatwoot_inbox_id": 3}, "display_name")

    def test_no_inbox(self):
        with patch.object(pages, "frappe", MagicMock()) as frappe:
            self.assertEqual(pages.page_of_inbox(""), "")
            frappe.db.get_value.assert_not_called()


if __name__ == "__main__":
    unittest.main()
