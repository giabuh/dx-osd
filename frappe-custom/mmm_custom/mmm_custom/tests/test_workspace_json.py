import json
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parent.parent / "mmm_custom"
WORKSPACE = MODULE / "workspace" / "bot_sao_viet" / "bot_sao_viet.json"
EXTERNAL = {"CRM Product", "CRM Lead", "CRM Territory"}
FRAPPE_ICONS = {"education", "support", "crm", "customer", "dashboard", "tool", "setting", "users", "message", "chart"}


class TestBotWorkspace(unittest.TestCase):
    def setUp(self):
        self.ws = json.loads(WORKSPACE.read_text(encoding="utf-8"))

    def test_every_block_shortcut_exists(self):
        names = {s["label"] for s in self.ws["shortcuts"]}
        blocks = [b["data"]["shortcut_name"] for b in json.loads(self.ws["content"]) if b["type"] == "shortcut"]
        self.assertEqual(sorted(blocks), sorted(names))

    def test_shortcuts_point_at_real_doctypes_and_pages(self):
        doctypes = {json.loads(p.read_text(encoding="utf-8"))["name"] for p in (MODULE / "doctype").glob("*/*.json")}
        pages = {json.loads(p.read_text(encoding="utf-8"))["name"] for p in (MODULE / "page").glob("*/*.json")}
        for s in self.ws["shortcuts"]:
            if s["type"] == "DocType":
                self.assertIn(s["link_to"], doctypes | EXTERNAL, s["label"])
            elif s["type"] == "Page":
                self.assertIn(s["link_to"], pages, s["label"])
            else:
                self.assertEqual(s["type"], "URL", s["label"])
                self.assertTrue(s["url"].startswith("/crm"), s["label"])

    def test_name_label_and_title_match(self):
        # the desk routes a workspace by slug(name) but its sidebar link uses slug(title): they must be equal
        self.assertEqual((self.ws["name"], self.ws["label"]), (self.ws["title"], self.ws["title"]))

    def test_only_managers_see_it(self):
        self.assertEqual({r["role"] for r in self.ws["roles"]}, {"System Manager", "Sales Manager"})

    def test_icon_exists_in_frappe(self):
        self.assertIn(self.ws["icon"], FRAPPE_ICONS)


if __name__ == "__main__":
    unittest.main()
