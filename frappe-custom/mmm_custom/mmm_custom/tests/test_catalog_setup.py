import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# setup.py imports frappe unconditionally; swap in a mock only for this import so other modules keep
# their own ImportError fallbacks. (patch.dict would also drop every module imported inside it.)
_real_frappe = sys.modules.get("frappe")
sys.modules["frappe"] = MagicMock()
try:
    import mmm_custom.setup as setup_mod
finally:
    if _real_frappe is None:
        del sys.modules["frappe"]
    else:
        sys.modules["frappe"] = _real_frappe


class TestEnsureCustomField(unittest.TestCase):
    def setUp(self):
        self.frappe = MagicMock()

    def test_inserts_when_missing(self):
        self.frappe.db.exists.return_value = False
        field = {"fieldname": "branch_code", "label": "Branch Code", "fieldtype": "Data"}
        with patch.object(setup_mod, "frappe", self.frappe):
            setup_mod.ensure_custom_field("CRM Territory", field)
        self.frappe.db.exists.assert_called_with("Custom Field", "CRM Territory-branch_code")
        doc = self.frappe.get_doc.call_args[0][0]
        self.assertEqual(doc["doctype"], "Custom Field")
        self.assertEqual(doc["dt"], "CRM Territory")
        self.assertEqual(doc["fieldname"], "branch_code")

    def test_updates_when_present(self):
        self.frappe.db.exists.return_value = True
        existing = MagicMock()
        self.frappe.get_doc.return_value = existing
        field = {"fieldname": "branch_code", "label": "Mã chi nhánh", "fieldtype": "Data"}
        with patch.object(setup_mod, "frappe", self.frappe):
            setup_mod.ensure_custom_field("CRM Territory", field)
        self.frappe.get_doc.assert_called_with("Custom Field", "CRM Territory-branch_code")
        self.assertEqual(existing.label, "Mã chi nhánh")
        existing.save.assert_called_once()

    def test_unchanged_field_is_not_saved(self):
        self.frappe.db.exists.return_value = True
        existing = MagicMock(fieldname="branch_code", label="Branch Code", fieldtype="Data")
        self.frappe.get_doc.return_value = existing
        with patch.object(setup_mod, "frappe", self.frappe):
            setup_mod.ensure_custom_field("CRM Territory", {"fieldname": "branch_code", "label": "Branch Code", "fieldtype": "Data"})
        existing.save.assert_not_called()


class TestCatalogFields(unittest.TestCase):
    def test_territory_fields(self):
        names = [f["fieldname"] for f in setup_mod.CATALOG_FIELDS["CRM Territory"]]
        self.assertEqual(names, ["branch_code", "button_label", "branch_tier", "address", "hotline", "map_url", "aliases"])

    def test_button_labels_are_capped(self):
        for dt, fields in setup_mod.CATALOG_FIELDS.items():
            for f in fields:
                if f["fieldname"] == "button_label":
                    self.assertEqual(f.get("length"), 20, dt)

    def test_product_fields(self):
        names = [f["fieldname"] for f in setup_mod.CATALOG_FIELDS["CRM Product"]]
        self.assertEqual(names, ["course_group", "button_label", "audience", "min_age", "max_age",
                                 "duration_text", "certificate", "offer", "aliases", "next_courses", "is_demo_data"])


if __name__ == "__main__":
    unittest.main()
