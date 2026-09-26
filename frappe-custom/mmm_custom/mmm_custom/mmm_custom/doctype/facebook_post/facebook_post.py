# Copyright (c) 2026, MMM and contributors
# For license information, please see license.txt

import io
import json
import os
import random
import requests

try:
    import frappe
    from frappe import _
    from frappe.model.document import Document
    from frappe.utils import now_datetime
    from frappe.utils.file_manager import save_file
except ImportError:
    from unittest.mock import MagicMock
    frappe = MagicMock()
    _ = lambda x: x
    def _whitelist(*args, **kwargs):
        def decorator(f):
            return f
        if args and callable(args[0]):
            return args[0]
        return decorator
    frappe.whitelist = _whitelist
    class Document:
        pass
    def now_datetime():
        from datetime import datetime
        return datetime.now()
    def save_file(*args, **kwargs):
        mock_file = MagicMock()
        mock_file.file_url = f"/files/{args[0]}"
        return mock_file

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image, ImageDraw, ImageFont = None, None, None


# Course metadata for banner and AI generation
COURSE_META = {
    "Tiếng Anh": {
        "key": "tieng_anh",
        "emoji": "🇬🇧",
        "color": (41, 128, 185),
        "accent": (52, 152, 219),
        "title": "HỌC TIẾNG ANH",
        "subtitle": "Giao tiếp tự tin • Cam kết đầu ra",
    },
    "Bơi lội": {
        "key": "boi_loi",
        "emoji": "🏊",
        "color": (39, 174, 96),
        "accent": (46, 204, 113),
        "title": "HỌC BƠI",
        "subtitle": "An toàn vui khỏe • HLV chuyên nghiệp",
    },
    "Toán tư duy": {
        "key": "toan_tu_duy",
        "emoji": "🧮",
        "color": (142, 68, 173),
        "accent": (155, 89, 182),
        "title": "TOÁN TƯ DUY",
        "subtitle": "Phát triển trí não • Rèn luyện logic",
    },
    "Chung": {
        "key": "chung",
        "emoji": "🎓",
        "color": (230, 126, 34),
        "accent": (243, 156, 18),
        "title": "EDUFLOW ACADEMY",
        "subtitle": "Hệ thống đào tạo kỹ năng hàng đầu",
    },
}


