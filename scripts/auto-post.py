#!/usr/bin/env python3
"""
EduFlow Auto-Post: Automatically post promotional content to Facebook Page.

Features:
- Generates Vietnamese promotional posts for EduFlow courses
- Creates branded images using Pillow (template-based, 100% FOSS)
- Posts to Facebook Page via Graph API
- Can be run manually or via cron/scheduler

Usage:
    python scripts/auto-post.py                    # Post random course (template caption)
    python scripts/auto-post.py --ai               # Post with AI-generated caption (9Router)
    python scripts/auto-post.py --course tieng_anh # Post specific course
    python scripts/auto-post.py --dry-run          # Preview without posting

Environment: reads from .env in project root
"""

import argparse
import os
import random
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding for emoji
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
except ImportError:
    print("Installing python-dotenv...")
    os.system(f"{sys.executable} -m pip install python-dotenv -q")
    from dotenv import load_dotenv

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system(f"{sys.executable} -m pip install requests -q")
    import requests

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Installing Pillow...")
    os.system(f"{sys.executable} -m pip install Pillow -q")
    from PIL import Image, ImageDraw, ImageFont


# ── Course content templates ──────────────────────────────────────

COURSE_TEMPLATES = {
    "tieng_anh": {
        "name": "Tiếng Anh",
        "emoji": "🇬🇧",
        "color": (41, 128, 185),      # Blue
        "accent": (52, 152, 219),
        "captions": [
            "🇬🇧 KHAI GIẢNG LỚP TIẾNG ANH GIAO TIẾP!\n\n"
            "✅ Giáo viên bản ngữ\n"
            "✅ Lớp học nhỏ 8-12 học viên\n"
            "✅ Phương pháp giao tiếp thực tế\n"
            "✅ Cam kết đầu ra\n\n"
            "📍 EduFlow Academy - Bình Thạnh | Quận 1 | Thủ Đức\n"
            "📞 Inbox ngay để được tư vấn MIỄN PHÍ!\n\n"
            "#EduFlow #TiengAnh #HocTiengAnh #English",

            "🌟 HỌC TIẾNG ANH - MỞ CÁNH CỬA TƯƠNG LAI!\n\n"
            "Bạn muốn tự tin giao tiếp tiếng Anh?\n"
            "EduFlow Academy giúp bạn đạt mục tiêu chỉ trong 3 tháng!\n\n"
            "🎯 Lộ trình cá nhân hóa\n"
            "🎯 Giáo trình cập nhật\n"
            "🎯 Luyện tập mỗi ngày\n\n"
            "💬 Inbox để nhận ưu đãi đặc biệt!\n\n"
            "#EduFlow #TiengAnh #IELTS #TOEIC",
        ],
        "image_text": ["HỌC TIẾNG ANH", "GIAO TIẾP TỰ TIN"],
        "sub_text": "Khai giảng liên tục • Cam kết đầu ra",
    },
    "boi_loi": {
        "name": "Bơi lội",
        "emoji": "🏊",
        "color": (39, 174, 96),        # Green
        "accent": (46, 204, 113),
        "captions": [
            "🏊 ĐĂNG KÝ HỌC BƠI - AN TOÀN CHO BÉ!\n\n"
            "✅ HLV chuyên nghiệp, chứng chỉ quốc tế\n"
            "✅ Hồ bơi sạch, tiêu chuẩn\n"
            "✅ Lớp 4-6 bé, kèm sát\n"
            "✅ Bé biết bơi sau 8-10 buổi\n\n"
            "📍 EduFlow Academy - Bình Thạnh | Quận 1 | Thủ Đức\n"
            "📞 Inbox ngay để đăng ký!\n\n"
            "#EduFlow #HocBoi #BoiLoi #Swimming",

            "🌊 MÙA HÈ NÀY - CHO BÉ HỌC BƠI!\n\n"
            "Bơi lội không chỉ là kỹ năng sinh tồn,\n"
            "mà còn giúp bé phát triển thể chất toàn diện!\n\n"
            "🎁 ƯU ĐÃI: Giảm 20% khi đăng ký nhóm 3 bé\n\n"
            "💬 Inbox để nhận lịch học!\n\n"
            "#EduFlow #HocBoi #KyNangSinhTon",
        ],
        "image_text": ["HỌC BƠI", "AN TOÀN • VUI KHỎE"],
        "sub_text": "HLV chuyên nghiệp • Cam kết biết bơi",
    },
    "toan_tu_duy": {
        "name": "Toán tư duy",
        "emoji": "🧮",
        "color": (142, 68, 173),       # Purple
        "accent": (155, 89, 182),
        "captions": [
            "🧮 TOÁN TƯ DUY - RÈN LUYỆN TRÍ NÃO SIÊU VIỆT!\n\n"
            "✅ Phát triển tư duy logic\n"
            "✅ Giải toán sáng tạo\n"
            "✅ Phương pháp học qua trò chơi\n"
            "✅ Phù hợp bé 5-12 tuổi\n\n"
            "📍 EduFlow Academy - Bình Thạnh | Quận 1 | Thủ Đức\n"
            "📞 Inbox để đăng ký lớp học thử MIỄN PHÍ!\n\n"
            "#EduFlow #ToanTuDuy #Math #TuDuyLogic",

            "🎯 TOÁN TƯ DUY - NỀN TẢNG CHO TƯƠNG LAI!\n\n"
            "Giúp con:\n"
            "🧠 Tư duy logic sắc bén\n"
            "📐 Giải quyết vấn đề sáng tạo\n"
            "🏆 Tự tin trong học tập\n\n"
            "💬 Inbox ngay - Nhận buổi học thử MIỄN PHÍ!\n\n"
            "#EduFlow #ToanTuDuy #GiaoDucSom",
        ],
        "image_text": ["TOÁN TƯ DUY", "PHÁT TRIỂN TRÍ NÃO"],
        "sub_text": "Bé 5-12 tuổi • Học qua trò chơi",
    },
}


