"""The bot drafts a registration (D-118): class buttons, the slot a tap fills, the effect after the answer."""

import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, fill, schedule

from mmm_custom import catalog_rules
from mmm_custom.engine import decide, offers
from mmm_custom.engine.actions import run_action
from mmm_custom.engine.context import base_context
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import enrol_drafts
from mmm_custom.engine.state import ConversationState

CAT = demo_catalog()
TODAY = date(2026, 9, 28)


def act(slots, repo):
    ctx = base_context(slots, CAT, ConversationState("1", slots=slots))
    return run_action(CAT.skills["register"], ctx, slots, CAT, repo, TODAY)


def repo_with_classes():
    repo = FakeRepo(CAT, TODAY)
    repo.schedules = [schedule("VP-EXCEL", "CN Quận 7", date(2026, 10, 6)),
                      schedule("VP-EXCEL", "CN Quận 7", date(2026, 10, 11), shift="Sáng 8:00–11:00")]
    return repo


class TestEnrolAction(unittest.TestCase):
    def test_register_needs_only_the_course_so_a_hot_customer_still_gets_the_classes(self):
        self.assertEqual(CAT.skills["register"].params, ("course",))

    def test_register_is_an_enrol_skill_that_hands_off(self):
        skill = CAT.skills["register"]
        self.assertEqual(skill.action, "enrol")
        self.assertTrue(skill.handoff_after)

    def test_action_is_known_everywhere_action_types_are_listed(self):
        self.assertIn("enrol", catalog_rules.ACTION_TYPES)
        self.assertIn("enrol", decide.LIVE_ACTIONS)
        self.assertIn("enrol", offers.BUTTON_ACTIONS)

    def test_next_classes_become_buttons_that_fill_the_class_slot(self):
        out = act({"course": fill("VP-EXCEL"), "branch": fill("CN Quận 7")}, repo_with_classes())
        self.assertEqual([b["title"] for b in out["_buttons"]], ["06/10 Tối Quận 7", "11/10 Sáng Quận 7"])
        self.assertEqual(out["_buttons"][0]["action"], {
            "type": "slot", "slot": "enrol_class", "skill": "register",
            "value": "VP-EXCEL · CN Quận 7 · 06/10/2026 · Tối"})

    def test_classes_of_one_day_at_different_branches_get_different_buttons(self):
        repo = FakeRepo(CAT, TODAY)
        repo.schedules = [schedule("VP-EXCEL", "CN Quận 6", date(2026, 10, 5)),
                          schedule("VP-EXCEL", "CN Bình Thạnh", date(2026, 10, 5))]
        titles = [b["title"] for b in act({"course": fill("VP-EXCEL")}, repo)["_buttons"]]
        self.assertEqual(len(set(titles)), 2)
        self.assertTrue(all(len(t) <= 20 for t in titles))

    def test_a_chosen_class_is_echoed_and_offers_no_more_buttons(self):
        out = act({"course": fill("VP-EXCEL"), "enrol_class": fill("VP-EXCEL · CN Quận 7 · 06/10/2026 · Tối")},
                  repo_with_classes())
        self.assertEqual(out, {"enrol_class": "VP-EXCEL · CN Quận 7 · 06/10/2026 · Tối"})

    def test_no_classes_no_buttons(self):
        out = act({"course": fill("VP-EXCEL")}, FakeRepo(CAT, TODAY))
        self.assertEqual((out["schedules"], out["_buttons"]), ([], []))

    def test_the_class_list_breaks_lines_for_real(self):
        for t in CAT.skills["register"].templates:
            self.assertNotIn("\\n", t.text)

    def test_reply_lists_classes_or_confirms_the_choice(self):
        from engine_fixtures import render

        skill = CAT.skills["register"]
        variants = {t.key: t for t in skill.templates}
        self.assertIn("enrol_class", variants["chosen"].when)
        text = render(variants["chosen"].text, {"brand": {"me": "em", "you": "anh/chị"},
                                                    "enrol_class": "Excel · 06/10"})
        self.assertIn("Excel · 06/10", text)


def turn(slots, lead="CRM-LEAD-1", skills=("register",)):
    state = ConversationState("7", lead=lead, slots=slots)
    return SimpleNamespace(state=state, decision=SimpleNamespace(skills=list(skills)),
                           reply=SimpleNamespace(errors=[]))


class TestEnrolDrafts(unittest.TestCase):
    def run_it(self, t, plan=None):
        fx = RecordingEffects()
        enrol_drafts(t, fx, CAT, plan)
        return fx, fx.of("enrol")

    def test_a_course_makes_a_draft_even_without_a_phone(self):
        _, calls = self.run_it(turn({"course": fill("VP-EXCEL")}), SimpleNamespace(owner="mai@x.vn"))
        self.assertEqual(calls, [{"lead": "CRM-LEAD-1", "course": "VP-EXCEL", "class_title": "", "owner": "mai@x.vn"}])

    def test_course_and_phone_make_a_draft(self):
        fx, calls = self.run_it(turn({"course": fill("VP-EXCEL"), "phone": fill("0901111222")}),
                                SimpleNamespace(owner="mai@x.vn"))
        self.assertEqual(calls, [{"lead": "CRM-LEAD-1", "course": "VP-EXCEL", "class_title": "", "owner": "mai@x.vn"}])

    def test_a_chosen_class_goes_along(self):
        _, calls = self.run_it(turn({"course": fill("VP-EXCEL"), "phone": fill("0901111222"),
                                     "enrol_class": fill("VP-EXCEL · CN Quận 7 · 06/10/2026 · Tối")}))
        self.assertEqual(calls[0]["class_title"], "VP-EXCEL · CN Quận 7 · 06/10/2026 · Tối")

    def test_no_course_or_no_lead_no_draft(self):
        for slots, lead in (({"phone": fill("0901111222")}, "CRM-LEAD-1"),
                            ({"course": fill("VP-EXCEL"), "phone": fill("0901111222")}, "")):
            self.assertEqual(self.run_it(turn(slots, lead))[1], [])

    def test_only_the_register_skill_drafts(self):
        t = turn({"course": fill("VP-EXCEL"), "phone": fill("0901111222")}, skills=("hotline",))
        self.assertEqual(self.run_it(t)[1], [])

    def test_a_failing_effect_is_recorded_not_raised(self):
        t = turn({"course": fill("VP-EXCEL"), "phone": fill("0901111222")})
        fx = RecordingEffects()

        def boom(*a, **k):
            raise RuntimeError("db")

        fx.enrol = boom
        enrol_drafts(t, fx, CAT, None)
        self.assertEqual(t.reply.errors[0]["type"], "enrol_failed")


if __name__ == "__main__":
    unittest.main()
