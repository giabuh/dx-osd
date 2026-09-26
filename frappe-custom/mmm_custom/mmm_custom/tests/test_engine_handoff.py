import sys
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, demo_consultants, fill, render, schedule

from mmm_custom.engine.chatwoot_setup import plan_attributes
from mmm_custom.engine.decide import Decision
from mmm_custom.engine.effects import ChatwootEffects
from mmm_custom.engine.handoff import HandoffPlan, plan_handoff
from mmm_custom.engine.routing import pick_consultant
from mmm_custom.engine.state import ConversationState

CAT = demo_catalog()
PEOPLE = [
    {"name": "mai@x", "full_name": "Mai", "branch": "CN Dĩ An", "chatwoot_agent_id": 11, "active": 1, "handles_b2b": 0},
    {"name": "lan@x", "full_name": "Lan", "branch": "CN Dĩ An", "chatwoot_agent_id": 12, "active": 1, "handles_b2b": 0},
    {"name": "an@x", "full_name": "An", "branch": "CN Dĩ An", "chatwoot_agent_id": None, "active": 1, "handles_b2b": 0},
    {"name": "hoa@x", "full_name": "Hoa", "branch": "", "chatwoot_agent_id": 20, "active": 1, "handles_b2b": 0},
    {"name": "b2b@x", "full_name": "B2B", "branch": "", "chatwoot_agent_id": 30, "active": 1, "handles_b2b": 1},
]


class TestRouting(unittest.TestCase):
    def test_least_loaded_in_branch_then_name(self):
        self.assertEqual(pick_consultant("CN Dĩ An", PEOPLE, {"mai@x": 3, "lan@x": 1})[0]["name"], "lan@x")
        self.assertEqual(pick_consultant("CN Dĩ An", PEOPLE, {"mai@x": 1, "lan@x": 1}),
                         (PEOPLE[1], "CN Dĩ An · ít khách nhất"))

    def test_consultant_without_chatwoot_agent_is_skipped(self):
        self.assertNotEqual(pick_consultant("CN Dĩ An", PEOPLE, {"mai@x": 5, "lan@x": 5})[0]["name"], "an@x")

    def test_returning_customer_goes_to_lead_owner(self):
        self.assertEqual(pick_consultant("CN Dĩ An", PEOPLE, {}, owner="hoa@x"),
                         (PEOPLE[3], "Khách quay lại · người phụ trách Lead"))
        self.assertEqual(pick_consultant("CN Dĩ An", PEOPLE, {}, owner="gone@x")[0]["name"], "lan@x")

    def test_central_team_when_branch_has_nobody(self):
        self.assertEqual(pick_consultant("CN Vũng Tàu", PEOPLE, {}), (PEOPLE[3], "Tổng đài · ít khách nhất"))
        self.assertEqual(pick_consultant("", [], {}), (None, "Chưa có tư vấn viên phù hợp"))


class TestPlan(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo(CAT)
        self.repo.consultant_rows = demo_consultants()
        self.repo.schedules = [schedule("VP-EXCEL", "CN Dĩ An", date(2026, 10, 6))]
        self.slots = {"course": {**fill("VP-EXCEL"), "parent": "Tin học văn phòng"}, "branch": fill("CN Dĩ An"),
                      "phone": fill("+84901234567"), "customer_name": fill("Lan"), "learner": fill("child"),
                      "learner_age": fill(9)}

    def plan(self, state=None, **settings):
        cat = demo_catalog(**settings) if settings else CAT
        decision = Decision("handoff", slots=self.slots, skills=["fee_quote"], handoff_reason="required_filled",
                            reason="Đã đủ thông tin bắt buộc")
        return plan_handoff(state or ConversationState("1", answered=["schedule_lookup"]), decision, cat, self.repo, render)

    def test_branch_consultant_team_labels_attributes(self):
        p = self.plan()
        self.assertEqual((p.consultant["branch"], p.team, p.why), ("CN Dĩ An", "CN Dĩ An", "CN Dĩ An · ít khách nhất"))
        self.assertEqual(p.labels, ["tin-hoc-van-phong", "cn-di-an"])
        self.assertEqual(p.attributes["bot_course"], "Excel từ cơ bản đến nâng cao")
        self.assertEqual(p.attributes["bot_learner"], "Con em")
        self.assertEqual(p.owner, p.consultant["name"])
        self.assertEqual(p.consultant_ctx, {"name": p.consultant["full_name"], "branch": "CN Dĩ An"})

    def test_summary_note_from_template_with_computed_next_step(self):
        s = self.plan().summary
        for part in ("Lan", "+84901234567", "Con em (9 tuổi)", "Excel từ cơ bản đến nâng cao (1.800.000đ)", "CN Dĩ An",
                     "lịch khai giảng", "học phí", "gọi xác nhận lớp Thứ 3, 06/10 (Tối 17:00–21:00) tại CN Dĩ An, còn 6 chỗ",
                     "CN Dĩ An · ít khách nhất"):
            self.assertIn(part, s)

    def test_returning_customer_goes_back_to_owner(self):
        owner = next(c for c in demo_consultants() if c["branch"] == "CN Biên Hòa")
        self.repo.owners = {"L1": owner["name"]}
        p = self.plan(ConversationState("1", lead="L1", is_returning=True))
        self.assertEqual((p.consultant["name"], p.team), (owner["name"], "CN Biên Hòa"))

    def test_broken_summary_template_falls_back(self):
        p = self.plan(summary_template="{{ nope.x }}")
        self.assertEqual(p.errors[0]["type"], "render_error")
        self.assertTrue(p.summary.startswith("🤖 Bot chuyển khách"))


class TestEffects(unittest.TestCase):
    def test_handoff_step_failure_does_not_stop_others(self):
        bot, user = MagicMock(), MagicMock()
        bot.assign_conversation.side_effect = RuntimeError("401")
        user.list_teams.return_value = [{"id": 4, "name": "cn dĩ an"}]
        plan = HandoffPlan({"name": "mai@x", "chatwoot_agent_id": 11, "branch": "CN Dĩ An"}, "why", "CN Dĩ An",
                           labels=["cn-di-an"], attributes={"bot_branch": "CN Dĩ An"}, summary="note", owner="mai@x")
        with patch("mmm_custom.engine.repo.set_lead_owner") as owner:
            errors = ChatwootEffects(bot, user).handoff(5, plan, "L1")
        self.assertEqual([e["step"] for e in errors], ["assign_agent"])
        bot.assign_team.assert_called_once_with(5, 4)
        bot.toggle_status.assert_called_once_with(5, "open")
        bot.add_labels.assert_called_once_with(5, ["cn-di-an"])
        bot.set_conversation_attributes.assert_called_once_with(5, {"bot_branch": "CN Dĩ An"})
        bot.send_private_note.assert_called_once_with(5, "note")
        owner.assert_called_once_with("L1", "mai@x")


class TestChatwootSetup(unittest.TestCase):
    def test_plan_attributes_skips_existing(self):
        self.assertEqual(plan_attributes(CAT.slots[:2], {"bot_course"}), [("bot_branch", "Bot · Chi nhánh")])


if __name__ == "__main__":
    unittest.main()
