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
        replies_branch = cr.get_smart_quick_replies("Photoshop thực chiến", "có lớp tối ở Bình Thạnh không?")
        self.assertTrue(len(replies_branch) >= 3)
        for r in replies_branch:
            self.assertLessEqual(len(r["title"]), 20, f"Title too long: {r['title']}")
            self.assertEqual(r["content_type"], "text")

        replies_course = cr.get_smart_quick_replies(None, "tư vấn giúp mình")
        self.assertTrue(len(replies_course) >= 3)
        for r in replies_course:
            self.assertLessEqual(len(r["title"]), 20)

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
            self.assertEqual(kwargs["json"]["message"]["quick_replies"], qr)


if __name__ == "__main__":
    unittest.main()
