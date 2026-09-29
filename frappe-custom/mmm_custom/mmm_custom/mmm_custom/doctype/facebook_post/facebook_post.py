# Copyright (c) 2026, MMM and contributors
# For license information, please see license.txt

import io
import json
import os
import random
import re
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
        course_val = self.course or "Robotics"
        course_name = course_val
        if hasattr(frappe, "db") and hasattr(frappe.db, "exists"):
            try:
                if not isinstance(frappe.db, MagicMock) and frappe.db.exists("CRM Product", course_val):
                    pname = frappe.db.get_value("CRM Product", course_val, "product_name")
                    if isinstance(pname, str) and pname:
                        course_name = pname
            except Exception:
                pass
        course_name = str(course_name)

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

        clean_hashtag = re.sub(r'[^a-zA-Z0-9_]', '', course_name)
        prompt = (
            f"Bạn là chuyên viên marketing nội dung cao cấp của trung tâm EduFlow Academy.\n"
            f"Hãy viết bài đăng Facebook hấp dẫn để quảng cáo: \"{title_context}\" (Khóa {course_name}).\n\n"
            f"{angle_section}\n\n"
            f"{anti_cliche_rules}\n\n"
            f"Yêu cầu định dạng:\n"
            f"- Ngắn gọn dưới 150 từ, tiếng Việt, giọng văn cuốn hút, tự nhiên\n"
            f"- Kèm emoji sinh động ở tiêu đề, các gạch đầu dòng và phần kêu gọi hành động (ví dụ: 🚀, 💡, 🎯, 👨‍🏫, 🌟, 📚, ✨)\n"
            f"- Nêu bật 3 lợi ích chính dạng gạch đầu dòng rõ ràng, thu hút\n"
            f"- Đề cập rõ 3 cơ sở: CS1 Bình Thạnh, CS2 Quận 1, CS3 Thủ Đức (kèm hotline 0901.888.666)\n"
            f"- Kêu gọi hành động rõ ràng: nhắn tin/inbox fanpage để nhận tư vấn và ưu đãi\n"
            f"- Kèm hashtag: #EduFlow #EduFlowAcademy #{clean_hashtag}\n"
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
            gemini_models = [os.getenv("GEMINI_MODEL") or "gemini-3.5-flash", "gemini-3.8-flash"]
            if gemini_key:
                for g_model in gemini_models:
                    try:
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={gemini_key}"
                        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
                        if resp.status_code == 200:
                            data = resp.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                content = candidates[0]["content"]["parts"][0]["text"].strip()
                                if content:
                                    break
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

        from mmm_custom.banner_generator import generate_and_save_banner
        return generate_and_save_banner(self, user_feedback=user_feedback)


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
            raw_post_id = data.get("post_id") or data.get("id")
            if page_id and "_" not in str(raw_post_id):
                post_id = f"{page_id}_{raw_post_id}"
            else:
                post_id = str(raw_post_id)

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

    @frappe.whitelist()
    def sync_analytics(self):
        """Fetch latest reactions, comments, shares and CRM leads attributed to this post."""
        if getattr(self, "status", None) != "Posted" or not getattr(self, "fb_post_id", None):
            frappe.throw(_("Chỉ có thể đồng bộ số liệu cho bài viết đã xuất bản (status = Posted)."))

        page_id = os.getenv("FACEBOOK_PAGE_ID") or (frappe.conf.get("facebook_page_id") if hasattr(frappe, "conf") else None)
        token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") or (frappe.conf.get("facebook_page_access_token") if hasattr(frappe, "conf") else None)
        if not token:
            frappe.throw(_("Chưa cấu hình FACEBOOK_PAGE_ACCESS_TOKEN."))

        try:
            target_id = str(self.fb_post_id)
            if "_" not in target_id and page_id:
                target_id = f"{page_id}_{target_id}"
                self.fb_post_id = target_id
                self.fb_post_url = f"https://www.facebook.com/{target_id}"

            # 1. Pull post metrics from Graph API
            url = f"https://graph.facebook.com/v21.0/{target_id}"
            params = {
                "fields": "reactions.summary(total_count),comments.filter(stream).summary(total_count),shares",
                "access_token": token,
            }
            resp = requests.get(url, params=params, timeout=20)
            if not resp.ok:
                # Fallback without shares if object is a photo or doesn't support shares
                params["fields"] = "reactions.summary(total_count),comments.filter(stream).summary(total_count)"
                resp = requests.get(url, params=params, timeout=20)

            if resp.ok:
                data = resp.json()
                self.likes_count = data.get("reactions", {}).get("summary", {}).get("total_count", 0)
                self.comments_count = data.get("comments", {}).get("summary", {}).get("total_count", 0)
                self.shares_count = data.get("shares", {}).get("count", 0)

            # 2. Try fetching reach / impressions (optional, if read_insights permission exists)
            try:
                insights_url = f"https://graph.facebook.com/v21.0/{target_id}/insights"
                i_resp = requests.get(insights_url, params={"metric": "post_impressions", "access_token": token}, timeout=15)
                if i_resp.ok:
                    i_data = i_resp.json()
                    for item in i_data.get("data", []):
                        if item.get("name") == "post_impressions":
                            values = item.get("values", [])
                            if values and "value" in values[0]:
                                self.reach_count = values[0]["value"]
            except Exception:
                pass

            # 3. Measure attributed CRM Leads from this post
            if hasattr(frappe, "db") and hasattr(frappe.db, "sql") and type(frappe.db).__name__ not in ("MagicMock", "Mock"):
                try:
                    res = frappe.db.sql("""
                        SELECT COUNT(DISTINCT parent) FROM `tabFCRM Note`
                        WHERE parenttype = 'CRM Lead' AND (content LIKE %s OR title LIKE %s)
                    """, (f"%{self.fb_post_id}%", f"%{self.name}%"))
                    if res and len(res) > 0 and len(res[0]) > 0:
                        self.leads_count = res[0][0] or 0
                except Exception:
                    pass

            # Synchronize comments child table
            try:
                self.sync_comments(save=False)
            except Exception:
                pass

            self.evaluate_ads_potential()
            self.last_analytics_sync = now_datetime()
            self.save()
            if hasattr(frappe.db, "commit"):
                frappe.db.commit()

            return {
                "status": "success",
                "likes": getattr(self, "likes_count", 0),
                "comments": getattr(self, "comments_count", 0),
                "shares": getattr(self, "shares_count", 0),
                "reach": getattr(self, "reach_count", 0),
                "leads": getattr(self, "leads_count", 0),
                "ads_recommendation": getattr(self, "ads_recommendation", "Not Evaluated"),
                "synced_at": str(self.last_analytics_sync),
            }

        except Exception as e:
            err_msg = str(e)
            if hasattr(frappe, "log_error"):
                frappe.log_error(f"Sync analytics failed for post {self.name}: {err_msg}", "Facebook Analytics Sync")
            frappe.throw(_("Đồng bộ số liệu thất bại: {0}").format(err_msg))

    @frappe.whitelist()
    def sync_comments(self, save=True):
        """Fetch Facebook comments on this post and update child table 'comments'."""
        if getattr(self, "status", None) != "Posted" or not getattr(self, "fb_post_id", None):
            if save:
                frappe.throw(_("Chỉ có thể đồng bộ bình luận cho bài viết đã xuất bản (status = Posted)."))
            return {"status": "skipped", "count": 0}

        page_id = os.getenv("FACEBOOK_PAGE_ID") or (frappe.conf.get("facebook_page_id") if hasattr(frappe, "conf") else None)
        token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") or (frappe.conf.get("facebook_page_access_token") if hasattr(frappe, "conf") else None)
        if not token:
            if save:
                frappe.throw(_("Chưa cấu hình FACEBOOK_PAGE_ACCESS_TOKEN."))
            return {"status": "no_token", "count": 0}

        target_id = str(self.fb_post_id)
        if "_" not in target_id and page_id:
            target_id = f"{page_id}_{target_id}"

        url = f"https://graph.facebook.com/v21.0/{target_id}/comments"
        params = {
            "fields": "id,from,message,created_time,like_count",
            "limit": 50,
            "access_token": token,
        }
        try:
            resp = requests.get(url, params=params, timeout=20)
            if not resp.ok:
                if save:
                    frappe.throw(_("Lỗi khi tải bình luận từ Facebook: {0}").format(resp.text[:200]))
                return {"status": "error", "count": 0}

            data = resp.json().get("data", [])
            self.set("comments", [])
            for item in data:
                cid = item.get("id")
                from_name = item.get("from", {}).get("name", "Khách Facebook")
                msg = (item.get("message") or "").strip()
                ctime_str = item.get("created_time")
                formatted_time = None
                if ctime_str:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(ctime_str.replace("+0000", "+00:00"))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass

                lower = msg.lower()
                if any(k in lower for k in ["học phí", "giá", "bao nhiêu", "chi phí", "tiền"]):
                    sentiment = "Hỏi học phí / lịch"
                elif any(k in lower for k in ["tư vấn", "khóa học", "học", "lớp", "đăng ký", "cho mình", "inbox"]):
                    sentiment = "Quan tâm khóa học"
                elif any(k in lower for k in ["hay", "đẹp", "tuyệt", "xịn", "like", "thích", "chất"]):
                    sentiment = "Tích cực"
                else:
                    sentiment = "Spam / Khác"

                self.append("comments", {
                    "comment_id": cid,
                    "from_name": from_name,
                    "comment_message": msg,
                    "comment_time": formatted_time,
                    "sentiment": sentiment,
                })

            self.comments_count = len(self.comments)
            if save:
                self.save()
                if hasattr(frappe.db, "commit"):
                    frappe.db.commit()

            return {"status": "success", "count": len(self.comments)}
        except Exception as e:
            if save:
                frappe.throw(_("Đồng bộ bình luận thất bại: {0}").format(str(e)))
            return {"status": "error", "message": str(e), "count": 0}

    def evaluate_ads_potential(self):
        """Evaluates organic engagement to advise whether this post is worth running Meta Ads."""
        likes = getattr(self, "likes_count", 0) or 0
        comments = getattr(self, "comments_count", 0) or 0
        shares = getattr(self, "shares_count", 0) or 0
        leads = getattr(self, "leads_count", 0) or 0

        # Organic engagement score formula: 1*like + 3*comment + 5*share + 10*lead
        score = likes * 1 + comments * 3 + shares * 5 + leads * 10

        if leads > 0 or comments >= 2 or score >= 5:
            recommendation = "Recommended"
        elif score >= 1:
            recommendation = "Review"
        else:
            recommendation = "Not Recommended"

        self.ads_recommendation = recommendation
        return {
            "score": score,
            "recommendation": recommendation,
            "metrics": {
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "leads": leads,
            },
        }

    @frappe.whitelist()
    def get_ai_ads_advice(self):
        """Generates comprehensive AI advice for running Meta Ads on this post, including target persona, budget, and strategy."""
        eval_res = self.evaluate_ads_potential()
        if not self.is_new():
            try:
                self.save()
                if hasattr(frappe.db, "commit"):
                    frappe.db.commit()
            except Exception:
                pass

        course_val = getattr(self, "course", None) or "Robotics"
        course_name = course_val
        if hasattr(frappe, "db") and hasattr(frappe.db, "exists"):
            try:
                if not isinstance(frappe.db, MagicMock) and frappe.db.exists("CRM Product", course_val):
                    pname = frappe.db.get_value("CRM Product", course_val, "product_name")
                    if isinstance(pname, str) and pname:
                        course_name = pname
            except Exception:
                pass
        course_name = str(course_name)

        score = eval_res["score"]
        recommendation = eval_res["recommendation"]
        likes = eval_res["metrics"]["likes"]
        comments = eval_res["metrics"]["comments"]
        leads = eval_res["metrics"]["leads"]

        # Default / Heuristic Persona based on course
        post_title = getattr(self, "title", None) or ""
        post_content = getattr(self, "content", None) or ""
        lower_c = (course_name + " " + post_title).lower()
        if any(w in lower_c for w in ["anh", "english", "ielts", "toeic", "giao tiếp"]):
            default_age = "20 - 45 tuổi (Sinh viên, người đi làm & phụ huynh có con học sinh)"
            default_interests = "Tiếng Anh giao tiếp, Luyện thi IELTS/TOEIC, Phát âm tiếng Anh chuẩn, Du học, Phát triển sự nghiệp"
            default_gender = "Tất cả"
        elif any(w in lower_c for w in ["bơi", "swim", "lặn"]):
            default_age = "25 - 45 tuổi (Phụ huynh có con 4 - 14 tuổi)"
            default_interests = "Bơi lội trẻ em, Kỹ năng sinh tồn dưới nước, Lớp học bơi mùa hè, Hoạt động thể chất cho bé"
            default_gender = "Tất cả (Ưu tiên Mẹ / Nữ 60%)"
        elif any(w in lower_c for w in ["toán", "math", "soroban", "tư duy"]):
            default_age = "26 - 42 tuổi (Phụ huynh có con 4 - 10 tuổi)"
            default_interests = "Toán tư duy, Rèn luyện sự tập trung, Chuẩn bị vào lớp 1, Giáo dục sớm cho trẻ"
            default_gender = "Tất cả (Ưu tiên Phụ huynh)"
        elif any(w in lower_c for w in ["robo", "stem", "lập trình", "code", "ai", "python"]):
            default_age = "28 - 45 tuổi (Phụ huynh có con 6 - 15 tuổi, yêu thích công nghệ)"
            default_interests = "Giáo dục STEM, Robotics cho trẻ em, Lập trình Scratch & Python, Trường song ngữ, Tư duy logic sáng tạo"
            default_gender = "Tất cả"
        elif any(w in lower_c for w in ["đồ họa", "photoshop", "autocad", "thiết kế", "pts"]):
            default_age = "18 - 32 tuổi (Sinh viên, người mới tốt nghiệp & người muốn chuyển nghề)"
            default_interests = "Thiết kế đồ họa, Adobe Photoshop, Illustrator, Thiết kế nội thất, Mỹ thuật đa phương tiện, Freelance design"
            default_gender = "Tất cả"
        elif any(w in lower_c for w in ["excel", "văn phòng", "tin học"]):
            default_age = "20 - 38 tuổi (Nhân viên văn phòng, kế toán, sinh viên năm cuối)"
            default_interests = "Tin học văn phòng, Excel nâng cao, Tự động hóa báo cáo, Phân tích dữ liệu, Kỹ năng công sở"
            default_gender = "Tất cả"
        else:
            default_age = "22 - 45 tuổi (Người học kỹ năng & Phụ huynh học sinh)"
            default_interests = f"Khóa học {course_name}, Phát triển bản thân, Kỹ năng mềm, Giáo dục chất lượng cao"
            default_gender = "Tất cả"

        if recommendation == "Recommended":
            default_daily_budget = "100.000đ - 200.000đ / ngày"
            default_duration = "5 - 7 ngày để thuật toán Meta tối ưu hoá tệp chuyển đổi"
            default_objective = "Tin nhắn Messenger (Messages) kết nối Chatwoot bot hoặc Thu hút khách hàng tiềm năng (Leads)"
            default_cpl = "25.000đ - 45.000đ / Lead tư vấn"
            default_rationale = (
                f"Bài viết đã có tín hiệu tương tác tự nhiên tốt ({likes} Thích, {comments} Bình luận, {leads} Leads). "
                "Bình luận của học viên/khách hàng tạo hiệu ứng Social Proof tự nhiên rất mạnh. "
                "Chạy quảng cáo cho bài này sẽ giúp giảm chi phí CPA/CPL tới 30-40% so với tạo quảng cáo hoàn toàn mới."
            )
            default_tips = [
                "Chọn mục tiêu 'Tin nhắn' (Messenger) để khách hàng bấm vào tự động kích hoạt EduFlow Chatwoot Bot trả lời & lấy thông tin ngay.",
                "Sử dụng bài viết có sẵn (Use Existing Post) để giữ nguyên toàn bộ lượt Like, Comment và Social Proof đã có.",
                "Ghim bình luận phản hồi tích cực hoặc giải đáp thắc mắc hay nhất lên đầu bài để tăng độ tin cậy.",
                "Chạy thử nghiệm ngân sách 100k/ngày trong 3 ngày đầu, nếu CPL < 35k thì mở rộng ngân sách lên 300k/ngày.",
            ]
        elif recommendation == "Review":
            default_daily_budget = "50.000đ - 100.000đ / ngày"
            default_duration = "3 ngày test thử nghiệm"
            default_objective = "Tương tác bài viết (Post Engagement) để thăm dò thị trường"
            default_cpl = "Chưa xác định (Cần đo lường thêm)"
            default_rationale = (
                f"Bài viết đã có tương tác ban đầu ({likes} Thích, {comments} Bình luận) nhưng chưa đủ mạnh để bung ngân sách lớn. "
                "Nên chạy thử nghiệm ngân sách nhỏ trong 3 ngày để kiểm tra mức độ thu hút của tiêu đề và hình ảnh."
            )
            default_tips = [
                "Bắt đầu với ngân sách nhỏ (50k - 100k/ngày) trong 3 ngày để đo lường CTR và lượt click vào tin nhắn.",
                "Theo dõi chi phí mỗi lượt nhắn tin (Cost per Messaging Conversation Started). Nếu trên 50k, cân nhắc đổi hình ảnh banner hoặc câu mở đầu.",
                "Tương tác trả lời nhanh các bình luận phát sinh để tăng điểm chất lượng bài viết trong mắt thuật toán Facebook."
            ]
        else:
            default_daily_budget = "Không khuyến nghị chạy ngay"
            default_duration = "0 ngày (Tạm hoãn chi ngân sách)"
            default_objective = "Tối ưu lại nội dung và hình ảnh trước khi chạy"
            default_cpl = "Rủi ro lãng phí ngân sách cao"
            default_rationale = (
                "Bài viết hiện chưa có tương tác tự nhiên đáng kể. Nếu bung tiền chạy quảng cáo ngay lúc này, "
                "chi phí quảng cáo có thể cao do thiếu Social Proof và bài viết chưa được kiểm chứng độ thu hút."
            )
            default_tips = [
                "Bấm nút 'AI viết lại nội dung' hoặc 'Tạo lại banner' để thử góc tiếp cận mới hấp dẫn hơn.",
                "Chia sẻ bài viết vào một số hội nhóm hoặc nhờ đồng nghiệp/học viên cũ tương tác ban đầu.",
                "Khi bài viết có tối thiểu 2-3 bình luận hoặc phản hồi tích cực, hãy quay lại bấm đánh giá để kích hoạt chiến dịch quảng cáo."
            ]

        # Call AI for personalized advice if API key exists
        prompt = (
            f"Bạn là chuyên gia cố vấn quảng cáo Meta Ads (Facebook Ads) cho học viện EduFlow.\n"
            f"Dưới đây là thông tin bài viết và số liệu tương tác thực tế từ Facebook:\n"
            f"- Khóa học: {course_name}\n"
            f"- Tiêu đề: {post_title or 'N/A'}\n"
            f"- Nội dung tóm tắt: {post_content[:200]}\n"
            f"- Số lượt Thích: {likes}\n"
            f"- Số lượt Bình luận: {comments}\n"
            f"- Số Leads CRM thu về: {leads}\n"
            f"- Đánh giá tiềm năng: {recommendation} (Điểm: {score})\n\n"
            f"Hãy đưa ra tư vấn chạy quảng cáo tối ưu dưới định dạng JSON duy nhất như sau (không kèm markdown hay chữ thừa bên ngoài):\n"
            f"{{\n"
            f'  "rationale": "Giải thích ngắn gọn (2-3 câu) vì sao nên hoặc không nên chạy ads cho bài này",\n'
            f'  "target_audience": {{\n'
            f'    "age": "Độ tuổi phù hợp",\n'
            f'    "location": "Khu vực địa lý",\n'
            f'    "interests": "Sở thích và hành vi chi tiết",\n'
            f'    "gender": "Giới tính"\n'
            f'  }},\n'
            f'  "budget_plan": {{\n'
            f'    "daily_budget": "Mức ngân sách ngày đề xuất",\n'
            f'    "duration": "Thời gian chạy",\n'
            f'    "objective": "Mục tiêu chiến dịch Meta Ads",\n'
            f'    "expected_cpl": "Chi phí ước tính trên mỗi Lead/Tin nhắn"\n'
            f'  }},\n'
            f'  "tips": [\n'
            f'    "Mẹo 1",\n'
            f'    "Mẹo 2",\n'
            f'    "Mẹo 3"\n'
            f'  ]\n'
            f"}}"
        )

        ai_advice = None
        nine_key = os.getenv("NINE_ROUTER_API_KEY") or (hasattr(frappe, "conf") and frappe.conf.get("nine_router_api_key"))
        default_nine_url = "http://host.docker.internal:20128/v1" if (os.path.exists("/.dockerenv") or os.environ.get("container")) else "http://localhost:20128/v1"
        nine_url = os.getenv("NINE_ROUTER_BASE_URL") or (hasattr(frappe, "conf") and frappe.conf.get("nine_router_base_url")) or default_nine_url
        nine_model = os.getenv("NINE_ROUTER_MODEL") or (hasattr(frappe, "conf") and frappe.conf.get("nine_router_model")) or "ag/gemini-3.7-flash-low"

        if nine_key:
            try:
                resp = requests.post(
                    f"{nine_url}/chat/completions",
                    json={
                        "model": nine_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 600,
                        "stream": False,
                    },
                    headers={"Authorization": f"Bearer {nine_key}"},
                    timeout=25,
                )
                if resp.status_code == 200:
                    raw_text = _extract_ai_response_text(resp)
                    if raw_text:
                        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                        if json_match:
                            ai_advice = json.loads(json_match.group(0))
            except Exception:
                pass

        if not ai_advice:
            gemini_key = os.getenv("GEMINI_API_KEY") or (hasattr(frappe, "conf") and frappe.conf.get("gemini_api_key"))
            gemini_models = [os.getenv("GEMINI_MODEL") or "gemini-3.5-flash", "gemini-3.8-flash"]
            if gemini_key:
                for g_model in gemini_models:
                    try:
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={gemini_key}"
                        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
                        if resp.status_code == 200:
                            data = resp.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                raw_text = candidates[0]["content"]["parts"][0]["text"].strip()
                                json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                                if json_match:
                                    ai_advice = json.loads(json_match.group(0))
                                    if ai_advice:
                                        break
                    except Exception:
                        pass

        final_rationale = (ai_advice.get("rationale") if (ai_advice and isinstance(ai_advice.get("rationale"), str)) else default_rationale)
        final_target = {
            "age": (ai_advice.get("target_audience", {}).get("age") if (ai_advice and isinstance(ai_advice.get("target_audience"), dict)) else default_age) or default_age,
            "location": (ai_advice.get("target_audience", {}).get("location") if (ai_advice and isinstance(ai_advice.get("target_audience"), dict)) else "Bán kính 5 - 10km quanh trung tâm (TP.HCM / Hà Nội)") or "Bán kính 5 - 10km quanh trung tâm",
            "interests": (ai_advice.get("target_audience", {}).get("interests") if (ai_advice and isinstance(ai_advice.get("target_audience"), dict)) else default_interests) or default_interests,
            "gender": (ai_advice.get("target_audience", {}).get("gender") if (ai_advice and isinstance(ai_advice.get("target_audience"), dict)) else default_gender) or default_gender,
        }
        final_budget = {
            "daily_budget": (ai_advice.get("budget_plan", {}).get("daily_budget") if (ai_advice and isinstance(ai_advice.get("budget_plan"), dict)) else default_daily_budget) or default_daily_budget,
            "duration": (ai_advice.get("budget_plan", {}).get("duration") if (ai_advice and isinstance(ai_advice.get("budget_plan"), dict)) else default_duration) or default_duration,
            "objective": (ai_advice.get("budget_plan", {}).get("objective") if (ai_advice and isinstance(ai_advice.get("budget_plan"), dict)) else default_objective) or default_objective,
            "expected_cpl": (ai_advice.get("budget_plan", {}).get("expected_cpl") if (ai_advice and isinstance(ai_advice.get("budget_plan"), dict)) else default_cpl) or default_cpl,
        }
        final_tips = (ai_advice.get("tips") if (ai_advice and isinstance(ai_advice.get("tips"), list) and len(ai_advice.get("tips")) > 0) else default_tips)

        return {
            "status": "success",
            "post_name": getattr(self, "name", None),
            "post_title": post_title,
            "course": course_name,
            "score": score,
            "recommendation": recommendation,
            "metrics": eval_res["metrics"],
            "rationale": final_rationale,
            "target_audience": final_target,
            "budget_plan": final_budget,
            "tips": final_tips,
            "ads_manager_url": "https://adsmanager.facebook.com/",
        }


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


@frappe.whitelist()
def sync_post_comments(post_name):
    """Whitelisted function to sync Facebook comments for a specific post."""
    if not hasattr(frappe, "get_doc"):
        return {"status": "success", "comments_count": 0, "comments": []}
    doc = frappe.get_doc("Facebook Post", post_name)
    res = doc.sync_comments(save=True)
    return {
        "status": "success",
        "comments_count": len(doc.get("comments", [])),
        "comments": [c.as_dict() if hasattr(c, "as_dict") else c for c in doc.get("comments", [])],
    }


@frappe.whitelist()
def sync_post_analytics(post_name):
    """Whitelisted function to sync Facebook analytics (likes, comments, reach, shares) for a specific post."""
    if not hasattr(frappe, "get_doc"):
        return {"status": "success", "likes": 0, "comments": 0}
    doc = frappe.get_doc("Facebook Post", post_name)
    res = doc.sync_analytics()
    return {
        "status": "success",
        "analytics": res,
    }


@frappe.whitelist()
def sync_all_posted_analytics():
    """Background scheduler task & whitelisted API: periodically synchronizes analytics for posts published in the last 14 days."""
    if not hasattr(frappe, "get_all"):
        return {"status": "success", "synced_count": 0}
    try:
        from datetime import timedelta
        cutoff = now_datetime() - timedelta(days=14)
        posts = frappe.get_all(
            "Facebook Post",
            filters={"status": "Posted", "posted_at": [">=", cutoff]},
            pluck="name",
        )
        synced_count = 0
        for name in posts:
            try:
                doc = frappe.get_doc("Facebook Post", name)
                doc.sync_analytics()
                synced_count += 1
            except Exception as e:
                if hasattr(frappe, "log_error"):
                    frappe.log_error(f"Periodic analytics sync failed for {name}: {e}", "Facebook Post Analytics Scheduler")
        return {"status": "success", "synced_count": synced_count}
    except Exception as e:
        if hasattr(frappe, "log_error"):
            frappe.log_error(f"sync_all_posted_analytics failed: {e}", "Facebook Post Analytics Scheduler")
        return {"status": "error", "message": str(e), "synced_count": 0}


@frappe.whitelist()
def get_marketing_overview():
    """Aggregates comprehensive Facebook marketing analytics and top performing posts."""
    if not hasattr(frappe, "get_all"):
        return {"status": "success", "kpis": {}, "top_leads": [], "top_engagement": []}

    try:
        posts = frappe.get_all(
            "Facebook Post",
            fields=[
                "name", "title", "course", "status", "day_of_week",
                "scheduled_time", "posted_at", "fb_post_id", "fb_post_url",
                "likes_count", "comments_count", "shares_count", "reach_count", "leads_count",
                "ads_recommendation"
            ]
        )

        total_posts = len(posts)
        posted_count = sum(1 for p in posts if p.get("status") == "Posted")
        scheduled_count = sum(1 for p in posts if p.get("status") == "Scheduled")
        pending_count = sum(1 for p in posts if p.get("status") == "Pending Approval")
        draft_count = sum(1 for p in posts if p.get("status") == "Draft")

        total_likes = sum(p.get("likes_count") or 0 for p in posts)
        total_comments = sum(p.get("comments_count") or 0 for p in posts)
        total_shares = sum(p.get("shares_count") or 0 for p in posts)
        total_reach = sum(p.get("reach_count") or 0 for p in posts)
        total_leads = sum(p.get("leads_count") or 0 for p in posts)
        recommended_ads_count = sum(1 for p in posts if p.get("ads_recommendation") == "Recommended")

        # Top posts by leads
        posts_with_leads = [p for p in posts if (p.get("leads_count") or 0) > 0]
        top_leads = sorted(posts_with_leads or posts, key=lambda x: x.get("leads_count") or 0, reverse=True)[:5]

        # Top posts by engagement (likes + comments + shares)
        def engagement_score(p):
            return (p.get("likes_count") or 0) + (p.get("comments_count") or 0) * 2 + (p.get("shares_count") or 0) * 3

        top_engagement = sorted(posts, key=engagement_score, reverse=True)[:5]

        return {
            "status": "success",
            "kpis": {
                "total_posts": total_posts,
                "posted_count": posted_count,
                "scheduled_count": scheduled_count,
                "pending_count": pending_count,
                "draft_count": draft_count,
                "total_likes": total_likes,
                "total_comments": total_comments,
                "total_shares": total_shares,
                "total_reach": total_reach,
                "total_leads": total_leads,
                "recommended_ads_count": recommended_ads_count,
            },
            "top_leads": top_leads,
            "top_engagement": top_engagement,
        }
    except Exception as e:
        if hasattr(frappe, "log_error"):
            frappe.log_error(f"get_marketing_overview failed: {e}", "Facebook Post Marketing Overview")
        return {"status": "error", "message": str(e), "kpis": {}, "top_leads": [], "top_engagement": []}


