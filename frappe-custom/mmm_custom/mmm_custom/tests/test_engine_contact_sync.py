import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog

from mmm_custom.engine.chatwoot_setup import CONTACT_ATTRIBUTES, plan_contact_attributes
from mmm_custom.engine.effects import ChatwootEffects
from mmm_custom.engine.lead import contact_update
from mmm_custom.engine.state import ConversationState

CAT = demo_catalog()
EXCEL = CAT.courses["VP-EXCEL"]


class TestContactUpdate(unittest.TestCase):
    def test_what_the_bot_learned_goes_on_the_contact(self):
        fields = {"mobile_no": "+84912345678", "territory": "CN Dĩ An", "status": "Qualified"}
        self.assertEqual(contact_update(fields, [EXCEL], "CRM-LEAD-1"), {
            "phone_number": "+84912345678",
            "custom_attributes": {"crm_lead_id": "CRM-LEAD-1", "khoa_hoc_quan_tam": "Excel từ cơ bản đến nâng cao",
                                  "chi_nhanh": "CN Dĩ An", "trang_thai_lead": "tiềm năng"}})

    def test_only_known_values_are_sent(self):
        self.assertEqual(contact_update({}, [], "CRM-LEAD-1"), {"custom_attributes": {"crm_lead_id": "CRM-LEAD-1"}})

    def test_every_attribute_has_a_definition(self):
        keys = set(contact_update({"mobile_no": "+84912345678", "territory": "X", "status": "New"}, [EXCEL], "L")["custom_attributes"])
        self.assertEqual(keys, {k for k, _ in CONTACT_ATTRIBUTES})


class TestSaveLeadWritesTheContact(unittest.TestCase):
    def save(self, user):
        state = ConversationState("7", contact_id="9")
        with patch("mmm_custom.engine.repo.save_lead", return_value="CRM-LEAD-1", create=True), \
                patch("mmm_custom.engine.effects.compute_data_quality"):
            return ChatwootEffects(MagicMock(), user).save_lead(state, {"mobile_no": "+84912345678"}, [EXCEL], {"id": 9})

    def test_phone_and_attributes_in_one_call(self):
        user = MagicMock()
        self.assertEqual(self.save(user), "CRM-LEAD-1")
        user.update_contact.assert_called_once_with(9, {"crm_lead_id": "CRM-LEAD-1", "khoa_hoc_quan_tam": EXCEL.name},
                                                    phone_number="+84912345678")

    def test_a_phone_chatwoot_refuses_still_saves_the_attributes(self):
        user = MagicMock()
        user.update_contact.side_effect = [RuntimeError("422 phone taken"), {}]
        self.assertEqual(self.save(user), "CRM-LEAD-1")
        self.assertEqual(user.update_contact.call_args_list[1].kwargs, {})
        self.assertEqual(user.update_contact.call_count, 2)


class TestContactAttributeSetup(unittest.TestCase):
    def test_missing_definitions_are_planned(self):
        self.assertEqual(plan_contact_attributes({"crm_lead_id"}), [a for a in CONTACT_ATTRIBUTES if a[0] != "crm_lead_id"])


if __name__ == "__main__":
    unittest.main()
