import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mmm_custom import hooks
from mmm_custom.lifecycle import (
    BOT_REASON, CONTACTED, CONVERTED, DEAL_STATUSES, EXISTING_STUDENT, JUNK, LABELS, LEAD_STATUSES, NEW, NURTURE,
    OTHER, PENDING_PAYMENT, QUALIFIED, SPAM, TRIAL_BOOKED, UNQUALIFIED, auto_update, can_auto_move, deal_rows,
    lead_rows, needs_registration, plan_statuses, reached, reason_for_lost)


class TestStatuses(unittest.TestCase):
    def test_eight_lead_statuses_in_journey_order(self):
        self.assertEqual([s[0] for s in LEAD_STATUSES],
                         [NEW, QUALIFIED, CONTACTED, TRIAL_BOOKED, NURTURE, CONVERTED, UNQUALIFIED, JUNK])
        self.assertEqual([r["position"] for r in lead_rows()], list(range(1, 9)))

    def test_qualified_is_a_step_not_the_goal(self):
        types = {r["name"]: r["type"] for r in lead_rows()}
        self.assertEqual(types[QUALIFIED], "Ongoing")
        self.assertEqual(types[NURTURE], "On Hold")
        self.assertEqual(types[CONVERTED], "Won")
        self.assertEqual({types[UNQUALIFIED], types[JUNK]}, {"Lost"})

    def test_labels_do_not_reuse_the_page_name(self):
        # the whole Leads page is "Khách hàng tiềm năng": no status may be called "tiềm năng"
        self.assertFalse([k for k, v in LABELS.items() if "tiềm năng" in v.lower()])

    def test_deal_is_a_registration_record(self):
        self.assertEqual([s[0] for s in DEAL_STATUSES],
                         ["Awaiting Confirmation", PENDING_PAYMENT, "Deposit Paid", "Won", "Lost"])
        self.assertEqual([r["position"] for r in deal_rows()], [1, 2, 3, 4, 5])
        self.assertEqual(deal_rows()[0]["type"], "Open")
        self.assertEqual(deal_rows()[-1]["probability"], 0)


class TestRegistrationGuard(unittest.TestCase):
    def test_registered_needs_a_confirmed_registration(self):
        self.assertTrue(needs_registration(CONVERTED, True, False))

    def test_a_confirmed_registration_or_an_unchanged_status_passes(self):
        self.assertFalse(needs_registration(CONVERTED, True, True))
        self.assertFalse(needs_registration(CONVERTED, False, False))

    def test_other_statuses_are_not_guarded(self):
        for status in (NEW, QUALIFIED, CONTACTED, TRIAL_BOOKED, NURTURE, UNQUALIFIED, JUNK):
            self.assertFalse(needs_registration(status, True, False))

    def test_the_guard_is_a_lead_validate_hook(self):
        self.assertIn("mmm_custom.lifecycle.guard_converted", hooks.doc_events["CRM Lead"]["validate"])


