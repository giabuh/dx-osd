// Copyright (c) 2026, MMM and contributors
// For license information, please see license.txt

frappe.listview_settings["Facebook Post"] = {
	add_fields: ["status", "course", "scheduled_time", "batch_id"],
	get_indicator: function (doc) {
		if (doc.status === "Draft") {
			return [__("Bản nháp"), "gray", "status,=,Draft"];
		} else if (doc.status === "Pending Approval") {
			return [__("Chờ duyệt"), "orange", "status,=,Pending Approval"];
		} else if (doc.status === "Scheduled") {
			return [__("Đã lên lịch"), "blue", "status,=,Scheduled"];
		} else if (doc.status === "Posted") {
			return [__("Đã đăng"), "green", "status,=,Posted"];
		} else if (doc.status === "Failed") {
			return [__("Lỗi"), "red", "status,=,Failed"];
		} else if (doc.status === "Cancelled") {
			return [__("Đã hủy"), "darkgray", "status,=,Cancelled"];
		}
		return [__("Bản nháp"), "gray", "status,=,Draft"];
	},
	onload: function (listview) {
		// 1. Agent: Lên kế hoạch tuần
		listview.page.add_inner_button(__("🤖 Agent: Lên kế hoạch tuần"), function () {
			frappe.prompt(
				[
					{
						fieldname: "boss_directive",
						fieldtype: "Small Text",
						label: __("Chỉ đạo của Giám đốc cho tuần này (Tùy chọn)"),
						description: __(
							'Ví dụ: "Tuần này tập trung xả ưu đãi Bơi lội 50%", "Nhấn mạnh khai giảng lớp Toán tháng 10"...'
						)
					}
				],
				function (values) {
					frappe.show_alert({
						message: __("Agent đang lên kế hoạch và tạo bài viết cho cả tuần..."),
						indicator: "blue"
					});
					frappe.call({
						method: "mmm_custom.autopilot.generate_weekly_batch",
						args: {
							boss_directive: values.boss_directive || ""
						},
						freeze: true,
						freeze_message: __("Agent đang tự động tạo 4 bài viết và thiết kế banner..."),
						callback: function (r) {
							if (r.message && r.message.status === "success") {
								frappe.show_alert({
									message: __("Đã tạo kế hoạch tuần thành công!"),
									indicator: "green"
								});
								listview.refresh();
							}
						}
					});
				},
				__("Lên kế hoạch tuần tự động"),
				__("Tạo kế hoạch")
			);
		});

		// 2. Duyệt tất cả tuần này
		let approve_btn = listview.page.add_inner_button(
			__("✅ Duyệt tất cả tuần này"),
			function () {
				frappe.confirm(
					__(
						"Bạn có chắc chắn muốn duyệt và lên lịch tự động cho toàn bộ bài viết đang chờ duyệt không?"
					),
					function () {
						frappe.call({
							method: "mmm_custom.autopilot.approve_weekly_batch",
							freeze: true,
							freeze_message: __("Đang duyệt và lên lịch toàn bộ bài viết..."),
							callback: function (r) {
								if (r.message && r.message.status === "success") {
									frappe.show_alert({
										message: __("Đã duyệt tất cả bài viết thành công!"),
										indicator: "green"
									});
									listview.refresh();
								}
							}
						});
					}
				);
			},
			null,
			"primary"
		);
		if (approve_btn) {
			approve_btn.addClass("btn-primary");
		}

		// 3. Làm lại cả tuần
		listview.page.add_inner_button(__("🔄 Làm lại cả tuần"), function () {
			frappe.prompt(
				[
					{
						fieldname: "new_directive",
						fieldtype: "Small Text",
						label: __("Góp ý / Yêu cầu điều chỉnh lại cho Agent"),
						description: __(
							"Agent sẽ thu hồi các bài chờ duyệt cũ và tạo lại 1 bộ 4 bài mới theo chỉ đạo này."
						)
					}
				],
				function (values) {
					frappe.show_alert({
						message: __("Agent đang thu hồi bài cũ và tạo lại bộ bài mới..."),
						indicator: "blue"
					});
					frappe.call({
						method: "mmm_custom.autopilot.rollback_weekly_batch",
						args: {
							new_directive: values.new_directive || ""
						},
						freeze: true,
						freeze_message: __("Đang làm lại toàn bộ kế hoạch tuần..."),
						callback: function (r) {
							if (r.message && r.message.status === "success") {
								frappe.show_alert({
									message: __("Đã làm lại toàn bộ kế hoạch tuần thành công!"),
									indicator: "green"
								});
								listview.refresh();
							}
						}
					});
				},
				__("Yêu cầu Agent làm lại cả tuần"),
				__("Làm lại")
			);
		});
	}
};
