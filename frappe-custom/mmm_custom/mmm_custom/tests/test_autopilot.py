import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.mmm_custom.doctype.facebook_post.facebook_post import FacebookPost


from mmm_custom import autopilot


class TestAutopilotSchema(unittest.TestCase):
    def test_post_has_autopilot_fields(self):
        doc = FacebookPost()
        doc.status = "Pending Approval"
        doc.batch_id = "BATCH-2026-W39"
        doc.boss_directive = "Ưu đãi 50% bơi lội hè"
        doc.day_of_week = "Thứ Hai"
        self.assertEqual(doc.status, "Pending Approval")
        self.assertEqual(doc.batch_id, "BATCH-2026-W39")
        self.assertEqual(doc.boss_directive, "Ưu đãi 50% bơi lội hè")
        self.assertEqual(doc.day_of_week, "Thứ Hai")

    def test_facebook_post_json_schema(self):
        schema_path = (
            Path(__file__).resolve().parent.parent
            / "mmm_custom"
            / "doctype"
            / "facebook_post"
            / "facebook_post.json"
        )
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        fields = {f["fieldname"]: f for f in schema.get("fields", [])}

        # Check status options
        self.assertIn("status", fields)
        status_options = fields["status"].get("options", "").split("\n")
        self.assertIn("Pending Approval", status_options)
        self.assertIn("Cancelled", status_options)

        # Check batch_id
        self.assertIn("batch_id", fields)
        self.assertEqual(fields["batch_id"].get("fieldtype"), "Data")
        self.assertEqual(fields["batch_id"].get("in_list_view"), 1)
        self.assertEqual(fields["batch_id"].get("in_standard_filter"), 1)
        self.assertEqual(fields["batch_id"].get("label"), "Mã đợt (Batch ID)")

        # Check boss_directive
        self.assertIn("boss_directive", fields)
        self.assertEqual(fields["boss_directive"].get("fieldtype"), "Small Text")
        self.assertEqual(fields["boss_directive"].get("label"), "Chỉ đạo tuần (Boss Directive)")

        # Check day_of_week
        self.assertIn("day_of_week", fields)
        self.assertEqual(fields["day_of_week"].get("fieldtype"), "Select")
        self.assertEqual(fields["day_of_week"].get("in_list_view"), 1)
        self.assertEqual(fields["day_of_week"].get("in_standard_filter"), 1)
        self.assertEqual(fields["day_of_week"].get("label"), "Thứ trong tuần")
        dow_options = fields["day_of_week"].get("options", "").split("\n")
        self.assertEqual(
            dow_options,
            ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"],
        )

        # Check field_order
        field_order = schema.get("field_order", [])
        self.assertIn("batch_id", field_order)
        self.assertIn("boss_directive", field_order)
        self.assertIn("day_of_week", field_order)


PLAN = [{"code": c, "name": n, "title": n, "reason": r} for c, n, r in (
    ("DH-PTS", "Photoshop cơ bản", "lớp khai giảng 05/10 còn 6 chỗ"),
    ("VP-EXCEL", "Excel cơ bản", "bài gần đây ra 2 khách tiềm năng"),
    ("TE-ROBO", "Robotics cơ bản", "lâu chưa đăng"),
    ("KT-TH", "Kế toán tổng hợp", "đang có ưu đãi “Giảm 500.000đ”"))]


BEFORE_THE_WEEK = autopilot.datetime(2026, 9, 27, 12, 0)


