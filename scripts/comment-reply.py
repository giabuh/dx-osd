#!/usr/bin/env python3
"""
EduFlow Comment Auto-Reply: Automatically reply to comments on Facebook Page posts.

This script monitors recent posts for new comments and replies with a CTA
to inbox the page. When the user messages the page, they enter the existing
Messenger bot qualification flow (course → branch → phone → agent handoff).

Features:
- Scans recent posts for unreplied comments
- Auto-replies with personalized CTA
- Tracks replied comments to avoid duplicates
- Can be run as a cron job

Usage:
    python scripts/comment-reply.py              # Process all unreplied comments
    python scripts/comment-reply.py --dry-run    # Preview without replying
    python scripts/comment-reply.py --post-id ID # Process specific post only

Environment: reads from .env in project root
"""

import argparse
import json
import os
import random
import sys
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


# ── Reply templates ───────────────────────────────────────────────

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
        pass  # Non-critical, ignore errors


def main():
    parser = argparse.ArgumentParser(description="EduFlow Comment Auto-Reply")
    parser.add_argument("--dry-run", action="store_true", help="Preview without replying")
    parser.add_argument("--post-id", help="Process specific post ID only")
    parser.add_argument("--limit", type=int, default=5, help="Number of recent posts to check")
    args = parser.parse_args()

    # Load environment
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    page_id = os.getenv("FACEBOOK_PAGE_ID")
    token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")

    if not page_id or not token:
        print("❌ Missing FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN in .env")
        sys.exit(1)

    replied = load_replied_comments()
    new_replies = 0

    if args.post_id:
        posts = [{"id": args.post_id}]
    else:
        print(f"📋 Fetching last {args.limit} posts...")
        posts = get_recent_posts(page_id, token, args.limit)
        print(f"   Found {len(posts)} posts")

    for post in posts:
        post_id = post["id"]
        post_msg = post.get("message", "")[:50] if "message" in post else "(no text)"
        print(f"\n📝 Post: {post_id} — {post_msg}...")

        comments = get_comments(post_id, token)
        print(f"   💬 {len(comments)} comments")

        for comment in comments:
            cid = comment["id"]
            commenter = comment.get("from", {}).get("name", "Unknown")
            commenter_id = comment.get("from", {}).get("id", "")
            msg = comment.get("message", "")

            # Skip if already replied
            if cid in replied:
                continue

            # Skip comments from the page itself
            if commenter_id == page_id:
                continue

            print(f"   → {commenter}: {msg[:60]}...")

            reply_text = random.choice(REPLY_TEMPLATES)

            if args.dry_run:
                print(f"     🔍 Would reply: {reply_text[:50]}...")
            else:
                try:
                    reply_to_comment(cid, token, reply_text)
                    like_comment(cid, token)
                    print(f"     ✅ Replied & liked!")
                    replied.add(cid)
                    new_replies += 1
                except requests.RequestException as e:
                    print(f"     ❌ Error: {e}")

    if not args.dry_run:
        save_replied_comments(replied)

    print(f"\n{'🔍 DRY RUN' if args.dry_run else '✅ Done'}: {new_replies} new replies")


if __name__ == "__main__":
    main()
