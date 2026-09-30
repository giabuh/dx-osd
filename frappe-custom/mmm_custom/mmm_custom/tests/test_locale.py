"""Every word of the customer journey has its Vietnamese label in crm/crm/locale/vi.po (D-116, D-117)."""

import re
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

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

from mmm_custom import lifecycle

PO = APP_DIR.parent.parent / "crm" / "crm" / "locale" / "vi.po"


def translations():
    text = PO.read_text(encoding="utf-8")
    return {m.group(1): m.group(2) for m in re.finditer(r'^msgid "(.*)"\nmsgstr "(.*)"$', text, re.M)}


class TestVietnamese(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vi = translations()

    def assertTranslated(self, words):
        missing = [w for w in words if not self.vi.get(w)]
        self.assertEqual(missing, [])

    def test_every_status_has_its_label(self):
        self.assertTranslated([s[0] for s in lifecycle.LEAD_STATUSES + lifecycle.DEAL_STATUSES])
        for key, label, *_ in lifecycle.LEAD_STATUSES:
            self.assertEqual(self.vi[key], label, key)  # vi.po and the labels mmm_custom writes agree
        for key, label, *_ in lifecycle.DEAL_STATUSES:
            if key != lifecycle.LOST:  # "Lost" is also the Lead status type; it reads as a cancelled registration
                self.assertEqual(self.vi[key], label, key)

    def test_every_lost_reason_is_translated(self):
        self.assertTranslated([r for r, _ in lifecycle.LOST_REASONS])

    def test_every_lead_custom_field_is_translated(self):
        fields = setup_mod.CATALOG_FIELDS["CRM Lead"] + setup_mod.AI_FIELDS
        self.assertTranslated([f["label"] for f in fields] + ["Course Interest", "Branch", "Data Quality",
                                                              "Chatwoot Contact ID"])

    def test_every_deal_custom_field_is_translated(self):
        self.assertTranslated([f["label"] for f in setup_mod.CATALOG_FIELDS.get("CRM Deal", [])
                               if f["fieldtype"] not in ("Column Break",)])

    def test_core_words_of_the_journey(self):
        self.assertEqual(self.vi["Lead"], "Khách hàng tiềm năng")  # was "Chì" (the metal)
        self.assertEqual(self.vi["Leads"], "Khách hàng tiềm năng")
        self.assertEqual(self.vi["Deals"], "Học viên đăng ký")
        self.assertEqual(self.vi["Convert to Deal"], "Ghi danh")
        self.assertEqual(self.vi["Territory"], "Chi nhánh")
        leftovers = {k: v for k, v in self.vi.items() if re.search(r"\bDeals?\b|Lãnh thổ|^Chì$", v)}
        self.assertEqual(leftovers, {})


if __name__ == "__main__":
    unittest.main()
