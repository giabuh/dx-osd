#!/usr/bin/env python3
"""
EduFlow Comment Auto-Reply: Automatically reply to comments on Facebook Page posts.

This script monitors recent posts for new comments and replies with a personalized CTA
to inbox the page. When the user messages the page, they enter the existing
Messenger bot qualification flow (course → branch → phone → agent handoff).

Features:
- AI-powered personalized replies via Gemini / Google AI Studio (fallback to template)
- Real-time continuous monitoring with --watch flag
- Scans recent posts for unreplied comments
- Tracks replied comments to avoid duplicates (.replied_comments.json)

Usage:
    python scripts/comment-reply.py              # Process all unreplied comments once
    python scripts/comment-reply.py --watch      # Run continuously in background (every 10s)
    python scripts/comment-reply.py --dry-run    # Preview without replying
    python scripts/comment-reply.py --post-id ID # Process specific post only

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


# ── Fallback Reply Templates ──────────────────────────────────────

REPLY_TEMPLATES = [
    "Cảm ơn bạn đã quan tâm! 💬 Inbox em để được tư vấn chi tiết nhé! 🎓",
    "Dạ cảm ơn bạn! 🌟 Nhắn tin cho trang để em tư vấn khóa học phù hợp nhé! 📚",
    "Cảm ơn bạn nhé! 😊 Inbox trang để biết thêm chi tiết và nhận ưu đãi nha! 🎁",
    "Dạ hi bạn! 👋 Bạn inbox cho em để được hỗ trợ nhanh nhất nhé! 💪",
    "Cảm ơn bạn đã quan tâm! 🙏 Nhắn tin cho trang em sẽ tư vấn ngay ạ! ✨",
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
    """Reply to a comment."""
    url = f"https://graph.facebook.com/v21.0/{comment_id}/comments"
    resp = requests.post(
        url,
        data={"message": message, "access_token": token},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def like_comment(comment_id: str, token: str):
    """Like a comment to acknowledge it."""
    url = f"https://graph.facebook.com/v21.0/{comment_id}/likes"
    try:
        requests.post(url, data={"access_token": token}, timeout=10)
    except requests.RequestException:
        pass


def generate_ai_comment_reply(commenter_name: str, comment_text: str) -> str | None:
    """Generate a polite, personalized comment reply using Gemini or 9Router."""
    # 1. Try Google Gemini API
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    prompt = (
        f"Bạn là trợ lý tư vấn thân thiện của trung tâm giáo dục EduFlow Academy.\n"
        f"Học viên/phụ huynh tên '{commenter_name}' vừa bình luận: \"{comment_text}\".\n"
        f"Hãy viết 1 câu trả lời ngắn gọn (dưới 35 từ), rất thân thiện, lễ phép (dạ, em chào...),\n"
        f"có emoji phù hợp, và khéo léo mời khách nhắn tin/inbox fanpage để được tư vấn lộ trình và học phí chi tiết.\n"
        f"Quy tắc quan trọng: KHÔNG dùng markdown (không **, ##), chỉ trả về đúng câu phản hồi."
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

    # 2. Try 9Router fallback
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


def process_comments(page_id: str, token: str, limit: int = 5, post_id: str | None = None, dry_run: bool = False, verbose: bool = True) -> int:
    """Scan posts and reply to any unreplied comments. Returns count of new replies."""
    replied = load_replied_comments()
    new_replies = 0

    if post_id:
        posts = [{"id": post_id}]
    else:
        posts = get_recent_posts(page_id, token, limit)

    for post in posts:
        pid = post["id"]
        post_msg = post.get("message", "")[:40] if "message" in post else "(media)"

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
                print(f"💬 New comment from {commenter}: \"{msg}\"")

            # Try generating AI reply first, fallback to templates
            reply_text = generate_ai_comment_reply(commenter, msg)
            if not reply_text:
                reply_text = random.choice(REPLY_TEMPLATES)

            if dry_run:
                if verbose:
                    print(f"   🔍 [DRY RUN] Would reply: {reply_text}")
                replied.add(cid)
                new_replies += 1
            else:
                try:
                    reply_to_comment(cid, token, reply_text)
                    like_comment(cid, token)
                    if verbose:
                        print(f"   ✅ Replied: \"{reply_text}\"")
                    replied.add(cid)
                    new_replies += 1
                except requests.RequestException as e:
                    if verbose:
                        print(f"   ❌ Reply error: {e}")

    if not dry_run and new_replies > 0:
        save_replied_comments(replied)

    return new_replies


def main():
    parser = argparse.ArgumentParser(description="EduFlow Comment Auto-Reply")
    parser.add_argument("--watch", action="store_true", help="Run continuously in background loop")
    parser.add_argument("--interval", type=int, default=10, help="Poll interval in seconds for --watch mode (default: 10)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without replying")
    parser.add_argument("--post-id", help="Process specific post ID only")
    parser.add_argument("--limit", type=int, default=5, help="Number of recent posts to check (default: 5)")
    args = parser.parse_args()

    # Load environment
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    page_id = os.getenv("FACEBOOK_PAGE_ID")
    token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")

    if not page_id or not token:
        print("❌ Missing FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN in .env")
        sys.exit(1)

    print(f"🤖 EduFlow Comment Auto-Reply active for Page {page_id}")
    has_gemini = bool(os.getenv("GEMINI_API_KEY"))
    has_9router = bool(os.getenv("NINE_ROUTER_API_KEY"))
    engine = "Gemini AI" if has_gemini else ("9Router AI" if has_9router else "Templates")
    print(f"🧠 Intelligence Engine: {engine}")

    if args.watch:
        print(f"👀 Watching for new comments every {args.interval}s (Ctrl+C to stop)...")
        while True:
            try:
                process_comments(page_id, token, limit=args.limit, post_id=args.post_id, dry_run=args.dry_run, verbose=True)
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n🛑 Stopped comment auto-reply.")
                break
            except Exception as e:
                print(f"⚠️ Polling loop error: {e}")
                time.sleep(args.interval)
    else:
        count = process_comments(page_id, token, limit=args.limit, post_id=args.post_id, dry_run=args.dry_run, verbose=True)
        print(f"\n{'🔍 DRY RUN' if args.dry_run else '✅ Done'}: {count} new replies")


if __name__ == "__main__":
    main()
