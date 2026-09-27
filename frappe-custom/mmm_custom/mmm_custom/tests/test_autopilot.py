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


class TestAutopilotEngine(unittest.TestCase):
    def test_get_weekly_matrix(self):
        matrix = autopilot.get_weekly_matrix()
        self.assertEqual(len(matrix), 4)

        # Slot 0: Monday
        self.assertEqual(matrix[0]["course"], "Tiếng Anh")
        self.assertEqual(matrix[0]["day_of_week"], "Thứ Hai")
        self.assertEqual(matrix[0]["time"], "08:30:00")
        self.assertEqual(matrix[0]["default_title"], "Khai giảng Tiếng Anh giao tiếp")

        # Slot 1: Wednesday
        self.assertEqual(matrix[1]["course"], "Toán tư duy")
        self.assertEqual(matrix[1]["day_of_week"], "Thứ Tư")
        self.assertEqual(matrix[1]["time"], "11:30:00")
        self.assertEqual(matrix[1]["default_title"], "Phát triển tư duy logic")

        # Slot 2: Friday
        self.assertEqual(matrix[2]["course"], "Bơi lội")
        self.assertEqual(matrix[2]["day_of_week"], "Thứ Sáu")
        self.assertEqual(matrix[2]["time"], "19:30:00")
        self.assertEqual(matrix[2]["default_title"], "Khóa bơi sinh tồn cho bé")

        # Slot 3: Sunday
        self.assertEqual(matrix[3]["course"], "Chung")
        self.assertEqual(matrix[3]["day_of_week"], "Chủ Nhật")
        self.assertEqual(matrix[3]["time"], "09:00:00")
        self.assertEqual(matrix[3]["default_title"], "Tuyển sinh & Học bổng EduFlow")

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
        self.assertEqual(created_docs[0].course, "Tiếng Anh")
        self.assertEqual(created_docs[0].day_of_week, "Thứ Hai")
        self.assertEqual(created_docs[0].scheduled_time, "2026-09-28 08:30:00")

        # Check Sunday slot
        self.assertEqual(created_docs[3].course, "Chung")
        self.assertEqual(created_docs[3].day_of_week, "Chủ Nhật")
        self.assertEqual(created_docs[3].scheduled_time, "2026-10-04 09:00:00")

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
        self.assertEqual(created_docs[0].title, "Khai giảng Tiếng Anh giao tiếp")
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
            pluck="name",
        )
        self.assertEqual(mock_frappe.db.set_value.call_count, 2)
        mock_frappe.db.set_value.assert_any_call("Facebook Post", "POST-1", "status", "Scheduled")
        mock_frappe.db.set_value.assert_any_call("Facebook Post", "POST-2", "status", "Scheduled")
        mock_frappe.db.commit.assert_called_once()
        self.assertEqual(res, {"status": "success", "approved_count": 2})

    @patch("mmm_custom.autopilot.frappe")
    def test_approve_weekly_batch_without_id(self, mock_frappe):
        mock_frappe.get_all.return_value = ["POST-1", "POST-2", "POST-3"]
        res = autopilot.approve_weekly_batch()

        mock_frappe.get_all.assert_called_once_with(
            "Facebook Post",
            filters={"status": "Pending Approval"},
            pluck="name",
        )
        self.assertEqual(mock_frappe.db.set_value.call_count, 3)
        mock_frappe.db.commit.assert_called_once()
        self.assertEqual(res, {"status": "success", "approved_count": 3})

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


if __name__ == "__main__":
    unittest.main()
