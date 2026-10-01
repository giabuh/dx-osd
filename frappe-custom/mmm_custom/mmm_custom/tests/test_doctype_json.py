import json
from pathlib import Path
import unittest

DOCTYPE_DIR = Path(__file__).resolve().parent.parent / "mmm_custom" / "doctype"
EXTERNAL = {"CRM Product", "CRM Territory", "User", "CRM Lead", "Facebook Page"}


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
        for name in ("Course Group", "Course Link", "Course Group Link", "Consultant", "Territory Link", "Course Schedule", "Course Promotion", "Bot Slot", "Bot Slot Option", "Bot Slot Link", "Bot Skill", "Bot Skill Template", "Bot Skill Follow Up", "Lead Engine Settings", "Bot Conversation", "AI Decision Log", "Bot Learning Signal", "Course FAQ", "Channel Connection"):
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

    def test_select_options_match_rules(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from mmm_custom import catalog_rules as r
        def opts(dt, field):
            return [f for f in self.doctypes[dt][1]["fields"] if f["fieldname"] == field][0]["options"]
        self.assertEqual(opts("Bot Slot", "slot_type"), "\n".join(r.SLOT_TYPES))
        self.assertEqual(opts("Bot Skill", "action_type"), "\n".join(r.ACTION_TYPES))
        self.assertEqual(opts("Bot Skill Follow Up", "target_type"), "\n".join(r.FOLLOW_UP_TARGETS))
        self.assertEqual(opts("Bot Slot", "catalog_source"), "\n" + "\n".join(r.CATALOG_SOURCES))

    def test_settings_is_single(self):
        self.assertEqual(self.doctypes["Lead Engine Settings"][1].get("issingle"), 1)


if __name__ == "__main__":
    unittest.main()
