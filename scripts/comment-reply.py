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


# ── Bot Slot CRM Dynamic Integration ──────────────────────────────
_SLOT_CACHE = {"timestamp": 0, "data": None}

PREFERRED_SLOT_ORDER = [
    "course",
    "learner",
    "learner_age",
    "level",
    "goal",
    "branch",
    "preferred_shift",
    "phone",
]


def fetch_bot_slots_config(cache_ttl: int = 30) -> dict:
    """Fetch active Bot Slot configuration and options from Frappe CRM (cached for cache_ttl seconds)."""
    global _SLOT_CACHE
    now = time.time()
    if _SLOT_CACHE["data"] and (now - _SLOT_CACHE["timestamp"] < cache_ttl):
        return _SLOT_CACHE["data"]

    cmd = [
        "docker", "exec", "-w", "/home/frappe/frappe-bench", "crm-frappe-1",
        "./env/bin/python", "-c",
        "import frappe, json; frappe.init(site='crm.localhost', sites_path='sites'); frappe.connect(); "
        "slots = frappe.get_all('Bot Slot', filters={'active': 1}, fields=['name', 'slot_key', 'label', 'slot_type', 'required', 'ask_template', 'lead_field']); "
        "opts = frappe.get_all('Bot Slot Option', fields=['parent', 'value', 'label', 'button_label', 'aliases']); "
        "print(json.dumps({'slots': slots, 'options': opts}))"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout.strip())
            _SLOT_CACHE = {"timestamp": now, "data": data}
            return data
    except Exception:
        pass

    return _SLOT_CACHE.get("data") or {
        "slots": [
            {"slot_key": "course", "label": "Khóa học", "slot_type": "catalog", "required": 1},
            {"slot_key": "branch", "label": "Chi nhánh", "slot_type": "catalog", "required": 1},
            {"slot_key": "learner_age", "label": "Tuổi người học", "slot_type": "number", "required": 1},
            {"slot_key": "phone", "label": "Số điện thoại", "slot_type": "phone", "required": 1},
        ],
        "options": []
    }


def extract_learner_age(text: str) -> int | None:
    """Extract learner age from message text or quick reply payload."""
    if not text:
        return None
    lower = text.lower()
    if "age_kids" in lower or "6 - 9" in lower:
        return 8
    if "age_teens" in lower or "10 - 15" in lower:
        return 12
    if "age_adult" in lower or any(k in lower for k in ["sinh viên", "đi làm", "người lớn"]):
        return 22

    m = re.search(r"(?:bé|cháu|con|em|mình|học viên)?\s*(\d{1,2})\s*(?:tuổi|tuoi|t\b)", lower)
    if m:
        try:
            val = int(m.group(1))
            if 3 <= val <= 80:
                return val
        except ValueError:
            pass

    m_plain = re.fullmatch(r"\s*(\d{1,2})\s*", text.strip())
    if m_plain:
        try:
            val = int(m_plain.group(1))
            if 4 <= val <= 70:
                return val
        except ValueError:
            pass
    return None


def extract_preferred_shift(text: str) -> str | None:
    """Extract preferred study shift."""
    if not text:
        return None
    lower = text.lower()
    if any(k in lower for k in ["tối", "toi", "2-4-6", "3-5-7", "evening", "shift_evening"]):
        return "Ca tối (18h30 - 20h30)"
    if any(k in lower for k in ["sáng", "sang", "cuối tuần", "thứ 7", "chủ nhật", "t7", "cn", "weekend", "shift_weekend"]):
        return "Ca cuối tuần (Sáng T7 - CN)"
    if any(k in lower for k in ["chiều", "chieu", "afternoon", "shift_afternoon"]):
        return "Ca chiều"
    return None


