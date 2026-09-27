import sys
from datetime import date
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, fill, promo, schedule

from mmm_custom import catalog_rules
from mmm_custom.engine.actions import ACTIONS, run_action
from mmm_custom.engine.context import base_context
from mmm_custom.engine.state import ConversationState

CAT = demo_catalog()
TODAY = date(2026, 9, 28)


def act(skill_key, slots, repo=None):
    ctx = base_context(slots, CAT, ConversationState("1", slots=slots))
    return run_action(CAT.skills[skill_key], ctx, slots, CAT, repo or FakeRepo(CAT), TODAY)


class TestContext(unittest.TestCase):
    def test_contract_keys_and_values(self):
        slots = {"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An"), "learner": fill("child"),
                 "customer_name": fill("Lan")}
        ctx = base_context(slots, CAT, ConversationState("1", is_returning=True))
        self.assertEqual(set(ctx), {"brand", "customer", "course", "branch", "area", "schedules", "promotions",
                                    "final_fee", "recommendations", "slots", "missing"})
        self.assertEqual((ctx["course"]["name"], ctx["course"]["fee"]), ("Excel từ cơ bản đến nâng cao", 1800000.0))
        self.assertEqual(ctx["course"]["next_courses"], ["Excel nâng cao & Dashboard", "Luyện thi MOS quốc tế"])
        self.assertEqual((ctx["branch"]["name"], ctx["area"]), ("CN Dĩ An", "Bình Dương"))
        self.assertEqual(ctx["customer"], {"name": "Lan", "learner": "Con em", "learner_age": "", "shift": "",
                                           "is_returning": True})
        self.assertEqual(ctx["slots"]["course"], "Excel từ cơ bản đến nâng cao")
        self.assertEqual(ctx["missing"], ["Số điện thoại"])
        self.assertEqual(ctx["brand"]["you"], "anh/chị")

    def test_empty_slots(self):
        ctx = base_context({}, CAT, ConversationState("1"))
        self.assertEqual((ctx["course"], ctx["branch"], ctx["area"], ctx["final_fee"]), ({}, {}, "", 0))


class TestActions(unittest.TestCase):
    def test_registry_matches_select_options(self):
        self.assertEqual(set(ACTIONS), set(catalog_rules.ACTION_TYPES))

    def test_fee_quote_takes_best_applicable_promotion(self):
        repo = FakeRepo(CAT)
        repo.promotions = [promo("Tất cả -10%"), promo("Long Thành -15%", amount=15, branches=["CN Long Thành"]),
                           promo("KT tổng hợp -500k", "Amount", 500000, courses=["KT-TH"])]
        out = act("fee_quote", {"course": fill("VP-EXCEL")}, repo)
        self.assertEqual((out["final_fee"], [p["title"] for p in out["promotions"]]), (1620000.0, ["Tất cả -10%"]))
        out = act("fee_quote", {"course": fill("VP-EXCEL"), "branch": fill("CN Long Thành")}, repo)
        self.assertEqual(out["final_fee"], 1530000.0)
        out = act("fee_quote", {"course": fill("KT-TH")}, repo)
        self.assertEqual(out["final_fee"], 3000000.0)
        self.assertEqual(out["promotions"][1]["discount"], "500.000đ")

    def test_schedule_lookup_falls_back_from_branch_and_shift(self):
        repo = FakeRepo(CAT)
        repo.schedules = [schedule("VP-EXCEL", "CN Dĩ An", date(2026, 10, 6)),
                          schedule("VP-EXCEL", "CN Dĩ An", date(2026, 9, 1))]
        out = act("schedule_lookup", {"course": fill("VP-EXCEL"), "branch": fill("CN Bình Thạnh"),
                                      "preferred_shift": fill("morning")}, repo)
        self.assertEqual([s["date"] for s in out["schedules"]], [date(2026, 10, 6)])
        self.assertEqual(act("schedule_lookup", {}, repo), {"schedules": []})

    def test_recommend_courses_filters_by_data(self):
        kids = act("kids_courses", {})
        self.assertEqual([r["code"] for r in kids["recommendations"]], ["TE-THUD", "TE-SCRATCH", "TE-PY"])
        self.assertEqual(kids["_buttons"][0]["action"], {"type": "slot", "slot": "course", "value": "TE-THUD"})
        teen = act("kids_courses", {"learner_age": fill(13)})
        self.assertEqual([r["code"] for r in teen["recommendations"]], ["TE-PY", "TE-ROBO-NC"])
        adult = act("course_advisor", {"learner": fill("self")})
        self.assertTrue(all(CAT.courses[r["code"]].audience != "Trẻ em" for r in adult["recommendations"]))

    def test_branch_info_lists_area_branches(self):
        out = act("branch_info", {"branch": {"parent": "Đồng Nai"}})
        self.assertEqual([b["name"] for b in out["branches"]], ["CN Biên Hòa", "CN Long Thành"])

    def test_send_media_without_image_attaches_nothing(self):
        self.assertEqual(act("course_content", {"course": fill("VP-EXCEL")}), {})


if __name__ == "__main__":
    unittest.main()
