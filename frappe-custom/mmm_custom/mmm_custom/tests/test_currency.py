"""VND as the CRM currency (D-120): the planner only writes what is missing."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_real_frappe = sys.modules.get("frappe")
sys.modules["frappe"] = MagicMock()
try:
    import mmm_custom.setup as setup_mod
finally:
    if _real_frappe is None:
        del sys.modules["frappe"]
    else:
        sys.modules["frappe"] = _real_frappe

READY = {"enabled": 1, "symbol": "₫", "number_format": "#.###", "symbol_on_right": 1}


class TestVndPlan(unittest.TestCase):
    def test_a_fresh_site_gets_everything(self):
        plan = setup_mod.vnd_plan({"enabled": 0, "symbol": None, "number_format": "#.###", "symbol_on_right": 0}, {}, {})
        self.assertEqual(plan["currency"], READY)
        self.assertEqual(plan["system"], {"currency": "VND", "currency_precision": "0", "number_format": "#.###"})
        self.assertEqual(plan["fcrm"], {"currency": "VND"})

    def test_a_site_already_on_vnd_needs_nothing(self):
        self.assertEqual(setup_mod.vnd_plan(READY, {"currency": "VND"}, {"currency": "VND"}), {})

    def test_a_deliberate_other_currency_is_kept(self):
        plan = setup_mod.vnd_plan(READY, {"currency": "USD"}, {"currency": "USD"})
        self.assertNotIn("system", plan)
        self.assertNotIn("fcrm", plan)


class TestVndDefaults(unittest.TestCase):
    SYSTEM = {"currency": "VND", "currency_precision": "0", "number_format": "#.###"}

    def test_the_page_reads_defaults_so_they_follow_the_system_settings(self):
        self.assertEqual(setup_mod.vnd_defaults(self.SYSTEM, {"currency": "VND"}),
                         {"currency_precision": "0", "number_format": "#.###"})

    def test_nothing_to_do_when_they_already_match(self):
        self.assertEqual(setup_mod.vnd_defaults(self.SYSTEM, dict(self.SYSTEM)), {})

    def test_another_currency_is_left_alone(self):
        self.assertEqual(setup_mod.vnd_defaults({**self.SYSTEM, "currency": "USD"}, {}), {})


if __name__ == "__main__":
    unittest.main()
