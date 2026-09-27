import sys
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom import staff_switch

SM = ["System Manager"]
TV = ["Sales User"]


class TestRefusal(unittest.TestCase):
    def test_system_manager_into_active_consultant(self):
        self.assertEqual(staff_switch.refusal(SM, False, False, TV, True), "")

    def test_refusals(self):
        cases = [
            (["Sales Manager"], False, False, TV, True),  # only System Manager switches
            (SM, True, False, TV, True),  # already switched
            (SM, False, True, TV, True),  # turned off by site config
            (SM, False, False, [], False),  # not an active consultant
            (SM, False, False, ["Sales User", "Sales Manager"], True),  # never into a manager
        ]
        for case in cases:
            self.assertTrue(staff_switch.refusal(*case), case)


def fake_frappe(user="admin@x.vn", roles=SM, session_data=None, consultant=True):
    frappe = MagicMock()
    frappe.session = SimpleNamespace(user=user, sid="sid-1", data=session_data or {})
    frappe.conf = {}
    frappe.get_roles.side_effect = lambda u=None: roles if u is None else TV
    frappe.db.get_value.side_effect = lambda doctype, *a, **k: ("tv@x.vn" if consultant else None) if doctype == "Consultant" else 1
    frappe.PermissionError = PermissionError
    frappe.throw.side_effect = lambda msg, exc=Exception: (_ for _ in ()).throw(exc(msg))
    return frappe


class TestSwitch(unittest.TestCase):
    def test_switch_logs_then_impersonates(self):
        frappe = fake_frappe()
        with patch.object(staff_switch, "frappe", frappe):
            self.assertEqual(staff_switch.switch_to("tv@x.vn"), {"user": "tv@x.vn"})
        frappe.local.login_manager.impersonate.assert_called_once_with("tv@x.vn")
        frappe.get_doc.return_value.insert.assert_called_once()

    def test_refused_switch_never_impersonates(self):
        frappe = fake_frappe(roles=["Sales Manager"])
        with patch.object(staff_switch, "frappe", frappe):
            with self.assertRaises(PermissionError):
                staff_switch.switch_to("tv@x.vn")
        frappe.local.login_manager.impersonate.assert_not_called()

    def test_switch_back_returns_to_the_manager(self):
        frappe = fake_frappe(user="tv@x.vn", roles=TV, session_data={"impersonated_by": "admin@x.vn"})
        with patch.object(staff_switch, "frappe", frappe), patch.dict(sys.modules, {"frappe.sessions": MagicMock()}):
            self.assertEqual(staff_switch.switch_back(), {"user": "admin@x.vn"})
            sys.modules["frappe.sessions"].delete_session.assert_called_once_with(
                "sid-1", user="tv@x.vn", reason="Staff switch ended")
        frappe.local.login_manager.login_as.assert_called_once_with("admin@x.vn")

    def test_switch_back_needs_a_switched_session(self):
        frappe = fake_frappe(user="tv@x.vn", roles=TV)
        with patch.object(staff_switch, "frappe", frappe):
            with self.assertRaises(PermissionError):
                staff_switch.switch_back()
        frappe.local.login_manager.login_as.assert_not_called()


if __name__ == "__main__":
    unittest.main()
