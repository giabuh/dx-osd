import sys
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom import desk, hooks


class TestDesk(unittest.TestCase):
    def test_only_expected_workspaces_are_hidden_once(self):
        frappe = MagicMock()
        frappe.db.exists.side_effect = lambda _, name: name != "Build"
        frappe.db.get_value.side_effect = lambda _, name, field: 1 if name == "Tools" else 0
        with patch.object(desk, "frappe", frappe):
            desk.hide_unused_workspaces()
        self.assertEqual(set(desk.HIDDEN_WORKSPACES), {"Website", "Tools", "Integrations", "Build"})
        self.assertEqual(frappe.db.set_value.call_count, 2)
        changed = {call.args[1] for call in frappe.db.set_value.call_args_list}
        self.assertEqual(changed, {"Website", "Integrations"})
        frappe.db.set_value.reset_mock()
        frappe.db.get_value.return_value = 1
        frappe.db.get_value.side_effect = None
        with patch.object(desk, "frappe", frappe):
            desk.hide_unused_workspaces()
        frappe.db.set_value.assert_not_called()

    def test_bot_access_requires_manager_role(self):
        frappe = MagicMock()
        with patch.object(desk, "frappe", frappe):
            frappe.get_roles.return_value = ["Sales User"]
            self.assertFalse(desk.can_open_bot())
            frappe.get_roles.return_value = ["Sales Manager"]
            self.assertTrue(desk.can_open_bot())
            frappe.get_roles.return_value = ["System Manager"]
            self.assertTrue(desk.can_open_bot())

    def test_apps_entry_targets_admin_page(self):
        self.assertEqual(hooks.add_to_apps_screen[0]["route"], "/admin")
        self.assertEqual(hooks.add_to_apps_screen[0]["title"], "Quản trị")
        self.assertIn({"source": "/bot", "target": "/admin"}, hooks.website_redirects)
        self.assertEqual(hooks.add_to_apps_screen[0]["has_permission"], "mmm_custom.desk.can_open_bot")
        self.assertIn("mmm_custom.desk.hide_unused_workspaces", hooks.after_migrate)

    def test_migrate_updates_existing_bot_workspace_icon(self):
        frappe = MagicMock()
        frappe.db.exists.return_value = True
        frappe.db.get_value.side_effect = ["chat", "education"]
        with patch.object(desk, "frappe", frappe):
            desk.ensure_bot_workspace_icon()
            desk.ensure_bot_workspace_icon()
        frappe.db.set_value.assert_called_once_with("Workspace", "Bot Sao Việt", "icon", "education")
        self.assertIn("mmm_custom.desk.ensure_bot_workspace_icon", hooks.after_migrate)

    def test_migrate_removes_the_old_unaccented_workspace(self):
        frappe = MagicMock()
        present = {"Bot Sao Viet", "Bot Sao Việt"}
        frappe.db.exists.side_effect = lambda doctype, name: name in present
        frappe.delete_doc.side_effect = lambda doctype, name, **kw: present.discard(name)
        with patch.object(desk, "frappe", frappe):
            desk.remove_old_bot_workspace()
            desk.remove_old_bot_workspace()
        frappe.delete_doc.assert_called_once_with("Workspace", "Bot Sao Viet", ignore_permissions=True, force=True)

    def test_migrate_imports_the_workspace_when_the_sync_skipped_it(self):
        frappe = MagicMock()
        frappe.db.exists.side_effect = lambda doctype, name: False
        frappe.get_app_path.return_value = "/app/ws.json"
        with patch.object(desk, "frappe", frappe), patch.object(desk, "import_file_by_path", create=True) as imp:
            desk.remove_old_bot_workspace()
        imp.assert_called_once_with("/app/ws.json", force=True)
        self.assertIn("mmm_custom.desk.remove_old_bot_workspace", hooks.after_migrate)


class TestDefaultApp(unittest.TestCase):
    def test_home_by_role(self):
        manager, consultant = ["Sales Manager", "Sales User"], ["Sales User"]
        cases = [(manager, "", "mmm_custom"), (manager, "mmm_custom", None), (manager, "crm", None),
                 (consultant, "", None), (consultant, "mmm_custom", ""), (consultant, "crm", None)]
        for roles, current, expected in cases:
            self.assertEqual(desk.default_app_for(roles, current), expected, (roles, current))

    def fake_site(self):
        frappe = MagicMock()
        state = {"system": "", "users": {"Administrator": "", "boss@x.vn": "hrms", "tv@x.vn": "mmm_custom",
                                         "new@x.vn": ""}}
        roles = {"Administrator": ["System Manager"], "boss@x.vn": ["Sales Manager"], "tv@x.vn": ["Sales User"],
                 "new@x.vn": ["Sales User"]}
        frappe.db.get_single_value.side_effect = lambda doctype, field: state["system"]
        frappe.db.set_single_value.side_effect = lambda doctype, field, value: state.update(system=value)
        frappe.get_all.side_effect = lambda *a, **kw: [
            SimpleNamespace(name=name, default_app=app) for name, app in state["users"].items()]
        frappe.get_roles.side_effect = lambda user: roles[user]
        def set_value(doctype, name, field, value, update_modified=True):
            state["users"][name] = value
        frappe.db.set_value.side_effect = set_value
        return frappe, state

    def test_migrate_sets_crm_default_and_each_users_home_once(self):
        frappe, state = self.fake_site()
        with patch.object(desk, "frappe", frappe):
            desk.apply_default_apps()
            self.assertEqual(state, {"system": "crm", "users": {"Administrator": "mmm_custom", "boss@x.vn": "hrms",
                                                                "tv@x.vn": "", "new@x.vn": ""}})
            self.assertEqual(frappe.db.set_value.call_count, 2)
            frappe.db.set_value.reset_mock()
            frappe.db.set_single_value.reset_mock()
            desk.apply_default_apps()
        frappe.db.set_value.assert_not_called()
        frappe.db.set_single_value.assert_not_called()
        self.assertIn("mmm_custom.desk.apply_default_apps", hooks.after_migrate)

    def test_saving_a_user_applies_their_role(self):
        frappe = MagicMock()
        frappe.db.get_value.return_value = ""
        doc = MagicMock(enabled=1, user_type="System User")
        doc.name = "boss@x.vn"
        doc.get.return_value = [MagicMock(role="Sales Manager")]
        with patch.object(desk, "frappe", frappe):
            desk.apply_user_default_app(doc)
            frappe.db.set_value.assert_called_once_with("User", "boss@x.vn", "default_app", "mmm_custom",
                                                        update_modified=False)
            frappe.db.set_value.reset_mock()
            doc.user_type = "Website User"
            desk.apply_user_default_app(doc)
        frappe.db.set_value.assert_not_called()
        self.assertEqual(hooks.doc_events["User"]["on_update"], "mmm_custom.desk.apply_user_default_app")


if __name__ == "__main__":
    unittest.main()