def extract_learner_type(text: str) -> str | None:
    """Extract learner target group."""
    if not text:
        return None
    lower = text.lower()
    if any(k in lower for k in ["con em", "cho con", "bé", "cho bé", "cháu", "learner_child"]):
        return "Con em"
    if any(k in lower for k in ["bản thân", "cho mình", "cho tôi", "tôi học", "mình học", "learner_self"]):
        return "Bản thân"
    if any(k in lower for k in ["công ty", "doanh nghiệp", "nhân viên", "learner_staff"]):
        return "Nhân viên công ty"
    return None


def extract_level(text: str) -> str | None:
    """Extract current knowledge level."""
    if not text:
        return None
    lower = text.lower()
    if any(k in lower for k in ["chưa biết gì", "mất gốc", "mới bắt đầu", "từ đầu", "từ số 0", "level_beginner"]):
        return "Chưa biết gì"
    if any(k in lower for k in ["cơ bản", "biết chút", "đã biết", "level_basic"]):
        return "Biết cơ bản"
    if any(k in lower for k in ["nâng cao", "chuyên sâu", "level_advanced"]):
        return "Muốn nâng cao"
    return None


def extract_goal(text: str) -> str | None:
    """Extract learning objective."""
    if not text:
        return None
    lower = text.lower()
    if any(k in lower for k in ["chứng chỉ", "thi mos", "lấy bằng", "goal_cert"]):
        return "Lấy chứng chỉ"
    if any(k in lower for k in ["văn phòng", "công việc", "đi làm", "goal_office"]):
        return "Công việc văn phòng"
    if any(k in lower for k in ["cho bé", "làm quen", "goal_kids"]):
        return "Cho bé làm quen"
    return None


def extract_all_slots(full_thread_text: str, latest_msg: str, slots_config: dict) -> dict:
    """Extract all available slot values from conversation thread & latest message."""
    collected = {}

    c = detect_course_from_text(full_thread_text)
    if c:
        collected["course"] = c

    b = detect_branch_from_text(full_thread_text)
    if b:
        collected["branch"] = b

    m_phone = re.search(r"(0\d{9}|\+84\d{9})", full_thread_text)
    if m_phone:
        collected["phone"] = m_phone.group(1)

    age = extract_learner_age(latest_msg) or extract_learner_age(full_thread_text)
    if age:
        collected["learner_age"] = age

    shift = extract_preferred_shift(latest_msg) or extract_preferred_shift(full_thread_text)
    if shift:
        collected["preferred_shift"] = shift

    l_type = extract_learner_type(latest_msg) or extract_learner_type(full_thread_text)
    if l_type:
        collected["learner"] = l_type

    lvl = extract_level(latest_msg) or extract_level(full_thread_text)
    if lvl:
        collected["level"] = lvl

    g = extract_goal(latest_msg) or extract_goal(full_thread_text)
    if g:
        collected["goal"] = g

    return collected


def get_next_missing_slot(collected_slots: dict, slots_config: dict) -> dict | None:
    """Find the next required slot according to Bot Slot configuration that has not been collected."""
    slots = slots_config.get("slots", [])
    required_slots = {
        s.get("slot_key"): s
        for s in slots
        if s.get("required") and s.get("slot_key") != "customer_name"
    }

    for key in PREFERRED_SLOT_ORDER:
        if key in required_slots and key not in collected_slots:
            return required_slots[key]

    for key, slot_def in required_slots.items():
        if key not in collected_slots:
            return slot_def

    return None


