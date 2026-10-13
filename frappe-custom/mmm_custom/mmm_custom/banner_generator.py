# Copyright (c) 2026, MMM and contributors
# For license information, please see license.txt

import base64
import io
import os
from pathlib import Path
import random
import re
import urllib.parse
import requests
from PIL import Image, ImageDraw, ImageFont

try:
    import frappe
    from frappe import _
    from frappe.utils.file_manager import save_file
except ImportError:
    from unittest.mock import MagicMock
    frappe = MagicMock()
    _ = lambda x: x
    def save_file(*args, **kwargs):
        mock_file = MagicMock()
        mock_file.file_url = f"/files/{args[0]}"
        return mock_file


# Comprehensive course domain metadata customized for high-impact commercial posters
COURSE_META = {
    "Robotics": {
        "key": "robotics",
        "theme": (2, 132, 199),     # Cyber Blue
        "accent": (255, 204, 0),    # Bright Gold CTA
        "brand_name": "Sao Việt ROBOTICS & STEM",
        "hook_1": "TỪ Ý TƯỞNG NHỎ",
        "hook_2": "ĐẾN ROBOT THẬT",
        "subtitle": "Một dự án – Nhiều kỹ năng – Kết quả thật",
        "cta": "BẮT ĐẦU DỰ ÁN ĐẦU TIÊN",
        "steps": [
            ("1. Ý tưởng", "và thiết kế sơ đồ", (37, 99, 235)),
            ("2. Lắp ráp", "và nạp code robot", (234, 88, 12)),
            ("3. Chạy thật", "thi đấu & thuyết trình", (16, 185, 129)),
        ],
    },
    "design": {
        "key": "design",
        "theme": (109, 40, 217),    # Purple / Violet
        "accent": (255, 204, 0),    # Bright Gold CTA
        "brand_name": "Sao Việt CREATIVE DESIGN",
        "hook_1": "TỪ NGƯỜI CHƯA BIẾT GÌ",
        "hook_2": "THÀNH THẠO THIẾT KẾ",
        "subtitle": "Chỉnh sửa ảnh đỉnh – Dựng video chất – Nhận dự án ngay",
        "cta": "NHẬN KHÓA HỌC THỬ NGAY",
        "steps": [
            ("1. Công cụ", "làm chủ phần mềm đồ họa", (109, 40, 217)),
            ("2. Thực chiến", "thiết kế ấn phẩm & video", (234, 88, 12)),
            ("3. Portfolio", "tự tin nhận dự án thật", (16, 185, 129)),
        ],
    },
    "autocad": {
        "key": "autocad",
        "theme": (15, 76, 129),     # Classic Engineering Blue
        "accent": (255, 204, 0),    # Bright Gold CTA
        "brand_name": "Sao Việt CAD & 3D DESIGN",
        "hook_1": "TỪ BẢN VẼ Ý TƯỞNG",
        "hook_2": "ĐẾN CÔNG TRÌNH THỰC TẾ",
        "subtitle": "Đọc bản vẽ chuẩn – Dựng 3D chân thực – Kết xuất chuyên nghiệp",
        "cta": "ĐĂNG KÝ HỌC THỬ MIỄN PHÍ",
        "steps": [
            ("1. Dựng hình", "chuẩn tỷ lệ & kỹ thuật", (15, 76, 129)),
            ("2. 3D Model", "phối cảnh & ánh sáng", (234, 88, 12)),
            ("3. Xuất file", "hồ sơ thi công hoàn chỉnh", (16, 185, 129)),
        ],
    },
    "excel": {
        "key": "excel",
        "theme": (16, 130, 80),     # Office Emerald Green
        "accent": (255, 204, 0),    # Bright Gold CTA
        "brand_name": "Sao Việt OFFICE & DATA",
        "hook_1": "TỪ THỦ CÔNG TỐN GIỜ",
        "hook_2": "LÀM CHỦ EXCEL & DỮ LIỆU",
        "subtitle": "Hàm nâng cao – Tự động hóa báo cáo – Dashboard trực quan",
        "cta": "NHẬN ƯU ĐÃI KHÓA HỌC",
        "steps": [
            ("1. Chuẩn hóa", "dữ liệu & phím tắt tốc độ", (16, 130, 80)),
            ("2. Tự động", "hàm xử lý & pivot table", (234, 88, 12)),
            ("3. Dashboard", "báo cáo quản trị đa chiều", (16, 185, 129)),
        ],
    },
    "accounting": {
        "key": "accounting",
        "theme": (30, 64, 175),     # Ledger Blue
        "accent": (255, 204, 0),    # Bright Gold CTA
        "brand_name": "Sao Việt KẾ TOÁN",
        "hook_1": "TỪ SỔ SÁCH RỐI RẮM",
        "hook_2": "ĐẾN BÁO CÁO CHUẨN",
        "subtitle": "Định khoản chuẩn – Làm sổ sách thực tế – Quyết toán thuế tự tin",
        "cta": "NHẬN ƯU ĐÃI KHÓA HỌC",
        "steps": [
            ("1. Nguyên lý", "hạch toán & định khoản", (30, 64, 175)),
            ("2. Thực hành", "chứng từ, sổ sách, MISA", (234, 88, 12)),
            ("3. Báo cáo", "thuế & báo cáo tài chính", (16, 185, 129)),
        ],
    },
    "programming": {
        "key": "programming",
        "theme": (30, 41, 59),      # Slate Tech
        "accent": (255, 204, 0),    # Bright Gold CTA
        "brand_name": "Sao Việt TECH & CODING",
        "hook_1": "TỪ CHƯA BIẾT GÌ",
        "hook_2": "XÂY DỰNG WEB & APP",
        "subtitle": "Học qua dự án – Tư duy logic – Sẵn sàng việc làm công nghệ",
        "cta": "BẮT ĐẦU HỌC THỬ NGAY",
        "steps": [
            ("1. Nền tảng", "cú pháp & tư duy logic", (37, 99, 235)),
            ("2. Dự án", "xây dựng ứng dụng thực tế", (234, 88, 12)),
            ("3. Triển khai", "đưa sản phẩm lên internet", (16, 185, 129)),
        ],
    },
    "marketing": {
        "key": "marketing",
        "theme": (234, 88, 12),     # Vibrant Orange
        "accent": (255, 204, 0),    # Bright Gold CTA
        "brand_name": "Sao Việt DIGITAL MARKETING",
        "hook_1": "TỪ CHẠY ADS TỐN KÉM",
        "hook_2": "TỐI ƯU ĐƠN HÀNG THẬT",
        "subtitle": "Target chuẩn tệp – Tối ưu chi phí – Đột phá doanh số",
        "cta": "NHẬN LỘ TRÌNH TƯ VẤN",
        "steps": [
            ("1. Nghiên cứu", "tệp khách & content đỉnh", (234, 88, 12)),
            ("2. Thực chiến", "lên chiến dịch đa nền tảng", (37, 99, 235)),
            ("3. Tối ưu", "đo lường & tăng doanh thu", (16, 185, 129)),
        ],
    },
    "ai": {
        "key": "ai",
        "theme": (79, 70, 229),     # Cyber Indigo
        "accent": (255, 204, 0),    # Bright Gold CTA
        "brand_name": "Sao Việt AI & AUTOMATION",
        "hook_1": "TỪ LÀM VIỆC THỦ CÔNG",
        "hook_2": "LÀM CHỦ CÔNG NGHỆ AI",
        "subtitle": "Tự động hóa quy trình – Ứng dụng AI – Tăng tốc 10x",
        "cta": "KHÁM PHÁ CÔNG NGHỆ MỚI",
        "steps": [
            ("1. Làm quen", "prompting & công cụ AI đỉnh", (79, 70, 229)),
            ("2. Tích hợp", "xây dựng quy trình tự động", (234, 88, 12)),
            ("3. Bứt phá", "vận hành tự động hóa 24/7", (16, 185, 129)),
        ],
    },
    "Tiếng Anh": {
        "key": "tieng_anh",
        "theme": (37, 99, 235),      # Royal Blue
        "accent": (255, 204, 0),     # Bright Gold CTA
        "brand_name": "Sao Việt ENGLISH",
        "hook_1": "TỪ NGẠI NGÙNG BỠ NGỠ",
        "hook_2": "ĐẾN TỰ TIN GIAO TIẾP",
        "subtitle": "100% Bản ngữ – Phản xạ chuẩn – Bứt phá tương lai",
        "cta": "ĐĂNG KÝ HỌC THỬ MIỄN PHÍ",
        "steps": [
            ("1. Chuẩn hóa", "phát âm & phản xạ", (37, 99, 235)),
            ("2. Thực chiến", "giao tiếp 1 kèm 1", (234, 88, 12)),
            ("3. Tự tin", "nói tiếng Anh trôi chảy", (16, 185, 129)),
        ],
    },
    "Bơi lội": {
        "key": "boi_loi",
        "theme": (13, 148, 136),     # Teal
        "accent": (255, 204, 0),     # Bright Gold CTA
        "brand_name": "Sao Việt AQUATICS",
        "hook_1": "TỪ SỢ NƯỚC RỤT RÈ",
        "hook_2": "ĐẾN BƠI LỘI THÀNH THẠO",
        "subtitle": "An toàn dưới nước – Bơi vững sau 8 buổi – Hồ ấm 4 mùa",
        "cta": "ĐĂNG KÝ HỌC THỬ BUỔI ĐẦU",
        "steps": [
            ("1. Làm quen", "thở nước & thả nổi", (13, 148, 136)),
            ("2. Rèn luyện", "kỹ thuật bơi chuẩn", (234, 88, 12)),
            ("3. Tốt nghiệp", "bơi vững sau 8 buổi", (16, 185, 129)),
        ],
    },
    "Toán tư duy": {
        "key": "toan_tu_duy",
        "theme": (124, 58, 237),    # Purple
        "accent": (255, 204, 0),    # Bright Gold CTA
        "brand_name": "Sao Việt MATH & LOGIC",
        "hook_1": "TỪ SỢ HÃI MÔN TOÁN",
        "hook_2": "ĐẾN ĐAM MÊ TƯ DUY",
        "subtitle": "Khai mở tiềm năng – Học qua trò chơi – Bứt phá tư duy",
        "cta": "NHẬN TEST TƯ DUY MIỄN PHÍ",
        "steps": [
            ("1. Khám phá", "toán học qua trò chơi", (124, 58, 237)),
            ("2. Độc lập", "rèn tư duy phản biện", (234, 88, 12)),
            ("3. Bứt phá", "tự tin giải bài khó", (16, 185, 129)),
        ],
    },
    "Chung": {
        "key": "chung",
        "theme": (234, 88, 12),     # Orange
        "accent": (255, 204, 0),    # Bright Gold CTA
        "brand_name": "Sao Việt ACADEMY",
        "hook_1": "TỪ CON SỐ 0",
        "hook_2": "ĐẾN LÀM CHỦ CÔNG NGHỆ",
        "subtitle": "Học viện kỹ năng – Đào tạo thực chiến – Tuyển sinh 2026",
        "cta": "NHẬN HỌC BỔNG KHAI GIẢNG",
        "steps": [
            ("1. Định hướng", "lộ trình cá nhân hóa", (234, 88, 12)),
            ("2. Thực hành", "dự án thực tế 100%", (37, 99, 235)),
            ("3. Thành thạo", "kỹ năng tương lai", (16, 185, 129)),
        ],
    },
}


