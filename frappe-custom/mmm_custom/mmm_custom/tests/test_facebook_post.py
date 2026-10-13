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
            self.assertEqual(doc.ads_recommendation, "Recommended")
            self.assertEqual(res["ads_recommendation"], "Recommended")
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

    def test_evaluate_ads_potential_scoring(self):
        """Test evaluate_ads_potential computes scores and assigns recommendations."""
        doc = FacebookPost()

        # Test Recommended by leads
        doc.likes_count = 0
        doc.comments_count = 0
        doc.shares_count = 0
        doc.leads_count = 1
        res = doc.evaluate_ads_potential()
        self.assertEqual(res["recommendation"], "Recommended")
        self.assertEqual(doc.ads_recommendation, "Recommended")
        self.assertEqual(res["score"], 10)

        # Test Recommended by comments >= 2
        doc.leads_count = 0
        doc.comments_count = 2
        res = doc.evaluate_ads_potential()
        self.assertEqual(res["recommendation"], "Recommended")
        self.assertEqual(doc.ads_recommendation, "Recommended")
        self.assertEqual(res["score"], 6)

        # Test Recommended by total score >= 5
        doc.comments_count = 1
        doc.likes_count = 2
        # score = 2*1 + 1*3 = 5
        res = doc.evaluate_ads_potential()
        self.assertEqual(res["recommendation"], "Recommended")
        self.assertEqual(res["score"], 5)

        # Test Review for score 1..4
        doc.comments_count = 0
        doc.likes_count = 1
        # score = 1
        res = doc.evaluate_ads_potential()
        self.assertEqual(res["recommendation"], "Review")
        self.assertEqual(doc.ads_recommendation, "Review")
        self.assertEqual(res["score"], 1)

        # Test Not Recommended for score 0
        doc.likes_count = 0
        res = doc.evaluate_ads_potential()
        self.assertEqual(res["recommendation"], "Not Recommended")
        self.assertEqual(doc.ads_recommendation, "Not Recommended")
        self.assertEqual(res["score"], 0)

    @patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.requests.post")
    def test_get_ai_ads_advice_with_gemini(self, mock_post):
        """Test get_ai_ads_advice parses Gemini advice response into structured output."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{\n"rationale": "Tương tác ban đầu tích cực với 2 bình luận hỏi khóa học.",\n"target_audience": {"age": "25-45 tuổi", "location": "TP.HCM", "interests": "Tiếng Anh giao tiếp", "gender": "Tất cả"},\n"budget_plan": {"daily_budget": "150.000đ/ngày", "duration": "5 ngày", "objective": "Tin nhắn Messenger", "expected_cpl": "30.000đ/lead"},\n"tips": ["Bật nút Gửi tin nhắn", "Chạy test 3 ngày"]\n}'
                            }
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        doc = FacebookPost()
        doc.course = "Tiếng Anh"
        doc.title = "Tiếng Anh cho người đi làm"
        doc.likes_count = 5
        doc.comments_count = 2
        doc.save = MagicMock()

        with patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.os.getenv") as mock_env:
            mock_env.side_effect = lambda k, default=None: "dummy_key" if k == "GEMINI_API_KEY" else default
            res = doc.get_ai_ads_advice()
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["recommendation"], "Recommended")
            self.assertIn("target_audience", res)
            self.assertEqual(res["target_audience"]["age"], "25-45 tuổi")
            self.assertEqual(res["budget_plan"]["daily_budget"], "150.000đ/ngày")
            self.assertTrue(len(res["tips"]) >= 2)

    def test_get_ai_ads_advice_fallback_heuristic(self):
        """Test get_ai_ads_advice provides heuristic structured advice even without AI API."""
        doc = FacebookPost()
        doc.course = "Tiếng Anh"
        doc.title = "Tiếng Anh giao tiếp"
        doc.likes_count = 10
        doc.comments_count = 3
        doc.save = MagicMock()

        with patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.os.getenv") as mock_env:
            mock_env.return_value = None  # No API key
            res = doc.get_ai_ads_advice()
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["recommendation"], "Recommended")
            self.assertIn("target_audience", res)
            self.assertIn("budget_plan", res)
            self.assertIn("tips", res)
            self.assertIn("https://adsmanager.facebook.com/", res.get("ads_manager_url", ""))

    def test_sync_comments_not_posted_skipped(self):
        """Test sync_comments on unposted doc returns skipped status."""
        doc = FacebookPost()
        doc.status = "Draft"
        res = doc.sync_comments(save=False)
        self.assertEqual(res["status"], "skipped")

    def test_sync_comments_success_with_sentiment(self):
        """Test sync_comments pulls Graph API comments and classifies sentiment correctly."""
        doc = FacebookPost()
        doc.status = "Posted"
        doc.fb_post_id = "123_456"
        doc.comments = []
        doc.set = lambda field, val: setattr(doc, field, val)
        doc.append = lambda field, row: getattr(doc, field).append(row)
        doc.save = MagicMock()

        mock_comments_data = {
            "data": [
                {
                    "id": "c_1",
                    "from": {"name": "Nguyễn Văn A"},
                    "message": "Cho mình xin học phí với ạ",
                    "created_time": "2026-09-29T10:00:00+0000",
                },
                {
                    "id": "c_2",
                    "from": {"name": "Trần Thị B"},
                    "message": "Tư vấn lớp photoshop cho người mới bắt đầu",
                    "created_time": "2026-09-29T10:05:00+0000",
                },
                {
                    "id": "c_3",
                    "from": {"name": "Lê C"},
                    "message": "Ảnh thiết kế đẹp quá ad ơi",
                    "created_time": "2026-09-29T10:10:00+0000",
                },
                {
                    "id": "c_4",
                    "from": {"name": "Bot Spammer"},
                    "message": "Check link bio nha mọi người",
                    "created_time": "2026-09-29T10:15:00+0000",
                },
            ]
        }

        with patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.ok = True
            mock_resp.json.return_value = mock_comments_data
            mock_get.return_value = mock_resp

            with patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.os.getenv") as mock_env:
                mock_env.side_effect = lambda k: "fake_token" if k == "FACEBOOK_PAGE_ACCESS_TOKEN" else "123"
                res = doc.sync_comments(save=False)

                self.assertEqual(res["status"], "success")
                self.assertEqual(res["count"], 4)
                self.assertEqual(doc.comments_count, 4)
                self.assertEqual(len(doc.comments), 4)

                # Verify sentiment classifications
                self.assertEqual(doc.comments[0]["sentiment"], "Hỏi học phí / lịch")
                self.assertEqual(doc.comments[1]["sentiment"], "Quan tâm khóa học")
                self.assertEqual(doc.comments[2]["sentiment"], "Tích cực")
                self.assertEqual(doc.comments[3]["sentiment"], "Spam / Khác")

    @patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.frappe.get_doc")
    def test_get_page_credentials_from_facebook_page(self, mock_get_doc):
        """When facebook_page is specified, credentials should be fetched from Facebook Page doctype."""
        doc = FacebookPost()
        doc.facebook_page = "1324629057402921"

        mock_page = MagicMock()
        mock_page.id = "1324629057402921"
        mock_page.access_token = "EAAPageToken123"
        mock_get_doc.return_value = mock_page

        page_id, token = doc._get_page_credentials()
        self.assertEqual(page_id, "1324629057402921")
        self.assertEqual(token, "EAAPageToken123")
        mock_get_doc.assert_called_with("Facebook Page", "1324629057402921")

    @patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.os.getenv")
    def test_get_page_credentials_fallback_to_env(self, mock_env):
        """When facebook_page is not specified, credentials should fall back to environment variables."""
        doc = FacebookPost()
        doc.facebook_page = None

        mock_env.side_effect = lambda k: "ENV_PAGE_ID" if k == "FACEBOOK_PAGE_ID" else ("ENV_TOKEN" if k == "FACEBOOK_PAGE_ACCESS_TOKEN" else None)

        page_id, token = doc._get_page_credentials()
        self.assertEqual(page_id, "ENV_PAGE_ID")
        self.assertEqual(token, "ENV_TOKEN")

    @patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.requests.post")
    @patch("mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.frappe.get_doc")
    def test_post_to_facebook_with_page_credentials(self, mock_get_doc, mock_post):
        """post_to_facebook should post to the specific page endpoint with page token."""
        doc = FacebookPost()
        doc.title = "Khai giảng chi nhánh 2"
        doc.content = "Nội dung bài viết chi nhánh 2"
        doc.facebook_page = "1324629057402921"
        doc.status = "Draft"
        doc.save = MagicMock()

        mock_page = MagicMock()
        mock_page.id = "1324629057402921"
        mock_page.access_token = "EAAPageToken123"
        mock_get_doc.return_value = mock_page

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"id": "1324629057402921_99999"}
        mock_post.return_value = mock_resp

        res = doc.post_to_facebook()
        self.assertEqual(res["status"], "success")
        self.assertEqual(doc.status, "Posted")
        self.assertEqual(doc.fb_post_id, "1324629057402921_99999")
        # Ensure requests.post was called with page_id in url and token in data
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        call_data = mock_post.call_args[1]["data"]
        self.assertIn("1324629057402921", call_url)
        self.assertEqual(call_data["access_token"], "EAAPageToken123")


if __name__ == "__main__":
    unittest.main()


