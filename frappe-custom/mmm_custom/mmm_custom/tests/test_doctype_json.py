import json
from pathlib import Path
import unittest

DOCTYPE_DIR = Path(__file__).resolve().parent.parent / "mmm_custom" / "doctype"
EXTERNAL = {"CRM Product", "CRM Territory", "User", "CRM Lead"}


def load_all():
    out = {}
    for folder in sorted(p for p in DOCTYPE_DIR.iterdir() if p.is_dir() and not p.name.startswith("__")):
        data = json.loads((folder / f"{folder.name}.json").read_text(encoding="utf-8"))
        out[data["name"]] = (folder, data)
    return out


class TestDocTypeJson(unittest.TestCase):
    def setUp(self):
        self.doctypes = load_all()

    def test_expected_doctypes_present(self):
        for name in ("Course Group", "Course Link", "Course Group Link", "Consultant", "Territory Link", "Course Schedule", "Course Promotion"):
            self.assertIn(name, self.doctypes)

    def test_folder_names_and_module(self):
        for name, (folder, data) in self.doctypes.items():
            self.assertEqual(folder.name, name.lower().replace(" ", "_"), name)
            self.assertEqual(data["module"], "MMM Custom", name)
            self.assertTrue((folder / "__init__.py").exists(), name)
            self.assertTrue((folder / f"{folder.name}.py").exists(), name)

    def test_field_order_matches_fields(self):
        for name, (_, data) in self.doctypes.items():
            self.assertEqual(data["field_order"], [f["fieldname"] for f in data["fields"]], name)

    def test_links_resolve(self):
        known = set(self.doctypes) | EXTERNAL
        for name, (_, data) in self.doctypes.items():
            for f in data["fields"]:
                if f["fieldtype"] in ("Link", "Table", "Table MultiSelect"):
                    self.assertIn(f["options"], known, f"{name}.{f['fieldname']}")

    def test_table_multiselect_children_have_one_link(self):
        for name, (_, data) in self.doctypes.items():
            for f in data["fields"]:
                if f["fieldtype"] == "Table MultiSelect":
                    child = self.doctypes[f["options"]][1]
                    self.assertEqual(child.get("istable"), 1, f["options"])
                    self.assertEqual([c["fieldtype"] for c in child["fields"]], ["Link"], f["options"])

    def test_button_labels_capped(self):
        for name, (_, data) in self.doctypes.items():
            for f in data["fields"]:
                if f["fieldname"] in ("button_label", "title") and f.get("length"):
                    self.assertLessEqual(f["length"], 20, name)


if __name__ == "__main__":
    unittest.main()
