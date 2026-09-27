import sys
from datetime import date
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, fill, schedule

from mmm_custom.engine.actions import run_action
from mmm_custom.engine.context import base_context
from mmm_custom.engine.repo import trial_due
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding, apply_action

CAT = demo_catalog()
TODAY = date(2026, 9, 28)


def act(skill_key, slots, repo):
    ctx = base_context(slots, CAT, ConversationState("1", slots=slots))
    return run_action(CAT.skills[skill_key], ctx, slots, CAT, repo, TODAY)


class TestTrialOffer(unittest.TestCase):
    def test_next_classes_become_booking_buttons(self):
        repo = FakeRepo(CAT, TODAY)
        repo.schedules = [schedule("VP-EXCEL", "CN Quận 7", date(2026, 10, 6)),
                          schedule("VP-EXCEL", "CN Quận 7", date(2026, 10, 11), shift="Sáng 8:00–11:00")]
        out = act("trial_class", {"course": fill("VP-EXCEL"), "branch": fill("CN Quận 7")}, repo)
        self.assertEqual([b["title"] for b in out["_buttons"]], ["T3 06/10 Tối", "CN 11/10 Sáng"])
        self.assertEqual(out["_buttons"][0]["action"], {
            "type": "slot", "slot": "trial_class", "skill": "trial_booked",
            "value": "Excel từ cơ bản đến nâng cao · Thứ 3, 06/10 · Tối 17:00–21:00 · CN Quận 7"})
        self.assertTrue(all(len(b["title"]) <= 20 for b in out["_buttons"]))

    def test_no_classes_no_buttons(self):
        out = act("trial_class", {"course": fill("VP-EXCEL")}, FakeRepo(CAT, TODAY))
        self.assertEqual((out["schedules"], out["_buttons"]), ([], []))

    def test_booking_skill_reads_the_slot(self):
        out = act("trial_booked", {"trial_class": fill("Excel · Thứ 3, 06/10")}, FakeRepo(CAT, TODAY))
        self.assertEqual(out, {"trial": "Excel · Thứ 3, 06/10"})

    def test_a_tap_fills_the_slot_and_answers_the_skill(self):
        u = Understanding()
        apply_action(u, {"type": "slot", "slot": "trial_class", "value": "X", "skill": "trial_booked"})
        self.assertEqual((u.fills["trial_class"]["value"], u.skills), ("X", ["trial_booked"]))


class TestTrialDue(unittest.TestCase):
    def test_next_occurrence_of_the_day(self):
        self.assertEqual(trial_due("Excel · Thứ 3, 06/10 · Tối", TODAY), date(2026, 10, 6))
        self.assertEqual(trial_due("Excel · Thứ 2, 05/01", TODAY), date(2027, 1, 5))
        self.assertIsNone(trial_due("không có ngày", TODAY))
        self.assertIsNone(trial_due("31/02", TODAY))


if __name__ == "__main__":
    unittest.main()
