import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import mmm_custom.data_quality as dq
from mmm_custom.data_quality import (COMPLETE, CROSS_BRANCH, DUPLICATE, NO_CONTACT, classify, compute_data_quality,
                                     course_keys, phone_variants)


def lead(name, territory="CN Bình Thạnh", courses=("photoshop cơ bản",)):
    return {"name": name, "territory": territory, "courses": frozenset(courses)}


class TestCourseKeys(unittest.TestCase):
    def test_products_and_summary_are_both_used(self):
        keys = course_keys([{"product_code": "VP-CB", "product_name": "Tin học cơ bản"}], "Tin học cơ bản, Photoshop")
        self.assertEqual(keys, frozenset({"vp-cb", "tin học cơ bản", "photoshop"}))

    def test_nothing_known(self):
        self.assertEqual(course_keys(None, ""), frozenset())


class TestPhoneVariants(unittest.TestCase):
    def test_local_and_international_forms(self):
        self.assertEqual(phone_variants("0901 234 567"), ["+84901234567", "0901234567", "0901 234 567"])
        self.assertEqual(phone_variants("+84901234567"), ["+84901234567", "0901234567"])
        self.assertEqual(phone_variants(""), [])


class TestClassify(unittest.TestCase):
    def test_no_match(self):
        self.assertEqual(classify(lead("A"), []), (COMPLETE, ""))

    def test_same_course_same_branch_is_a_duplicate(self):
        self.assertEqual(classify(lead("A"), [lead("B")]), (DUPLICATE, "B"))

    def test_same_course_other_branch(self):
        self.assertEqual(classify(lead("A"), [lead("B", "CN Thủ Đức")]), (CROSS_BRANCH, "B"))

    def test_another_course_is_not_a_duplicate(self):
        self.assertEqual(classify(lead("A"), [lead("B", "CN Thủ Đức", ("robotics stem",))]), (COMPLETE, ""))

    def test_one_shared_course_among_several_counts(self):
        """Old rule compared the whole text: "Photoshop, Excel" vs "Photoshop" looked like different courses."""
        me = lead("A", courses=("photoshop cơ bản", "excel"))
        self.assertEqual(classify(me, [lead("B", "CN Thủ Đức")]), (CROSS_BRANCH, "B"))

    def test_unknown_course_counts_as_conflict(self):
        self.assertEqual(classify(lead("A"), [lead("B", courses=())]), (DUPLICATE, "B"))

    def test_same_branch_wins_over_other_branch(self):
        got = classify(lead("A"), [lead("B", "CN Thủ Đức"), lead("C")])
        self.assertEqual(got, (DUPLICATE, "C"))

    def test_unknown_branch_counts_as_same_branch(self):
        self.assertEqual(classify(lead("A"), [lead("B", "")]), (DUPLICATE, "B"))


class FakeFrappe:
    """Enough of frappe for compute_data_quality: CRM Lead rows and their products."""

    def __init__(self, leads, products=()):
        self.leads, self.products = leads, list(products)
        self.saved = {}
        self.db = MagicMock()
        self.db.get_value.side_effect = lambda dt, name, fields, as_dict=True: (
            {f: self.leads[name].get(f) for f in fields} if name in self.leads else None)
        self.db.set_value.side_effect = lambda dt, name, values, update_modified=False: self.saved.update(
            {name: values})
        meta = MagicMock()
        meta.has_field.side_effect = lambda f: f == "duplicate_of"
        self.get_meta = lambda dt: meta

    def get_all(self, doctype, filters=None, fields=None):
        if doctype == "CRM Products":
            return [p for p in self.products if p["parent"] in filters["parent"][1]]
        out = []
        for name, row in self.leads.items():
            if name == filters["name"][1]:
                continue
            if "email" in filters and row.get("email") != filters["email"]:
                continue
            if "mobile_no" in filters and row.get("mobile_no") not in filters["mobile_no"][1]:
                continue
            out.append({"name": name, "territory": row.get("territory"), "course_interest": row.get("course_interest")})
        return out


class TestComputeDataQuality(unittest.TestCase):
    def run_with(self, fake, name, **kw):
        with patch.object(dq, "frappe", fake):
            return compute_data_quality(name, **kw)

    def test_lead_not_found_returns_none(self):
        self.assertIsNone(self.run_with(FakeFrappe({}), "MISSING"))

    def test_missing_email_and_phone(self):
        fake = FakeFrappe({"A": {"email": None, "mobile_no": ""}})
        self.assertEqual(self.run_with(fake, "A"), NO_CONTACT)
        self.assertEqual(fake.saved["A"], {"data_quality": NO_CONTACT, "duplicate_of": None})

    def test_complete_no_duplicates(self):
        fake = FakeFrappe({"A": {"email": "a@x.vn", "mobile_no": "+84901234567"}})
        self.assertEqual(self.run_with(fake, "A"), COMPLETE)

    def test_phone_written_differently_still_matches_and_both_sides_are_flagged(self):
        fake = FakeFrappe({
            "A": {"mobile_no": "0911223344", "territory": "CN Bình Thạnh", "course_interest": "Photoshop cơ bản"},
            "B": {"mobile_no": "+84911223344", "territory": "CN Thủ Đức", "course_interest": "Photoshop cơ bản"},
        })
        self.assertEqual(self.run_with(fake, "A"), CROSS_BRANCH)
        self.assertEqual(fake.saved["A"], {"data_quality": CROSS_BRANCH, "duplicate_of": "B"})
        self.assertEqual(fake.saved["B"], {"data_quality": CROSS_BRANCH, "duplicate_of": "A"})

    def test_products_decide_the_course(self):
        fake = FakeFrappe({
            "A": {"email": "c@x.vn", "territory": "CN Bình Thạnh", "course_interest": ""},
            "B": {"email": "c@x.vn", "territory": "CN Thủ Đức", "course_interest": ""},
        }, products=[{"parent": "A", "product_code": "DH-PTS", "product_name": "Photoshop cơ bản"},
                     {"parent": "B", "product_code": "TE-ROBO", "product_name": "Robotics STEM"}])
        self.assertEqual(self.run_with(fake, "A"), COMPLETE)

    def test_same_branch_same_course_duplicate(self):
        fake = FakeFrappe({
            "A": {"email": "d@x.vn", "territory": "CN Bình Thạnh", "course_interest": "Photoshop cơ bản"},
            "B": {"email": "d@x.vn", "territory": "CN Bình Thạnh", "course_interest": "Photoshop cơ bản"},
        })
        self.assertEqual(self.run_with(fake, "A", sync_matching=False), DUPLICATE)
        self.assertNotIn("B", fake.saved)

    def test_select_options_cover_every_quality(self):
        self.assertEqual(dq.SELECT_OPTIONS.split("\n")[1:], list(dq.QUALITIES))


if __name__ == "__main__":
    unittest.main()