def create_post_image(course_key: str, output_path: str) -> str:
    """Create a modern, agency-grade Facebook Ad flyer (1080x1080) with real hero photo."""
    template = COURSE_TEMPLATES[course_key]
    W, H = 1080, 1080
    canvas = Image.new("RGB", (W, H), (248, 250, 252))
    draw = ImageDraw.Draw(canvas)

    theme_color = template["color"]
    accent_color = template["accent"]

    # Fonts
    repo_root = Path(__file__).resolve().parent.parent
    font_bold_path = repo_root / "frappe-custom" / "mmm_custom" / "mmm_custom" / "public" / "fonts" / "bold.ttf"
    font_reg_path = repo_root / "frappe-custom" / "mmm_custom" / "mmm_custom" / "public" / "fonts" / "regular.ttf"

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
    f_foot = get_font(25, bold=False)
    f_foot_b = get_font(25, bold=True)
    f_promo = get_font(23, bold=True)

    # Top Bar
    draw.rectangle([0, 0, W, 120], fill=theme_color)
    draw.text((50, 42), "EDUFLOW ACADEMY", fill=(255, 255, 255), font=f_brand)
    draw.rounded_rectangle([770, 35, 1030, 85], radius=15, fill=(255, 255, 255))
    draw.text((800, 47), "TUYỂN SINH 2026", fill=theme_color, font=f_badge)

    # Title & Subtitle
    title_text = " ".join(template.get("image_text", [template["name"]]))
    draw.text((50, 155), title_text[:35], fill=(15, 23, 42), font=f_title)
    draw.text((50, 220), template.get("sub_text", ""), fill=theme_color, font=f_sub)

    # Hero Photo
    photo_path = repo_root / "frappe-custom" / "mmm_custom" / "mmm_custom" / "public" / "images" / "courses" / f"{course_key}.jpg"
    if photo_path.exists():
        photo = Image.open(str(photo_path)).convert("RGB")
        photo = photo.resize((500, 500), Image.Resampling.LANCZOS)

        mask = Image.new("L", (500, 500), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, 500, 500], radius=24, fill=255)

        draw.rounded_rectangle([536, 276, 1040, 780], radius=26, fill=(203, 213, 225))
        canvas.paste(photo, (540, 280), mask)

        # Promo Badge
        promo_text = "ƯU ĐÃI 30% HÔM NAY"
        bbox_p = draw.textbbox((0, 0), promo_text, font=f_promo)
        pw = bbox_p[2] - bbox_p[0]
        badge_left = max(550, 1020 - pw - 40)
        draw.rounded_rectangle([badge_left, 300, 1020, 360], radius=18, fill=(220, 38, 38))
        draw.text((badge_left + 20, 316), promo_text, fill=(255, 255, 255), font=f_promo)

    # Default Benefits
    benefits_map = {
        "tieng_anh": [
            ("Giáo Viên Bản Ngữ", "100% giáo viên phát âm chuẩn"),
            ("Lớp Nhỏ 8-12 Bạn", "Tương tác phản xạ liên tục"),
            ("Phương Pháp Thực Chiến", "Giao tiếp tự nhiên, không học vẹt"),
            ("Cam Kết Chuẩn Đầu Ra", "Đạt mục tiêu chỉ sau 3 tháng"),
        ],
        "boi_loi": [
            ("HLV Kèm Sát 1:1", "HLV tận tâm, chứng chỉ quốc tế"),
            ("Hồ Nước Ấm 4 Mùa", "Khử trùng an toàn, đạt chuẩn"),
            ("Cam Kết Biết Bơi", "Bé tự tin bơi sau 8-10 buổi"),
            ("Lịch Học Linh Hoạt", "Sắp xếp phù hợp lịch của bé"),
        ],
        "toan_tu_duy": [
            ("Rèn Tư Duy Độc Lập", "Bé chủ động giải quyết vấn đề"),
            ("Học Qua Trò Chơi", "Phương pháp trực quan, hào hứng"),
            ("Dành Cho Bé 4-12 Tuổi", "Lộ trình cá nhân hóa từng độ tuổi"),
            ("Tự Tin Học Toán", "Không còn sợ hãi môn Toán"),
        ],
    }

    y_ben = 280
    for b_title, b_sub in benefits_map.get(course_key, []):
        draw.rounded_rectangle([50, y_ben, 510, y_ben + 95], radius=16, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
        # Green checkmark circle
        draw.ellipse([68, y_ben + 28, 104, y_ben + 64], fill=(16, 185, 129))
        draw.line([(78, y_ben + 46), (84, y_ben + 54), (96, y_ben + 38)], fill=(255, 255, 255), width=3)
        draw.text((118, y_ben + 18), b_title, fill=(15, 23, 42), font=f_item_title)
        draw.text((118, y_ben + 54), b_sub, fill=(100, 116, 139), font=f_item_sub)
        y_ben += 115

    # Call to Action Button
    draw.rounded_rectangle([50, 835, 510, 925], radius=24, fill=accent_color)
    bbox_cta = draw.textbbox((0, 0), "INBOX ĐĂNG KÝ NGAY", font=f_cta)
    cta_w = bbox_cta[2] - bbox_cta[0]
    draw.text((50 + (460 - cta_w) // 2, 860), "INBOX ĐĂNG KÝ NGAY", fill=(255, 255, 255), font=f_cta)

    # Footer Bar
    draw.rectangle([0, 960, W, H], fill=(15, 23, 42))
    draw.text((50, 985), "Chi nhánh: Quận 1 • Bình Thạnh • Thủ Đức", fill=(255, 255, 255), font=f_foot)
    draw.text((50, 1025), "Hotline: 0901.888.666  |  Website: eduflow.vn", fill=(148, 163, 184), font=f_foot_b)

    canvas.save(output_path, "JPEG", quality=95)
    return output_path


def post_to_facebook(page_id: str, token: str, message: str, image_path: str | None = None) -> dict:
    """Post to Facebook Page. With image if provided, text-only otherwise."""
    if image_path and os.path.exists(image_path):
        # Post with photo
        url = f"https://graph.facebook.com/v21.0/{page_id}/photos"
        with open(image_path, "rb") as f:
            resp = requests.post(
                url,
                data={"caption": message, "access_token": token},
                files={"source": ("post.png", f, "image/png")},
                timeout=30,
            )
    else:
        # Text-only post
        url = f"https://graph.facebook.com/v21.0/{page_id}/feed"
        resp = requests.post(
            url,
            data={"message": message, "access_token": token},
            timeout=30,
        )

    resp.raise_for_status()
    return resp.json()


def generate_ai_caption(course_key: str) -> str | None:
    """Generate a creative caption using Gemini AI or 9Router. Returns None if unavailable."""
    template = COURSE_TEMPLATES[course_key]
    prompt = (
        f"Viết một bài đăng Facebook quảng cáo khóa học {template['name']} "
        f"cho trung tâm EduFlow Academy. Yêu cầu:\n"
        f"- Dưới 150 từ, tiếng Việt\n"
        f"- Có emoji phù hợp\n"
        f"- Có hashtag (#EduFlow, #EduFlowAcademy, và hashtag liên quan)\n"
        f"- Kêu gọi inbox trang để tư vấn\n"
        f"- Đề cập chi nhánh: Bình Thạnh, Quận 1, Thủ Đức\n"
        f"- Giọng văn thân thiện, chuyên nghiệp\n"
        f"- KHÔNG dùng markdown (**, ##, etc.)\n"
        f"Chỉ trả về nội dung bài viết, không thêm giải thích."
    )

    # 1. Try Gemini API directly
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={gemini_key}"
            resp = requests.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=20,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return content.replace("**", "").replace("##", "").replace("# ", "")
        except Exception as e:
            print(f"⚠️ Gemini API failed ({e}), trying 9Router...")

    # 2. Try 9Router fallback
    api_key = os.getenv("NINE_ROUTER_API_KEY")
    base_url = os.getenv("NINE_ROUTER_BASE_URL", "http://localhost:20128/v1")
    model = os.getenv("NINE_ROUTER_MODEL", "ag/gemini-3.7-flash-low")

    if not api_key:
        return None

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 400,
                "stream": False,
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        # Remove any markdown formatting
        content = content.replace("**", "").replace("##", "").replace("# ", "")
        return content
    except Exception as e:
        print(f"⚠️ AI caption failed ({e}), using template")
        return None


def main():
    parser = argparse.ArgumentParser(description="EduFlow Auto-Post to Facebook Page")
    parser.add_argument(
        "--course",
        choices=["tieng_anh", "boi_loi", "toan_tu_duy"],
        help="Specific course to post about (random if not specified)",
    )
    parser.add_argument("--ai", action="store_true", help="Use 9Router AI to generate caption")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument("--no-image", action="store_true", help="Post text only, no image")
    args = parser.parse_args()

    # Load environment
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    page_id = os.getenv("FACEBOOK_PAGE_ID")
    token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")

    if not page_id or not token:
        print("❌ Missing FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN in .env")
        sys.exit(1)

    # Select course
    course_key = args.course or random.choice(list(COURSE_TEMPLATES.keys()))
    template = COURSE_TEMPLATES[course_key]

    # Generate caption
    if args.ai:
        print("🤖 Generating AI caption via 9Router...")
        caption = generate_ai_caption(course_key)
        if caption:
            print("✨ AI caption generated!")
        else:
            caption = random.choice(template["captions"])
            print("📝 Fell back to template caption")
    else:
        caption = random.choice(template["captions"])

    print(f"\n📝 Course: {template['name']} {template['emoji']}")
    print(f"📄 Caption:\n{caption}\n")

    if args.dry_run:
        print("🔍 DRY RUN — not posting to Facebook")
        if not args.no_image:
            img_path = os.path.join(tempfile.gettempdir(), "eduflow_preview.png")
            create_post_image(course_key, img_path)
            print(f"🖼️ Preview image saved: {img_path}")
        return

    # Create image
    image_path = None
    if not args.no_image:
        image_path = os.path.join(tempfile.gettempdir(), f"eduflow_{course_key}_{datetime.now():%Y%m%d_%H%M%S}.png")
        create_post_image(course_key, image_path)
        print(f"🖼️ Image created: {image_path}")

    # Post to Facebook
    print("📤 Posting to Facebook Page...")
    result = post_to_facebook(page_id, token, caption, image_path)
    post_id = result.get("id") or result.get("post_id", "unknown")
    print(f"✅ Posted! ID: {post_id}")

    # Clean up temp image
    if image_path and os.path.exists(image_path):
        os.remove(image_path)

    return result


if __name__ == "__main__":
    main()