class TestAutoMoves(unittest.TestCase):
    def test_bot_qualifies_only_a_new_lead(self):
        self.assertTrue(can_auto_move(NEW, QUALIFIED))
        self.assertTrue(can_auto_move("", QUALIFIED))
        for current in (CONTACTED, TRIAL_BOOKED, NURTURE, CONVERTED):
            self.assertFalse(can_auto_move(current, QUALIFIED), current)

    def test_a_real_customer_leaves_the_bot_s_own_lost_status(self):
        self.assertTrue(can_auto_move(UNQUALIFIED, QUALIFIED, EXISTING_STUDENT))
        self.assertTrue(can_auto_move(JUNK, QUALIFIED, SPAM))
        self.assertFalse(can_auto_move(UNQUALIFIED, QUALIFIED, "Pricing"))  # a person closed it

    def test_lost_only_from_new(self):
        self.assertTrue(can_auto_move(NEW, UNQUALIFIED))
        self.assertTrue(can_auto_move(NEW, JUNK))
        self.assertFalse(can_auto_move(QUALIFIED, UNQUALIFIED))
        self.assertFalse(can_auto_move(CONTACTED, JUNK))

    def test_handoff_and_trial_move_forward_only(self):
        for current in (NEW, QUALIFIED, NURTURE):
            self.assertTrue(can_auto_move(current, CONTACTED), current)
        self.assertFalse(can_auto_move(TRIAL_BOOKED, CONTACTED))
        self.assertFalse(can_auto_move(CONVERTED, CONTACTED))
        self.assertTrue(can_auto_move(CONTACTED, TRIAL_BOOKED))
        self.assertFalse(can_auto_move(CONVERTED, TRIAL_BOOKED))
        self.assertFalse(can_auto_move(UNQUALIFIED, TRIAL_BOOKED))

    def test_nobody_moves_a_lead_into_nurture_automatically(self):
        for current in (NEW, QUALIFIED, CONTACTED, TRIAL_BOOKED):
            self.assertFalse(can_auto_move(current, NURTURE))

    def test_same_status_is_no_move(self):
        self.assertFalse(can_auto_move(QUALIFIED, QUALIFIED))
        self.assertEqual(auto_update(CONTACTED, CONTACTED), {})

    def test_lost_status_carries_the_bot_reason(self):
        self.assertEqual(auto_update(NEW, UNQUALIFIED), {"status": UNQUALIFIED, "lost_reason": EXISTING_STUDENT})
        self.assertEqual(auto_update(NEW, JUNK), {"status": JUNK, "lost_reason": SPAM})
        self.assertEqual(set(BOT_REASON.values()), {EXISTING_STUDENT, SPAM})

    def test_leaving_lost_clears_the_bot_reason(self):
        self.assertEqual(auto_update(UNQUALIFIED, QUALIFIED, EXISTING_STUDENT),
                         {"status": QUALIFIED, "lost_reason": ""})
        self.assertEqual(auto_update(NEW, QUALIFIED), {"status": QUALIFIED})


class TestReached(unittest.TestCase):
    def test_later_steps_have_reached_earlier_ones(self):
        self.assertTrue(reached(TRIAL_BOOKED, QUALIFIED))
        self.assertTrue(reached(NURTURE, CONTACTED))
        self.assertFalse(reached(NEW, QUALIFIED))
        self.assertFalse(reached(UNQUALIFIED, QUALIFIED))
        self.assertTrue(reached(QUALIFIED, CONVERTED, converted=1))  # converted before D-116


class TestMigrationPlan(unittest.TestCase):
    def test_missing_statuses_are_created(self):
        plan = plan_statuses({}, lead_rows())
        self.assertEqual([a for a, _ in plan], ["create"] * 8)

    def test_upstream_statuses_are_brought_in_line(self):
        existing = {r["name"]: {k: v for k, v in r.items() if k != "name"} for r in lead_rows()}
        existing[QUALIFIED] = {"type": "Won", "color": "green", "position": 4}
        plan = plan_statuses(existing, lead_rows())
        self.assertEqual(plan, [("update", lead_rows()[1])])

    def test_create_only_keeps_a_manager_s_edits(self):
        existing = {r["name"]: {"type": r["type"], "color": "pink", "position": 99} for r in lead_rows()}
        del existing[TRIAL_BOOKED]
        plan = plan_statuses(existing, lead_rows(), create_only=True)
        self.assertEqual([(a, r["name"]) for a, r in plan], [("create", TRIAL_BOOKED)])

    def test_backfilled_lost_reasons(self):
        self.assertEqual(reason_for_lost("support", UNQUALIFIED), EXISTING_STUDENT)
        self.assertEqual(reason_for_lost("spam", UNQUALIFIED), SPAM)
        self.assertEqual(reason_for_lost(None, JUNK), SPAM)
        self.assertEqual(reason_for_lost(None, UNQUALIFIED), OTHER)


class TestHooks(unittest.TestCase):
    def test_fresh_install_and_migrate_run_the_lifecycle(self):
        self.assertIn("mmm_custom.lifecycle.migrate", hooks.after_install)
        self.assertIn("mmm_custom.lifecycle.ensure_statuses_hook", hooks.after_migrate)

    def test_patch_is_registered(self):
        patches = (Path(hooks.__file__).parent / "patches.txt").read_text()
        self.assertIn("mmm_custom.patches.v1_1.education_lifecycle", patches)


if __name__ == "__main__":
    unittest.main()
