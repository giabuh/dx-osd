import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog

from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import understand
from mmm_custom.referral import ALPHABET, PREFIX, code_for, find_code

CAT = demo_catalog()


class TestReferralCodes(unittest.TestCase):
    def test_codes_are_stable_readable_and_salted(self):
        code = code_for("CRM-LEAD-2026-00001")
        self.assertEqual(code, code_for("CRM-LEAD-2026-00001"))
        self.assertNotEqual(code, code_for("CRM-LEAD-2026-00001", salt=1))
        self.assertTrue(code.startswith(PREFIX) and len(code) == 7 and all(c in ALPHABET for c in code[2:]))

    def test_find_code_in_a_message(self):
        self.assertEqual(find_code("mã của bạn mình là svk7m2q nha"), "SVK7M2Q")
        self.assertEqual(find_code("SVK7M2Q"), "SVK7M2Q")
        self.assertEqual(find_code("SV0K7M2 có số 0"), "")  # 0 is not in the alphabet
        self.assertEqual(find_code("sđt 0901234567"), "")

    def test_the_bot_hears_a_code_anywhere_without_asking(self):
        u = understand("được bạn giới thiệu, mã SVK7M2Q, học excel", ConversationState("1"), CAT)
        self.assertEqual(u.fills["referral_code"]["value"], "SVK7M2Q")
        self.assertEqual(u.fills["course"]["value"], "VP-EXCEL")
        self.assertNotIn("svk7m2q", u.unmatched)
        self.assertIn("referral", u.skills)


if __name__ == "__main__":
    unittest.main()