def strip_emoji(text):
    """Strip emojis and non-standard unicode symbols that do not render in standard TrueType fonts."""
    if not text:
        return ""
    pattern = re.compile(r'[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50\u200d\ufe0f\u2700-\u27bf]')
    cleaned = pattern.sub('', text)
    return re.sub(r'\s+', ' ', cleaned).strip()


def resolve_course_display_name(course):
    """Resolve human-readable product name if course is a CRM Product ID like TE-ROBO or VP-EXCEL."""
    if not course:
        return "Robotics"
    if hasattr(frappe, "db") and hasattr(frappe.db, "exists"):
        try:
            if not isinstance(frappe.db, MagicMock) and frappe.db.exists("CRM Product", course):
                pname = frappe.db.get_value("CRM Product", course, "product_name")
                if isinstance(pname, str) and pname:
                    return pname
        except Exception:
            pass
    return str(course)


def get_course_meta(course):
    """Retrieve metadata matching course code or domain keywords."""
    if not course:
        return COURSE_META["Robotics"]

    raw = str(course).strip()
    norm = raw.lower()

    # Exact key match
    if raw in COURSE_META:
        return COURSE_META[raw]

    # Robotics & STEM
    if any(k in norm for k in ["robot", "scratch", "stem"]) or norm.startswith("te-"):
        return COURSE_META["Robotics"]

    # Creative & Graphic Design
    if any(k in norm for k in ["photoshop", "illustrator", "premiere", "after effects", "corel", "đồ họa", "design"]) or norm.startswith("dh-"):
        return COURSE_META["design"]

    # AutoCAD & 3D Engineering
    if any(k in norm for k in ["autocad", "3ds", "revit", "sketchup", "solidworks", "inventor", "vray", "kiến trúc", "bản vẽ", "cad"]) or norm.startswith("vkt-"):
        return COURSE_META["autocad"]

    # Digital Marketing (Check before kt- to avoid mkt- substring collision)
    if any(k in norm for k in ["marketing", "facebook ads", "google ads", "tiktok", "seo", "quảng cáo"]) or norm.startswith("mkt-"):
        return COURSE_META["marketing"]

    # Programming & Tech
    if any(k in norm for k in ["lập trình", "web", "mobile", "vba", "coding", "python"]) or norm.startswith("lt-"):
        return COURSE_META["programming"]

    # Accounting (its own poster: "Làm chủ Excel" on an accounting course was wrong)
    if any(k in norm for k in ["kế toán", "misa", "thuế", "ke toan"]) or norm.startswith("kt-") and "excel" not in norm:
        return COURSE_META["accounting"]

    # Office & Excel
    if any(k in norm for k in ["excel", "word", "powerpoint", "mos", "ic3", "văn phòng"]) or norm.startswith("vp-") or norm.startswith("kt-"):
        return COURSE_META["excel"]

    # AI & Automation
    if any(k in norm for k in ["vibe", "n8n", "tự động hóa", "trí tuệ nhân tạo"]) or norm.startswith("ai-"):
        return COURSE_META["ai"]

    # Legacy EduFlow courses
    if any(k in norm for k in ["bơi", "swimming", "aquatics"]):
        return COURSE_META["Bơi lội"]
    if any(k in norm for k in ["tiếng anh", "english"]):
        return COURSE_META["Tiếng Anh"]
    if any(k in norm for k in ["toán", "math"]):
        return COURSE_META["Toán tư duy"]

    return COURSE_META["Chung"]


