import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_fixtures  # noqa: F401  (puts the app on sys.path)

from mmm_custom.engine.customers import build, handoff_why

PEOPLE = [
    {"user": "mai@x", "full_name": "Mai", "branch": "CN Bình Thạnh", "level": "Team Lead", "handles_b2b": 0},
    {"user": "anh@x", "full_name": "Anh", "branch": "", "level": "Consultant", "handles_b2b": 1},
]


def lead(name, **kw):
    return {"name": name, "lead_name": name.title(), "creation": f"2026-09-2{len(name) % 8} 10:00", **kw}


LEADS = [
    lead("a", source="Facebook Messenger", mobile_no="+84901", status="Qualified", lead_owner="mai@x",
         territory="CN Bình Thạnh", ai_hotness="hot"),
    lead("bb", source="Messenger Bot", status="New", territory="CN Quận 7"),
    lead("ccc", source="Facebook", mobile_no="+84902", status="Qualified", lead_owner="mai@x", converted=1),
    lead("dddd", source="Báo giấy", lead_owner="anh@x", ai_hotness="warm"),
]
GROUPS = {"a": ["Tin học văn phòng"], "ccc": ["Tin học văn phòng", "Kế toán"]}


class TestCustomerDashboard(unittest.TestCase):
    def setUp(self):
        self.out = build(LEADS, GROUPS, PEOPLE, {"a": "CN Bình Thạnh · chuyên Tin học văn phòng · ít khách nhất"})

    def test_funnel_counts_each_stage(self):
        self.assertEqual([s["count"] for s in self.out["funnel"]], [4, 2, 2, 3, 1, 1])
        self.assertEqual([s["stage"] for s in self.out["funnel"]],
                         ["Lead mới", "Có số điện thoại", "Đủ thông tin", "Đã giao tư vấn", "Hẹn học thử", "Đã đăng ký"])
        self.assertEqual((self.out["totals"]["hot"], self.out["totals"]["b2b"]), (1, 1))

    def test_sources_list_every_channel_legacy_names_included_and_other(self):
        counts = {s["key"]: s["count"] for s in self.out["sources"]}
        self.assertEqual((counts["facebook_messenger"], counts["facebook_lead_ads"], counts["zalo"], counts[""]), (2, 1, 0, 1))
        self.assertEqual(next(s for s in self.out["sources"] if s["key"] == "tiktok")["status"], "planned")
        messenger = next(s for s in self.out["sources"] if s["key"] == "facebook_messenger")
        self.assertEqual(messenger["values"], ["Facebook Messenger", "Messenger", "Messenger Bot"])  # list filter

    def test_groups_branches_and_hotness(self):
        self.assertEqual(self.out["groups"][0], {"name": "Tin học văn phòng", "count": 2})
        self.assertIn({"name": "Chưa rõ khóa", "count": 2}, self.out["groups"])
        self.assertIn({"name": "Chưa rõ chi nhánh", "count": 2}, self.out["branches"])
        self.assertEqual([h["count"] for h in self.out["hotness"]], [1, 1, 0, 2])

    def test_consultant_leaderboard_ranks_by_enrolments(self):
        top = self.out["consultants"][0]
        self.assertEqual((top["full_name"], top["leads"], top["qualified"], top["converted"], top["rate"]), ("Mai", 2, 2, 1, 50))
        self.assertEqual(self.out["consultants"][1]["branch"], "Doanh nghiệp (B2B)")

    def test_latest_leads_explain_the_assignment(self):
        row = next(r for r in self.out["latest"] if r["name"] == "a")
        self.assertEqual((row["source"], row["owner"], row["status"], row["hotness"]),
                         ("Facebook Messenger", "Mai", "Đủ thông tin", "Nóng"))
        self.assertIn("ít khách nhất", row["why"])
        self.assertEqual(next(r for r in self.out["latest"] if r["name"] == "ccc")["status"], "Đã đăng ký")

    def test_later_steps_count_as_qualified(self):
        out = build([lead("e", status="Contacted", lead_owner="mai@x"), lead("f", status="Trial Booked")], {}, PEOPLE, {})
        self.assertEqual((out["totals"]["qualified"], out["totals"]["trial"]), (2, 1))
        self.assertEqual(out["latest"][0]["status"] in ("Đang tư vấn", "Hẹn học thử / test"), True)

    def test_handoff_why_keeps_only_the_routing_part(self):
        self.assertEqual(handoff_why("Đã đủ thông tin bắt buộc · CN Quận 7 · ít khách nhất · Lead: Đủ thông tin"),
                         "CN Quận 7 · ít khách nhất")
        self.assertEqual(handoff_why(""), "")


if __name__ == "__main__":
    unittest.main()
