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

    @patch("mmm_custom.banner_generator.generate_hero_image")
    @patch("mmm_custom.banner_generator.save_file")
    def test_generate_banner_with_feedback(self, mock_save_file, mock_hero):
        """Test banner generation adapts to user feedback (custom promo or benefits)."""
        mock_hero.return_value = Image.new("RGB", (1080, 1080), color=(10, 50, 100))
        doc = FacebookPost()
        doc.name = "test_fb_post_1"
        doc.course = "Bơi lội"
        doc.title = "Tuyển sinh bơi hè"
        doc.is_new = MagicMock(return_value=False)
        doc.save = MagicMock()

        mock_file = MagicMock()
        mock_file.file_url = "/files/test_banner.jpg"
        mock_save_file.return_value = mock_file

        res = doc.generate_banner(user_feedback="TẶNG BALO VÀ GIẢM 40%")
        self.assertEqual(res["status"], "success")
        self.assertEqual(doc.image, "/files/test_banner.jpg")


    @patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.requests.post")
    def test_generate_ai_content_with_dynamic_angle(self, mock_post):
        """Test AI content generation includes dynamic angle and anti-cliche constraints."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Bé từng rất sợ nước, nhưng hôm nay đã tự tin bơi 50m! #EduFlow"}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        doc = FacebookPost()
        doc.course = "Bơi lội"
        doc.title = "Khóa bơi sinh tồn cho bé"
        doc.day_of_week = "Thứ Sáu"
        doc.save = MagicMock()

        with patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.os.getenv") as mock_env:
            mock_env.side_effect = lambda k, default=None: "dummy_key" if k == "GEMINI_API_KEY" else default
            res = doc.generate_ai_content()
            self.assertEqual(res["status"], "success")
            sent_payload = mock_post.call_args[1]["json"]
            prompt_text = sent_payload["contents"][0]["parts"][0]["text"]
            self.assertIn("ANTI-CLICHÉ", prompt_text)
            self.assertIn("GÓC TIẾP CẬN", prompt_text)
            self.assertIn("HUMOR", prompt_text)

    def test_sync_analytics_requires_posted_status(self):
        """Test sync_analytics throws if post is not in Posted status."""
        doc = FacebookPost()
        doc.status = "Draft"
        doc.fb_post_id = "12345"
        with self.assertRaises(Exception):
            doc.sync_analytics()

    @patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.requests.get")
    def test_sync_analytics_success(self, mock_get):
        """Test sync_analytics successfully pulls metrics from Facebook Graph API."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "reactions": {"summary": {"total_count": 42}},
            "comments": {"summary": {"total_count": 15}},
            "shares": {"count": 8},
        }
        mock_get.return_value = mock_resp

        doc = FacebookPost()
        doc.status = "Posted"
        doc.fb_post_id = "1334466483083776_122103569720760450"
        doc.save = MagicMock()

        with patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.os.getenv") as mock_env:
            mock_env.return_value = "dummy_token"
            res = doc.sync_analytics()
            self.assertEqual(res["status"], "success")
            self.assertEqual(doc.likes_count, 42)
            self.assertEqual(doc.comments_count, 15)
            self.assertEqual(doc.shares_count, 8)
            self.assertIsNotNone(doc.last_analytics_sync)
            doc.save.assert_called()

    @patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.frappe.get_doc")
    @patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.frappe.get_all")
    def test_sync_all_posted_analytics(self, mock_get_all, mock_get_doc):
        """Test sync_all_posted_analytics iterates posted posts and calls sync_analytics."""
        from mmm_custom.mmm_custom.doctype.facebook_post.facebook_post import sync_all_posted_analytics
        mock_get_all.return_value = ["FB-001", "FB-002"]
        mock_doc1 = MagicMock()
        mock_doc2 = MagicMock()
        mock_get_doc.side_effect = [mock_doc1, mock_doc2]

        result = sync_all_posted_analytics()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["synced_count"], 2)
        mock_doc1.sync_analytics.assert_called_once()
        mock_doc2.sync_analytics.assert_called_once()

    @patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.frappe.get_all")
    def test_get_marketing_overview(self, mock_get_all):
        """Test get_marketing_overview correctly calculates aggregates and top posts."""
        from mmm_custom.mmm_custom.doctype.facebook_post.facebook_post import get_marketing_overview
        mock_get_all.return_value = [
            {
                "name": "FB-01",
                "title": "Post 1",
                "course": "TE-ROBO",
                "status": "Posted",
                "likes_count": 10,
                "comments_count": 5,
                "shares_count": 2,
                "reach_count": 100,
                "leads_count": 3,
            },
            {
                "name": "FB-02",
                "title": "Post 2",
                "course": "VP-EXCEL",
                "status": "Scheduled",
                "likes_count": 0,
                "comments_count": 0,
                "shares_count": 0,
                "reach_count": 0,
                "leads_count": 0,
            },
            {
                "name": "FB-03",
                "title": "Post 3",
                "course": "DH-PTS",
                "status": "Posted",
                "likes_count": 50,
                "comments_count": 20,
                "shares_count": 5,
                "reach_count": 500,
                "leads_count": 8,
            },
        ]
        result = get_marketing_overview()
        self.assertEqual(result["status"], "success")
        kpis = result["kpis"]
        self.assertEqual(kpis["total_posts"], 3)
        self.assertEqual(kpis["posted_count"], 2)
        self.assertEqual(kpis["scheduled_count"], 1)
        self.assertEqual(kpis["total_likes"], 60)
        self.assertEqual(kpis["total_comments"], 25)
        self.assertEqual(kpis["total_shares"], 7)
        self.assertEqual(kpis["total_reach"], 600)
        self.assertEqual(kpis["total_leads"], 11)
        self.assertEqual(len(result["top_leads"]), 2)
        self.assertEqual(result["top_leads"][0]["name"], "FB-03")
        self.assertEqual(result["top_engagement"][0]["name"], "FB-03")


if __name__ == "__main__":
    unittest.main()

