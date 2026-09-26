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
    """Create a branded promotional image using Pillow (no external API)."""
    template = COURSE_TEMPLATES[course_key]
    width, height = 1200, 630  # Facebook recommended size

    # Create gradient background
    img = Image.new("RGB", (width, height), template["color"])
    draw = ImageDraw.Draw(img)

    # Draw gradient overlay
    for y in range(height):
        alpha = y / height
        r = int(template["color"][0] * (1 - alpha * 0.5))
        g = int(template["color"][1] * (1 - alpha * 0.5))
        b = int(template["color"][2] * (1 - alpha * 0.5))
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Draw decorative circles
    for _ in range(8):
        cx = random.randint(0, width)
        cy = random.randint(0, height)
        cr = random.randint(30, 120)
        circle_color = (*template["accent"], 60)
        for r_offset in range(cr, 0, -1):
            draw.ellipse(
                [cx - r_offset, cy - r_offset, cx + r_offset, cy + r_offset],
                fill=(*template["accent"],),
                outline=None,
            )

    # Try to load a nice font, fallback to default
    try:
        title_font = ImageFont.truetype("arial.ttf", 72)
        sub_font = ImageFont.truetype("arial.ttf", 32)
        brand_font = ImageFont.truetype("arial.ttf", 28)
    except (OSError, IOError):
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
            sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
            brand_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except (OSError, IOError):
            title_font = ImageFont.load_default()
            sub_font = ImageFont.load_default()
            brand_font = ImageFont.load_default()

    # Draw white content area
    margin = 60
    draw.rounded_rectangle(
        [margin, margin, width - margin, height - margin],
        radius=20,
        fill=(255, 255, 255, 230),
    )

    # Draw title lines
    y_pos = 140
    for line in template["image_text"]:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        text_width = bbox[2] - bbox[0]
        x_pos = (width - text_width) // 2
        draw.text((x_pos, y_pos), line, fill=template["color"], font=title_font)
        y_pos += 90

    # Draw subtitle
    bbox = draw.textbbox((0, 0), template["sub_text"], font=sub_font)
    text_width = bbox[2] - bbox[0]
    x_pos = (width - text_width) // 2
    draw.text((x_pos, y_pos + 30), template["sub_text"], fill=(100, 100, 100), font=sub_font)

    # Draw brand name
    brand_text = "EduFlow Academy"
    bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
    text_width = bbox[2] - bbox[0]
    x_pos = (width - text_width) // 2
    draw.text((x_pos, height - 110), brand_text, fill=template["color"], font=brand_font)

    # Draw emoji
    emoji_text = template["emoji"]
    draw.text((width // 2 - 20, 80), emoji_text, fill=template["color"], font=sub_font)

    img.save(output_path, "PNG", quality=95)
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
