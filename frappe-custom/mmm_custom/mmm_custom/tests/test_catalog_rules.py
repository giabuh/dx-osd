import sys
from pathlib import Path
import unittest

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.catalog_rules import assert_leaf_branch

TREE = {"CN Dĩ An": 0, "Bình Dương": 1}


class TestAssertLeafBranch(unittest.TestCase):
    def test_empty_branch_is_allowed(self):
        assert_leaf_branch(None, TREE.get)
        assert_leaf_branch("", TREE.get)

    def test_leaf_branch_passes(self):
        assert_leaf_branch("CN Dĩ An", TREE.get)

    def test_area_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "is an area"):
            assert_leaf_branch("Bình Dương", TREE.get)

    def test_unknown_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown branch"):
            assert_leaf_branch("CN Mars", TREE.get)


from datetime import date
from mmm_custom.catalog_rules import validate_promotion


class TestValidatePromotion(unittest.TestCase):
    def test_valid_percent(self):
        validate_promotion("Percent", 10, date(2026, 10, 1), date(2026, 11, 30))

    def test_validate_promotion_percent_over_100(self):
        with self.assertRaisesRegex(ValueError, "100"):
            validate_promotion("Percent", 120, None, None)

    def test_validate_promotion_non_positive(self):
        with self.assertRaisesRegex(ValueError, "greater than 0"):
            validate_promotion("Amount", 0, None, None)

    def test_validate_promotion_inverted_dates(self):
        with self.assertRaisesRegex(ValueError, "before"):
            validate_promotion("Amount", 500000, date(2026, 11, 1), date(2026, 10, 1))


from mmm_custom.catalog_rules import validate_slot_dependency


class TestValidateSlotDependency(unittest.TestCase):
    def test_catalog_needs_source(self):
        with self.assertRaisesRegex(ValueError, "catalog_source"):
            validate_slot_dependency("catalog", None, None, None)

    def test_dependency_needs_both_parts(self):
        with self.assertRaisesRegex(ValueError, "depends_on"):
            validate_slot_dependency("number", None, "learner", None)

    def test_valid(self):
        validate_slot_dependency("number", None, "learner", "child")
        validate_slot_dependency("catalog", "course", None, None)


if __name__ == "__main__":
    unittest.main()
