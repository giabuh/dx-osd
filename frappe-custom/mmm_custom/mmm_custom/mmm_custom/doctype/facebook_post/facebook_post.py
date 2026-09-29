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
                "synced_at": str(self.last_analytics_sync),
            }

        except Exception as e:
            err_msg = str(e)
            if hasattr(frappe, "log_error"):
                frappe.log_error(f"Sync analytics failed for post {self.name}: {err_msg}", "Facebook Analytics Sync")
            frappe.throw(_("Đồng bộ số liệu thất bại: {0}").format(err_msg))


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
                "likes_count", "comments_count", "shares_count", "reach_count", "leads_count"
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
            },
            "top_leads": top_leads,
            "top_engagement": top_engagement,
        }
    except Exception as e:
        if hasattr(frappe, "log_error"):
            frappe.log_error(f"get_marketing_overview failed: {e}", "Facebook Post Marketing Overview")
        return {"status": "error", "message": str(e), "kpis": {}, "top_leads": [], "top_engagement": []}

