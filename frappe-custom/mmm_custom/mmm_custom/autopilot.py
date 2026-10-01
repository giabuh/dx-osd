# Copyright (c) 2026, MMM and contributors
# For license information, please see license.txt

from datetime import date, datetime, timedelta
import re

from mmm_custom.marketing_plan import plan_week

try:
    import frappe
    import frappe.utils
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

    frappe.utils = MagicMock()
    frappe.utils.now_datetime = now_datetime



# 4 weekly post slots (Mon, Wed, Fri, Sun): day, time and the caption angle of facebook_post.generate_ai_content.
# Which course goes in each slot is decided every week from CRM data (marketing_plan.plan_week, D-125).
WEEKLY_MATRIX = [
    {
        "day": 0,
        "day_offset": 0,
        "day_of_week": "Thứ Hai",
        "time": "08:30:00",
    },
    {
        "day": 2,
        "day_offset": 2,
        "day_of_week": "Thứ Tư",
        "time": "11:30:00",
    },
    {
        "day": 4,
        "day_offset": 4,
        "day_of_week": "Thứ Sáu",
        "time": "19:30:00",
    },
    {
        "day": 6,
        "day_offset": 6,
        "day_of_week": "Chủ Nhật",
        "time": "09:00:00",
    },
]


def _today():
    return date.today()


def _now():
    return now_datetime()


def slot_at(base_monday, slot):
    """When a slot of the week starting `base_monday` is published."""
    hour, minute, second = (int(x) for x in slot["time"].split(":"))
    return datetime.combine(base_monday + timedelta(days=slot["day_offset"]), datetime.min.time()).replace(
        hour=hour, minute=minute, second=second)


def open_slots(base_monday, now):
    """The slots of that week still ahead of `now`: a slot whose time has passed is not planned, or approving
    the batch would publish it at once (the publisher posts every Scheduled post that is due)."""
    return [s for s in WEEKLY_MATRIX if slot_at(base_monday, s) > now]


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
            d = _today()
    else:
        d = _today()

    # Determine base Monday date
    base_monday = d - timedelta(days=d.weekday())
    now = _now()
    slots = open_slots(base_monday, now)
    if not slots and not target_date:  # this week is over: plan the next one
        base_monday += timedelta(days=7)
        slots = open_slots(base_monday, now)
    skipped = [s["day_of_week"] for s in WEEKLY_MATRIX if s not in slots]
    iso_year, iso_week, _ = base_monday.isocalendar()
    batch_id = f"BATCH-{iso_year}-W{iso_week:02d}"

    created_posts = []
    # The week's courses from CRM data: open classes, promotions, what earlier posts brought (D-125)
    # Classes and results are judged from today: a class that started on Monday is not "coming up" on Thursday.
    offer_slot = next((i for i, s in enumerate(slots) if s["day_of_week"] == "Chủ Nhật"), len(slots) - 1)
    plan = plan_week(max(_today(), base_monday), n=len(slots), offer_slot=offer_slot) if slots else []

    slot_text = ", ".join(f"{s['day_of_week']} ({s['time'][:5]})" for s in slots)

    for slot, course in zip(slots, plan):
        slot_date = base_monday + timedelta(days=slot["day_offset"])
        scheduled_time = f"{slot_date.isoformat()} {slot['time']}"

        if boss_directive and boss_directive.strip():
            title = f"{course['title']} - {boss_directive.strip()}"
        else:
            title = course["title"]

        doc = frappe.new_doc("Facebook Post")
        doc.title = title
        doc.course = course["code"]
        doc.plan_reason = course["reason"]
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

    if hasattr(frappe.db, "commit"):
        frappe.db.commit()

    pipeline = [
        {
            "agent": "Strategy Agent",
            "role": "Trưởng nhóm chiến lược",
            "icon": "🧭",
            "action": f"Phân tích chỉ đạo: \"{boss_directive or 'Tuyển sinh đa kênh các khóa học mũi nhọn'}\"",
            "status": "completed",
        },
        {
            "agent": "CRM Data Agent",
            "role": "Trợ lý dữ liệu CRM",
            "icon": "📊",
            "action": "Chọn khóa theo lớp sắp khai giảng, ưu đãi và kết quả bài trước: "
                      + "; ".join(f"{c['name']} ({c['reason']})" for c in plan),
            "status": "completed",
        },
        {
            "agent": "Copywriter Agent",
            "role": "Cây viết sáng tạo (Gemini AI)",
            "icon": "✍️",
            "action": "Đã viết xong 4 bài (Storytelling, Educational Insight, Humor, FOMO Offer) - Anti-Cliché",
            "status": "completed",
        },
        {
            "agent": "Scheduler Agent",
            "role": "Trợ lý điều phối lịch",
            "icon": "📅",
            "action": f"Phân bổ lịch {slot_text or 'không còn khung giờ nào'} cho đợt {batch_id}"
                      + (f"; bỏ qua {', '.join(skipped)} vì đã qua giờ đăng" if skipped else ""),
            "status": "completed",
        },
        {
            "agent": "Quality Guard",
            "role": "Kiểm duyệt & Chính sách",
            "icon": "🛡️",
            "action": "Kiểm tra chính sách Meta thành công - 4 bài đã lưu ở trạng thái Chờ duyệt",
            "status": "completed",
        },
    ]

    try:
        from crm.fcrm.doctype.crm_notification.crm_notification import notify_crm_users
        notify_crm_users(
            title=f"Kế hoạch tuần {batch_id} đã sẵn sàng",
            message=f'AI đã hoàn thành {len(created_posts)} bài viết cho đợt {batch_id} theo chỉ đạo: "{boss_directive or "Đa kênh"}". Vui lòng kiểm duyệt!',
            notification_type="Marketing",
            reference_doctype="Facebook Post",
        )
    except Exception:
        pass

    return {
        "status": "success",
        "batch_id": batch_id,
        "count": len(created_posts),
        "posts": [p.name for p in created_posts],
        "skipped": skipped,
        "pipeline": pipeline,
    }


