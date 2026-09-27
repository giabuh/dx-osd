import sys
from pathlib import Path
import unittest
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

    def test_apps_entry_targets_bot_page(self):
        self.assertEqual(hooks.add_to_apps_screen[0]["route"], "/bot")
        self.assertEqual(hooks.add_to_apps_screen[0]["has_permission"], "mmm_custom.desk.can_open_bot")
        self.assertIn("mmm_custom.desk.hide_unused_workspaces", hooks.after_migrate)

    def test_migrate_updates_existing_bot_workspace_icon(self):
        frappe = MagicMock()
        frappe.db.exists.return_value = True
        frappe.db.get_value.side_effect = ["chat", "education"]
        with patch.object(desk, "frappe", frappe):
            desk.ensure_bot_workspace_icon()
            desk.ensure_bot_workspace_icon()
        frappe.db.set_value.assert_called_once_with("Workspace", "Bot Sao Viet", "icon", "education")
        self.assertIn("mmm_custom.desk.ensure_bot_workspace_icon", hooks.after_migrate)


if __name__ == "__main__":
    unittest.main()
