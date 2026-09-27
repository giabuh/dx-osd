import frappe

@frappe.whitelist()
def seed_tasks():
    tasks = [
        {
            "title": "Gọi điện tư vấn lộ trình học cho học viên Hoàng Thành",
            "priority": "High",
            "status": "In Progress",
            "assigned_to": "mai.hcm-bt@demo.saoviet.invalid",
            "start_date": "2026-09-27",
            "due_date": "2026-09-28 17:00:00",
            "reference_doctype": "CRM Lead",
            "reference_docname": "CRM-LEAD-2026-00019",
            "description": "<p>Học viên quan tâm khóa <strong>Luyện thi MOS quốc tế</strong>. Cần gọi điện kiểm tra trình độ đầu vào, gửi đề thi thử và xếp lịch học tại cơ sở Bình Thạnh.</p>",
        },
        {
            "title": "Gửi tài liệu & bảng báo giá ưu đãi tháng 9 cho phụ huynh",
            "priority": "High",
            "status": "Todo",
            "assigned_to": "Administrator",
            "start_date": "2026-09-27",
            "due_date": "2026-09-29 11:30:00",
            "reference_doctype": "CRM Deal",
            "reference_docname": "CRM-DEAL-2026-00007",
            "description": "<p>Gửi brochure chi tiết khóa học Bơi lội & Toán tư duy, kèm voucher giảm giá 30% qua Zalo/Email cho phụ huynh.</p>",
        },
        {
            "title": "Chuẩn bị phòng học và giáo cụ khai giảng khóa mới (CS Quận 1)",
            "priority": "Medium",
            "status": "Todo",
            "assigned_to": "nam.quan1@eduflow.vn",
            "start_date": "2026-09-28",
            "due_date": "2026-09-30 18:00:00",
            "reference_doctype": "CRM Lead",
            "reference_docname": "CRM-LEAD-2026-00027",
            "description": "<p>Kiểm tra hệ thống máy chiếu, bàn ghế và tài liệu in ấn cho lớp Tiếng Anh giao tiếp khai giảng cuối tuần.</p>",
        },
        {
            "title": "Kiểm tra báo cáo chi phí chiến dịch Facebook Ads đợt tuyển sinh tuần 39",
            "priority": "Medium",
            "status": "In Progress",
            "assigned_to": "Administrator",
            "start_date": "2026-09-26",
            "due_date": "2026-09-28 15:00:00",
            "reference_doctype": None,
            "reference_docname": None,
            "description": "<p>Rà soát số lượng Lead thu về từ chiến dịch quảng cáo Facebook, đối soát CPL (Cost Per Lead) và tỷ lệ chuyển đổi của các bài viết Fanpage.</p>",
        },
        {
            "title": "Xác nhận hoàn tất thủ tục nhập học & thu học phí đợt 1",
            "priority": "Low",
            "status": "Done",
            "assigned_to": "mai.hcm-bt@demo.saoviet.invalid",
            "start_date": "2026-09-25",
            "due_date": "2026-09-26 12:00:00",
            "reference_doctype": "CRM Deal",
            "reference_docname": "CRM-DEAL-2026-00007",
            "description": "<p>Đã cấp mã học viên, xuất hóa đơn điện tử và gửi tin nhắn chào mừng học viên gia nhập hệ thống EduFlow.</p>",
        },
        {
            "title": "Lên kế hoạch nội dung bài viết và banner tuần 40 (Autopilot)",
            "priority": "High",
            "status": "Backlog",
            "assigned_to": "phuc.thuduc@eduflow.vn",
            "start_date": "2026-09-29",
            "due_date": "2026-10-02 17:00:00",
            "reference_doctype": None,
            "reference_docname": None,
            "description": "<p>Chỉ đạo AI tạo đợt bài tuần mới BATCH-2026-W40 với chủ đề: 'Tuần lễ vàng học thử miễn phí'.</p>",
        },
    ]

    created = []
    for t in tasks:
        if frappe.db.exists("CRM Task", {"title": t["title"]}):
            continue
        doc = frappe.get_doc({
            "doctype": "CRM Task",
            **t
        })
        doc.insert(ignore_permissions=True)
        created.append(doc.name)

    frappe.db.commit()
    return {"status": "success", "created": created, "count": len(created)}


@frappe.whitelist()
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