def build_image_prompt(course, title=None, feedback=None):
    """Craft a high quality commercial photo prompt with subject-specific English keywords."""
    course_name = resolve_course_display_name(course)
    course_clean = (course_name or "").lower()

    if any(k in course_clean for k in ["bơi", "swimming"]):
        subject_desc = "children swimming with certified coach in a crystal clear turquoise heated indoor pool, splashing water, bright smiles"
    elif any(k in course_clean for k in ["tiếng anh", "english"]):
        subject_desc = "Vietnamese student happily practicing English conversation with friendly native teacher in modern classroom"
    elif any(k in course_clean for k in ["toán", "math"]):
        subject_desc = "enthusiastic Vietnamese students solving colorful 3D math puzzle cubes and geometry models in bright modern classroom"
    elif any(k in course_clean for k in ["photoshop", "illustrator", "đồ họa", "design"]):
        subject_desc = "cheerful Vietnamese student working on creative graphic design artwork with drawing tablet and iMac in modern design studio"
    elif any(k in course_clean for k in ["autocad", "cad", "revit", "3ds", "kiến trúc"]):
        subject_desc = "Vietnamese student happily learning AutoCAD 3D architectural blueprints on dual monitors in modern engineering lab"
    elif any(k in course_clean for k in ["excel", "văn phòng", "kế toán"]):
        subject_desc = "cheerful Vietnamese office specialist analyzing dynamic colorful Excel dashboards and business charts on laptop in sunny modern office"
    elif any(k in course_clean for k in ["python", "lập trình", "web", "mobile", "code"]):
        subject_desc = "cheerful Vietnamese student coding Python web application on laptop with clean code lines in modern tech innovation hub"
    elif any(k in course_clean for k in ["marketing", "ads", "seo", "quảng cáo"]):
        subject_desc = "cheerful Vietnamese marketer presenting social media ad analytics and sales growth graphs in bright modern marketing agency"
    elif any(k in course_clean for k in ["ai", "n8n", "tự động hóa"]):
        subject_desc = "cheerful Vietnamese student experimenting with artificial intelligence workflows and robotics in high-tech laboratory"
    elif any(k in course_clean for k in ["robot", "lego", "stem", "scratch"]):
        subject_desc = "Vietnamese student and teacher happily testing modular STEM Lego robot with glowing LEDs in modern robotics academy"
    else:
        subject_desc = "inspiring Vietnamese students collaborating happily on educational project in bright modern academy"

    prompt = (
        f"Award-winning, bright, authentic commercial advertising photo of cheerful {subject_desc}, "
        f"smiling, laughing, high energy, sharp focus, professional photography, 35mm lens, 8k resolution, cinematic lighting"
    )
    if feedback and feedback.strip():
        prompt += f", highlighting {feedback.strip()}"
    return prompt


