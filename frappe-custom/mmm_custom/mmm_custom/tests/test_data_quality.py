import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import mmm_custom.data_quality as dq_mod
from mmm_custom.data_quality import compute_data_quality


class TestComputeDataQuality(unittest.TestCase):
    def setUp(self):
        self.mock_frappe = MagicMock()

    def test_lead_not_found_returns_none(self):
        self.mock_frappe.db.get_value.return_value = None
        with patch.object(dq_mod, "frappe", self.mock_frappe):
            result = compute_data_quality("CRM-LEAD-MISSING")
        self.assertIsNone(result)

    def test_missing_email_and_phone(self):
        self.mock_frappe.db.get_value.return_value = {
            "first_name": "Test User",
            "email": None,
            "mobile_no": None,
        }
        with patch.object(dq_mod, "frappe", self.mock_frappe):
            result = compute_data_quality("CRM-LEAD-001")
        self.assertEqual(result, "Thiếu SĐT/Email")
        self.mock_frappe.db.set_value.assert_called_with(
            "CRM Lead", "CRM-LEAD-001", "data_quality", "Thiếu SĐT/Email"
        )

    def test_missing_email_empty_phone(self):
        self.mock_frappe.db.get_value.return_value = {
            "first_name": "Test User",
            "email": "",
            "mobile_no": "",
        }
        with patch.object(dq_mod, "frappe", self.mock_frappe):
            result = compute_data_quality("CRM-LEAD-002")
        self.assertEqual(result, "Thiếu SĐT/Email")

    def test_complete_no_duplicates(self):
        self.mock_frappe.db.get_value.return_value = {
            "first_name": "Test User",
            "email": "test@example.com",
            "mobile_no": "+84901234567",
        }
        self.mock_frappe.db.count.return_value = 0
        with patch.object(dq_mod, "frappe", self.mock_frappe):
            result = compute_data_quality("CRM-LEAD-003")
        self.assertEqual(result, "Đầy đủ")
        self.mock_frappe.db.set_value.assert_called_with(
            "CRM Lead", "CRM-LEAD-003", "data_quality", "Đầy đủ"
        )

    def test_duplicate_by_email(self):
        self.mock_frappe.db.get_value.return_value = {
            "first_name": "Test User",
            "email": "dup@example.com",
            "mobile_no": "+84901234567",
        }
        # Email duplicate found
        self.mock_frappe.db.count.return_value = 1
        with patch.object(dq_mod, "frappe", self.mock_frappe):
            result = compute_data_quality("CRM-LEAD-004")
        self.assertEqual(result, "Nghi trùng")
        self.mock_frappe.db.set_value.assert_called_with(
            "CRM Lead", "CRM-LEAD-004", "data_quality", "Nghi trùng"
        )

    def test_duplicate_by_phone_only(self):
        self.mock_frappe.db.get_value.return_value = {
            "first_name": "Test User",
            "email": "unique@example.com",
            "mobile_no": "+84901234567",
        }

        def count_side_effect(doctype, filters):
            if "email" in filters:
                return 0  # no email duplicate
            if "mobile_no" in filters:
                return 2  # phone duplicate found
            return 0

        self.mock_frappe.db.count.side_effect = count_side_effect
        with patch.object(dq_mod, "frappe", self.mock_frappe):
            result = compute_data_quality("CRM-LEAD-005")
        self.assertEqual(result, "Nghi trùng")

    def test_has_phone_only_no_duplicates(self):
        """Lead with phone but no email, and no duplicates → Đầy đủ."""
        self.mock_frappe.db.get_value.return_value = {
            "first_name": "Nguyễn Văn A",
            "email": None,
            "mobile_no": "+84901234567",
        }
        self.mock_frappe.db.count.return_value = 0
        with patch.object(dq_mod, "frappe", self.mock_frappe):
            result = compute_data_quality("CRM-LEAD-006")
        self.assertEqual(result, "Đầy đủ")


if __name__ == "__main__":
    unittest.main()