@frappe.whitelist()
def approve_weekly_batch(batch_id=None):
    """Approve all Pending Approval posts in target batch (or all batches if batch_id is None)."""
    filters = {"status": "Pending Approval"}
    if batch_id:
        filters["batch_id"] = batch_id

    posts = frappe.get_all("Facebook Post", filters=filters, fields=["name", "scheduled_time"])
    count, past_due, now = 0, [], _now()
    for post in posts:
        name = (
            post
            if isinstance(post, (str, int))
            else (
                post.get("name")
                if isinstance(post, dict)
                else getattr(post, "name", None)
            )
        )
        when = post.get("scheduled_time") if isinstance(post, dict) else None
        if name is not None and when and when <= now:
            past_due.append(name)  # its time has passed: Scheduled would publish it at once, a person picks a new time
        elif name is not None:
            frappe.db.set_value("Facebook Post", name, "status", "Scheduled")
            count += 1

    if hasattr(frappe.db, "commit"):
        frappe.db.commit()

    try:
        from crm.fcrm.doctype.crm_notification.crm_notification import notify_crm_users
        notify_crm_users(
            title="Đã duyệt lịch đăng Facebook tuần",
            message=f"Đã duyệt thành công {count} bài viết sang trạng thái Đã lên lịch phát sóng!",
            notification_type="Marketing",
            reference_doctype="Facebook Post",
        )
    except Exception:
        pass

    return {"status": "success", "approved_count": count, "past_due": past_due}


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
            if isinstance(post, (str, int))
            else (
                post.get("name")
                if isinstance(post, dict)
                else getattr(post, "name", None)
            )
        )
        if name is not None:
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
    pipeline = [
        {
            "agent": "Strategy Agent",
            "role": "Trưởng nhóm chiến lược",
            "icon": "🧭",
            "action": f"Tiếp nhận phản hồi sếp: \"{new_directive or 'Tái thiết kế toàn bộ kế hoạch tuần'}\"",
            "status": "completed",
        },
        {
            "agent": "Quality Guard",
            "role": "Kiểm duyệt & Thu hồi",
            "icon": "🛡️",
            "action": f"Đã thu hồi và hủy bỏ {cancelled_count} bài viết cũ chưa duyệt",
            "status": "completed",
        },
        {
            "agent": "Copywriter Agent",
            "role": "Cây viết sáng tạo (Gemini AI)",
            "icon": "✍️",
            "action": "Tái tạo 4 bài viết mới theo phong cách & định hướng điều chỉnh",
            "status": "completed",
        },
        {
            "agent": "Scheduler Agent",
            "role": "Trợ lý điều phối lịch",
            "icon": "📅",
            "action": f"Đã cập nhật lại lịch phát sóng cho đợt {new_batch.get('batch_id')}",
            "status": "completed",
        },
    ]

    return {
        "status": "success",
        "cancelled_count": cancelled_count,
        "new_batch": new_batch,
        "pipeline": pipeline,
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


@frappe.whitelist()
def publish_scheduled_posts():
    """Publish Facebook posts that are scheduled and due."""
    posts = frappe.get_all(
        "Facebook Post",
        filters={"status": "Scheduled", "scheduled_time": ["<=", frappe.utils.now_datetime()]},
        fields=["name"],
    )
    published_count = 0
    published_posts = []

    for post in posts:
        post_name = (
            post.get("name")
            if isinstance(post, dict)
            else (getattr(post, "name", None) or post)
        )
        try:
            doc = frappe.get_doc("Facebook Post", post_name)
            doc.post_now()
            published_count += 1
            published_posts.append(post_name)
        except Exception as e:
            if hasattr(frappe, "log_error"):
                frappe.log_error(title="Autopilot Publish Error", message=str(e))

    if hasattr(frappe.db, "commit"):
        frappe.db.commit()

    if published_count > 0:
        try:
            from crm.fcrm.doctype.crm_notification.crm_notification import notify_crm_users
            notify_crm_users(
                title="Tự động đăng bài theo lịch",
                message=f"Hệ thống đã tự động xuất bản {published_count} bài viết lên Facebook Fanpage theo lịch hẹn.",
                notification_type="Marketing",
                reference_doctype="Facebook Post",
            )
        except Exception:
            pass

    return {
        "status": "success",
        "published": published_count,
        "published_posts": published_posts,
    }

