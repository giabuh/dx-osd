import sys
from pathlib import Path
import unittest

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom import bot_admin


def row(name, parent, is_group=0):
    return {"name": name, "parent_crm_territory": parent, "is_group": is_group}


class TestSplitTree(unittest.TestCase):
    def test_root_areas_and_branches(self):
        rows = [row("Sao Việt", None, 1), row("Bình Dương", "Sao Việt", 1), row("Đồng Nai", "Sao Việt", 1),
                row("CN Thuận An", "Bình Dương"), row("CN Dĩ An", "Bình Dương"), row("CN Biên Hòa", "Đồng Nai")]
        root, areas, branches = bot_admin.split_tree(rows)
        self.assertEqual(root, "Sao Việt")
        self.assertEqual(areas, ["Bình Dương", "Đồng Nai"])
        self.assertEqual([b["name"] for b in branches], ["CN Dĩ An", "CN Thuận An", "CN Biên Hòa"])

    def test_leaf_directly_under_root_is_not_a_branch(self):
        rows = [row("Sao Việt", None, 1), row("Lẻ", "Sao Việt")]
        self.assertEqual(bot_admin.split_tree(rows), ("Sao Việt", [], []))


if __name__ == "__main__":
    unittest.main()