# ── Conversational Messenger Reply Generator ───────────────────────
def generate_ai_conversation_reply(
    customer_name: str,
    history: list[str],
    latest_msg: str,
    collected_slots: dict | None = None,
    next_missing_slot: dict | None = None,
) -> str:
    """Generate a highly contextual, natural, consultative Messenger response based on Bot Slot configuration."""
    collected = collected_slots or {}
    phone_match = re.search(r"(0\d{9}|\+84\d{9})", latest_msg)
    lower = latest_msg.lower()

    # 1. Deterministic phone number detection (actual digits provided)
    if phone_match:
        phone = phone_match.group(1)
        collected["phone"] = phone
        # If all required slots are now complete, send full summary confirmation
        summary_items = []
        if collected.get("course"):
            summary_items.append(f"• Khóa học: {collected['course']}")
        if collected.get("learner_age"):
            summary_items.append(f"• Độ tuổi: {collected['learner_age']} tuổi")
        if collected.get("preferred_shift"):
            summary_items.append(f"• Ca học: {collected['preferred_shift']}")
        if collected.get("branch"):
            summary_items.append(f"• Cơ sở: {collected['branch']}")
        summary_items.append(f"• Số điện thoại: {phone}")

        summary_text = "\n".join(summary_items)
        return (
            f"Dạ em cảm ơn anh/chị {customer_name} nhiều ạ! Em đã ghi nhận đầy đủ hồ sơ đăng ký cho mình:\n"
            f"{summary_text}\n\n"
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
    collected_summary = ", ".join(f"{k}: {v}" for k, v in collected.items()) if collected else "Chưa có"

    # Contextual goal guidance for AI
    if next_missing_slot:
        missing_label = next_missing_slot.get("label", "thông tin tiếp theo")
        missing_key = next_missing_slot.get("slot_key", "")
        missing_template = next_missing_slot.get("ask_template", "")
        next_step_instruction = (
            f"MỤC TIÊU BẮT BUỘC LƯỢT NÀY (theo cấu hình CRM Bot Slot):\n"
            f"Thu thập thông tin: [{missing_label}] (key: {missing_key}).\n"
            f"Gợi ý câu hỏi: \"{missing_template}\".\n"
            f"Yêu cầu: Hãy xác nhận thân thiện thông tin khách vừa gửi ở tin nhắn mới nhất, sau đó khéo léo hỏi khách thông tin [{missing_label}] để phục vụ xếp lớp/tư vấn lộ trình."
        )
    else:
        next_step_instruction = (
            "Tất cả các thông tin bắt buộc đã được thu thập đầy đủ. Hãy chúc mừng và mời khách để lại SĐT hoặc xác nhận lại lịch học."
        )

    prompt = (
        f"Bạn là Chuyên viên Tư vấn Tuyển sinh Cao cấp của Học viện EduFlow Academy (Việt Nam).\n"
        f"Nhiệm vụ: Phản hồi tin nhắn Messenger của học viên '{customer_name}' một cách tự nhiên, lễ phép, thông minh, chuyên nghiệp và KHÔNG BỊ SƯỢNG.\n\n"
        f"Lịch sử trò chuyện gần nhất:\n{history_str}\n\n"
        f"Tin nhắn mới nhất của {customer_name}: \"{latest_msg}\"\n\n"
        f"Thông tin đã thu thập được từ khách: {collected_summary}\n\n"
        f"{next_step_instruction}\n\n"
        f"Kiến thức đào tạo EduFlow:\n"
        f"1. Photoshop Thực chiến: 12 buổi (6 tuần), thực hành 100% trên máy tính. Học từ con số 0 đến tự làm banner, poster, chỉnh ảnh chuyên nghiệp. Học bổng hỗ trợ 35% học phí + tặng 50GB tài nguyên thiết kế.\n"
        f"2. Tin học văn phòng & MOS: Excel/Word/PowerPoint từ căn bản đến nâng cao, cam kết chuẩn đầu ra MOS quốc tế.\n"
        f"3. Lập trình Python & Web: Dành cho người mới bắt đầu từ số 0 đến tự xây dựng phần mềm và phân tích dữ liệu.\n"
        f"4. Cơ sở đào tạo: CS1 Điện Biên Phủ (Bình Thạnh), CS2 Nguyễn Thị Minh Khai (Q.1), CS3 Võ Văn Ngân (TP. Thủ Đức).\n"
        f"5. Lịch học các cơ sở: Lớp tối 2-4-6 (18h30 - 20h30), Lớp cuối tuần (Sáng T7 - CN 9h00 - 11h30).\n"
        f"6. Học phí: Ưu đãi 35% chỉ còn ~1.950.000đ - 2.500.000đ tùy khóa.\n\n"
        f"QUY TẮC PHẢN HỒI:\n"
        f"1. Tuyệt đối KHÔNG gửi menu cứng nhắc, KHÔNG lặp lại giới thiệu chung nếu khách đã chọn bước tiếp theo.\n"
        f"2. Luôn xác nhận thông tin khách vừa chọn một cách hào hứng và tích cực.\n"
        f"3. Giọng văn: Ấm áp, lịch sự, xưng 'em', gọi khách là 'anh/chị' hoặc 'anh/chị {customer_name}'. Ngắn gọn dưới 60 từ. Không dùng markdown (** hay ##)."
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
    missing_key = next_missing_slot.get("slot_key") if next_missing_slot else None

    if missing_key == "learner_age":
        return (
            f"Dạ tuyệt vời ạ! Để EduFlow chuẩn bị tài liệu và xếp lớp có độ tuổi và nhóm học phù hợp nhất, bé nhà mình (hoặc anh/chị) năm nay bao nhiêu tuổi rồi ạ? 👶"
        )

    if missing_key == "branch":
        return (
            f"Dạ EduFlow có 3 cơ sở đào tạo với phòng máy thực hành cấu hình cao tại TP.HCM:\n"
            f"📍 CS1: Điện Biên Phủ, Q. Bình Thạnh\n"
            f"📍 CS2: Nguyễn Thị Minh Khai, Q.1\n"
            f"📍 CS3: Võ Văn Ngân, TP. Thủ Đức\n\n"
            f"Mình thấy tiện học ở cơ sở nào để em hỗ trợ giữ lịch học thử cho mình nhé! 🏢"
        )

    if missing_key == "preferred_shift":
        return (
            f"Dạ EduFlow có 2 khung giờ học rất thuận tiện:\n"
            f"• Lớp tối 2-4-6 (18h30 - 20h30)\n"
            f"• Lớp cuối tuần (Sáng Thứ 7 & Chủ Nhật)\n\n"
            f"Anh/chị {customer_name} thấy ca học nào phù hợp hơn để em hỗ trợ đăng ký cho mình nhé? ⏰"
        )

    if missing_key == "phone":
        return (
            f"Dạ để hoàn tất giữ suất học bổng ưu đãi 35% học phí và nhận vé tham gia buổi học thử 1-1 miễn phí, anh/chị nhắn em xin Số Điện Thoại (SĐT) trực tiếp vào ô chat để chuyên viên hỗ trợ làm hồ sơ cho mình nhé! 📱"
        )

    if missing_key == "learner":
        return (
            f"Dạ khóa học này mình đang tìm hiểu cho con em hay cho bản thân/công ty học vậy ạ? 🎓"
        )

    if missing_key == "level":
        return (
            f"Dạ mình đã từng học qua hoặc biết cơ bản về môn này chưa, hay học từ số 0 để em tư vấn lộ trình nhé ạ? ✨"
        )

    # General course intro fallback
    return (
        f"Dạ em chào anh/chị {customer_name}! EduFlow Academy có các chương trình đào tạo thực chiến nổi bật:\n"
        f"1. Thiết kế đồ họa / Photoshop\n"
        f"2. Tin học văn phòng & Luyện thi MOS\n"
        f"3. Lập trình Python & Tự động hóa\n\n"
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
    next_missing_slot: dict | None = None,
    slots_config: dict | None = None,
) -> list[dict]:
    """Return contextual Quick Reply buttons for Facebook Messenger based on Bot Slot progression."""
    lower = (message_text or "").lower()

    # 1. Concluded / phone provided / thank you -> NO buttons (completely clean chat)
    if has_phone or re.search(r"(0\d{9}|\+84\d{9})", message_text):
        return []

    if any(k in lower for k in ["cảm ơn", "cam on", "thank", "tks", "bye", "tạm biệt", "ok em", "chúc em", "tuyệt vời"]):
        return []

    # 2. If next missing slot is phone -> NO buttons (let customer type their phone cleanly)
    if next_missing_slot and next_missing_slot.get("slot_key") == "phone":
        return []

    if any(k in lower for k in ["gửi số điện thoại", "sđt", "sdt", "số điện thoại", "cho sdt", "gửi sdt"]):
        return []

    # 3. Schedule chosen -> bot asks for phone number -> NO buttons (leave text bar clean)
    if any(k in lower for k in ["tối", "cuối tuần", "2-4-6", "3-5-7", "t7", "cn", "sáng"]):
        if not next_missing_slot or next_missing_slot.get("slot_key") == "phone":
            return []

    # 4. Dynamic buttons driven by next_missing_slot
    if next_missing_slot:
        missing_key = next_missing_slot.get("slot_key")

        if missing_key == "course":
            return [
                {"content_type": "text", "title": "🎨 Khóa Photoshop", "payload": "COURSE_PHOTOSHOP"},
                {"content_type": "text", "title": "📊 Tin học MOS", "payload": "COURSE_MOS"},
                {"content_type": "text", "title": "💻 Lập trình Python", "payload": "COURSE_PYTHON"},
                {"content_type": "text", "title": "🤖 Robotics STEM", "payload": "COURSE_STEM"},
            ]

        if missing_key == "branch":
            return [
                {"content_type": "text", "title": "📍 CS1 Bình Thạnh", "payload": "CS1_BINH_THANH"},
                {"content_type": "text", "title": "📍 CS2 Quận 1", "payload": "CS2_QUAN_1"},
                {"content_type": "text", "title": "📍 CS3 Thủ Đức", "payload": "CS3_THU_DUC"},
            ]

        if missing_key == "learner_age":
            return [
                {"content_type": "text", "title": "👶 Bé 6 - 9 tuổi", "payload": "AGE_KIDS"},
                {"content_type": "text", "title": "👦 Bé 10 - 15 tuổi", "payload": "AGE_TEENS"},
                {"content_type": "text", "title": "🎓 Sinh viên / Đi làm", "payload": "AGE_ADULT"},
            ]

        if missing_key == "preferred_shift":
            return [
                {"content_type": "text", "title": "🌙 Lớp tối 2-4-6", "payload": "SHIFT_EVENING"},
                {"content_type": "text", "title": "☀️ Lớp sáng T7 - CN", "payload": "SHIFT_WEEKEND"},
            ]

        if missing_key == "learner":
            return [
                {"content_type": "text", "title": "👶 Cho con em", "payload": "LEARNER_CHILD"},
                {"content_type": "text", "title": "🙋 Cho bản thân", "payload": "LEARNER_SELF"},
                {"content_type": "text", "title": "🏢 Cho công ty", "payload": "LEARNER_STAFF"},
            ]

        if missing_key == "level":
            return [
                {"content_type": "text", "title": "🌱 Chưa biết gì", "payload": "LEVEL_BEGINNER"},
                {"content_type": "text", "title": "📘 Biết cơ bản", "payload": "LEVEL_BASIC"},
                {"content_type": "text", "title": "🚀 Muốn nâng cao", "payload": "LEVEL_ADVANCED"},
            ]

        if missing_key == "goal":
            return [
                {"content_type": "text", "title": "💼 Đi làm văn phòng", "payload": "GOAL_OFFICE"},
                {"content_type": "text", "title": "📜 Lấy chứng chỉ", "payload": "GOAL_CERT"},
                {"content_type": "text", "title": "👶 Cho bé làm quen", "payload": "GOAL_KIDS"},
            ]

    # Default fallback
    if course_context:
        return [
            {"content_type": "text", "title": "📍 CS1 Bình Thạnh", "payload": "CS1_BINH_THANH"},
            {"content_type": "text", "title": "📍 CS2 Quận 1", "payload": "CS2_QUAN_1"},
            {"content_type": "text", "title": "📍 CS3 Thủ Đức", "payload": "CS3_THU_DUC"},
            {"content_type": "text", "title": "💰 Học phí ưu đãi", "payload": "TUITION_DISCOUNT"},
        ]

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


def sync_to_frappe_crm(
    customer_name: str,
    phone: str = None,
    course: str = None,
    branch: str = None,
    collected_slots: dict | None = None,
):
    """Sync qualified lead info to Frappe CRM using dynamic Bot Slot values."""
    try:
        collected = collected_slots or {}
        course = collected.get("course") or course
        branch = collected.get("branch") or branch
        phone = collected.get("phone") or phone
        learner_age = collected.get("learner_age")
        preferred_shift = collected.get("preferred_shift")
        learner = collected.get("learner")

        # Check if lead exists
        cmd = [
            "docker", "exec", "crm-frappe-1",
            "bench", "--site", "crm.localhost", "execute",
            "frappe.db.get_value",
            "--args", json.dumps(["CRM Lead", {"lead_name": customer_name}, ["name", "status"]]),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        try:
            lead_name, lead_status = json.loads(res.stdout.strip() or "null") or (None, None)
        except (ValueError, TypeError):
            lead_name, lead_status = None, None

        if lead_name:
            # D-116: never un-register a Lead (converted stays) and only a New Lead becomes Qualified;
            # a later step (Contacted, Trial Booked, Converted) or a status a person set is left alone.
            update_fields = {}
            if course:
                update_fields["course_interest"] = course
            if branch:
                update_fields["branch"] = branch
            if phone:
                update_fields["mobile_no"] = phone
                if lead_status in (None, "", "New"):
                    update_fields["status"] = "Qualified"
            if learner_age:
                update_fields["learner_age"] = int(learner_age)
            if preferred_shift:
                update_fields["preferred_shift"] = preferred_shift
            if learner:
                update_fields["learner_type"] = learner
            if not update_fields:
                return

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
            if learner_age:
                doc["learner_age"] = int(learner_age)
            if preferred_shift:
                doc["preferred_shift"] = preferred_shift
            if learner:
                doc["learner_type"] = learner

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

        # Fetch dynamic Bot Slot configuration from CRM
        slots_config = fetch_bot_slots_config()

        # Detect course, branch and all slots from conversation context
        full_thread_text = " ".join(history) + " " + msg_text
        collected_slots = extract_all_slots(full_thread_text, msg_text, slots_config)
        next_missing_slot = get_next_missing_slot(collected_slots, slots_config)

        # Detect phone number in current message or thread
        phone_match = re.search(r"(0\d{9}|\+84\d{9})", msg_text)
        has_phone_in_thread = bool("phone" in collected_slots or phone_match or re.search(r"(0\d{9}|\+84\d{9})", full_thread_text))

        # Generate intelligent contextual reply driven by Bot Slot requirements
        reply_text = generate_ai_conversation_reply(
            customer_name=sender_name,
            history=history,
            latest_msg=msg_text,
            collected_slots=collected_slots,
            next_missing_slot=next_missing_slot,
        )

        # Smart quick reply buttons for the next missing slot
        smart_quick_replies = get_smart_quick_replies(
            course_context=collected_slots.get("course"),
            message_text=msg_text,
            history=history,
            has_phone=has_phone_in_thread,
            next_missing_slot=next_missing_slot,
            slots_config=slots_config,
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

                # Sync all collected slots (course, branch, phone, age, shift, learner) to CRM Lead
                sync_to_frappe_crm(sender_name, collected_slots=collected_slots)

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

