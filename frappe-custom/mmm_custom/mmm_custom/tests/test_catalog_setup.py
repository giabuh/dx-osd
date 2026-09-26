import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# setup.py imports frappe unconditionally; mock it only for this import so other modules keep
# their own ImportError fallbacks (e.g. bot_api's fake whitelist decorator).
with patch.dict(sys.modules, {"frappe": MagicMock()}):
    import mmm_custom.setup as setup_mod


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


class TestCatalogFields(unittest.TestCase):
    def test_territory_fields(self):
        names = [f["fieldname"] for f in setup_mod.CATALOG_FIELDS["CRM Territory"]]
        self.assertEqual(names, ["branch_code", "button_label", "branch_tier", "address", "hotline", "map_url", "aliases"])

    def test_button_labels_are_capped(self):
        for dt, fields in setup_mod.CATALOG_FIELDS.items():
            for f in fields:
                if f["fieldname"] == "button_label":
                    self.assertEqual(f.get("length"), 20, dt)


if __name__ == "__main__":
    unittest.main()
