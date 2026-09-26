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


if __name__ == "__main__":
    unittest.main()
