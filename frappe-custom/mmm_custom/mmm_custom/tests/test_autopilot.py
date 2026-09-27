import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.mmm_custom.doctype.facebook_post.facebook_post import FacebookPost


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


if __name__ == "__main__":
    unittest.main()
