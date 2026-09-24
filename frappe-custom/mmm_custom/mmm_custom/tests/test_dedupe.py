import os
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

# Ensure mmm_custom package is importable when running unittest standalone
APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.dedupe import (
    normalize_phone,
    build_lead_search_filters,
    find_matching_lead,
)


class TestDedupeLogic(unittest.TestCase):
    def test_normalize_phone_vn(self):
        # 1. Local VN number starting with 0
        self.assertEqual(normalize_phone("0901234567"), "+84901234567")
        # 2. Already formatted international number
        self.assertEqual(normalize_phone("+84901234567"), "+84901234567")
        # 3. Spaces inside phone number
        self.assertEqual(normalize_phone("090 123 4567"), "+84901234567")
        # 4. Dashes inside phone number
        self.assertEqual(normalize_phone("090-123-4567"), "+84901234567")
        # 5. Empty string
        self.assertEqual(normalize_phone(""), "")
        # 6. None value
        self.assertEqual(normalize_phone(None), "")
        # 7. Whitespace only string
        self.assertEqual(normalize_phone("   "), "")
        # 8. International non-VN number
        self.assertEqual(normalize_phone("+1 415 555 2671"), "+14155552671")

    def test_build_search_filters(self):
        # Both email and phone present
        filters = build_lead_search_filters("test@example.com", "0901234567")
        self.assertEqual(len(filters), 2)
        self.assertIn(["email_id", "=", "test@example.com"], filters)
        self.assertIn(["mobile_no", "=", "+84901234567"], filters)

        # Only email present
        email_only = build_lead_search_filters("test@example.com", "")
        self.assertEqual(email_only, [["email_id", "=", "test@example.com"]])

        # Only phone present
        phone_only = build_lead_search_filters(None, "0901234567")
        self.assertEqual(phone_only, [["mobile_no", "=", "+84901234567"]])

    def test_build_search_filters_empty(self):
        # Both empty or None
        self.assertEqual(build_lead_search_filters("", None), [])
        self.assertEqual(build_lead_search_filters(None, ""), [])
        self.assertEqual(build_lead_search_filters("   ", None), [])
        self.assertEqual(build_lead_search_filters("", "   "), [])

    def test_find_matching_lead_no_filters(self):
        # Should return None without making any DB queries if no filters
        result = find_matching_lead(None, None)
        self.assertIsNone(result)

        result_blank = find_matching_lead("", "")
        self.assertIsNone(result_blank)

    def test_find_matching_lead_without_frappe(self):
        # When frappe is not installed or import fails
        with patch.dict(sys.modules, {"frappe": None}):
            result = find_matching_lead("test@example.com", "0901234567")
            self.assertIsNone(result)

        original_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "frappe":
                raise ImportError("No module named 'frappe'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = find_matching_lead("test@example.com", "0901234567")
            self.assertIsNone(result)

    def test_find_matching_lead_found(self):
        mock_frappe = MagicMock()
        expected_lead = {
            "name": "CRM-LEAD-2026-00001",
            "first_name": "Nguyen Van A",
            "email_id": "test@example.com",
            "mobile_no": "+84901234567",
            "chatwoot_contact_id": "123",
        }
        mock_frappe.get_all.return_value = [expected_lead]

        with patch.dict(sys.modules, {"frappe": mock_frappe}):
            lead = find_matching_lead("test@example.com", "0901234567")
            self.assertEqual(lead, expected_lead)
            mock_frappe.get_all.assert_called_once_with(
                "CRM Lead",
                or_filters=[
                    ["email_id", "=", "test@example.com"],
                    ["mobile_no", "=", "+84901234567"],
                ],
                fields=["name", "first_name", "email_id", "mobile_no", "chatwoot_contact_id"],
                limit=1,
            )

    def test_find_matching_lead_not_found(self):
        mock_frappe = MagicMock()
        mock_frappe.get_all.return_value = []

        with patch.dict(sys.modules, {"frappe": mock_frappe}):
            lead = find_matching_lead("notfound@example.com", "0909999999")
            self.assertIsNone(lead)
            mock_frappe.get_all.assert_called_once()


if __name__ == "__main__":
    unittest.main()
