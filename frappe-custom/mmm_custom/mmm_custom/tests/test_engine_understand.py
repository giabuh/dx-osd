import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, fill

from mmm_custom import catalog_rules
from mmm_custom.engine.reply import compose
from mmm_custom.engine.decide import decide
from mmm_custom.engine.slot_types import REGISTRY
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import match_courses, understand

CAT = demo_catalog()


def st(pending_slot="", options=None, slots=None):
    return ConversationState("1", pending={"slot": pending_slot, "options": options or {}}, slots=slots or {}, turns=1)


class TestKeywordTier(unittest.TestCase):
    def test_multi_slot_free_text(self):
        u = understand("học phí excel ở bình thạnh", st(), CAT)
        self.assertEqual(u.fills["course"]["value"], "VP-EXCEL")
        self.assertEqual(u.fills["branch"]["value"], "CN Bình Thạnh")
        self.assertEqual(u.fills["course"]["source"], "keyword")
        self.assertEqual(u.skills, ["fee_quote"])
        self.assertFalse(u.tapped)

    def test_longest_course_alias_wins(self):
        self.assertEqual(understand("autocad 3d", st(), CAT).fills["course"]["value"], "VKT-CAD3D")
        self.assertEqual(understand("Excel nâng cao", st(), CAT).fills["course"]["value"], "VP-EXCEL-NC")

    def test_group_and_area_become_parents(self):
        u = understand("muốn học đồ họa ở bình dương", st(), CAT)
        self.assertEqual(u.parents, {"course": "Thiết kế đồ họa", "branch": "Bình Dương"})
        self.assertNotIn("course", u.fills)

    def test_ambiguous_courses_keep_candidates_and_common_parent(self):
        u = understand("photoshop hay illustrator", st(), CAT)
        self.assertEqual(u.ambiguous["course"], ["DH-AI", "DH-PTS"])
        self.assertEqual(u.parents["course"], "Thiết kế đồ họa")

    def test_exact_tap_maps_to_stored_action(self):
        options = {"Excel": {"type": "slot", "slot": "course", "value": "VP-EXCEL"}}
        u = understand("Excel", st("course", options), CAT)
        self.assertTrue(u.tapped)
        self.assertEqual(u.fills["course"], fill("VP-EXCEL", "button"))

    def test_stale_or_retyped_title_falls_back_to_keywords(self):
        options = {"Ca sáng": {"type": "slot", "slot": "preferred_shift", "value": "morning"}}
        u = understand("excel", st("preferred_shift", options), CAT)
        self.assertFalse(u.tapped)
        self.assertEqual(u.fills["course"]["value"], "VP-EXCEL")

    def test_single_word_choice_alias_only_when_pending(self):
        self.assertNotIn("preferred_shift", understand("tôi muốn hỏi", st(), CAT).fills)
        self.assertEqual(understand("học buổi tối", st(), CAT).fills["preferred_shift"]["value"], "evening")
        self.assertEqual(understand("tối", st("preferred_shift"), CAT).fills["preferred_shift"]["value"], "evening")
        self.assertEqual(understand("con", st("learner"), CAT).fills["learner"]["value"], "child")

    def test_number_and_text_only_when_pending(self):
        self.assertEqual(understand("bé 8 tuổi", st("learner_age"), CAT).fills["learner_age"]["value"], 8)
        self.assertNotIn("learner_age", understand("bé 8 tuổi", st(), CAT).fills)
        self.assertEqual(understand("Lan", st("customer_name"), CAT).fills["customer_name"]["value"], "Lan")
        u = understand("học phí bao nhiêu", st("customer_name"), CAT)
        self.assertNotIn("customer_name", u.fills)
        self.assertEqual(u.skills, ["fee_quote"])

    def test_phone_anywhere(self):
        self.assertEqual(understand("sdt em 0901 234 567", st(), CAT).fills["phone"]["value"], "+84901234567")

    def test_unmatched_words_are_collected(self):
        self.assertEqual(understand("abcxyz", st(), CAT).unmatched, ["abcxyz"])

    def test_match_courses_for_sync_webhook(self):
        self.assertEqual([c.code for c in match_courses("photoshop và illustrator", CAT)], ["DH-PTS", "DH-AI"])
        self.assertEqual(match_courses("xin chào", CAT), [])


class TestButtons(unittest.TestCase):
    def buttons(self, key, slots=None):
        slot = CAT.slot(key)
        return REGISTRY[slot.type].buttons(slot, slots or {}, CAT)

    def test_registry_matches_select_options(self):
        self.assertEqual(set(REGISTRY), set(catalog_rules.SLOT_TYPES))

    def test_course_buttons_are_tiered(self):
        top = self.buttons("course")
        self.assertEqual([b["title"] for b in top][:2], ["Tin học văn phòng", "Đồ họa"])
        self.assertEqual(top[0]["action"], {"type": "parent", "slot": "course", "value": "Tin học văn phòng"})
        inner = self.buttons("course", {"course": {"parent": "Kế toán"}})
        self.assertEqual(len(inner), 5)
        self.assertEqual(inner[0]["action"]["type"], "slot")

    def test_candidates_limit_buttons(self):
        got = self.buttons("course", {"course": {"candidates": ["DH-AI", "DH-PTS"]}})
        self.assertEqual({b["action"]["value"] for b in got}, {"DH-AI", "DH-PTS"})

    def test_advanced_course_offers_only_full_branches(self):
        got = self.buttons("branch", {"course": fill("VKT-REVIT"), "branch": {"parent": "TP. Hồ Chí Minh"}})
        self.assertEqual({b["title"] for b in got}, {"Bình Thạnh", "Thủ Đức"})
        none_there = self.buttons("branch", {"course": fill("VKT-REVIT"), "branch": {"parent": "Bà Rịa - Vũng Tàu"}})
        self.assertEqual(none_there[0]["action"]["type"], "parent")

    def test_choice_and_phone_buttons(self):
        self.assertEqual([b["title"] for b in self.buttons("learner")], ["Cho tôi", "Cho con em", "Cho công ty"])
        self.assertEqual(self.buttons("phone"), [])

    def test_compose_attaches_asked_slot_buttons(self):
        d = decide(ConversationState("1", turns=1), understand("xyz", st(), CAT), CAT)
        from engine_fixtures import render
        r = compose(d, ConversationState("1"), CAT, render)
        self.assertEqual(len(r.buttons), 8)
        self.assertEqual(r.options()["Kế toán"], {"type": "parent", "slot": "course", "value": "Kế toán"})


if __name__ == "__main__":
    unittest.main()