@patch("mmm_custom.autopilot._now", lambda: BEFORE_THE_WEEK)
@patch("mmm_custom.autopilot.plan_week", lambda *a, **k: PLAN)
class TestAutopilotEngine(unittest.TestCase):
    def test_get_weekly_matrix(self):
        """A slot is day, time and caption angle; the course comes from marketing_plan.plan_week (D-125)."""
        matrix = autopilot.get_weekly_matrix()
        self.assertEqual([(s["day_of_week"], s["time"]) for s in matrix],
                         [("Thứ Hai", "08:30:00"), ("Thứ Tư", "11:30:00"), ("Thứ Sáu", "19:30:00"),
                          ("Chủ Nhật", "09:00:00")])
        self.assertFalse(any("course" in s for s in matrix))

    @patch("mmm_custom.autopilot.frappe")
    def test_generate_weekly_batch(self, mock_frappe):
        created_docs = []

        def mock_new_doc(doctype):
            doc = MagicMock()
            doc.doctype = doctype
            doc.name = f"FB-TEST-{len(created_docs) + 1}"
            created_docs.append(doc)
            return doc

        mock_frappe.new_doc.side_effect = mock_new_doc

        directive = "Tập trung tuyển sinh hè giảm 50%"
        res = autopilot.generate_weekly_batch(
            boss_directive=directive,
            target_date="2026-09-28",
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["batch_id"], "BATCH-2026-W40")
        self.assertEqual(res["count"], 4)
        self.assertEqual(len(res["posts"]), 4)
        self.assertIn("pipeline", res)
        self.assertEqual(len(res["pipeline"]), 5)
        self.assertEqual(mock_frappe.new_doc.call_count, 4)

        # Verify docs attributes and method calls
        for idx, doc in enumerate(created_docs):
            self.assertEqual(doc.status, "Pending Approval")
            self.assertEqual(doc.batch_id, "BATCH-2026-W40")
            self.assertEqual(doc.boss_directive, directive)
            self.assertIn(directive, doc.title)
            doc.insert.assert_called_once_with(ignore_permissions=True)
            doc.generate_ai_content.assert_called_once_with(user_feedback=directive)
            doc.generate_banner.assert_called_once_with(user_feedback=directive)

        # Check Monday slot
        self.assertEqual(created_docs[0].course, "DH-PTS")
        self.assertEqual(created_docs[0].plan_reason, "lớp khai giảng 05/10 còn 6 chỗ")
        self.assertEqual(created_docs[0].day_of_week, "Thứ Hai")
        self.assertEqual(created_docs[0].scheduled_time, "2026-09-28 08:30:00")

        # Check Sunday slot
        self.assertEqual(created_docs[3].course, "KT-TH")
        self.assertEqual(created_docs[3].day_of_week, "Chủ Nhật")
        self.assertEqual(created_docs[3].scheduled_time, "2026-10-04 09:00:00")

    def test_plan_is_judged_from_today_not_from_monday(self):
        """On a Thursday the week's classes are those still to come, not the ones that started on Monday."""
        seen = []
        with patch("mmm_custom.autopilot.plan_week", lambda today, n=4, **kw: seen.append(today) or PLAN),                 patch("mmm_custom.autopilot.frappe") as mock_frappe,                 patch("mmm_custom.autopilot._today", lambda: autopilot.date(2026, 10, 1)):  # a Thursday
            mock_frappe.new_doc.side_effect = lambda doctype: MagicMock()
            autopilot.generate_weekly_batch(target_date="2026-10-01")
            autopilot.generate_weekly_batch(target_date="2026-10-12")  # a later week starts on its Monday
        self.assertEqual(seen, [autopilot.date(2026, 10, 1), autopilot.date(2026, 10, 12)])

    def test_slots_already_past_are_not_planned(self):
        """Planned on Thursday 01/10 at 10:00: Monday and Wednesday are gone, Friday and Sunday remain."""
        asked = []
        with patch("mmm_custom.autopilot._now", lambda: autopilot.datetime(2026, 10, 1, 10, 0)),                 patch("mmm_custom.autopilot._today", lambda: autopilot.date(2026, 10, 1)),                 patch("mmm_custom.autopilot.plan_week", lambda today, n=4, offer_slot=3: asked.append((n, offer_slot)) or PLAN[:n]),                 patch("mmm_custom.autopilot.frappe") as mock_frappe:
            docs = []
            mock_frappe.new_doc.side_effect = lambda doctype: docs.append(MagicMock()) or docs[-1]
            res = autopilot.generate_weekly_batch()
        self.assertEqual(res["count"], 2)
        self.assertEqual(res["skipped"], ["Thứ Hai", "Thứ Tư"])
        self.assertEqual(asked, [(2, 1)])  # Sunday is the second remaining slot: the offer slot
        self.assertEqual([d.scheduled_time for d in docs], ["2026-10-02 19:30:00", "2026-10-04 09:00:00"])
        self.assertIn("bỏ qua Thứ Hai, Thứ Tư", res["pipeline"][3]["action"])

    def test_a_finished_week_plans_the_next_one(self):
        with patch("mmm_custom.autopilot._now", lambda: autopilot.datetime(2026, 10, 4, 20, 0)),                 patch("mmm_custom.autopilot._today", lambda: autopilot.date(2026, 10, 4)),                 patch("mmm_custom.autopilot.frappe") as mock_frappe:
            docs = []
            mock_frappe.new_doc.side_effect = lambda doctype: docs.append(MagicMock()) or docs[-1]
            res = autopilot.generate_weekly_batch()
        self.assertEqual((res["batch_id"], res["count"], res["skipped"]), ("BATCH-2026-W41", 4, []))
        self.assertEqual(docs[0].scheduled_time, "2026-10-05 08:30:00")

    @patch("mmm_custom.autopilot.frappe")
    def test_approving_keeps_posts_whose_time_has_passed(self, mock_frappe):
        mock_frappe.get_all.return_value = [
            {"name": 39, "scheduled_time": autopilot.datetime(2026, 9, 26, 11, 30)},
            {"name": 40, "scheduled_time": autopilot.datetime(2026, 10, 2, 19, 30)},
        ]
        res = autopilot.approve_weekly_batch()
        mock_frappe.db.set_value.assert_called_once_with("Facebook Post", 40, "status", "Scheduled")
        self.assertEqual((res["approved_count"], res["past_due"]), (1, [39]))

    @patch("mmm_custom.autopilot.frappe")
    def test_generate_weekly_batch_no_directive(self, mock_frappe):
        created_docs = []

        def mock_new_doc(doctype):
            doc = MagicMock()
            doc.doctype = doctype
            doc.name = f"FB-TEST-{len(created_docs) + 1}"
            created_docs.append(doc)
            return doc

        mock_frappe.new_doc.side_effect = mock_new_doc

        res = autopilot.generate_weekly_batch(
            boss_directive=None,
            target_date="2026-09-28",
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["batch_id"], "BATCH-2026-W40")
        self.assertEqual(res["count"], 4)

        # Slot 0 default title
        self.assertEqual(created_docs[0].title, "Photoshop cơ bản")
        self.assertEqual(created_docs[0].boss_directive, "")
        created_docs[0].generate_ai_content.assert_called_once_with(user_feedback=None)
        created_docs[0].generate_banner.assert_called_once_with(user_feedback=None)

    @patch("mmm_custom.autopilot.frappe")
    def test_approve_weekly_batch_with_id(self, mock_frappe):
        mock_frappe.get_all.return_value = ["POST-1", "POST-2"]
        res = autopilot.approve_weekly_batch(batch_id="BATCH-2026-W40")

        mock_frappe.get_all.assert_called_once_with(
            "Facebook Post",
            filters={"status": "Pending Approval", "batch_id": "BATCH-2026-W40"},
            fields=["name", "scheduled_time"],
        )
        self.assertEqual(mock_frappe.db.set_value.call_count, 2)
        mock_frappe.db.set_value.assert_any_call("Facebook Post", "POST-1", "status", "Scheduled")
        mock_frappe.db.set_value.assert_any_call("Facebook Post", "POST-2", "status", "Scheduled")
        mock_frappe.db.commit.assert_called_once()
        self.assertEqual(res, {"status": "success", "approved_count": 2, "past_due": []})

    @patch("mmm_custom.autopilot.frappe")
    def test_approve_weekly_batch_without_id(self, mock_frappe):
        mock_frappe.get_all.return_value = ["POST-1", "POST-2", "POST-3"]
        res = autopilot.approve_weekly_batch()

        mock_frappe.get_all.assert_called_once_with(
            "Facebook Post",
            filters={"status": "Pending Approval"},
            fields=["name", "scheduled_time"],
        )
        self.assertEqual(mock_frappe.db.set_value.call_count, 3)
        mock_frappe.db.commit.assert_called_once()
        self.assertEqual(res, {"status": "success", "approved_count": 3, "past_due": []})

    @patch("mmm_custom.autopilot.frappe")
    def test_approve_weekly_batch_integer_ids(self, mock_frappe):
        mock_frappe.get_all.return_value = [10, 11, 12]
        res = autopilot.approve_weekly_batch(batch_id="BATCH-2026-W39")

        self.assertEqual(mock_frappe.db.set_value.call_count, 3)
        mock_frappe.db.set_value.assert_any_call("Facebook Post", 10, "status", "Scheduled")
        mock_frappe.db.set_value.assert_any_call("Facebook Post", 11, "status", "Scheduled")
        mock_frappe.db.set_value.assert_any_call("Facebook Post", 12, "status", "Scheduled")
        mock_frappe.db.commit.assert_called_once()
        self.assertEqual(res, {"status": "success", "approved_count": 3, "past_due": []})

    @patch("mmm_custom.autopilot.frappe")
    def test_rollback_weekly_batch(self, mock_frappe):
        mock_frappe.get_all.return_value = ["OLD-POST-1", "OLD-POST-2"]

        # Mock newly generated doc
        mock_doc = MagicMock()
        mock_doc.name = "NEW-POST-1"
        mock_frappe.new_doc.return_value = mock_doc

        res = autopilot.rollback_weekly_batch(
            batch_id="BATCH-2026-W40",
            new_directive="Chỉ đạo mới tuần 40",
        )

        mock_frappe.get_all.assert_called_once_with(
            "Facebook Post",
            filters={
                "status": ["in", ["Pending Approval", "Scheduled"]],
                "batch_id": "BATCH-2026-W40",
            },
            pluck="name",
        )
        self.assertEqual(mock_frappe.db.set_value.call_count, 2)
        mock_frappe.db.set_value.assert_any_call("Facebook Post", "OLD-POST-1", "status", "Cancelled")
        mock_frappe.db.set_value.assert_any_call("Facebook Post", "OLD-POST-2", "status", "Cancelled")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["cancelled_count"], 2)
        self.assertIn("pipeline", res)
        self.assertEqual(len(res["pipeline"]), 4)
        self.assertEqual(res["new_batch"]["status"], "success")
        self.assertEqual(res["new_batch"]["batch_id"], "BATCH-2026-W40")

    @patch("mmm_custom.autopilot.frappe")
    def test_rollback_weekly_batch_without_id(self, mock_frappe):
        mock_frappe.get_all.return_value = ["OLD-POST-1"]
        mock_doc = MagicMock()
        mock_doc.name = "NEW-POST-1"
        mock_frappe.new_doc.return_value = mock_doc

        res = autopilot.rollback_weekly_batch()

        mock_frappe.get_all.assert_called_once_with(
            "Facebook Post",
            filters={"status": ["in", ["Pending Approval", "Scheduled"]]},
            pluck="name",
        )
        self.assertEqual(mock_frappe.db.set_value.call_count, 1)
        self.assertEqual(res["cancelled_count"], 1)
        self.assertEqual(res["new_batch"]["status"], "success")

    @patch("mmm_custom.autopilot.frappe")
    def test_recall_post_scheduled(self, mock_frappe):
        mock_doc = MagicMock()
        mock_doc.name = "POST-10"
        mock_doc.status = "Scheduled"
        mock_frappe.get_doc.return_value = mock_doc

        res = autopilot.recall_post("POST-10")

        mock_frappe.get_doc.assert_called_once_with("Facebook Post", "POST-10")
        self.assertEqual(mock_doc.status, "Pending Approval")
        mock_doc.save.assert_called_once()
        mock_frappe.db.commit.assert_called_once()
        self.assertEqual(res, {"status": "success", "name": "POST-10", "status": "Pending Approval"})

    @patch("mmm_custom.autopilot.frappe")
    def test_recall_post_non_scheduled(self, mock_frappe):
        mock_doc = MagicMock()
        mock_doc.name = "POST-11"
        mock_doc.status = "Posted"
        mock_frappe.get_doc.return_value = mock_doc

        res = autopilot.recall_post("POST-11")

        mock_frappe.get_doc.assert_called_once_with("Facebook Post", "POST-11")
        self.assertEqual(mock_doc.status, "Posted")
        mock_doc.save.assert_not_called()
        self.assertEqual(res, {"status": "success", "name": "POST-11", "status": "Posted"})

    @patch("mmm_custom.autopilot.frappe")
    def test_publish_scheduled_posts_success(self, mock_frappe):
        mock_frappe.get_all.return_value = [{"name": "FB-POST-1"}]
        mock_doc = MagicMock()
        mock_frappe.get_doc.return_value = mock_doc

        res = autopilot.publish_scheduled_posts()

        mock_frappe.get_all.assert_called_once()
        mock_frappe.get_doc.assert_called_once_with("Facebook Post", "FB-POST-1")
        mock_doc.post_now.assert_called_once()
        mock_frappe.db.commit.assert_called_once()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["published"], 1)
        self.assertEqual(res["published_posts"], ["FB-POST-1"])

    @patch("mmm_custom.autopilot.frappe")
    def test_publish_scheduled_posts_no_due_posts(self, mock_frappe):
        mock_frappe.get_all.return_value = []

        res = autopilot.publish_scheduled_posts()

        mock_frappe.get_all.assert_called_once()
        mock_frappe.get_doc.assert_not_called()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["published"], 0)
        self.assertEqual(res["published_posts"], [])

    @patch("mmm_custom.autopilot.frappe")
    def test_publish_scheduled_posts_handles_exception(self, mock_frappe):
        mock_frappe.get_all.return_value = [{"name": "FB-POST-ERR"}]
        mock_doc = MagicMock()
        mock_doc.post_now.side_effect = Exception("Meta API network timeout")
        mock_frappe.get_doc.return_value = mock_doc

        res = autopilot.publish_scheduled_posts()

        mock_frappe.get_all.assert_called_once()
        mock_frappe.get_doc.assert_called_once_with("Facebook Post", "FB-POST-ERR")
        mock_doc.post_now.assert_called_once()
        mock_frappe.log_error.assert_called_once_with(
            title="Autopilot Publish Error",
            message="Meta API network timeout",
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["published"], 0)
        self.assertEqual(res["published_posts"], [])

    def test_hooks_register_publish_scheduled_posts(self):
        hooks_content = (APP_DIR / "mmm_custom" / "hooks.py").read_text(encoding="utf-8")
        self.assertIn('"mmm_custom.autopilot.publish_scheduled_posts"', hooks_content)
        self.assertIn('"*/5 * * * *"', hooks_content)

    @patch("mmm_custom.autopilot.frappe.db.commit")
    @patch("mmm_custom.autopilot.frappe.new_doc")
    def test_generate_weekly_batch_with_facebook_page(self, mock_new_doc, mock_commit):
        """Batch generation should set facebook_page on each post when provided."""
        created_mock_docs = []

        def side_effect(doctype):
            d = MagicMock()
            d.doctype = doctype
            d.name = f"FB-TEST-{len(created_mock_docs) + 1}"
            d.title = ""
            d.course = ""
            d.facebook_page = None
            d.status = ""
            created_mock_docs.append(d)
            return d

        mock_new_doc.side_effect = side_effect

        target_date = "2026-10-12"
        res = autopilot.generate_weekly_batch(
            boss_directive="Chi nhánh 2 ưu đãi",
            target_date=target_date,
            facebook_page="1324629057402921",
        )
        self.assertEqual(res["status"], "success")
        self.assertGreater(len(created_mock_docs), 0)
        for doc in created_mock_docs:
            self.assertEqual(doc.facebook_page, "1324629057402921")


if __name__ == "__main__":
    unittest.main()