class FacebookPost(Document):
    @frappe.whitelist()
    def generate_ai_content(self):
        """Generate high quality Facebook post caption using Gemini AI or 9Router."""
        course_name = self.course or "Tiếng Anh"
        title_context = self.title or f"Khóa học {course_name}"

        prompt = (
            f"Bạn là chuyên viên marketing nội dung của trung tâm EduFlow Academy.\n"
            f"Hãy viết bài đăng Facebook hấp dẫn để quảng cáo: \"{title_context}\" (Khóa {course_name}).\n"
            f"Yêu cầu:\n"
            f"- Ngắn gọn dưới 150 từ, tiếng Việt, đầy cảm hứng\n"
            f"- Có emoji sinh động\n"
            f"- Nêu bật 3 lợi ích chính dạng gạch đầu dòng\n"
            f"- Đề cập 3 cơ sở: Quận 1, Bình Thạnh, Thủ Đức\n"
            f"- Kêu gọi hành động: nhắn tin/inbox fanpage để nhận tư vấn và ưu đãi\n"
            f"- Kèm hashtag: #EduFlow #EduFlowAcademy #{course_name.replace(' ', '')}\n"
            f"- Tuyệt đối KHÔNG dùng markdown (không dùng **, ##), trả về chữ thuần."
        )

        content = None
        gemini_key = os.getenv("GEMINI_API_KEY") or frappe.conf.get("gemini_api_key")
        gemini_model = os.getenv("GEMINI_MODEL") or "gemini-3.8-flash"

        if gemini_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={gemini_key}"
                resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                frappe.log_error(f"Gemini API error: {e}", "FacebookPost AI Content")

        if not content:
            nine_key = os.getenv("NINE_ROUTER_API_KEY") or frappe.conf.get("nine_router_api_key")
            nine_url = os.getenv("NINE_ROUTER_BASE_URL", "http://localhost:20128/v1")
            nine_model = os.getenv("NINE_ROUTER_MODEL", "ag/gemini-3.7-flash-low")
            if nine_key:
                try:
                    resp = requests.post(
                        f"{nine_url}/chat/completions",
                        json={"model": nine_model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 400},
                        headers={"Authorization": f"Bearer {nine_key}"},
                        timeout=25,
                    )
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"]["content"].strip()
                except Exception as e:
                    frappe.log_error(f"9Router error: {e}", "FacebookPost AI Content")

        if content:
            self.content = content.replace("**", "").replace("##", "")
            self.save()
            return {"status": "success", "content": self.content}
        else:
            frappe.throw(_("Không thể tạo nội dung qua AI. Vui lòng kiểm tra API Key."))

    @frappe.whitelist()
    def generate_banner(self):
        """Generate a branded Facebook flyer image (1200x630) using Pillow and attach to document."""
        if not Image:
            frappe.throw(_("Thư viện Pillow chưa được cài đặt trên hệ thống."))

        meta = COURSE_META.get(self.course, COURSE_META["Chung"])
        width, height = 1200, 630

        img = Image.new("RGB", (width, height), meta["color"])
        draw = ImageDraw.Draw(img)

        # Gradient
        for y in range(height):
            alpha = y / height
            r = int(meta["color"][0] * (1 - alpha * 0.45))
            g = int(meta["color"][1] * (1 - alpha * 0.45))
            b = int(meta["color"][2] * (1 - alpha * 0.45))
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Card container
        margin = 50
        draw.rounded_rectangle([margin, margin, width - margin, height - margin], radius=24, fill=(255, 255, 255))

        # Fonts fallback
        try:
            title_font = ImageFont.truetype("arial.ttf", 68)
            sub_font = ImageFont.truetype("arial.ttf", 32)
            brand_font = ImageFont.truetype("arial.ttf", 26)
        except Exception:
            title_font = ImageFont.load_default()
            sub_font = ImageFont.load_default()
            brand_font = ImageFont.load_default()

        # Title
        title_text = meta["title"]
        bbox = draw.textbbox((0, 0), title_text, font=title_font)
        x_pos = (width - (bbox[2] - bbox[0])) // 2
        draw.text((x_pos, 160), title_text, fill=meta["color"], font=title_font)

        # Subtitle
        sub_text = meta["subtitle"]
        bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
        x_pos = (width - (bbox[2] - bbox[0])) // 2
        draw.text((x_pos, 260), sub_text, fill=(90, 90, 90), font=sub_font)

        # Centers info
        centers_text = "📍 Chi nhánh: Quận 1 • Bình Thạnh • Thủ Đức"
        bbox = draw.textbbox((0, 0), centers_text, font=sub_font)
        x_pos = (width - (bbox[2] - bbox[0])) // 2
        draw.text((x_pos, 350), centers_text, fill=(50, 50, 50), font=sub_font)

        # Brand Footer
        brand_text = "EDUFLOW ACADEMY — HỆ THỐNG ĐÀO TẠO THÔNG MINH"
        bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
        x_pos = (width - (bbox[2] - bbox[0])) // 2
        draw.text((x_pos, height - 110), brand_text, fill=meta["color"], font=brand_font)

        # Save to buffer and attach via Frappe
        buf = io.BytesIO()
        img.save(buf, format="PNG", quality=95)
        buf.seek(0)

        file_name = f"banner_{meta['key']}_{self.name}.png"
        file_doc = save_file(file_name, buf.getvalue(), self.doctype, self.name, is_private=0)

        self.image = file_doc.file_url
        self.save()
        return {"status": "success", "image": self.image}

    @frappe.whitelist()
    def post_now(self):
        """Immediately publish this post to the Facebook Page via Graph API."""
        if not self.content:
            frappe.throw(_("Bài đăng chưa có nội dung. Vui lòng soạn nội dung trước."))

        page_id = os.getenv("FACEBOOK_PAGE_ID") or frappe.conf.get("facebook_page_id")
        token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") or frappe.conf.get("facebook_page_access_token")

        if not page_id or not token:
            frappe.throw(_("Chưa cấu hình FACEBOOK_PAGE_ID hoặc FACEBOOK_PAGE_ACCESS_TOKEN."))

        try:
            # Check if there is an attached image
            if self.image:
                image_abs_path = None
                # If image is a local uploaded file (e.g. /files/banner.png)
                if self.image.startswith("/files/") or self.image.startswith("/private/files/"):
                    site_path = frappe.get_site_path("public" if not self.image.startswith("/private") else "", self.image.lstrip("/"))
                    if os.path.exists(site_path):
                        image_abs_path = site_path

                if image_abs_path:
                    url = f"https://graph.facebook.com/v21.0/{page_id}/photos"
                    with open(image_abs_path, "rb") as f:
                        resp = requests.post(
                            url,
                            data={"caption": self.content, "access_token": token},
                            files={"source": (os.path.basename(image_abs_path), f, "image/png")},
                            timeout=35,
                        )
                else:
                    # Upload by URL or text
                    url = f"https://graph.facebook.com/v21.0/{page_id}/feed"
                    resp = requests.post(
                        url,
                        data={"message": self.content, "access_token": token},
                        timeout=35,
                    )
            else:
                url = f"https://graph.facebook.com/v21.0/{page_id}/feed"
                resp = requests.post(
                    url,
                    data={"message": self.content, "access_token": token},
                    timeout=35,
                )

            resp.raise_for_status()
            data = resp.json()
            post_id = data.get("id") or data.get("post_id")

            self.status = "Posted"
            self.fb_post_id = post_id
            self.fb_post_url = f"https://www.facebook.com/{post_id}"
            self.posted_at = now_datetime()
            self.error_message = ""
            self.save()

            frappe.msgprint(_("Đã đăng thành công lên Facebook! ID: {0}").format(post_id), alert=True)
            return {"status": "success", "post_id": post_id, "url": self.fb_post_url}

        except Exception as e:
            error_msg = str(e)
            self.status = "Failed"
            self.error_message = error_msg
            self.save()
            frappe.throw(_("Đăng bài thất bại: {0}").format(error_msg))


def check_scheduled_posts():
    """Background scheduler task: checks and posts any scheduled Facebook posts whose time has arrived."""
    now = now_datetime()
    scheduled = frappe.get_all(
        "Facebook Post",
        filters={"status": "Scheduled", "scheduled_time": ["<=", now]},
        pluck="name",
    )

    for name in scheduled:
        try:
            doc = frappe.get_doc("Facebook Post", name)
            doc.post_now()
        except Exception as e:
            frappe.log_error(f"Scheduled post failed for {name}: {e}", "Facebook Post Scheduler")
