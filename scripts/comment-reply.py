#!/usr/bin/env python3
"""
EduFlow Comment Auto-Reply & Messenger Private Reply System.

Automatically responds to comments on Facebook Page posts:
1. Public Comment Reply: Acknowledges the comment, likes it, and notifies the commenter that
   details have been sent to their Messenger inbox.
2. Private Message (Messenger Private Reply): Delivers a personalized consultation message
   directly into the commenter's Facebook Messenger inbox using the Messenger Platform API
   (POST /{page-id}/messages with recipient={"comment_id": comment_id}).
3. When the user replies in Messenger, they seamlessly enter the Chatwoot EduFlow qualification flow
   (course → branch → phone → CRM Lead creation & staff assignment).

Features:
- AI-powered personalized public & private replies via Gemini / 9Router (fallback to templates)
- Real-time continuous monitoring with --watch flag
- Scans recent posts for unreplied comments
- Tracks replied comments to avoid duplicates (.replied_comments.json)
- Graceful handling of Facebook 1-reply-per-comment policy (error code 10900)

Usage:
    python scripts/comment-reply.py              # Process all unreplied comments once
    python scripts/comment-reply.py --watch      # Run continuously in background (every 10s)
    python scripts/comment-reply.py --dry-run    # Preview without replying
    python scripts/comment-reply.py --post-id ID # Process specific post only
    python scripts/comment-reply.py --no-private # Only reply publicly on the comment
    python scripts/comment-reply.py --private-only # Only send private Messenger message

Environment: reads from .env in project root
"""

import argparse
import json
import os
import random
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

# File to track replied comments (avoid duplicates)
REPLIED_FILE = Path(__file__).resolve().parent.parent / ".replied_comments.json"


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
    parser = argparse.ArgumentParser(description="EduFlow Comment Auto-Reply & Messenger Private Reply")
    parser.add_argument("--watch", action="store_true", help="Run continuously in background loop")
    parser.add_argument("--interval", type=int, default=10, help="Poll interval in seconds for --watch mode (default: 10)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without replying")
    parser.add_argument("--post-id", help="Process specific post ID only")
    parser.add_argument("--limit", type=int, default=5, help="Number of recent posts to check (default: 5)")
    parser.add_argument("--no-private", action="store_true", help="Only reply publicly, do not send private Messenger message")
    parser.add_argument("--private-only", action="store_true", help="Only send private Messenger message, do not reply publicly")
    args = parser.parse_args()

    # Load environment
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    page_id = os.getenv("FACEBOOK_PAGE_ID")
    token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")

    if not page_id or not token:
        print("❌ Missing FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN in .env")
        sys.exit(1)

    print(f"🤖 EduFlow Comment & Private Reply System active for Page {page_id}")
    has_gemini = bool(os.getenv("GEMINI_API_KEY"))
    has_9router = bool(os.getenv("NINE_ROUTER_API_KEY"))
    engine = "Gemini AI" if has_gemini else ("9Router AI" if has_9router else "Templates")
    print(f"🧠 Intelligence Engine: {engine}")
    if args.no_private:
        print("ℹ️ Mode: Public Comment Replies ONLY")
    elif args.private_only:
        print("ℹ️ Mode: Private Messenger Messages ONLY")
    else:
        print("🚀 Mode: DUAL (Public Comment Reply + Private Messenger Message)")

    if args.watch:
        print(f"👀 Watching for new comments every {args.interval}s (Ctrl+C to stop)...")
        while True:
            try:
                process_comments(
                    page_id,
                    token,
                    limit=args.limit,
                    post_id=args.post_id,
                    dry_run=args.dry_run,
                    verbose=True,
                    no_private=args.no_private,
                    private_only=args.private_only,
                )
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n🛑 Stopped comment auto-reply.")
                break
            except Exception as e:
                print(f"⚠️ Polling loop error: {e}")
                time.sleep(args.interval)
    else:
        count = process_comments(
            page_id,
            token,
            limit=args.limit,
            post_id=args.post_id,
            dry_run=args.dry_run,
            verbose=True,
            no_private=args.no_private,
            private_only=args.private_only,
        )
        print(f"\n{'🔍 DRY RUN' if args.dry_run else '✅ Done'}: {count} processed")


if __name__ == "__main__":
    main()
