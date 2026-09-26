import importlib
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, fill

from mmm_custom.engine.lead import contact_prefill, lead_updates, prefill_slots

CAT = demo_catalog()


def lead_source(value):
    return {"value": value, "source": "lead", "confidence": 1.0}


class TestLeadMapping(unittest.TestCase):
    def test_slots_to_lead_fields(self):
        slots = {"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An"), "learner": fill("child"),
                 "learner_age": fill(8), "preferred_shift": fill("evening"), "customer_name": fill("Lan"),
                 "phone": fill("+84901234567"), "learner_extra": {"asked": 1}}
        fields, courses = lead_updates(slots, CAT)
        self.assertEqual(fields, {"territory": "CN Dĩ An", "learner_type": "Con em", "learner_age": 8,
                                  "preferred_shift": "Tối", "first_name": "Lan", "mobile_no": "+84901234567"})
        self.assertEqual([c.code for c in courses], ["VP-EXCEL"])

    def test_prefill_from_lead_never_courses(self):
        values = {"territory": "CN Dĩ An", "mobile_no": "+84901234567", "first_name": "Lan", "learner_type": "Con em",
                  "preferred_shift": "Tối", "learner_age": 9}
        self.assertEqual(prefill_slots(values, CAT), {
            "branch": lead_source("CN Dĩ An"), "learner": lead_source("child"), "learner_age": lead_source(9),
            "preferred_shift": lead_source("evening"), "customer_name": lead_source("Lan"),
            "phone": lead_source("+84901234567")})

    def test_prefill_skips_values_outside_catalog(self):
        values = {"territory": "CS1 Bình Thạnh", "first_name": "Khách Messenger", "learner_type": "Học sinh",
                  "learner_age": 0, "mobile_no": ""}
        self.assertEqual(prefill_slots(values, CAT), {})

    def test_contact_name_prefills_customer_name(self):
        self.assertEqual(contact_prefill({"name": "Nguyễn Văn A"}, CAT),
                         {"customer_name": {"value": "Nguyễn Văn A", "source": "contact", "confidence": 1.0}})
        self.assertEqual(contact_prefill({"name": "Khách Messenger"}, CAT), {})
        self.assertEqual(contact_prefill({}, CAT), {})

    def test_every_slot_lead_field_exists_on_crm_lead(self):
        saved = sys.modules.get("frappe")
        sys.modules["frappe"] = MagicMock()
        try:
            setup_mod = importlib.import_module("mmm_custom.setup")
        finally:
            if saved is None:
                sys.modules.pop("frappe", None)
            else:
                sys.modules["frappe"] = saved
        custom = {f["fieldname"] for f in setup_mod.CATALOG_FIELDS["CRM Lead"]}
        for slot in CAT.slots:
            self.assertIn(slot.lead_field, custom | {"products", "territory", "first_name", "mobile_no"}, slot.key)


if __name__ == "__main__":
    unittest.main()
