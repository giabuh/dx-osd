"""Demo CRM Tasks. Dates are days from today, so a demo on any day shows tasks due today and soon instead of all
overdue; running it again moves the dates of the tasks it created before (matched by title)."""

from datetime import date, timedelta

try:
    import frappe
except ImportError:  # offline tests
    frappe = None


def _day(today, offset, time=""):
    day = (date.fromisoformat(str(today)[:10]) + timedelta(days=offset)).isoformat()
    return f"{day} {time}" if time else day


def demo_tasks(today):
    """The demo tasks with `start_date` / `due_date` worked out from `today` ("start" / "due" are day offsets)."""
    return [{**{k: v for k, v in t.items() if k not in ("start", "due", "due_time")},
             "start_date": _day(today, t["start"]), "due_date": _day(today, t["due"], t["due_time"])} for t in TASKS]


TASKS = [
    {
        "title": "Gọi điện tư vấn lộ trình học cho học viên Hoàng Thành",
        "priority": "High",
        "status": "In Progress",
        "assigned_to": "mai.hcm-bt@demo.saoviet.invalid",
        "start": -1, "due": 0, "due_time": "17:00:00",
        "reference_doctype": "CRM Lead",
        "reference_docname": "CRM-LEAD-2026-00019",
        "description": "<p>Học viên quan tâm khóa <strong>Luyện thi MOS quốc tế</strong>. Cần gọi điện kiểm tra trình độ đầu vào, gửi đề thi thử và xếp lịch học tại cơ sở Bình Thạnh.</p>",
    },
    {
        "title": "Gửi tài liệu & bảng báo giá ưu đãi tháng 9 cho phụ huynh",
        "priority": "High",
        "status": "Todo",
        "assigned_to": "Administrator",
        "start": -1, "due": 1, "due_time": "11:30:00",
        "reference_doctype": "CRM Deal",
        "reference_docname": "CRM-DEAL-2026-00007",
        "description": "<p>Gửi brochure chi tiết khóa học Bơi lội & Toán tư duy, kèm voucher giảm giá 30% qua Zalo/Email cho phụ huynh.</p>",
    },
    {
        "title": "Chuẩn bị phòng học và giáo cụ khai giảng khóa mới (CS Quận 1)",
        "priority": "Medium",
        "status": "Todo",
        "assigned_to": "nam.quan1@eduflow.vn",
        "start": 0, "due": 2, "due_time": "18:00:00",
        "reference_doctype": "CRM Lead",
        "reference_docname": "CRM-LEAD-2026-00027",
        "description": "<p>Kiểm tra hệ thống máy chiếu, bàn ghế và tài liệu in ấn cho lớp Tiếng Anh giao tiếp khai giảng cuối tuần.</p>",
    },
    {
        "title": "Kiểm tra báo cáo chi phí chiến dịch Facebook Ads đợt tuyển sinh tuần 39",
        "priority": "Medium",
        "status": "In Progress",
        "assigned_to": "Administrator",
        "start": -2, "due": 0, "due_time": "15:00:00",
        "reference_doctype": None,
        "reference_docname": None,
        "description": "<p>Rà soát số lượng Lead thu về từ chiến dịch quảng cáo Facebook, đối soát CPL (Cost Per Lead) và tỷ lệ chuyển đổi của các bài viết Fanpage.</p>",
    },
    {
        "title": "Xác nhận hoàn tất thủ tục nhập học & thu học phí đợt 1",
        "priority": "Low",
        "status": "Done",
        "assigned_to": "mai.hcm-bt@demo.saoviet.invalid",
        "start": -3, "due": -2, "due_time": "12:00:00",
        "reference_doctype": "CRM Deal",
        "reference_docname": "CRM-DEAL-2026-00007",
        "description": "<p>Đã cấp mã học viên, xuất hóa đơn điện tử và gửi tin nhắn chào mừng học viên gia nhập hệ thống EduFlow.</p>",
    },
    {
        "title": "Lên kế hoạch nội dung bài viết và banner tuần 40 (Autopilot)",
        "priority": "High",
        "status": "Backlog",
        "assigned_to": "phuc.thuduc@eduflow.vn",
        "start": 1, "due": 4, "due_time": "17:00:00",
        "reference_doctype": None,
        "reference_docname": None,
        "description": "<p>Chỉ đạo AI tạo đợt bài tuần mới BATCH-2026-W40 với chủ đề: 'Tuần lễ vàng học thử miễn phí'.</p>",
    },
]


@frappe.whitelist() if frappe else (lambda fn: fn)
def seed_tasks():
    created, moved = [], []
    for t in demo_tasks(frappe.utils.today()):
        existing = frappe.db.get_value("CRM Task", {"title": t["title"]})
        if existing:
            frappe.db.set_value("CRM Task", existing, {"start_date": t["start_date"], "due_date": t["due_date"]},
                                update_modified=False)
            moved.append(existing)
            continue
        doc = frappe.get_doc({"doctype": "CRM Task", **t})
        doc.insert(ignore_permissions=True)
        created.append(doc.name)

    frappe.db.commit()
    return {"status": "success", "created": created, "count": len(created), "moved": moved}


@frappe.whitelist() if frappe else (lambda fn: fn)
def remove_duplicate_mai():
    old_email = "mai.binhthanh@eduflow.vn"
    new_email = "mai.hcm-bt@demo.saoviet.invalid"

    # 1. CRM Task
    tasks = frappe.get_all("CRM Task", filters={"assigned_to": old_email}, pluck="name")
    for t in tasks:
        frappe.db.set_value("CRM Task", t, "assigned_to", new_email, update_modified=False)

    # 2. CRM Deal
    deals = frappe.get_all("CRM Deal", filters={"deal_owner": old_email}, pluck="name")
    for d in deals:
        frappe.db.set_value("CRM Deal", d, "deal_owner", new_email, update_modified=False)

    # 3. CRM Lead
    leads = frappe.get_all("CRM Lead", filters={"lead_owner": old_email}, pluck="name")
    for l in leads:
        frappe.db.set_value("CRM Lead", l, "lead_owner", new_email, update_modified=False)

    # 4. ToDo
    todos = frappe.get_all("ToDo", filters={"allocated_to": old_email}, pluck="name")
    for td in todos:
        frappe.db.set_value("ToDo", td, "allocated_to", new_email, update_modified=False)

    # 5. CRM Notification
    notifs = frappe.get_all("CRM Notification", filters={"to_user": old_email}, pluck="name")
    for n in notifs:
        frappe.db.set_value("CRM Notification", n, "to_user", new_email, update_modified=False)

    # 6. Delete old User doc
    deleted_user = False
    if frappe.db.exists("User", old_email):
        frappe.db.delete("Has Role", {"parent": old_email})
        frappe.db.delete("User", {"name": old_email})
        deleted_user = True

    frappe.db.commit()
    return {
        "status": "success",
        "tasks_reassigned": len(tasks),
        "deals_reassigned": len(deals),
        "leads_reassigned": len(leads),
        "todos_reassigned": len(todos),
        "notifications_reassigned": len(notifs),
        "deleted_user": deleted_user,
    }
