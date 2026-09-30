# Copyright (c) 2026, MMM and contributors
# For license information, please see license.txt

import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

# Dynamically import scripts/comment-reply.py
REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = REPO_ROOT / "scripts" / "comment-reply.py"
spec = importlib.util.spec_from_file_location("comment_reply_mod", SCRIPT_PATH)
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)


class TestCommentReplySystem(unittest.TestCase):
    def test_send_private_reply_success(self):
        """Test successful private Messenger reply dispatch."""
        with patch.object(cr.requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "recipient_id": "12345",
                "message_id": "m_abc123",
            }
            mock_post.return_value = mock_resp

            res = cr.send_private_reply("page_123", "token_xyz", "comment_456", "Xin chào bạn!")
            self.assertIsNotNone(res)
            self.assertEqual(res["message_id"], "m_abc123")
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            self.assertEqual(kwargs["json"]["recipient"]["comment_id"], "comment_456")
            self.assertEqual(kwargs["json"]["message"]["text"], "Xin chào bạn!")

    def test_send_private_reply_already_replied(self):
        """Test handling of Facebook code 10900 (already replied)."""
        with patch.object(cr.requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 400
            mock_resp.json.return_value = {
                "error": {
                    "message": "(#10900) Activity already replied to",
                    "code": 10900,
                }
            }
            mock_post.return_value = mock_resp

            res = cr.send_private_reply("page_123", "token_xyz", "comment_456", "Xin chào!")
            self.assertIsNotNone(res)
            self.assertEqual(res.get("status"), "already_replied")

    @patch.dict("os.environ", {"GEMINI_API_KEY": "fake_gemini_key", "GEMINI_MODEL": "gemini-3.8-flash"})
    def test_generate_ai_comment_reply_gemini(self):
        """Test public comment reply generation using Gemini AI."""
        with patch.object(cr.requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "Dạ em chào anh Nam! Em đã gửi tin nhắn riêng cho anh rồi ạ ✨"}]
                        }
                    }
                ]
            }
            mock_post.return_value = mock_resp

            reply = cr.generate_ai_comment_reply("Nam", "Học phí bao nhiêu ạ?")
            self.assertIn("Dạ em chào anh Nam", reply)

    @patch.dict("os.environ", {"GEMINI_API_KEY": "fake_gemini_key", "GEMINI_MODEL": "gemini-3.8-flash"})
    def test_generate_ai_private_reply_gemini(self):
        """Test private Messenger reply generation using Gemini AI."""
        with patch.object(cr.requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "Dạ em chào bạn Linh! Khóa học đang có ưu đãi 30%, bạn để lại SĐT để em tư vấn nhé 🎓"
                                }
                            ]
                        }
                    }
                ]
            }
            mock_post.return_value = mock_resp

            reply = cr.generate_ai_private_reply("Linh", "Khóa này có học online không?")
            self.assertIn("Dạ em chào bạn Linh", reply)
            self.assertIn("30%", reply)

    @patch.object(cr, "load_replied_comments", return_value=set())
    @patch.object(cr, "save_replied_comments")
    @patch.object(cr, "get_recent_posts")
    @patch.object(cr, "get_comments")
    @patch.object(cr, "reply_to_comment")
    @patch.object(cr, "send_private_reply")
    @patch.object(cr, "like_comment")
    def test_process_comments_dual_mode(
        self,
        mock_like,
        mock_send_private,
        mock_reply,
        mock_get_comments,
        mock_get_posts,
        mock_save,
        mock_load,
    ):
        """Test that process_comments triggers both public reply and private Messenger message."""
        mock_get_posts.return_value = [{"id": "post_1", "message": "Khai giảng khóa mới"}]
        mock_get_comments.return_value = [
            {
                "id": "c_1",
                "from": {"name": "Hải", "id": "user_hai"},
                "message": "Quan tâm khóa học",
            }
        ]
        mock_reply.return_value = {"id": "c_1_reply"}
        mock_send_private.return_value = {"message_id": "m_hai"}

        count = cr.process_comments("page_test", "token_test", limit=1, dry_run=False, verbose=False)
        self.assertEqual(count, 1)

        mock_reply.assert_called_once()
        mock_send_private.assert_called_once_with(
            "page_test", "token_test", "c_1", unittest.mock.ANY
        )
        mock_like.assert_called_once_with("c_1", "token_test")

    def test_get_smart_quick_replies_rules(self):
        """Test contextual quick reply generation and Facebook 20-character limit."""
        replies_branch = cr.get_smart_quick_replies("Photoshop thực chiến", "mình muốn học ở Bình Thạnh")
        self.assertTrue(len(replies_branch) >= 3)
        for r in replies_branch:
            self.assertLessEqual(len(r["title"]), 20, f"Title too long: {r['title']}")
            self.assertEqual(r["content_type"], "text")

        # Initial conversation without course -> offers course choices
        replies_course = cr.get_smart_quick_replies(None, "tư vấn giúp mình")
        self.assertTrue(len(replies_course) >= 3)
        for r in replies_course:
            self.assertLessEqual(len(r["title"]), 20)

        # Phone provided -> must return NO buttons (clean conclusion)
        self.assertEqual(cr.get_smart_quick_replies("Photoshop", "0901234567"), [])
        self.assertEqual(cr.get_smart_quick_replies("Photoshop", "đây là số mình", has_phone=True), [])

        # Thank you / Goodbye -> must return NO buttons
        self.assertEqual(cr.get_smart_quick_replies("Photoshop", "cảm ơn em nhiều nha"), [])

        # Asking for phone / customer clicked send phone -> NO buttons (clean typing input)
        self.assertEqual(cr.get_smart_quick_replies("Photoshop", "gửi số điện thoại"), [])
        self.assertEqual(cr.get_smart_quick_replies("Photoshop", "lớp tối 2-4-6"), [])

    def test_phone_number_handling(self):
        """Test asking for real digits vs acknowledging valid phone."""
        # Clicked phone button or said "gửi số điện thoại" without digits
        ask_digits = cr.generate_ai_conversation_reply("Thành", [], "gửi số điện thoại")
        self.assertIn("chữ số điện thoại", ask_digits)

        # Provided actual phone digits
        ack_phone = cr.generate_ai_conversation_reply("Thành", [], "SĐT mình là 0912345678 nhé")
        self.assertIn("0912345678", ack_phone)
        self.assertIn("liên hệ", ack_phone)

        # Concluding thanks
        ack_thanks = cr.generate_ai_conversation_reply("Thành", [], "Cảm ơn em")
        self.assertIn("Chúc", ack_thanks)

    def test_detect_course_and_branch_matchers(self):
        """Test heuristic detection of course and campus."""
        self.assertEqual(cr.detect_course_from_text("mình muốn học pts thiết kế"), "Photoshop thực chiến")
        self.assertEqual(cr.detect_course_from_text("lớp excel và luyện thi mos"), "Tin học văn phòng & Luyện thi MOS")
        self.assertEqual(cr.detect_course_from_text("khóa python cơ bản"), "Lập trình Python thực chiến")
        self.assertIsNone(cr.detect_course_from_text("xin chào ad"))

        self.assertEqual(cr.detect_branch_from_text("mình ở gần cơ sở bình thạnh"), "CS1 Bình Thạnh")
        self.assertEqual(cr.detect_branch_from_text("lớp quận 1 còn chỗ không"), "CS2 Quận 1")
        self.assertEqual(cr.detect_branch_from_text("ở thủ đức học mấy giờ"), "CS3 Thủ Đức")
        self.assertIsNone(cr.detect_branch_from_text("học phí bao nhiêu"))

    def test_send_messenger_message_with_quick_replies(self):
        """Test send_messenger_message correctly passes quick_replies array."""
        with patch.object(cr.requests, "post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"recipient_id": "user_123", "message_id": "m_qr_1"}
            mock_post.return_value = mock_resp

            qr = [{"content_type": "text", "title": "📍 CS1 Bình Thạnh", "payload": "CS1"}]
            res = cr.send_messenger_message("page_test", "token_test", "user_123", "Chọn cơ sở:", quick_replies=qr)

            self.assertIsNotNone(res)
            self.assertEqual(res["message_id"], "m_qr_1")
            kwargs = mock_post.call_args[1]
    def test_dynamic_bot_slot_progression(self):
        """Test Bot Slot dynamic configuration progression and slot extractors."""
        config = {
            "slots": [
                {"slot_key": "course", "label": "Khóa học", "required": 1},
                {"slot_key": "branch", "label": "Chi nhánh", "required": 1},
                {"slot_key": "learner_age", "label": "Tuổi người học", "required": 1},
                {"slot_key": "preferred_shift", "label": "Ca học", "required": 1},
                {"slot_key": "phone", "label": "Số điện thoại", "required": 1},
            ],
            "options": []
        }

        # Step 1: Empty thread -> missing course
        slots = cr.extract_all_slots("", "Em muốn tìm hiểu học", config)
        self.assertNotIn("course", slots)
        next_s = cr.get_next_missing_slot(slots, config)
        self.assertIsNotNone(next_s)
        self.assertEqual(next_s["slot_key"], "course")
        qr = cr.get_smart_quick_replies(None, "Em muốn tìm hiểu học", next_missing_slot=next_s, slots_config=config)
        self.assertTrue(any("Photoshop" in r["title"] for r in qr))

        # Step 2: Customer picked course -> missing learner_age
        slots = cr.extract_all_slots("Em học Photoshop", "Photoshop", config)
        self.assertEqual(slots.get("course"), "Photoshop thực chiến")
        next_s = cr.get_next_missing_slot(slots, config)
        self.assertEqual(next_s["slot_key"], "learner_age")
        qr = cr.get_smart_quick_replies("Photoshop thực chiến", "Photoshop", next_missing_slot=next_s, slots_config=config)
        self.assertTrue(any("tuổi" in r["title"] for r in qr))

        # Step 3: Customer specified age -> missing branch
        slots = cr.extract_all_slots("Em học Photoshop", "bé 8 tuổi", config)
        self.assertEqual(slots.get("learner_age"), 8)
        next_s = cr.get_next_missing_slot(slots, config)
        self.assertEqual(next_s["slot_key"], "branch")
        qr = cr.get_smart_quick_replies("Photoshop thực chiến", "bé 8 tuổi", next_missing_slot=next_s, slots_config=config)
        self.assertTrue(any("Bình Thạnh" in r["title"] for r in qr))

        # Step 4: Customer picked branch -> missing preferred_shift
        slots = cr.extract_all_slots("Em học Photoshop bé 8 tuổi ở Bình Thạnh", "CS1 Bình Thạnh", config)
        self.assertEqual(slots.get("branch"), "CS1 Bình Thạnh")
        next_s = cr.get_next_missing_slot(slots, config)
        self.assertEqual(next_s["slot_key"], "preferred_shift")

        # Step 5: Customer picked shift -> missing phone
        slots = cr.extract_all_slots("Em học Photoshop bé 8 tuổi ở Bình Thạnh lớp tối 2-4-6", "lớp tối 2-4-6", config)
        self.assertEqual(slots.get("preferred_shift"), "Ca tối (18h30 - 20h30)")
        next_s = cr.get_next_missing_slot(slots, config)
        self.assertEqual(next_s["slot_key"], "phone")
        qr = cr.get_smart_quick_replies("Photoshop thực chiến", "lớp tối 2-4-6", next_missing_slot=next_s, slots_config=config)
        self.assertEqual(qr, [])  # Empty for phone input

        # Step 6: All slots collected -> next_missing_slot is None
        slots["phone"] = "0901234567"
        self.assertIsNone(cr.get_next_missing_slot(slots, config))


if __name__ == "__main__":
    unittest.main()