def get_app_root():
    """Locate the app root directory containing public/images and public/fonts."""
    current_file = Path(__file__).resolve()
    if (current_file.parent / "public" / "images" / "courses").exists():
        return current_file.parent
    for p in current_file.parents:
        if (p / "public" / "images" / "courses").exists():
            return p
        if (p / "mmm_custom" / "public" / "images" / "courses").exists():
            return p / "mmm_custom"
    return current_file.parent


def get_fonts(app_root=None):
    """Load bold and regular fonts with full Vietnamese unicode support."""
    root = app_root or get_app_root()
    font_bold_path = root / "public" / "fonts" / "bold.ttf"
    font_reg_path = root / "public" / "fonts" / "regular.ttf"

    def loader(size, bold=True):
        target = font_bold_path if bold else font_reg_path
        if target.exists():
            try:
                return ImageFont.truetype(str(target), size)
            except Exception:
                pass
        fallback_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
        ]
        for candidate in fallback_candidates:
            if os.path.exists(candidate):
                try:
                    return ImageFont.truetype(candidate, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    return loader


STOCK_PHOTO_FALLBACK = {"accounting": "excel"}  # course field → the stock photo that fits it best


def brand_pill(meta, brand=""):
    """Top pill text: the post's brand (its Facebook Page, else the CRM brand) and the course field, e.g.
    "EduFlow Academy · OFFICE & DATA". COURSE_META keeps a "Sao Việt" prefix from the first demo; it is not a brand
    and is never printed. Pure."""
    field = re.sub(r"^\s*Sao Việt\s*", "", meta.get("brand_name") or "").strip()
    brand = (brand or "").strip()
    if brand and field:
        return f"{brand} · {field}"
    return brand or field or "ACADEMY"


def generate_hero_image(course, title=None, feedback=None, api_key=None, app_root=None):
    """The hero photo only (see hero_image for why a stock photo was used)."""
    return hero_image(course, title=title, feedback=feedback, api_key=api_key, app_root=app_root)[0]


def gemini_failure_note(status, body):
    """What to tell the person when Gemini gave no image (the stock course photo is used instead). Pure."""
    if status == 429:
        return ("Gemini không tạo ảnh: key đang ở gói miễn phí, gói này không có hạn mức tạo ảnh (lỗi 429). "
                "Bật thanh toán cho key trên Google AI Studio, hoặc tải banner từ máy. Đang dùng ảnh mẫu.")
    if status in (401, 403):
        return f"Gemini từ chối key (lỗi {status}): kiểm tra gemini_api_key. Đang dùng ảnh mẫu."
    message = ""
    try:
        import json as _json

        message = (_json.loads(body or "{}").get("error") or {}).get("message", "")
    except Exception:
        message = str(body or "")
    return f"Gemini không tạo được ảnh (lỗi {status}): {message[:140]}. Đang dùng ảnh mẫu."


def hero_image(course, title=None, feedback=None, api_key=None, app_root=None):
    """
    (image, note): a Gemini / Imagen photo when the key can make one, else the course's stock photo with a note
    saying why, so a failed Gemini call is no longer silent.
    """
    note = ""
    meta = get_course_meta(course)
    course_key = meta["key"]
    root = app_root or get_app_root()

    # 1. Tier 1: Gemini / Imagen Image Generation API if key provided
    effective_api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not effective_api_key and hasattr(frappe, "conf"):
        effective_api_key = frappe.conf.get("gemini_api_key")

    if not effective_api_key:
        note = "Chưa cấu hình gemini_api_key nên dùng ảnh mẫu."
    if effective_api_key:
        prompt = build_image_prompt(course, title, feedback)

        # Attempt A: Google Generative AI generateContent with IMAGE modality
        gemini_image_models = [
            "gemini-3.1-flash-image",
            "gemini-3.1-flash-lite-image",
            "gemini-2.5-flash-image",
            "gemini-3-pro-image",
        ]
        for img_model in gemini_image_models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{img_model}:generateContent?key={effective_api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseModalities": ["IMAGE"]}
                }
                resp = requests.post(url, json=payload, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for p in parts:
                            if "inlineData" in p and p["inlineData"].get("data"):
                                img_data = base64.b64decode(p["inlineData"]["data"])
                                img = Image.open(io.BytesIO(img_data)).convert("RGB")
                                return img.resize((980, 860), Image.Resampling.LANCZOS), ""
                    note = "Gemini trả lời nhưng không kèm ảnh. Đang dùng ảnh mẫu."
                else:
                    note = gemini_failure_note(resp.status_code, resp.text)
                    if resp.status_code == 429:  # free tier: no image quota on any image model
                        break
            except Exception as e:
                note = f"Không gọi được Gemini ({type(e).__name__}). Đang dùng ảnh mẫu."

        # Attempt B: Imagen 3 Predict endpoint (supports mock responses in unit tests & Vertex/GCP paid keys)
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={effective_api_key}"
            payload = {
                "instances": [{"prompt": prompt}],
                "parameters": {
                    "sampleCount": 1,
                    "aspectRatio": "1:1",
                    "outputMimeType": "image/jpeg"
                }
            }
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                predictions = data.get("predictions", [])
                if predictions and "bytesBase64Encoded" in predictions[0]:
                    img_data = base64.b64decode(predictions[0]["bytesBase64Encoded"])
                    img = Image.open(io.BytesIO(img_data)).convert("RGB")
                    return img.resize((980, 860), Image.Resampling.LANCZOS), ""
        except Exception as e:
            if hasattr(frappe, "log_error"):
                frappe.log_error(title="Imagen 3 API Error", message=str(e)[:500])

    # 2. Tier 2: Curated authentic commercial studio photography
    # the course's own photo, else the closest one (accounting has none: an office photo, never kids with robots),
    # else the neutral school photo
    candidate_keys = [course_key, STOCK_PHOTO_FALLBACK.get(course_key, "chung"), "chung"]
    for ck in candidate_keys:
        photo_path = root / "public" / "images" / "courses" / f"{ck}.jpg"
        if photo_path.exists():
            try:
                img = Image.open(str(photo_path)).convert("RGB")
                return img.resize((980, 860), Image.Resampling.LANCZOS), note
            except Exception:
                pass

    # 3. Emergency fallback canvas
    canvas = Image.new("RGB", (980, 860), meta["theme"])
    return canvas, note


def compose_commercial_banner(hero_image, course, title=None, feedback=None, app_root=None, footer=None,
                              has_offer=False, brand=""):
    """
    Composite a vibrant, commercial-grade 9:16 vertical poster (1080x1920) in the exact style of Sao Việt Robotics:
      - Vibrant Electric Blue gradient with tech particle grid
      - Curved top brand pill ("Sao Việt ROBOTICS" / "Sao Việt CAD & 3D" / "Sao Việt OFFICE & DATA")
      - 3D Extruded Title ("TỪ Ý TƯỞNG NHỎ" in white, "ĐẾN ROBOT THẬT" in golden yellow 3D lettering)
      - Subtitle oval pill
      - High-impact commercial hero photo of student & project
      - 3 Transformation Roadmap Cards connected by yellow vector arrows
      - Giant bright golden-yellow CTA button with target icon 🎯
      - Modern footer with Hotline and branches: `footer` from CRM data (marketing_plan.footer_text, D-125);
        without it a neutral line, never invented contact details. `has_offer`: an active promotion applies.
    """
    W, H = 1080, 1920
    meta = get_course_meta(course)

    canvas = Image.new("RGB", (W, H), (0, 95, 230))
    draw = ImageDraw.Draw(canvas)

    # 1. Electric Blue Gradient with Cyan Glow
    for y in range(H):
        factor = y / float(H)
        r = int(0 + factor * 5)
        g = int(80 + (1 - factor) * 45)
        b = int(235 - factor * 70)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Subtle tech particle grid
    for gx in range(40, W, 120):
        for gy in range(40, H, 120):
            draw.ellipse([gx, gy, gx + 4, gy + 4], fill=(120, 200, 255))

    # Load fonts
    get_font = get_fonts(app_root)
    f_brand = get_font(36, bold=True)
    f_hook1 = get_font(56, bold=True)
    f_hook2 = get_font(76, bold=True)
    f_sub = get_font(28, bold=True)
    f_step = get_font(24, bold=True)
    f_step_sub = get_font(21, bold=True)
    f_cta = get_font(42, bold=True)
    f_foot = get_font(22, bold=True)

    # 2. Top Brand Badge (Clean curved white pill)
    brand_title = brand_pill(meta, brand)
    bbox_br = draw.textbbox((0, 0), brand_title, font=f_brand)
    wbr = bbox_br[2] - bbox_br[0]
    badge_w = wbr + 120
    bx1 = (W - badge_w) // 2
    draw.rounded_rectangle([bx1, 45, bx1 + badge_w, 115], radius=35, fill=(255, 255, 255))
    # Vector blue star icon
    star_x = bx1 + 35
    draw.polygon([
        (star_x, 80), (star_x + 5, 68), (star_x + 17, 68), (star_x + 7, 88),
        (star_x + 11, 100), (star_x, 92), (star_x - 11, 100), (star_x - 7, 88),
        (star_x - 17, 68), (star_x - 5, 68)
    ], fill=(0, 102, 255))
    draw.text((star_x + 30, 58), brand_title, fill=(0, 51, 153), font=f_brand)

    # 3. Dynamic Catchy 3D Hook Title
    t1 = meta.get("hook_1", "TỪ Ý TƯỞNG NHỎ")
    t2 = meta.get("hook_2", "ĐẾN KẾT QUẢ THẬT")

    # If title has custom text
    if title and len(title.strip()) > 5:
        clean_title = strip_emoji(title)
        if " - " in clean_title:
            parts = clean_title.split(" - ")
            t1 = parts[0].upper()[:24]
            t2 = parts[1].upper()[:24]
        elif len(clean_title) <= 25:
            t2 = clean_title.upper()

    t1 = strip_emoji(t1)
    t2 = strip_emoji(t2)

    # Line 1 (White 3D with dark blue stroke)
    bbox1 = draw.textbbox((0, 0), t1, font=f_hook1)
    w1 = bbox1[2] - bbox1[0]
    x1 = (W - w1) // 2
    for dx, dy in [(-2,-2), (2,-2), (-2,2), (2,2), (0,3), (3,0)]:
        draw.text((x1 + dx, 160 + dy), t1, fill=(0, 30, 90), font=f_hook1)
    draw.text((x1, 160), t1, fill=(255, 255, 255), font=f_hook1)

    # Line 2 (Giant 3D Extruded Golden Yellow)
    bbox2 = draw.textbbox((0, 0), t2, font=f_hook2)
    w2 = bbox2[2] - bbox2[0]
    x2 = (W - w2) // 2
    for d in range(10, 0, -1):
        draw.text((x2 + d, 235 + d), t2, fill=(0, 20, 70), font=f_hook2)
    # Orange inner bevel
    draw.text((x2 + 2, 235 + 2), t2, fill=(234, 88, 12), font=f_hook2)
    draw.text((x2, 235), t2, fill=(255, 215, 0), font=f_hook2)

    # 4. Subtitle Pill
    sub_txt = meta.get("subtitle", "Một dự án – Nhiều kỹ năng – Kết quả thật")
    if feedback and feedback.strip() and len(feedback.strip()) < 35:
        sub_txt = strip_emoji(feedback.strip())
    sub_txt = strip_emoji(sub_txt)

    bbox_s = draw.textbbox((0, 0), sub_txt, font=f_sub)
    ws = bbox_s[2] - bbox_s[0]
    xs = (W - ws) // 2
    draw.rounded_rectangle([xs - 30, 350, xs + ws + 30, 415], radius=32, fill=(255, 255, 255))
    draw.text((xs, 365), sub_txt, fill=(0, 51, 153), font=f_sub)

    # 5. Hero Photo in Middle (Smooth rounded frame with glowing cyan border)
    if hero_image:
        hero = hero_image.convert("RGB")
        hero = hero.resize((980, 860), Image.Resampling.LANCZOS)
        mask = Image.new("L", (980, 860), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, 980, 860], radius=40, fill=255)
        # Glowing border behind
        draw.rounded_rectangle([46, 441, 1034, 1319], radius=44, fill=(56, 189, 248))
        canvas.paste(hero, (50, 445), mask)

    # 6. Three Transformation Roadmap Cards (White cards with yellow vector arrows)
    card_w = 280
    card_h = 240
    gap = 40
    start_x = (W - (card_w * 3 + gap * 2)) // 2
    y_cards = 1360

    steps = meta.get("steps", [
        ("1. Ý tưởng", "và thiết kế sơ đồ", (37, 99, 235)),
        ("2. Lắp ráp", "và nạp code robot", (234, 88, 12)),
        ("3. Chạy thật", "thi đấu & thuyết trình", (16, 185, 129)),
    ])

    for i, (s_title, s_desc, color) in enumerate(steps[:3]):
        cx = start_x + i * (card_w + gap)
        # Card shadow
        draw.rounded_rectangle([cx + 4, y_cards + 6, cx + card_w + 4, y_cards + card_h + 6], radius=24, fill=(0, 20, 60))
        # Card body
        draw.rounded_rectangle([cx, y_cards, cx + card_w, y_cards + card_h], radius=24, fill=(255, 255, 255))

        # Step badge inside card
        draw.rounded_rectangle([cx + 25, y_cards + 20, cx + card_w - 25, y_cards + 75], radius=14, fill=color)
        bb_t = draw.textbbox((0, 0), s_title, font=f_step)
        wt = bb_t[2] - bb_t[0]
        draw.text((cx + (card_w - wt) // 2, y_cards + 32), s_title, fill=(255, 255, 255), font=f_step)

        # Step description
        bb_d = draw.textbbox((0, 0), s_desc, font=f_step_sub)
        wd = bb_d[2] - bb_d[0]
        draw.text((cx + (card_w - wd) // 2, y_cards + 105), s_desc, fill=(15, 23, 42), font=f_step_sub)

        # Checkmark circle indicator at bottom of card
        draw.ellipse([cx + card_w // 2 - 18, y_cards + 160, cx + card_w // 2 + 18, y_cards + 196], fill=color)
        # Vector checkmark
        vcx, vcy = cx + card_w // 2, y_cards + 178
        draw.line([(vcx - 6, vcy), (vcx - 2, vcy + 5), (vcx + 6, vcy - 4)], fill=(255, 255, 255), width=3)

        # Yellow Vector Arrow connecting to next card
        if i < 2:
            ax = cx + card_w + 6
            ay = y_cards + card_h // 2
            draw.polygon([
                (ax, ay - 12), (ax + 14, ay - 12), (ax + 14, ay - 20),
                (ax + 28, ay),
                (ax + 14, ay + 20), (ax + 14, ay + 12), (ax, ay + 12)
            ], fill=(255, 215, 0))

    # 7. Big Glowing Golden-Yellow CTA Button
    cta_y = 1660
    draw.rounded_rectangle([90, cta_y + 8, 990, cta_y + 138], radius=65, fill=(0, 20, 60))
    draw.rounded_rectangle([80, cta_y, 1000, cta_y + 130], radius=65, fill=(255, 204, 0), outline=(255, 255, 255), width=4)

    # Vector Target Icon 🎯
    tcx, tcy = 150, cta_y + 65
    draw.ellipse([tcx - 30, tcy - 30, tcx + 30, tcy + 30], fill=(220, 38, 38))
    draw.ellipse([tcx - 20, tcy - 20, tcx + 20, tcy + 20], fill=(255, 255, 255))
    draw.ellipse([tcx - 10, tcy - 10, tcx + 10, tcy + 10], fill=(220, 38, 38))

    cta_txt = meta.get("cta", "BẮT ĐẦU DỰ ÁN ĐẦU TIÊN")
    if has_offer or (feedback and ("ưu đãi" in feedback.lower() or "giảm" in feedback.lower() or "học bổng" in feedback.lower())):
        cta_txt = "INBOX NHẬN ƯU ĐÃI NGAY"
    cta_txt = strip_emoji(cta_txt)

    draw.text((215, cta_y + 38), cta_txt, fill=(0, 35, 102), font=f_cta)

    # Vector Chevron Arrow on right
    draw.polygon([
        (910, cta_y + 45), (935, cta_y + 65), (910, cta_y + 85),
        (922, cta_y + 85), (947, cta_y + 65), (922, cta_y + 45)
    ], fill=(0, 35, 102))

    # 8. Modern Footer Bar
    draw.rectangle([0, 1835, W, H], fill=(0, 20, 60))
    from mmm_custom.marketing_plan import NEUTRAL_FOOTER

    foot_txt = footer or NEUTRAL_FOOTER
    bbf = draw.textbbox((0, 0), foot_txt, font=f_foot)
    wf = bbf[2] - bbf[0]
    draw.text(((W - wf) // 2, 1860), foot_txt, fill=(203, 213, 225), font=f_foot)

    return canvas


def generate_and_save_banner(doc, user_feedback=None):
    """
    High-level banner generator called by FacebookPost.generate_banner().
    Generates the commercial poster and saves it to Frappe files.
    """
    course = getattr(doc, "course", "Robotics") or "Robotics"
    title = getattr(doc, "title", None)
    feedback = user_feedback or getattr(doc, "ai_feedback", None) or ""

    if user_feedback:
        doc.ai_feedback = user_feedback

    # 1. Generate or retrieve joyful commercial hero photo (with the reason when it is a stock photo)
    photo, note = hero_image(course, title=title, feedback=feedback)
    if note and hasattr(frappe, "log_error") and "429" not in note:
        frappe.log_error(title="Banner: Gemini image not generated", message=note)

    # 2. Composite the poster with the brand of the post's Facebook Page and contact facts from the CRM
    from mmm_custom.marketing_plan import footer_text, post_facts

    facts = post_facts(course, page=getattr(doc, "facebook_page", None))
    banner = compose_commercial_banner(photo, course, title=title, feedback=feedback,
                                       footer=footer_text(facts), has_offer=bool(facts.get("promo")),
                                       brand=facts.get("brand") or "")

    # 3. Save to BytesIO
    buf = io.BytesIO()
    banner.save(buf, format="JPEG", quality=95)
    buf.seek(0)

    if doc.is_new():
        doc.insert(ignore_permissions=True)

    meta = get_course_meta(course)
    file_name = f"banner_{meta['key']}_{doc.name}.jpg"
    doctype_name = getattr(doc, "doctype", "Facebook Post")

    file_doc = save_file(file_name, buf.getvalue(), doctype_name, doc.name, is_private=0)

    doc.image = file_doc.file_url
    doc.save()
    if hasattr(frappe.db, "commit"):
        frappe.db.commit()

    return {"status": "success", "image": doc.image, "note": note}
