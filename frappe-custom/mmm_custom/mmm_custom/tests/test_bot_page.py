import importlib.util
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

PAGE = Path(__file__).resolve().parent.parent / "www" / "admin.py"


class TestBotPage(unittest.TestCase):
    def load_page(self, frappe):
        with patch.dict(sys.modules, {"frappe": frappe}):
            spec = importlib.util.spec_from_file_location("test_bot_www", PAGE)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        return module

    def test_guest_redirects_to_login(self):
        frappe = MagicMock()
        frappe.session.user = "Guest"
        class Redirect(Exception):
            pass
        frappe.Redirect = Redirect
        page = self.load_page(frappe)
        with self.assertRaises(Redirect) as raised:
            page.get_context(SimpleNamespace())
        self.assertEqual(raised.exception.args, (302,))
        self.assertEqual(frappe.flags.redirect_location, "/login?redirect-to=/admin")

    def test_wrong_role_is_forbidden(self):
        frappe = MagicMock()
        frappe.session.user = "staff@example.com"
        frappe.PermissionError = PermissionError
        frappe.throw.side_effect = PermissionError
        page = self.load_page(frappe)
        with patch.object(page, "can_open_bot", return_value=False):
            with self.assertRaises(PermissionError):
                page.get_context(SimpleNamespace())

    def test_manager_gets_csrf_and_chatwoot_url(self):
        frappe = MagicMock()
        frappe.session.user = "manager@example.com"
        frappe.sessions.get_csrf_token.return_value = "csrf-test"
        frappe.conf.get.return_value = "http://127.0.0.1:3000"
        page = self.load_page(frappe)
        context = SimpleNamespace()
        with patch.object(page, "can_open_bot", return_value=True):
            page.get_context(context)
        self.assertEqual(context.csrf_token, "csrf-test")
        self.assertEqual(context.chatwoot_url, "http://127.0.0.1:3000")
        self.assertEqual(context.no_cache, 1)
        script = Path(__file__).resolve().parent.parent / "public" / "js" / "bot_page.js"
        self.assertEqual(context.asset_version, int(script.stat().st_mtime))  # a new file busts the 12 h asset cache

    def test_page_loads_the_script_with_its_version(self):
        html = (PAGE.parent / "admin.html").read_text(encoding="utf-8")
        self.assertIn('src="/assets/mmm_custom/js/bot_page.js?v={{ asset_version }}"', html)


if __name__ == "__main__":
    unittest.main()
