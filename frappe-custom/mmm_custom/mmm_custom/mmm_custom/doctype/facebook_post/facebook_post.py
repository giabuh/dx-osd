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
        def is_new(self):
            return getattr(self, "name", None) is None
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


def _extract_ai_response_text(resp):
    """Safely extract text from an OpenAI-compatible response, handling both standard JSON and SSE streaming."""
    if not resp:
        return None
    try:
        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            val = msg.get("content", "").strip()
            if val:
                return val
    except Exception:
        pass

    # Fallback: Parse Server-Sent Events / SSE stream (e.g. data: {"choices": [{"delta": {"content": "..."}}]})
    try:
        text = resp.text
        content_parts = []
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("data: ") and line != "data: [DONE]":
                chunk_str = line[6:].strip()
                chunk = json.loads(chunk_str)
                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    if "content" in delta and delta["content"]:
                        content_parts.append(delta["content"])
                    elif "message" in choices[0] and choices[0]["message"].get("content"):
                        content_parts.append(choices[0]["message"]["content"])
        if content_parts:
            return "".join(content_parts).strip()
    except Exception:
        pass
    return None


# Course metadata for banner and AI generation
COURSE_META = {
    "Tiếng Anh": {
        "key": "tieng_anh",
        "emoji": "🇬🇧",
        "color": (37, 99, 235),  # Royal Blue
        "accent": (239, 68, 68),  # Red CTA
        "title": "TIẾNG ANH GIAO TIẾP TOÀN DIỆN",
        "subtitle": "Tự Tin Giao Tiếp • Bứt Phá Tương Lai",
        "promo": "TẶNG BUỔI HỌC THỬ MIỄN PHÍ",
        "benefits": [
            ("Giáo Viên Bản Ngữ", "100% giáo viên phát âm chuẩn"),
            ("Lớp Nhỏ 8-12 Bạn", "Tương tác phản xạ liên tục"),
            ("Phương Pháp Thực Chiến", "Giao tiếp tự nhiên, không học vẹt"),
            ("Cam Kết Chuẩn Đầu Ra", "Đạt mục tiêu chỉ sau 3 tháng"),
        ],
    },
    "Bơi lội": {
        "key": "boi_loi",
        "emoji": "🏊",
        "color": (13, 148, 136),  # Teal
        "accent": (245, 158, 11),  # Amber CTA
        "title": "KHÓA HỌC BƠI LỘI TRẺ EM",
        "subtitle": "An Toàn Dưới Nước • Tự Tin Vui Khỏe",
        "promo": "ƯU ĐÃI 30% HÔM NAY",
        "benefits": [
            ("HLV Kèm Sát 1:1", "HLV tận tâm, chứng chỉ quốc tế"),
            ("Hồ Nước Ấm 4 Mùa", "Khử trùng an toàn, đạt chuẩn"),
            ("Cam Kết Biết Bơi", "Bé tự tin bơi sau 8-10 buổi"),
            ("Lịch Học Linh Hoạt", "Sắp xếp phù hợp lịch của bé"),
        ],
    },
    "Toán tư duy": {
        "key": "toan_tu_duy",
        "emoji": "🧮",
        "color": (124, 58, 237),  # Purple
        "accent": (245, 158, 11),  # Amber CTA
        "title": "TOÁN TƯ DUY & LOGIC SÁNG TẠO",
        "subtitle": "Khai Mở Tiềm Năng • Phát Triển Não Bộ",
        "promo": "ƯU ĐÃI 35% HỌC PHÍ",
        "benefits": [
            ("Rèn Tư Duy Độc Lập", "Bé chủ động giải quyết vấn đề"),
            ("Học Qua Trò Chơi", "Phương pháp trực quan, hào hứng"),
            ("Dành Cho Bé 4-12 Tuổi", "Lộ trình cá nhân hóa từng độ tuổi"),
            ("Tự Tin Học Toán", "Không còn sợ hãi môn Toán"),
        ],
    },
    "Chung": {
        "key": "chung",
        "emoji": "🎓",
        "color": (230, 81, 0),  # Orange
        "accent": (13, 148, 136),  # Teal CTA
        "title": "EDUFLOW ACADEMY",
        "subtitle": "Hệ Thống Đào Tạo Kỹ Năng Hàng Đầu",
        "promo": "ƯU ĐÃI KHAI GIẢNG 2026",
        "benefits": [
            ("Đội Ngũ Giảng Viên Hàng Đầu", "Chuyên môn cao, giàu nhiệt huyết"),
            ("Cơ Sở Vật Chất Chuẩn Quốc Tế", "Trang thiết bị hiện đại, tiện nghi"),
            ("Lộ Trình Cá Nhân Hóa", "Phát triển toàn diện năng lực học viên"),
            ("Hỗ Trợ Học Viên 24/7", "Đồng hành sát sao suốt khóa học"),
        ],
    },
}


