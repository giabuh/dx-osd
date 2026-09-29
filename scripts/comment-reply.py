#!/usr/bin/env python3
"""
EduFlow Comment Auto-Reply & Conversational Messenger Agent.

Comprehensive Facebook Page interaction automation:
1. Public Comment Reply: Acknowledges post comments with polite, personalized replies & likes.
2. Messenger Private Reply: Sends tailored consultation directly to commenter's Messenger inbox.
3. Conversational Messenger Agent: Actively monitors Messenger conversations and replies to customer
   messages in real time with natural, non-stiff consultative responses (Photoshop, Python, MOS Excel,
   branches, schedules, incentives, and lead qualification into Frappe CRM).

Features:
- AI-powered personalized public & private replies via Gemini / 9Router (fallback to templates)
- Real-time continuous monitoring with --watch flag for BOTH post comments and Messenger chats
- Scans recent posts for unreplied comments & recent conversations for unreplied messages
- Tracks replied comments (.replied_comments.json) and messages (.replied_messenger.json)
- Automatic qualification & sync into Frappe CRM (CRM Lead, course_interest, mobile_no, branch)

Usage:
    python scripts/comment-reply.py              # Process unreplied comments & chats once
    python scripts/comment-reply.py --watch      # Run continuously in background (every 10s)
    python scripts/comment-reply.py --dry-run    # Preview without replying
    python scripts/comment-reply.py --no-private # Only reply publicly on comments
    python scripts/comment-reply.py --no-messenger # Only handle comments, skip Messenger chats
    python scripts/comment-reply.py --messenger-only # Only monitor & reply to Messenger chats

Environment: reads from .env in project root
"""

import argparse
from datetime import datetime, timezone
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

# Fix Windows console encoding for emoji
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
except ImportError:
    os.system(f"{sys.executable} -m pip install python-dotenv -q")
    from dotenv import load_dotenv

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests -q")
    import requests


# ── Fallback Public Reply Templates ────────────────────────────────
PUBLIC_REPLY_TEMPLATES = [
    "Dạ em chào {name}! Em đã nhắn tin chi tiết khóa học và ưu đãi vào Messenger cho mình rồi ạ. Bạn kiểm tra tin nhắn giúp em nhé! ✨",
    "Cảm ơn {name} đã quan tâm! 💬 Em vừa gửi lộ trình học và học phí qua tin nhắn riêng cho mình rồi ạ, bạn check inbox nhé! 🎓",
    "Dạ em chào bạn {name}! 🌟 Em đã gửi ưu đãi đặc biệt tuần này vào hộp thư Messenger cho mình, bạn kiểm tra tin nhắn giúp em nhé! 📚",
    "Chào {name}! 👋 Em đã gửi thông tin lớp học và lịch khai giảng vào tin nhắn Messenger cho mình rồi ạ! ✨",
    "Cảm ơn {name} nhé! 😊 Em vừa gửi tin nhắn riêng qua Messenger cho mình rồi, bạn kiểm tra inbox giúp em nha! 🎁",
]

# ── Fallback Private Messenger Reply Templates ────────────────────
PRIVATE_REPLY_TEMPLATES = [
    "Dạ em chào {name}! Em thấy mình vừa quan tâm bình luận trên Fanpage. Khóa học bên em đang có ưu đãi học bổng 30% và tặng buổi học thử miễn phí trong tuần này. Mình để lại SĐT hoặc nhắn cơ sở gần mình nhất để em gửi lịch học và học phí chi tiết cho mình nhé! 🎓",
    "Chào {name}! Cảm ơn bạn đã quan tâm đến EduFlow Academy. Mình đang muốn tìm hiểu lộ trình học cho bản thân hay cho người thân vậy ạ? Nhắn em xin SĐT để chuyên viên hỗ trợ tư vấn và xếp lịch học thuận tiện nhất cho mình nhé! 🌟",
    "Dạ em chào {name}! Em gửi thông tin khóa học và ưu đãi học phí tuần này qua tin nhắn cho mình ạ. Mình tiện học vào buổi tối hay cuối tuần để em sắp xếp lớp phù hợp cho mình nhé! ✨",
]

# Files to track replied comments & messages (avoid duplicates)
REPLIED_FILE = Path(__file__).resolve().parent.parent / ".replied_comments.json"
REPLIED_MESSENGER_FILE = Path(__file__).resolve().parent.parent / ".replied_messenger.json"


def load_replied_comments() -> set:
    """Load set of already-replied comment IDs."""
    if REPLIED_FILE.exists():
        try:
            data = json.loads(REPLIED_FILE.read_text(encoding="utf-8"))
            return set(data)
        except (json.JSONDecodeError, KeyError):
            return set()
    return set()


def save_replied_comments(replied: set):
    """Save replied comment IDs. Keep last 1000 to prevent unbounded growth."""
    data = list(replied)[-1000:]
    REPLIED_FILE.write_text(json.dumps(data), encoding="utf-8")


def load_replied_messenger() -> set:
    """Load set of already-replied Messenger message IDs."""
    if REPLIED_MESSENGER_FILE.exists():
        try:
            data = json.loads(REPLIED_MESSENGER_FILE.read_text(encoding="utf-8"))
            return set(data)
        except (json.JSONDecodeError, KeyError):
            return set()
    return set()


def save_replied_messenger(replied: set):
    """Save replied Messenger message IDs. Keep last 1000."""
    data = list(replied)[-1000:]
    REPLIED_MESSENGER_FILE.write_text(json.dumps(data), encoding="utf-8")


