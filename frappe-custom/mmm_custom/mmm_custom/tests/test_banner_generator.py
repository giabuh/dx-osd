# Copyright (c) 2026, MMM and contributors
# For license information, please see license.txt

import base64
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.banner_generator import (
    build_image_prompt,
    generate_hero_image,
    compose_commercial_banner,
    generate_and_save_banner,
)


class TestBannerGenerator(unittest.TestCase):
    def test_build_image_prompt(self):
        """Verify prompt builder crafts relevant commercial photo prompts."""
        prompt_robot = build_image_prompt("Robotics", title="Khóa học Robotics", feedback="kèm bộ kit Lego")
        self.assertIn("commercial", prompt_robot.lower())
        self.assertIn("robot", prompt_robot.lower())
        self.assertIn("lego", prompt_robot.lower())

        prompt_swim = build_image_prompt("Bơi lội", feedback="bể bơi 4 mùa")
        self.assertIn("swimming", prompt_swim.lower())
        self.assertIn("pool", prompt_swim.lower())

        prompt_eng = build_image_prompt("Tiếng Anh")
        self.assertIn("english", prompt_eng.lower())

    @patch("mmm_custom.banner_generator.requests.post")
    def test_generate_hero_image_imagen3_success(self, mock_post):
        """Test Tier 1: Google Imagen 3 successfully generates image."""
        dummy_img = Image.new("RGB", (1080, 1080), color=(10, 50, 120))
        buf = io.BytesIO()
        dummy_img.save(buf, format="JPEG")
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "predictions": [
                {"bytesBase64Encoded": b64_str}
            ]
        }
        mock_post.return_value = mock_resp

        img = generate_hero_image("Tiếng Anh", api_key="dummy_gemini_key")
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (980, 860))
        self.assertTrue(mock_post.called)

    @patch("mmm_custom.banner_generator.requests.get")
    @patch("mmm_custom.banner_generator.requests.post")
    def test_generate_hero_image_pollinations_fallback(self, mock_post, mock_get):
        """Test Tier 2: Pollinations.ai fallback when Imagen 3 fails or has no key."""
        # Imagen 3 fails
        mock_post.side_effect = Exception("Imagen API rate limit or error")

        # Pollinations succeeds
        dummy_img = Image.new("RGB", (1080, 1080), color=(20, 80, 160))
        buf = io.BytesIO()
        dummy_img.save(buf, format="JPEG")

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.content = buf.getvalue()
        mock_get.return_value = mock_get_resp

        img = generate_hero_image("Bơi lội", api_key=None)
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (980, 860))

    @patch("mmm_custom.banner_generator.requests.get")
    @patch("mmm_custom.banner_generator.requests.post")
    def test_generate_hero_image_offline_fallback(self, mock_post, mock_get):
        """Test Tier 3: Local cached image fallback when all network calls fail."""
        mock_post.side_effect = Exception("Network offline")
        mock_get.side_effect = Exception("Network offline")

        img = generate_hero_image("Tiếng Anh", api_key="test_key")
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (980, 860))

    def test_compose_commercial_banner(self):
        """Test composing commercial banner with 3D text, cards, and CTA button."""
        base_img = Image.new("RGB", (980, 860), color=(15, 23, 42))
        composed = compose_commercial_banner(
            hero_image=base_img,
            course="Tiếng Anh",
            title="TIẾNG ANH GIAO TIẾP TOÀN DIỆN",
            feedback="Ưu đãi 30% hôm nay",
        )
        self.assertIsNotNone(composed)
        self.assertEqual(composed.size, (1080, 1920))
        self.assertEqual(composed.mode, "RGB")

    @patch("mmm_custom.banner_generator.generate_hero_image")
    @patch("mmm_custom.banner_generator.save_file")
    def test_generate_and_save_banner(self, mock_save_file, mock_hero):
        """Test high-level generate_and_save_banner integrates with FacebookPost doc."""
        mock_hero.return_value = Image.new("RGB", (1080, 1080), color=(10, 40, 90))
        mock_file = MagicMock()
        mock_file.file_url = "/files/test_banner_ai.jpg"
        mock_save_file.return_value = mock_file

        mock_doc = MagicMock()
        mock_doc.name = "FB-POST-001"
        mock_doc.course = "Bơi lội"
        mock_doc.title = "Khóa bơi sinh tồn cho bé"
        mock_doc.is_new.return_value = False

        res = generate_and_save_banner(mock_doc, user_feedback="Giảm 40% học phí hè")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["image"], "/files/test_banner_ai.jpg")
        self.assertEqual(mock_doc.image, "/files/test_banner_ai.jpg")
    def test_crm_course_domains_and_metadata(self):
        """Test metadata and banner composition across CRM course codes."""
        from mmm_custom.banner_generator import get_course_meta
        test_cases = [
            ("TE-ROBO", "robotics", "Sao Việt ROBOTICS & STEM"),
            ("DH-PTS", "design", "Sao Việt CREATIVE DESIGN"),
            ("VKT-CAD2D", "autocad", "Sao Việt CAD & 3D DESIGN"),
            ("VP-EXCEL", "excel", "Sao Việt OFFICE & DATA"),
            ("AI-VIBE", "ai", "Sao Việt AI & AUTOMATION"),
            ("LT-PY", "programming", "Sao Việt TECH & CODING"),
            ("MKT-FB", "marketing", "Sao Việt DIGITAL MARKETING"),
            ("KT-CB", "accounting", "Sao Việt KẾ TOÁN"),  # was the Excel poster (D-123)
            ("KT-EXCEL", "excel", "Sao Việt OFFICE & DATA"),
        ]
        for code, expected_key, expected_brand in test_cases:
            meta = get_course_meta(code)
            self.assertEqual(meta["key"], expected_key, f"Failed for {code}")
            self.assertEqual(meta["brand_name"], expected_brand, f"Failed for {code}")

            # Verify banner composition works cleanly for this domain
            banner = compose_commercial_banner(
                hero_image=Image.new("RGB", (980, 860), color=(10, 20, 50)),
                course=code,
                title=f"Khóa học {code} - Thực chiến 2026",
            )
            self.assertEqual(banner.size, (1080, 1920))


if __name__ == "__main__":
    unittest.main()