class FacebookPost(Document):
    @frappe.whitelist()
    def generate_ai_content(self, user_feedback=None):
        """Generate high quality Facebook post caption using Gemini AI or 9Router."""
        course_name = self.course or "Tiếng Anh"
        title_context = self.title or f"Khóa học {course_name}"
        feedback = user_feedback or getattr(self, "ai_feedback", None) or ""
        if user_feedback:
            self.ai_feedback = user_feedback

        day_dow = getattr(self, "day_of_week", None) or ""
        if "Hai" in day_dow:
            angle_section = (
                "GÓC TIẾP CẬN MARKETING: STORYTELLING (KỂ CHUYỆN THỰC TẾ)\n"
                "- Bắt đầu bằng một câu chuyện ngắn hoặc cảm xúc chân thực của học viên/phụ huynh (từ bỡ ngỡ, tự ti ban đầu đến tự tin, tiến bộ vượt bậc).\n"
                "- Chạm vào cảm xúc và truyền cảm hứng bắt đầu tuần mới tràn đầy năng lượng."
            )
        elif "Tư" in day_dow:
            angle_section = (
                "GÓC TIẾP CẬN MARKETING: EDUCATIONAL INSIGHT (CHUYÊN GIA & MẸO HAY)\n"
                "- Chia sẻ 1 mẹo thực chiến, kiến thức chuyên môn hoặc giải đáp 1 sai lầm thường gặp khi học/rèn luyện.\n"
                "- Cung cấp giá trị hữu ích trước khi dẫn dắt vào giải pháp của khóa học."
            )
        elif "Sáu" in day_dow:
            angle_section = (
                "GÓC TIẾP CẬN MARKETING: RELATABLE & HUMOR (ĐỜI THƯỜNG & HÓM HỈNH)\n"
                "- Bắt đầu bằng 1 tình huống vui, gần gũi cuối tuần mà phụ huynh/người học nào cũng từng gặp.\n"
                "- Giọng văn dí dỏm, thân thiện, giải tỏa căng thẳng và khơi gợi niềm vui học tập."
            )
        elif "Nhật" in day_dow:
            angle_section = (
                "GÓC TIẾP CẬN MARKETING: FOMO OFFER & SCHOLARSHIP (ƯU ĐÃI & HỌC BỔNG)\n"
                "- Sắc bén, kích thích hành động với ưu đãi/học bổng giới hạn số lượng dành riêng cho ngày cuối tuần.\n"
                "- Nêu lý do thuyết phục vì sao nên đăng ký giữ chỗ ngay hôm nay."
            )
        else:
            angle_section = (
                "GÓC TIẾP CẬN MARKETING: GIÁ TRỊ THỰC CHIẾN & ĐỘT PHÁ\n"
                "- Tập trung vào sự thay đổi rõ rệt và giá trị cốt lõi khóa học mang lại."
            )

        anti_cliche_rules = (
            "QUY TẮC CHỐNG VĂN MẪU SÁO RỖNG (ANTI-CLICHÉ):\n"
            "- TUYỆT ĐỐI KHÔNG mở đầu bằng các câu sáo rỗng như: 'Hè rực rỡ...', 'Bạn có biết...', 'Đừng bỏ lỡ...', 'Chào mừng bạn đến với...', 'Bạn đang tìm kiếm...'.\n"
            "- Hãy mở đầu trực tiếp bằng một câu hook bất ngờ, câu hỏi đánh trúng tâm lý, hoặc một lời tâm sự tự nhiên.\n"
            "- Viết như một chuyên gia tâm huyết đang trò chuyện trực tiếp với người đọc, chân thật và cuốn hút."
        )

        prompt = (
            f"Bạn là chuyên viên marketing nội dung cao cấp của trung tâm EduFlow Academy.\n"
            f"Hãy viết bài đăng Facebook hấp dẫn để quảng cáo: \"{title_context}\" (Khóa {course_name}).\n\n"
            f"{angle_section}\n\n"
            f"{anti_cliche_rules}\n\n"
            f"Yêu cầu định dạng:\n"
            f"- Ngắn gọn dưới 150 từ, tiếng Việt, giọng văn cuốn hút, tự nhiên\n"
            f"- Có emoji sinh động, đặt đúng chỗ\n"
            f"- Nêu bật 3 lợi ích chính dạng gạch đầu dòng\n"
            f"- Đề cập rõ 3 cơ sở: CS1 Bình Thạnh, CS2 Quận 1, CS3 Thủ Đức (kèm hotline 0901.888.666)\n"
            f"- Kêu gọi hành động rõ ràng: nhắn tin/inbox fanpage để nhận tư vấn và ưu đãi\n"
            f"- Kèm hashtag: #EduFlow #EduFlowAcademy #{course_name.replace(' ', '')}\n"
            f"- Tuyệt đối KHÔNG dùng markdown (không dùng **, ##), trả về chữ thuần."
        )

        if feedback.strip():
            prompt += (
                f"\n\nLƯU Ý ĐẶC BIỆT / GỢI Ý ĐIỀU CHỈNH TỪ NGƯỜI DÙNG:\n"
                f"\"{feedback.strip()}\"\n"
                f"Hãy tinh chỉnh nội dung bài viết, giọng văn hoặc ưu đãi theo đúng mong muốn trên!"
            )

        content = None
        nine_key = os.getenv("NINE_ROUTER_API_KEY") or frappe.conf.get("nine_router_api_key")
        default_nine_url = "http://host.docker.internal:20128/v1" if (os.path.exists("/.dockerenv") or os.environ.get("container")) else "http://localhost:20128/v1"
        nine_url = os.getenv("NINE_ROUTER_BASE_URL") or frappe.conf.get("nine_router_base_url") or default_nine_url
        nine_model = os.getenv("NINE_ROUTER_MODEL") or frappe.conf.get("nine_router_model") or "ag/gemini-3.7-flash-low"

        # 1. Try 9Router AI first
        if nine_key:
            try:
                resp = requests.post(
                    f"{nine_url}/chat/completions",
                    json={
                        "model": nine_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 500,
                        "stream": False,
                    },
                    headers={"Authorization": f"Bearer {nine_key}"},
                    timeout=30,
                )
                if resp.status_code == 200:
                    content = _extract_ai_response_text(resp)
            except Exception as e:
                if hasattr(frappe, "log_error"):
                    frappe.log_error(title="9Router Error", message=str(e)[:500])

        # 2. Fallback to direct Gemini API if 9Router did not return content
        if not content:
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
                    if hasattr(frappe, "log_error"):
                        frappe.log_error(title="Gemini API Error", message=str(e)[:500])

        if content:
            self.content = content.replace("**", "").replace("##", "")
            if not self.is_new():
                try:
                    self.save()
                    if hasattr(frappe.db, "commit"):
                        frappe.db.commit()
                except Exception:
                    pass
            return {"status": "success", "content": self.content}
        else:
            frappe.throw(_("Không thể tạo nội dung qua AI. Vui lòng kiểm tra API Key."))

    @frappe.whitelist()
    def generate_banner(self, user_feedback=None):
        """Generate a professional 1080x1080 Facebook Ad creative with hero photo and branding."""
        if not Image:
            frappe.throw(_("Thư viện Pillow chưa được cài đặt trên hệ thống."))

        feedback = user_feedback or getattr(self, "ai_feedback", None) or ""
        if user_feedback:
            self.ai_feedback = user_feedback

        meta = COURSE_META.get(self.course, COURSE_META["Chung"])
        W, H = 1080, 1080
        canvas = Image.new("RGB", (W, H), (248, 250, 252))
        draw = ImageDraw.Draw(canvas)

        theme_color = meta["color"]
        accent_color = meta["accent"]

        # Find fonts
        from pathlib import Path
        current_file = Path(__file__).resolve()
        app_root = current_file.parents[3]
        font_bold_path = app_root / "public" / "fonts" / "bold.ttf"
        font_reg_path = app_root / "public" / "fonts" / "regular.ttf"

        def get_font(size, bold=True):
            target = font_bold_path if bold else font_reg_path
            if target.exists():
                return ImageFont.truetype(str(target), size)
            for fallback in [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
            ]:
                if os.path.exists(fallback):
                    return ImageFont.truetype(fallback, size)
            return ImageFont.load_default()

        f_brand = get_font(36, bold=True)
        f_badge = get_font(24, bold=True)
        f_title = get_font(46, bold=True)
        f_sub = get_font(28, bold=True)
        f_item_title = get_font(27, bold=True)
        f_item_sub = get_font(21, bold=False)
        f_cta = get_font(32, bold=True)
        f_foot_b = get_font(23, bold=True)
        f_foot_addr = get_font(20, bold=False)
        f_foot_hotline = get_font(20, bold=False)
        f_promo = get_font(23, bold=True)

        # Top Bar
        draw.rectangle([0, 0, W, 120], fill=theme_color)
        draw.text((50, 42), "EDUFLOW ACADEMY", fill=(255, 255, 255), font=f_brand)
        draw.rounded_rectangle([770, 35, 1030, 85], radius=15, fill=(255, 255, 255))
        draw.text((800, 47), "TUYỂN SINH 2026", fill=theme_color, font=f_badge)

        # Title & Subtitle
        title_text = self.title or meta["title"]
        draw.text((50, 155), title_text[:35], fill=(15, 23, 42), font=f_title)
        draw.text((50, 220), meta["subtitle"], fill=theme_color, font=f_sub)

        # Hero Photo
        photo_dir = app_root / "public" / "images" / "courses"
        photo_path = photo_dir / f"{meta['key']}.jpg"
        if photo_path.exists():
            photo = Image.open(str(photo_path)).convert("RGB")
            photo = photo.resize((500, 500), Image.Resampling.LANCZOS)

            mask = Image.new("L", (500, 500), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([0, 0, 500, 500], radius=24, fill=255)

            draw.rounded_rectangle([536, 276, 1040, 780], radius=26, fill=(203, 213, 225))
            canvas.paste(photo, (540, 280), mask)

            # Promo Badge
            promo_text = meta.get("promo", "ƯU ĐÃI HÔM NAY")
            if feedback.strip():
                fb_clean = feedback.strip()
                nine_key = os.getenv("NINE_ROUTER_API_KEY") or frappe.conf.get("nine_router_api_key")
                default_nine_url = "http://host.docker.internal:20128/v1" if (os.path.exists("/.dockerenv") or os.environ.get("container")) else "http://localhost:20128/v1"
                nine_url = os.getenv("NINE_ROUTER_BASE_URL") or frappe.conf.get("nine_router_base_url") or default_nine_url
                nine_model = os.getenv("NINE_ROUTER_MODEL") or frappe.conf.get("nine_router_model") or "ag/gemini-3.7-flash-low"
                if nine_key and requests:
                    try:
                        p_badge = f"Từ yêu cầu: '{fb_clean}', hãy rút ra đúng 1 cụm từ ưu đãi/khẩu hiệu thật ngắn gọn dưới 24 ký tự in hoa để in lên huy hiệu banner quảng cáo (Ví dụ: ƯU ĐÃI 30% HÔM NAY, TẶNG 1 BUỔI HỌC THỬ, HỌC BỔNG VÀNG). Chỉ trả về đúng cụm từ in hoa đó."
                        resp_b = requests.post(
                            f"{nine_url}/chat/completions",
                            json={
                                "model": nine_model,
                                "messages": [{"role": "user", "content": p_badge}],
                                "max_tokens": 30,
                                "stream": False,
                            },
                            headers={"Authorization": f"Bearer {nine_key}"},
                            timeout=15,
                        )
                        if resp_b.status_code == 200:
                            badge_cand = _extract_ai_response_text(resp_b)
                            if badge_cand:
                                badge_cand = badge_cand.replace('"', '').replace("'", "")
                                if 3 <= len(badge_cand) <= 28:
                                    promo_text = badge_cand.upper()
                    except Exception:
                        pass

                if promo_text == meta.get("promo", "ƯU ĐÃI HÔM NAY"):
                    if len(fb_clean) <= 26:
                        promo_text = fb_clean.upper()
                    else:
                        import re
                        m = re.search(r"((?:giảm|tặng|học bổng|ưu đãi|sale|free|miễn phí)[^,\.\n]{2,25})", fb_clean, re.IGNORECASE)
                        if m:
                            promo_text = m.group(1).strip().upper()
                        else:
                            promo_text = fb_clean[:25].upper()

            bbox_p = draw.textbbox((0, 0), promo_text, font=f_promo)
            pw = bbox_p[2] - bbox_p[0]
            badge_left = max(550, 1020 - pw - 40)
            draw.rounded_rectangle([badge_left, 300, 1020, 360], radius=18, fill=(220, 38, 38))
            draw.text((badge_left + 20, 316), promo_text, fill=(255, 255, 255), font=f_promo)

        # Benefits List
        y_ben = 280
        for b_title, b_sub in meta.get("benefits", []):
            draw.rounded_rectangle([50, y_ben, 510, y_ben + 95], radius=16, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
            # Green checkmark circle
            draw.ellipse([68, y_ben + 28, 104, y_ben + 64], fill=(16, 185, 129))
            draw.line([(78, y_ben + 46), (84, y_ben + 54), (96, y_ben + 38)], fill=(255, 255, 255), width=3)
            draw.text((118, y_ben + 18), b_title, fill=(15, 23, 42), font=f_item_title)
            draw.text((118, y_ben + 54), b_sub, fill=(100, 116, 139), font=f_item_sub)
            y_ben += 115

        # Call to Action Button
        draw.rounded_rectangle([50, 835, 510, 915], radius=24, fill=accent_color)
        bbox_cta = draw.textbbox((0, 0), "INBOX ĐĂNG KÝ NGAY", font=f_cta)
        cta_w = bbox_cta[2] - bbox_cta[0]
        draw.text((50 + (460 - cta_w) // 2, 855), "INBOX ĐĂNG KÝ NGAY", fill=(255, 255, 255), font=f_cta)

        # Footer Bar
        draw.rectangle([0, 935, W, H], fill=(15, 23, 42))
        draw.text((50, 952), "Hệ thống cơ sở:  CS1: Bình Thạnh   •   CS2: Quận 1   •   CS3: Thủ Đức", fill=(255, 255, 255), font=f_foot_b)
        draw.text((50, 988), "Địa chỉ: 475A Điện Biên Phủ (Bình Thạnh)  •  45 Lê Duẩn (Q.1)  •  10 Võ Văn Ngân (Thủ Đức)", fill=(203, 213, 225), font=f_foot_addr)
        draw.text((50, 1028), "Hotline: 0901.888.666   |   Website: eduflow.vn   |   Inbox Fanpage nhận tư vấn ngay", fill=(148, 163, 184), font=f_foot_hotline)

        # Save to buffer and attach via Frappe
        buf = io.BytesIO()
        canvas.save(buf, format="JPEG", quality=95)
        buf.seek(0)

        if self.is_new():
            self.insert(ignore_permissions=True)

        file_name = f"banner_{meta['key']}_{self.name}.jpg"
        doctype_name = getattr(self, "doctype", "Facebook Post")
        file_doc = save_file(file_name, buf.getvalue(), doctype_name, self.name, is_private=0)

        self.image = file_doc.file_url
        self.save()
        if hasattr(frappe.db, "commit"):
            frappe.db.commit()
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
                    mime = "image/jpeg" if image_abs_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
                    with open(image_abs_path, "rb") as f:
                        resp = requests.post(
                            url,
                            data={"caption": self.content, "access_token": token},
                            files={"source": (os.path.basename(image_abs_path), f, mime)},
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

            if not resp.ok:
                err_detail = resp.text
                try:
                    err_json = resp.json()
                    if "error" in err_json:
                        err_msg = err_json["error"].get("message", "")
                        err_code = err_json["error"].get("code", "")
                        if err_code == 190 or "expired" in err_msg.lower():
                            err_detail = f"Facebook Page Access Token đã hết hạn (Session expired). Vui lòng cấp lại Token mới. Chi tiết: {err_msg}"
                        else:
                            err_detail = f"{err_msg} (Mã lỗi FB: {err_code})"
                except Exception:
                    pass
                raise Exception(err_detail)

            data = resp.json()
            post_id = data.get("id") or data.get("post_id")

            self.status = "Posted"
            self.fb_post_id = post_id
            self.fb_post_url = f"https://www.facebook.com/{post_id}"
            self.posted_at = now_datetime()
            self.error_message = ""
            self.save()
            frappe.db.commit()

            # Create CRM notification for user & managers
            try:
                from crm.fcrm.doctype.crm_notification.crm_notification import notify_crm_users
                post_title = getattr(self, "title", None) or f"Bài đăng #{self.name}"
                notify_crm_users(
                    title="Đăng bài Facebook thành công",
                    message=f'Bài viết "{post_title}" đã xuất bản lên Facebook Fanpage thành công! (ID: {post_id})',
                    to_users=[self.owner, "Administrator"] if getattr(self, "owner", None) else ["Administrator"],
                    notification_type="Marketing",
                    reference_doctype="Facebook Post",
                    reference_name=self.name,
                )
            except Exception:
                pass

            frappe.msgprint(_("Đã đăng thành công lên Facebook! ID: {0}").format(post_id), alert=True)
            return {"status": "success", "post_id": post_id, "url": self.fb_post_url}

        except Exception as e:
            error_msg = str(e)
            self.status = "Failed"
            self.error_message = error_msg
            self.save()
            frappe.db.commit()

            try:
                from crm.fcrm.doctype.crm_notification.crm_notification import notify_crm_users
                post_title = getattr(self, "title", None) or f"Bài đăng #{self.name}"
                notify_crm_users(
                    title="Đăng bài Facebook thất bại",
                    message=f'Bài viết "{post_title}" đăng thất bại: {error_msg}',
                    to_users=[self.owner, "Administrator"] if getattr(self, "owner", None) else ["Administrator"],
                    notification_type="Marketing",
                    reference_doctype="Facebook Post",
                    reference_name=self.name,
                )
            except Exception:
                pass

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
