# Copyright (c) 2026, MMM and contributors
# For license information, please see license.txt

from datetime import date, datetime, timedelta
import re

try:
    import frappe
    from frappe import _
    from frappe.utils import now_datetime
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

    def now_datetime():
        from datetime import datetime

        return datetime.now()


# 4 standard weekly post slots (Mon, Wed, Fri, Sun)
WEEKLY_MATRIX = [
    {
        "day": 0,
        "day_offset": 0,
        "day_of_week": "Thứ Hai",
        "time": "08:30:00",
        "course": "Tiếng Anh",
        "default_title": "Khai giảng Tiếng Anh giao tiếp",
    },
    {
        "day": 2,
        "day_offset": 2,
        "day_of_week": "Thứ Tư",
        "time": "11:30:00",
        "course": "Toán tư duy",
        "default_title": "Phát triển tư duy logic",
    },
    {
        "day": 4,
        "day_offset": 4,
        "day_of_week": "Thứ Sáu",
        "time": "19:30:00",
        "course": "Bơi lội",
        "default_title": "Khóa bơi sinh tồn cho bé",
    },
    {
        "day": 6,
        "day_offset": 6,
        "day_of_week": "Chủ Nhật",
        "time": "09:00:00",
        "course": "Chung",
        "default_title": "Tuyển sinh & Học bổng EduFlow",
    },
]


@frappe.whitelist()
def get_weekly_matrix():
    """Return the predefined weekly slots matrix."""
    return WEEKLY_MATRIX


@frappe.whitelist()
def generate_weekly_batch(boss_directive=None, target_date=None):
    """Generate 4 weekly posts for the target week based on WEEKLY_MATRIX."""
    # Determine reference date
    if target_date:
        if isinstance(target_date, str):
            clean_date_str = target_date.strip().split(" ")[0].split("T")[0]
            d = datetime.strptime(clean_date_str, "%Y-%m-%d").date()
        elif isinstance(target_date, datetime):
            d = target_date.date()
        elif isinstance(target_date, date):
            d = target_date
        else:
            d = date.today()
    else:
        d = date.today()

    # Determine base Monday date
    base_monday = d - timedelta(days=d.weekday())
    iso_year, iso_week, _ = base_monday.isocalendar()
    batch_id = f"BATCH-{iso_year}-W{iso_week:02d}"

    created_posts = []

    for slot in WEEKLY_MATRIX:
        slot_date = base_monday + timedelta(days=slot["day_offset"])
        scheduled_time = f"{slot_date.isoformat()} {slot['time']}"

        if boss_directive and boss_directive.strip():
            title = f"{slot['default_title']} - {boss_directive.strip()}"
        else:
            title = slot["default_title"]

        doc = frappe.new_doc("Facebook Post")
        doc.title = title
        doc.course = slot["course"]
        doc.status = "Pending Approval"
        doc.batch_id = batch_id
        doc.boss_directive = boss_directive or ""
        doc.day_of_week = slot["day_of_week"]
        doc.scheduled_time = scheduled_time

        doc.insert(ignore_permissions=True)

        if hasattr(doc, "generate_ai_content"):
            try:
                doc.generate_ai_content(user_feedback=boss_directive)
            except Exception as e:
                if hasattr(frappe, "log_error"):
                    frappe.log_error(
                        title="Autopilot AI Content Error",
                        message=str(e),
                    )

        if hasattr(doc, "generate_banner"):
            try:
                doc.generate_banner(user_feedback=boss_directive)
            except Exception as e:
                if hasattr(frappe, "log_error"):
                    frappe.log_error(
                        title="Autopilot Banner Error",
                        message=str(e),
                    )

        created_posts.append(doc)

    return {
        "status": "success",
        "batch_id": batch_id,
        "count": len(created_posts),
        "posts": [p.name for p in created_posts],
    }


@frappe.whitelist()
def approve_weekly_batch(batch_id=None):
    """Approve all Pending Approval posts in target batch (or all batches if batch_id is None)."""
    filters = {"status": "Pending Approval"}
    if batch_id:
        filters["batch_id"] = batch_id

    posts = frappe.get_all("Facebook Post", filters=filters, pluck="name")
    count = 0
    for post in posts:
        name = (
            post
            if isinstance(post, str)
            else (
                post.get("name")
                if isinstance(post, dict)
                else getattr(post, "name", None)
            )
        )
        if name:
            frappe.db.set_value("Facebook Post", name, "status", "Scheduled")
            count += 1

    if hasattr(frappe.db, "commit"):
        frappe.db.commit()

    return {"status": "success", "approved_count": count}


@frappe.whitelist()
def rollback_weekly_batch(batch_id=None, new_directive=None):
    """Cancel pending/scheduled posts in target batch and regenerate a fresh batch."""
    filters = {"status": ["in", ["Pending Approval", "Scheduled"]]}
    if batch_id:
        filters["batch_id"] = batch_id

    posts = frappe.get_all("Facebook Post", filters=filters, pluck="name")
    cancelled_count = 0
    for post in posts:
        name = (
            post
            if isinstance(post, str)
            else (
                post.get("name")
                if isinstance(post, dict)
                else getattr(post, "name", None)
            )
        )
        if name:
            frappe.db.set_value("Facebook Post", name, "status", "Cancelled")
            cancelled_count += 1

    if hasattr(frappe.db, "commit"):
        frappe.db.commit()

    target_date = None
    if batch_id:
        m = re.match(r"BATCH-(\d{4})-W(\d{1,2})", str(batch_id))
        if m:
            target_date = date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)

    new_batch = generate_weekly_batch(
        boss_directive=new_directive, target_date=target_date
    )
    return {
        "status": "success",
        "cancelled_count": cancelled_count,
        "new_batch": new_batch,
    }


@frappe.whitelist()
def recall_post(post_name):
    """Revert a Scheduled post back to Pending Approval."""
    doc = frappe.get_doc("Facebook Post", post_name)
    if getattr(doc, "status", None) == "Scheduled":
        doc.status = "Pending Approval"
        doc.save()
        if hasattr(frappe.db, "commit"):
            frappe.db.commit()
    return {"status": "success", "name": post_name, "status": doc.status}
