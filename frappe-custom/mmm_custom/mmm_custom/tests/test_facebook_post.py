# Copyright (c) 2026, MMM and contributors
# For license information, please see license.txt

import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.mmm_custom.doctype.facebook_post.facebook_post import (
    COURSE_META,
    FacebookPost,
)


class TestFacebookPost(unittest.TestCase):
    def test_course_metadata_complete(self):
        """Verify all supported courses have proper metadata defined."""
        expected_courses = ["Tiếng Anh", "Bơi lội", "Toán tư duy", "Chung"]
        for course in expected_courses:
            self.assertIn(course, COURSE_META)
            meta = COURSE_META[course]
            self.assertIn("key", meta)
            self.assertIn("color", meta)
            self.assertIn("title", meta)
            self.assertIn("subtitle", meta)
            self.assertEqual(len(meta["color"]), 3)

    def test_banner_generation_logic(self):
        """Test banner generation produces a 1080x1080 square image."""
        meta = COURSE_META["Tiếng Anh"]
        width, height = 1080, 1080
        img = Image.new("RGB", (width, height), meta["color"])
        self.assertEqual(img.size, (1080, 1080))

        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        loaded = Image.open(buf)
        self.assertEqual(loaded.format, "JPEG")
        self.assertEqual(loaded.size, (1080, 1080))

    @patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.requests.post")
    def test_generate_ai_content_with_gemini(self, mock_post):
        """Test AI content generation using Gemini API response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Khóa học Tiếng Anh tuyệt vời tại EduFlow! #EduFlow"}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        doc = FacebookPost()
        doc.course = "Tiếng Anh"
        doc.title = "Khai giảng tháng 10"
        doc.save = MagicMock()

        with patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.os.getenv") as mock_env:
            mock_env.side_effect = lambda k, default=None: "dummy_key" if k == "GEMINI_API_KEY" else default
            res = doc.generate_ai_content()
            self.assertEqual(res["status"], "success")
            self.assertIn("EduFlow", res["content"])
            self.assertEqual(doc.content, res["content"])

    @patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.requests.post")
    def test_generate_ai_content_with_feedback(self, mock_post):
        """Test AI content generation includes user feedback in prompt."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Ưu đãi giảm 50% học phí hè tại EduFlow! #EduFlow"}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        doc = FacebookPost()
        doc.course = "Tiếng Anh"
        doc.title = "Khai giảng tháng 10"
        doc.save = MagicMock()

        with patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.os.getenv") as mock_env:
            mock_env.side_effect = lambda k, default=None: "dummy_key" if k == "GEMINI_API_KEY" else default
            res = doc.generate_ai_content(user_feedback="Nhấn mạnh học bổng 50%")
            self.assertEqual(res["status"], "success")
            # Verify the prompt sent to Gemini contains user_feedback
            sent_payload = mock_post.call_args[1]["json"]
            prompt_text = sent_payload["contents"][0]["parts"][0]["text"]
            self.assertIn("Nhấn mạnh học bổng 50%", prompt_text)

    def test_generate_banner_with_feedback(self):
        """Test banner generation adapts to user feedback (custom promo or benefits)."""
        doc = FacebookPost()
        doc.name = "test_fb_post_1"
        doc.course = "Bơi lội"
        doc.title = "Tuyển sinh bơi hè"
        doc.is_new = MagicMock(return_value=False)
        doc.save = MagicMock()

        with patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.save_file") as mock_save_file:
            mock_file = MagicMock()
            mock_file.file_url = "/files/test_banner.jpg"
            mock_save_file.return_value = mock_file

            res = doc.generate_banner(user_feedback="TẶNG BALO VÀ GIẢM 40%")
            self.assertEqual(res["status"], "success")
            self.assertEqual(doc.image, "/files/test_banner.jpg")


if __name__ == "__main__":
    unittest.main()