def get_recent_posts(page_id: str, token: str, limit: int = 5) -> list:
    """Get recent posts from the Facebook Page."""
    url = f"https://graph.facebook.com/v21.0/{page_id}/posts"
    resp = requests.get(
        url,
        params={"access_token": token, "limit": limit, "fields": "id,message,created_time"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def get_comments(post_id: str, token: str) -> list:
    """Get comments on a specific post."""
    url = f"https://graph.facebook.com/v21.0/{post_id}/comments"
    resp = requests.get(
        url,
        params={
            "access_token": token,
            "fields": "id,from,message,created_time",
            "limit": 50,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def reply_to_comment(comment_id: str, token: str, message: str) -> dict:
    """Reply publicly to a Facebook comment."""
    url = f"https://graph.facebook.com/v21.0/{comment_id}/comments"
    resp = requests.post(
        url,
        data={"message": message, "access_token": token},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def send_private_reply(page_id: str, token: str, comment_id: str, message: str) -> dict | None:
    """Send a private message to a commenter via the Facebook Messenger Platform.
    
    Uses endpoint POST /{page-id}/messages with recipient.comment_id.
    Subject to Facebook's 7-day window and 1-private-reply-per-comment policy.
    """
    url = f"https://graph.facebook.com/v21.0/{page_id}/messages"
    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {"text": message},
    }
    try:
        resp = requests.post(
            url,
            params={"access_token": token},
            json=payload,
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
        data = resp.json()
        error = data.get("error", {})
        code = error.get("code")
        # Code 10900: Activity already replied to
        if code == 10900:
            return {"status": "already_replied", "message": "Activity already replied to"}
        print(f"   ⚠️ Private reply API notice: {error.get('message')} (code: {code})")
        return None
    except requests.RequestException as e:
        print(f"   ⚠️ Private reply network error: {e}")
        return None


def like_comment(comment_id: str, token: str):
    """Like a comment to acknowledge it."""
    url = f"https://graph.facebook.com/v21.0/{comment_id}/likes"
    try:
        requests.post(url, data={"access_token": token}, timeout=10)
    except requests.RequestException:
        pass


def generate_ai_comment_reply(commenter_name: str, comment_text: str, post_context: str = "") -> str | None:
    """Generate a polite, personalized public comment reply using Gemini or 9Router."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    prompt = (
        f"Bạn là trợ lý tư vấn thân thiện của trung tâm giáo dục EduFlow Academy.\n"
        f"Học viên tên '{commenter_name}' vừa bình luận trên bài viết: \"{comment_text}\".\n"
        f"Hãy viết 1 câu trả lời công khai ngắn gọn (dưới 30 từ), rất lịch sự, lễ phép (dạ, em chào...),\n"
        f"có emoji phù hợp, và thông báo rằng em đã gửi tin nhắn chi tiết vào hộp thư Messenger cho bạn ấy rồi, mời bạn check tin nhắn.\n"
        f"Quy tắc quan trọng: KHÔNG dùng markdown (không **, ##), chỉ trả về đúng 1 câu phản hồi."
    )

    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={gemini_key}"
            resp = requests.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = text.replace("**", "").replace("##", "")
                return text
        except Exception:
            pass

    nine_router_key = os.getenv("NINE_ROUTER_API_KEY")
    nine_router_base = os.getenv("NINE_ROUTER_BASE_URL", "http://localhost:20128/v1")
    nine_router_model = os.getenv("NINE_ROUTER_MODEL", "ag/gemini-3.7-flash-low")

    if nine_router_key:
        try:
            resp = requests.post(
                f"{nine_router_base}/chat/completions",
                json={
                    "model": nine_router_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                },
                headers={"Authorization": f"Bearer {nine_router_key}"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                text = text.replace("**", "").replace("##", "")
                return text
        except Exception:
            pass

    return None


def generate_ai_private_reply(commenter_name: str, comment_text: str, post_context: str = "") -> str | None:
    """Generate a consultative private message for Facebook Messenger using Gemini or 9Router."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    context_str = f"Bài viết khách quan tâm: '{post_context}'. " if post_context else ""
    prompt = (
        f"Bạn là chuyên viên tư vấn tuyển sinh tận tình của trung tâm đào tạo EduFlow Academy. {context_str}\n"
        f"Học viên tên '{commenter_name}' vừa bình luận: \"{comment_text}\".\n"
        f"Hãy viết một tin nhắn riêng tư để gửi thẳng vào Messenger của học viên.\n"
        f"Yêu cầu:\n"
        f"1. Lời chào ấm áp, xưng em - gọi {commenter_name} hoặc anh/chị.\n"
        f"2. Nêu bật ưu đãi khóa học (học bổng 30% hoặc học thử 1-1 miễn phí trong tuần).\n"
        f"3. Khéo léo mời khách để lại Số điện thoại hoặc chọn cơ sở gần nhất để em tư vấn lộ trình học chi tiết.\n"
        f"4. Ngắn gọn (3-4 câu, dưới 60 từ), lịch sự, có emoji trực quan.\n"
        f"Quy tắc quan trọng: KHÔNG dùng markdown (không **, ##), chỉ trả về đúng câu tin nhắn."
    )

    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={gemini_key}"
            resp = requests.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = text.replace("**", "").replace("##", "")
                return text
        except Exception:
            pass

    nine_router_key = os.getenv("NINE_ROUTER_API_KEY")
    nine_router_base = os.getenv("NINE_ROUTER_BASE_URL", "http://localhost:20128/v1")
    nine_router_model = os.getenv("NINE_ROUTER_MODEL", "ag/gemini-3.7-flash-low")

    if nine_router_key:
        try:
            resp = requests.post(
                f"{nine_router_base}/chat/completions",
                json={
                    "model": nine_router_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                },
                headers={"Authorization": f"Bearer {nine_router_key}"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                text = text.replace("**", "").replace("##", "")
                return text
        except Exception:
            pass

    return None


# ── Course & Branch Knowledge Matchers ─────────────────────────────
def detect_course_from_text(text: str) -> str | None:
    """Detect coarse course interest from conversation text."""
    lower = text.lower()
    if any(k in lower for k in ["photoshop", "pts", "đồ họa", "chỉnh ảnh", "thiết kế"]):
        return "Photoshop thực chiến"
    if any(k in lower for k in ["mos", "excel", "tin học", "văn phòng", "word", "powerpoint"]):
        return "Tin học văn phòng & Luyện thi MOS"
    if any(k in lower for k in ["python", "lập trình", "code"]):
        return "Lập trình Python thực chiến"
    if any(k in lower for k in ["robot", "stem"]):
        return "Robotics & STEM"
    return None


def detect_branch_from_text(text: str) -> str | None:
    """Detect branch preference from message text."""
    lower = text.lower()
    if any(k in lower for k in ["bình thạnh", "cs1", "điện biên phủ"]):
        return "CS1 Bình Thạnh"
    if any(k in lower for k in ["quận 1", "q1", "q.1", "nguyễn thị minh khai", "cs2"]):
        return "CS2 Quận 1"
    if any(k in lower for k in ["thủ đức", "tp thủ đức", "tp. thủ đức", "võ văn ngân", "cs3"]):
        return "CS3 Thủ Đức"
    return None


# ── Conversational Messenger Reply Generator ───────────────────────
def generate_ai_conversation_reply(customer_name: str, history: list[str], latest_msg: str) -> str:
    """Generate a highly contextual, natural, consultative Messenger response using 9Router/Gemini or smart heuristics."""
    phone_match = re.search(r"(0\d{9}|\+84\d{9})", latest_msg)
    lower = latest_msg.lower()

    # 1. Deterministic phone number detection (actual digits provided)
    if phone_match:
        phone = phone_match.group(1)
        return (
            f"Dạ em cảm ơn anh/chị {customer_name} nhiều ạ! Em đã lưu Số Điện Thoại {phone} của mình rồi ạ. "
            f"Chuyên viên tuyển sinh của EduFlow sẽ sớm liên hệ qua SĐT để hỗ trợ xếp lớp và gửi vé mời học thử miễn phí cho mình nhé! "
            f"Chúc anh/chị một ngày thật vui vẻ ạ! ✨"
        )

    # 2. User clicked "gửi số điện thoại" or mentioned phone without digits
    if any(k in lower for k in ["gửi số điện thoại", "sđt", "sdt", "số điện thoại", "cho sdt", "gửi sdt"]):
        return (
            f"Dạ anh/chị {customer_name} nhắn giúp em các chữ số điện thoại (ví dụ: 090xxxxxxx) trực tiếp vào ô chat này nhé ạ! "
            f"Để em lưu hồ sơ và chuyển chuyên viên hỗ trợ xếp lớp cho mình ngay ạ. 📞"
        )

    # 3. Thank you / Goodbye / Concluding message
    if any(k in lower for k in ["cảm ơn", "cam on", "thank", "tks", "bye", "tạm biệt", "ok em", "chúc em", "tuyệt vời"]):
        return (
            f"Dạ không có chi ạ! Chúc anh/chị {customer_name} một ngày thật nhiều niềm vui và học tập hiệu quả nhé! "
            f"Nếu cần hỗ trợ thêm thông tin gì, anh/chị cứ nhắn lại cho em bất cứ lúc nào nha! 🌟"
        )

    history_str = "\n".join(history[-6:])
    prompt = (
        f"Bạn là Chuyên viên Tư vấn Tuyển sinh Cao cấp của Học viện EduFlow Academy (Việt Nam).\n"
        f"Nhiệm vụ: Phản hồi tin nhắn Messenger của học viên '{customer_name}' một cách tự nhiên, lễ phép, thông minh, chuyên nghiệp và KHÔNG BỊ SƯỢNG.\n\n"
        f"Lịch sử trò chuyện gần nhất:\n{history_str}\n\n"
        f"Tin nhắn mới nhất của {customer_name}: \"{latest_msg}\"\n\n"
        f"Kiến thức đào tạo EduFlow:\n"
        f"1. Photoshop Thực chiến: 12 buổi (6 tuần), thực hành 100% trên máy tính. Học từ con số 0 đến tự làm banner, poster, chỉnh ảnh chuyên nghiệp. Học bổng hỗ trợ 35% học phí + tặng 50GB tài nguyên thiết kế.\n"
        f"2. Tin học văn phòng & MOS: Excel/Word/PowerPoint từ căn bản đến nâng cao, cam kết chuẩn đầu ra MOS quốc tế.\n"
        f"3. Lập trình Python & Web: Dành cho người mới bắt đầu từ số 0 đến tự xây dựng phần mềm và phân tích dữ liệu.\n"
        f"4. Cơ sở đào tạo:\n"
        f"   - CS1: Điện Biên Phủ, Q. Bình Thạnh (gần ngã tư Hàng Xanh)\n"
        f"   - CS2: Nguyễn Thị Minh Khai, Q.1\n"
        f"   - CS3: Võ Văn Ngân, TP. Thủ Đức\n"
        f"5. Lịch học các cơ sở:\n"
        f"   - Lớp tối 2-4-6 (18h30 - 20h30)\n"
        f"   - Lớp cuối tuần (Sáng Thứ 7 & Chủ Nhật: 9h00 - 11h30)\n"
        f"6. Học phí: Ưu đãi 35% chỉ còn ~1.950.000đ - 2.500.000đ tùy khóa.\n\n"
        f"QUY TẮC PHẢN HỒI (RẤT QUAN TRỌNG ĐỂ KHÔNG BỊ SƯỢNG):\n"
        f"1. Nếu khách vừa chọn cơ sở (vd: CS1 Bình Thạnh): Hãy nhiệt tình xác nhận cơ sở đã chọn, sau đó giới thiệu 2 khung giờ học (Tối 2-4-6 hoặc Sáng T7-CN) và hỏi khách tiện học giờ nào hơn.\n"
        f"2. Nếu khách vừa chọn ca học/giờ học (vd: Tối 2-4-6 hay Cuối tuần): Xác nhận ca học, và xin phép xin Số Điện Thoại (SĐT) trực tiếp vào ô chat để chuyên viên hỗ trợ giữ chỗ ưu đãi học bổng 35% và gửi vé học thử miễn phí.\n"
        f"3. Tuyệt đối KHÔNG gửi menu cứng nhắc, KHÔNG lặp lại giới thiệu chung nếu khách đã chọn bước tiếp theo.\n"
        f"4. Giọng văn: Ấm áp, lịch sự, xưng 'em', gọi khách là 'anh/chị' hoặc 'anh/chị {customer_name}'. Ngắn gọn dưới 60 từ. Không dùng markdown (** hay ##)."
    )

    # 1. Try 9Router (local fast proxy)
    nine_router_key = os.getenv("NINE_ROUTER_API_KEY")
    nine_router_base = os.getenv("NINE_ROUTER_BASE_URL", "http://localhost:20128/v1")
    nine_router_model = os.getenv("NINE_ROUTER_MODEL", "ag/gemini-3.7-flash-low")
    if nine_router_key:
        try:
            resp = requests.post(
                f"{nine_router_base}/chat/completions",
                json={
                    "model": nine_router_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "stream": False,
                },
                headers={"Authorization": f"Bearer {nine_router_key}"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                text = text.replace("**", "").replace("##", "")
                if text:
                    return text
        except Exception:
            pass

    # 2. Try direct Gemini API
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={gemini_key}"
            resp = requests.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=6,
            )
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    text = candidates[0]["content"]["parts"][0]["text"].strip()
                    text = text.replace("**", "").replace("##", "")
                    if text:
                        return text
        except Exception:
            pass

    # ── Contextual Heuristic Engine (100% natural, non-stiff fallback) ──
    # 2. Branch chosen (e.g. CS1 Bình Thạnh, CS2 Quận 1, CS3 Thủ Đức)
    branch_val = detect_branch_from_text(latest_msg)
    if branch_val:
        return (
            f"Dạ tuyệt vời ạ, cơ sở {branch_val} phòng máy thực hành cấu hình cao rất mới và thuận tiện đi lại luôn anh/chị {customer_name} ơi! ✨\n\n"
            f"Hiện tại cơ sở đang có 2 ca học cho khóa mới:\n"
            f"• Lớp tối 2-4-6: 18h30 - 20h30\n"
            f"• Lớp cuối tuần: Sáng Thứ 7 & Chủ Nhật (9h00 - 11h30)\n\n"
            f"Mình thấy khung giờ nào thuận tiện hơn để em hỗ trợ giữ chỗ ưu đãi học bổng 35% cho mình nhé? ⏰"
        )

    # 3. Schedule chosen (e.g. Tối 2-4-6, Cuối tuần)
    if any(k in lower for k in ["tối 2-4-6", "2-4-6", "tối 3-5-7", "cuối tuần", "thứ 7", "chủ nhật", "t7", "cn"]):
        return (
            f"Dạ em đã ghi nhận lịch học dự kiến của anh/chị {customer_name} rồi ạ! 🌟\n\n"
            f"Để hoàn tất giữ suất học bổng ưu đãi 35% học phí và nhận vé tham gia buổi học thử 1-1 miễn phí, anh/chị nhắn em xin Số Điện Thoại (SĐT) trực tiếp vào ô chat để chuyên viên hỗ trợ làm hồ sơ cho mình nhé! 📱"
        )

    # 4. Tuition / Price inquiry
    if any(k in lower for k in ["học phí", "giá", "bao nhiêu", "chi phí", "tiền"]):
        return (
            f"Dạ học phí các khóa tại EduFlow dao động từ 2.500.000đ - 3.800.000đ tùy nội dung đào tạo ạ.\n\n"
            f"🎁 Đặc biệt trong tuần này, EduFlow đang có Học bổng ưu đãi 35% học phí và tặng kèm buổi học thử 1-1 miễn phí.\n\n"
            f"Anh/chị {customer_name} đang quan tâm lớp học vào buổi tối hay cuối tuần để em báo mức ưu đãi chi tiết và giữ chỗ cho mình nhé! ✨"
        )

    # 5. Branch / Location general inquiry
    if any(k in lower for k in ["ở đâu", "địa chỉ", "cơ sở", "chi nhánh"]):
        return (
            f"Dạ EduFlow có 3 cơ sở đào tạo với phòng máy thực hành cấu hình cao tại TP.HCM ạ:\n"
            f"📍 CS1: Điện Biên Phủ, P.25, Q. Bình Thạnh\n"
            f"📍 CS2: Nguyễn Thị Minh Khai, P. Bến Nghé, Q.1\n"
            f"📍 CS3: Võ Văn Ngân, P. Linh Chiểu, TP. Thủ Đức\n\n"
            f"Các cơ sở đều có lớp tối (18h30 - 20h30) và cuối tuần. Mình tiện học ở cơ sở nào để em hỗ trợ giữ lịch học thử cho mình nhé! 🏢"
        )

    # 6. Schedule general inquiry
    if any(k in lower for k in ["buổi tối", "tối", "cuối tuần", "lịch học", "thời gian", "mấy giờ"]):
        return (
            f"Dạ EduFlow có lịch học linh hoạt rất thuận tiện cho người đi làm và sinh viên ạ:\n"
            f"• Lớp tối: 18h30 - 20h30 (Thứ 2-4-6 hoặc Thứ 3-5-7).\n"
            f"• Lớp cuối tuần: Sáng Thứ 7 & Chủ Nhật.\n\n"
            f"Khung giờ nào thuận tiện nhất cho anh/chị {customer_name} ạ? Nhắn em xin SĐT để chuyên viên xếp lớp phù hợp nhất cho mình nhé! ⏰"
        )

    full_context = " ".join(history) + " " + latest_msg
    course_context = detect_course_from_text(full_context)

    # 7. User said "ok", "dạ", "vâng", "tư vấn", or acknowledging previous course mention
    if course_context == "Photoshop thực chiến" or any(k in lower for k in ["photoshop", "pts", "đồ họa", "chỉnh ảnh"]):
        return (
            f"Dạ em gửi anh/chị {customer_name} thông tin khóa học Photoshop Thực chiến tại EduFlow ạ:\n\n"
            f"📚 Điểm nổi bật khóa học:\n"
            f"• Đi từ cơ bản đến nâng cao: Làm chủ công cụ, cắt ghép, chỉnh màu ảnh chân dung & sản phẩm.\n"
            f"• Thực hành thiết kế ấn phẩm thực tế: Banner, poster, cover Facebook truyền thông bán hàng.\n"
            f"• Thời lượng: 12 buổi (6 tuần) - thực hành 100% trên máy tính.\n"
            f"• Lịch học linh hoạt: Lớp tối 2-4-6 hoặc lớp cuối tuần (T7 - CN).\n\n"
            f"🎁 Ưu đãi tuần này: Giảm 35% học phí + tặng kèm kho 50GB Plugin & Font chữ thiết kế bản quyền.\n\n"
            f"Dạ mình tiện học tại cơ sở nào (Bình Thạnh, Quận 1 hay Thủ Đức) và muốn học tối hay cuối tuần để em hỗ trợ xếp lịch cho mình nhé! ✨"
        )

    if course_context == "Tin học văn phòng & Luyện thi MOS":
        return (
            f"Dạ em gửi anh/chị {customer_name} thông tin khóa Tin học văn phòng & Luyện thi MOS tại EduFlow ạ:\n\n"
            f"📚 Điểm nổi bật:\n"
            f"• Thành thạo Excel/Word/PowerPoint từ căn bản đến nâng cao.\n"
            f"• Làm chủ hàm nâng cao (VLOOKUP, INDEX/MATCH), Pivot Table & tự động hóa báo cáo doanh nghiệp.\n"
            f"• Cam kết chuẩn đầu ra đỗ chứng chỉ MOS quốc tế.\n"
            f"• Lịch học: Lớp tối 2-4-6 hoặc cuối tuần.\n\n"
            f"🎁 Ưu đãi: Giảm 35% học phí trong tuần này. Mình tiện học ở cơ sở Bình Thạnh, Q.1 hay Thủ Đức để em gửi lịch học thử cho mình nhé! 🌟"
        )

    if course_context == "Lập trình Python thực chiến":
        return (
            f"Dạ em gửi anh/chị {customer_name} lộ trình Lập trình Python Thực chiến tại EduFlow ạ:\n\n"
            f"📚 Điểm nổi bật:\n"
            f"• Dành cho người mới bắt đầu từ con số 0, không cần có nền tảng trước.\n"
            f"• Xây dựng tư duy logic, lập trình ứng dụng, xử lý dữ liệu và tự động hóa công việc.\n"
            f"• Thời lượng 8-10 tuần, giảng viên cầm tay chỉ việc 1-1.\n\n"
            f"🎁 Đang có học bổng hỗ trợ 35% học phí tuần này. Anh/chị {customer_name} đang tìm hiểu học để phục vụ công việc hay mục tiêu gì để em tư vấn kỹ hơn nhé! 💻"
        )

    # 8. General welcoming response
    return (
        f"Dạ em chào anh/chị {customer_name}! EduFlow Academy có các chương trình đào tạo thực chiến nổi bật:\n"
        f"1. Thiết kế đồ họa / Photoshop (cắt ghép, chỉnh màu, thiết kế banner/poster quảng cáo)\n"
        f"2. Tin học văn phòng & Luyện thi MOS (Word, Excel, PowerPoint chuyên nghiệp)\n"
        f"3. Lập trình Python & Tự động hóa từ cơ bản\n\n"
        f"Anh/chị đang quan tâm đến bộ môn nào để em gửi thông tin chi tiết và ưu đãi học bổng 35% cho mình nhé! 🎓"
    )


def get_recent_conversations(page_id: str, token: str, limit: int = 10) -> list:
    """Fetch recent Messenger conversations with messages and participants."""
    url = f"https://graph.facebook.com/v21.0/{page_id}/conversations"
    resp = requests.get(
        url,
        params={
            "access_token": token,
            "fields": "id,updated_time,unread_count,participants,messages{id,created_time,from,message}",
            "limit": limit,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def get_smart_quick_replies(
    course_context: str | None = None,
    message_text: str = "",
    history: list[str] | None = None,
    has_phone: bool = False,
) -> list[dict]:
    """Return contextual Quick Reply buttons for Facebook Messenger."""
    lower = (message_text or "").lower()

    # 1. Concluded / phone provided / thank you -> NO buttons (completely clean chat)
    if has_phone or re.search(r"(0\d{9}|\+84\d{9})", message_text):
        return []

    if any(k in lower for k in ["cảm ơn", "cam on", "thank", "tks", "bye", "tạm biệt", "ok em", "chúc em", "tuyệt vời"]):
        return []

    # 2. Asking for phone number (waiting for digits from customer) -> NO buttons (leave text bar clean)
    if any(k in lower for k in ["gửi số điện thoại", "sđt", "sdt", "số điện thoại", "cho sdt", "gửi sdt"]):
        return []

    # 3. Schedule chosen -> bot asks for phone number -> NO buttons (leave text bar clean)
    if any(k in lower for k in ["tối", "cuối tuần", "2-4-6", "3-5-7", "t7", "cn", "sáng"]):
        return []

    # 4. Customer just chose or mentioned a branch -> suggest schedule shifts
    if any(k in lower for k in ["bình thạnh", "quận 1", "q1", "thủ đức", "cs1", "cs2", "cs3"]):
        return [
            {"content_type": "text", "title": "🌙 Lớp tối 2-4-6", "payload": "SHIFT_EVENING"},
            {"content_type": "text", "title": "☀️ Lớp sáng T7 - CN", "payload": "SHIFT_WEEKEND"},
            {"content_type": "text", "title": "💰 Học phí ưu đãi", "payload": "TUITION_DISCOUNT"},
            {"content_type": "text", "title": "📞 Nhận tư vấn 1-1", "payload": "CONSULT_1_1"},
        ]

    # 5. In Photoshop context or learning from scratch -> suggest branches
    if course_context == "Photoshop thực chiến" or any(k in lower for k in ["photoshop", "pts", "đồ họa", "chỉnh ảnh", "từ số 0", "cơ bản", "mới bắt đầu", "đi làm"]):
        return [
            {"content_type": "text", "title": "📍 CS1 Bình Thạnh", "payload": "CS1_BINH_THANH"},
            {"content_type": "text", "title": "📍 CS2 Quận 1", "payload": "CS2_QUAN_1"},
            {"content_type": "text", "title": "📍 CS3 Thủ Đức", "payload": "CS3_THU_DUC"},
            {"content_type": "text", "title": "💰 Học phí ưu đãi", "payload": "TUITION_DISCOUNT"},
        ]

    # 6. If course context is already established, don't show generic course menu
    if course_context:
        return [
            {"content_type": "text", "title": "📍 CS1 Bình Thạnh", "payload": "CS1_BINH_THANH"},
            {"content_type": "text", "title": "📍 CS2 Quận 1", "payload": "CS2_QUAN_1"},
            {"content_type": "text", "title": "📍 CS3 Thủ Đức", "payload": "CS3_THU_DUC"},
            {"content_type": "text", "title": "💰 Học phí ưu đãi", "payload": "TUITION_DISCOUNT"},
        ]

    # 7. Default broad course selection only at very start
    return [
        {"content_type": "text", "title": "🎨 Khóa Photoshop", "payload": "COURSE_PHOTOSHOP"},
        {"content_type": "text", "title": "📊 Tin học MOS", "payload": "COURSE_MOS"},
        {"content_type": "text", "title": "💻 Lập trình Python", "payload": "COURSE_PYTHON"},
        {"content_type": "text", "title": "📍 Chọn cơ sở học", "payload": "CHOOSE_BRANCH"},
    ]


def send_messenger_message(
    page_id: str,
    token: str,
    recipient_id: str,
    message: str,
    quick_replies: list[dict] | None = None,
    image_path: str | None = None,
) -> dict | None:
    """Send a Facebook Messenger message directly via Graph API with optional quick replies and image attachment."""
    url = f"https://graph.facebook.com/v21.0/{page_id}/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message},
        "messaging_type": "RESPONSE",
    }
    if quick_replies:
        payload["message"]["quick_replies"] = quick_replies

    sent_res = None
    try:
        resp = requests.post(
            url,
            params={"access_token": token},
            json=payload,
            timeout=15,
        )
        if resp.status_code == 200:
            sent_res = resp.json()
        else:
            print(f"   ⚠️ Messenger Send API notice: {resp.status_code} {resp.text}")
    except requests.RequestException as e:
        print(f"   ⚠️ Messenger Send network error: {e}")

    # Optional image attachment upload
    if image_path and os.path.exists(image_path):
        try:
            with open(image_path, "rb") as f:
                files = {"filedata": (os.path.basename(image_path), f, "image/jpeg")}
                data = {
                    "recipient": json.dumps({"id": recipient_id}),
                    "message": json.dumps({"attachment": {"type": "image", "payload": {}}}),
                }
                img_resp = requests.post(
                    url,
                    params={"access_token": token},
                    data=data,
                    files=files,
                    timeout=20,
                )
                if img_resp.status_code == 200:
                    print(f"   🖼️ Image attachment sent ({os.path.basename(image_path)})")
        except Exception as img_err:
            print(f"   ⚠️ Error sending image attachment: {img_err}")

    return sent_res


def sync_to_frappe_crm(customer_name: str, phone: str = None, course: str = None, branch: str = None):
    """Sync qualified lead info to Frappe CRM."""
    try:
        # Check if lead exists
        cmd = [
            "docker", "exec", "crm-frappe-1",
            "bench", "--site", "crm.localhost", "execute",
            "frappe.db.get_value",
            "--args", json.dumps(["CRM Lead", {"lead_name": customer_name}, "name"]),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        lead_name = res.stdout.strip().replace('"', '')

        if lead_name and lead_name != "None":
            update_fields = {"converted": 0}
            if course:
                update_fields["course_interest"] = course
            if branch:
                update_fields["branch"] = branch
            if phone:
                update_fields["mobile_no"] = phone
                update_fields["status"] = "Qualified"

            cmd_update = [
                "docker", "exec", "crm-frappe-1",
                "bench", "--site", "crm.localhost", "execute",
                "frappe.client.set_value",
                "--kwargs", json.dumps({"doctype": "CRM Lead", "name": lead_name, "fieldname": update_fields}),
            ]
            subprocess.run(cmd_update, capture_output=True, text=True, timeout=8)
        else:
            # Create new CRM Lead if not yet created
            doc = {
                "doctype": "CRM Lead",
                "lead_name": customer_name,
                "first_name": customer_name,
                "status": "Qualified" if phone else "New",
                "source": "Messenger Bot",
                "converted": 0,
            }
            if phone:
                doc["mobile_no"] = phone
            if course:
                doc["course_interest"] = course
            if branch:
                doc["branch"] = branch
            cmd_insert = [
                "docker", "exec", "crm-frappe-1",
                "bench", "--site", "crm.localhost", "execute",
                "frappe.client.insert",
                "--kwargs", json.dumps({"doc": doc}),
            ]
            subprocess.run(cmd_insert, capture_output=True, text=True, timeout=8)
    except Exception:
        pass


def is_facebook_system_message(text: str) -> bool:
    """Check if message is an automated Facebook system event/label rather than a real conversational reply."""
    if not text:
        return True
    lower = text.lower().strip()
    system_prefixes = [
        "đã thêm nhãn tự động",
        "đã đặt giai đoạn",
        "automated label added",
        "đã gỡ nhãn",
        "đã thay đổi nhãn",
        "bạn đang phản hồi bình luận của người dùng",
    ]
    return any(p in lower for p in system_prefixes)


def process_messenger_conversations(
    page_id: str,
    token: str,
    limit: int = 10,
    dry_run: bool = False,
    verbose: bool = True,
) -> int:
    """Scan Messenger conversations, detect incoming customer messages, and reply intelligently."""
    replied = load_replied_messenger()
    new_replies = 0

    try:
        conversations = get_recent_conversations(page_id, token, limit=limit)
    except requests.RequestException as e:
        if verbose:
            print(f"⚠️ Error fetching Messenger conversations: {e}")
        return 0

    now_utc = datetime.now(timezone.utc)

    for conv in conversations:
        conv_id = conv["id"]
        messages = conv.get("messages", {}).get("data", [])
        if not messages:
            continue

        # Find the latest customer message
        customer_msg = None
        for m in messages:
            m_sender = m.get("from", {})
            m_sender_id = m_sender.get("id")
            if m_sender_id and m_sender_id != page_id and not m_sender.get("email", "").startswith(page_id):
                customer_msg = m
                break

        if not customer_msg:
            continue

        msg_id = customer_msg.get("id")
        sender = customer_msg.get("from", {})
        sender_id = sender.get("id")
        sender_name = sender.get("name", "Bạn")
        msg_text = customer_msg.get("message", "").strip()

        # If already replied to this message ID, skip
        if msg_id in replied:
            continue

        # Check if page has already sent a meaningful conversational text reply AFTER this customer message
        has_page_text_reply = False
        for m in messages:
            if m.get("id") == msg_id:
                break
            m_sender = m.get("from", {})
            m_sender_id = m_sender.get("id")
            m_text = m.get("message", "").strip()
            if (m_sender_id == page_id or m_sender.get("email", "").startswith(page_id)):
                if m_text and not is_facebook_system_message(m_text):
                    has_page_text_reply = True
                    break

        if has_page_text_reply:
            replied.add(msg_id)
            continue

        # Check message age: ignore messages older than 24 hours (Facebook messaging window limit)
        created_time_str = customer_msg.get("created_time", "")
        if created_time_str:
            try:
                dt = datetime.fromisoformat(created_time_str.replace("+0000", "+00:00"))
                age_seconds = (now_utc - dt).total_seconds()
                if age_seconds > 86400:  # > 24 hours
                    replied.add(msg_id)
                    continue
            except Exception:
                pass

        if not msg_text:
            continue

        if verbose:
            print(f"💬 [Messenger] New message from {sender_name}: \"{msg_text}\" (Conv: {conv_id})")

        # Format history of last 6 messages
        history = []
        for m in reversed(messages[:6]):
            m_sender = m.get("from", {})
            m_is_page = (m_sender.get("id") == page_id)
            m_text = m.get("message", "").strip()
            if m_text:
                m_role = "EduFlow Academy" if m_is_page else m_sender.get("name", "Khách")
                history.append(f"[{m_role}]: {m_text}")

        # Detect course and branch context
        full_thread_text = " ".join(history) + " " + msg_text
        course_val = detect_course_from_text(full_thread_text)
        branch_val = detect_branch_from_text(msg_text)

        # Generate intelligent contextual reply
        # Detect phone number in current message or thread
        phone_match = re.search(r"(0\d{9}|\+84\d{9})", msg_text)
        phone_val = phone_match.group(1) if phone_match else None
        has_phone_in_thread = bool(phone_match or re.search(r"(0\d{9}|\+84\d{9})", full_thread_text))

        # Generate intelligent contextual reply
        reply_text = generate_ai_conversation_reply(sender_name, history, msg_text)

        # Smart quick reply buttons (will be empty [] when phone provided, asking for phone, or concluded)
        smart_quick_replies = get_smart_quick_replies(
            course_context=course_val,
            message_text=msg_text,
            history=history,
            has_phone=has_phone_in_thread,
        )

        # Keep conversation clean and consultative - do not send unsolicited images
        image_to_attach = None

        if dry_run:
            if verbose:
                print(f"   🔍 [DRY RUN] Messenger Reply: \"{reply_text}\"")
                print(f"   🔍 [DRY RUN] Quick replies: {[b['title'] for b in smart_quick_replies]}")
                if image_to_attach:
                    print(f"   🔍 [DRY RUN] Image attachment: {image_to_attach}")
            replied.add(msg_id)
            new_replies += 1
        else:
            try:
                res = send_messenger_message(
                    page_id,
                    token,
                    sender_id,
                    reply_text,
                    quick_replies=smart_quick_replies,
                    image_path=image_to_attach,
                )
                if res and verbose:
                    mid = res.get("message_id")
                    btn_info = f" with {len(smart_quick_replies)} quick buttons" if smart_quick_replies else " (clean conclusion, no buttons)"
                    print(f"   📩 Messenger reply sent to {sender_name} (Ref: {mid}){btn_info}")

                # Check for phone, branch, course and sync to CRM
                sync_to_frappe_crm(sender_name, phone=phone_val, course=course_val, branch=branch_val)

                replied.add(msg_id)
                new_replies += 1
            except Exception as e:
                if verbose:
                    print(f"   ❌ Messenger reply error: {e}")

    if not dry_run and new_replies > 0:
        save_replied_messenger(replied)

    return new_replies


def process_comments(
    page_id: str,
    token: str,
    limit: int = 5,
    post_id: str | None = None,
    dry_run: bool = False,
    verbose: bool = True,
    no_private: bool = False,
    private_only: bool = False,
) -> int:
    """Scan posts, reply to comments publicly, and send private Messenger messages."""
    replied = load_replied_comments()
    new_replies = 0

    if post_id:
        posts = [{"id": post_id}]
    else:
        posts = get_recent_posts(page_id, token, limit)

    for post in posts:
        pid = post["id"]
        post_msg = post.get("message", "")[:60] if "message" in post else "(media)"

        try:
            comments = get_comments(pid, token)
        except requests.RequestException as e:
            if verbose:
                print(f"⚠️ Error fetching comments for post {pid}: {e}")
            continue

        for comment in comments:
            cid = comment["id"]
            commenter = comment.get("from", {}).get("name", "Bạn")
            commenter_id = comment.get("from", {}).get("id", "")
            msg = comment.get("message", "")

            # Skip if already replied
            if cid in replied:
                continue

            # Skip comments from the page itself
            if commenter_id == page_id:
                continue

            if verbose:
                print(f"💬 New comment from {commenter}: \"{msg}\" (Post: {pid})")

            # 1. Generate Public Comment Reply
            public_reply_text = None
            if not private_only:
                public_reply_text = generate_ai_comment_reply(commenter, msg, post_msg)
                if not public_reply_text:
                    public_reply_text = random.choice(PUBLIC_REPLY_TEMPLATES).format(name=commenter)

            # 2. Generate Private Messenger Reply
            private_reply_text = None
            if not no_private:
                private_reply_text = generate_ai_private_reply(commenter, msg, post_msg)
                if not private_reply_text:
                    private_reply_text = random.choice(PRIVATE_REPLY_TEMPLATES).format(name=commenter)

            if dry_run:
                if public_reply_text and verbose:
                    print(f"   🔍 [DRY RUN] Public Reply: \"{public_reply_text}\"")
                if private_reply_text and verbose:
                    print(f"   🔍 [DRY RUN] Private Messenger: \"{private_reply_text}\"")
                replied.add(cid)
                new_replies += 1
            else:
                try:
                    # Execute public reply
                    if public_reply_text:
                        reply_to_comment(cid, token, public_reply_text)
                        like_comment(cid, token)
                        if verbose:
                            print(f"   ✅ Public comment replied: \"{public_reply_text}\"")

                    # Execute private Messenger reply
                    if private_reply_text:
                        p_res = send_private_reply(page_id, token, cid, private_reply_text)
                        if p_res and verbose:
                            mid = p_res.get("message_id") or p_res.get("status")
                            print(f"   📩 Private Messenger sent to {commenter} (Ref: {mid})")

                    replied.add(cid)
                    new_replies += 1
                except requests.RequestException as e:
                    if verbose:
                        print(f"   ❌ Reply error: {e}")

    if not dry_run and new_replies > 0:
        save_replied_comments(replied)

    return new_replies


def main():
    parser = argparse.ArgumentParser(description="EduFlow Comment Auto-Reply & Conversational Messenger Agent")
    parser.add_argument("--watch", action="store_true", help="Run continuously in background loop")
    parser.add_argument("--interval", type=int, default=10, help="Poll interval in seconds for --watch mode (default: 10)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without replying")
    parser.add_argument("--post-id", help="Process specific post ID only")
    parser.add_argument("--limit", type=int, default=5, help="Number of recent posts/conversations to check (default: 5)")
    parser.add_argument("--no-private", action="store_true", help="Only reply publicly on comments, do not send private Messenger message")
    parser.add_argument("--private-only", action="store_true", help="Only send private Messenger message, do not reply publicly on comments")
    parser.add_argument("--no-messenger", action="store_true", help="Only handle post comments, skip Messenger chat monitoring")
    parser.add_argument("--messenger-only", action="store_true", help="Only monitor and reply to Messenger chats")
    args = parser.parse_args()

    # Load environment
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    page_id = os.getenv("FACEBOOK_PAGE_ID")
    token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")

    if not page_id or not token:
        print("❌ Missing FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN in .env")
        sys.exit(1)

    print(f"🤖 EduFlow Omnichannel Marketing & Messenger Agent active for Page {page_id}")
    has_gemini = bool(os.getenv("GEMINI_API_KEY"))
    has_9router = bool(os.getenv("NINE_ROUTER_API_KEY"))
    engine = "Gemini AI" if has_gemini else ("9Router AI" if has_9router else "Context Heuristics")
    print(f"🧠 Intelligence Engine: {engine}")

    if args.messenger_only:
        print("💬 Mode: Messenger Conversations ONLY")
    elif args.no_messenger:
        print("📝 Mode: Post Comments ONLY")
    else:
        print("🚀 Mode: DUAL (Post Comments + Messenger Conversations)")

    def run_tick():
        c_count = 0
        m_count = 0
        if not args.messenger_only:
            c_count = process_comments(
                page_id,
                token,
                limit=args.limit,
                post_id=args.post_id,
                dry_run=args.dry_run,
                verbose=True,
                no_private=args.no_private,
                private_only=args.private_only,
            )
        if not args.no_messenger:
            m_count = process_messenger_conversations(
                page_id,
                token,
                limit=args.limit,
                dry_run=args.dry_run,
                verbose=True,
            )
        return c_count, m_count

    if args.watch:
        print(f"👀 Watching for new comments & messages every {args.interval}s (Ctrl+C to stop)...")
        while True:
            try:
                run_tick()
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n🛑 Stopped agent.")
                break
            except Exception as e:
                print(f"⚠️ Polling loop error: {e}")
                time.sleep(args.interval)
    else:
        c, m = run_tick()
        print(f"\n{'🔍 DRY RUN' if args.dry_run else '✅ Done'}: {c} comments, {m} messages processed")


if __name__ == "__main__":
    main()

