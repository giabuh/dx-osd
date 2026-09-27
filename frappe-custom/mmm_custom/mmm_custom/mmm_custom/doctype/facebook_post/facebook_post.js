// Copyright (c) 2026, MMM and contributors
// For license information, please see license.txt

frappe.ui.form.on("Facebook Post", {
	refresh: function (frm) {
		// 1. Content Generation / Regeneration Button (ALWAYS AVAILABLE regardless of status)
		let content_btn_label = frm.doc.content ? __("🔄 AI Viết lại nội dung") : __("🤖 AI Viết nội dung");
		frm.add_custom_button(content_btn_label, function () {
			if (!frm.doc.course) {
				frappe.msgprint(__("Vui lòng chọn Khóa học trước khi yêu cầu AI viết bài."));
				return;
			}

			let runGenerateContent = function (feedback) {
				frappe.show_alert({ message: __("Đang nhờ Gemini AI soạn bài..."), indicator: "blue" });
				frm.call({
					method: "generate_ai_content",
					doc: frm.doc,
					args: { user_feedback: feedback || "" },
					freeze: true,
					freeze_message: __("Gemini AI đang viết lại bài theo gợi ý của bạn..."),
					callback: function (r) {
						if (r.message && r.message.status === "success") {
							frm.set_value("content", r.message.content);
							if (feedback) {
								frm.set_value("ai_feedback", feedback);
							}
							frappe.show_alert({
								message: __("Đã tạo nội dung bài viết thành công! Bấm lại nút nếu bạn muốn gợi ý để AI sửa lại."),
								indicator: "green"
							});
						}
					}
				});
			};

			if (frm.doc.content) {
				frappe.prompt(
					[
						{
							fieldname: "feedback",
							fieldtype: "Small Text",
							label: __("Gợi ý / Yêu cầu điều chỉnh cho AI"),
							default: frm.doc.ai_feedback || "",
							description: __(
								"Ví dụ: 'Nhấn mạnh giảm 40%', 'Văn phong trẻ trung hơn', 'Tập trung cơ sở Bình Thạnh'..."
							)
						}
					],
					function (values) {
						runGenerateContent(values.feedback);
					},
					__("Gợi ý để AI viết lại bài viết"),
					__("AI Viết lại")
				);
			} else {
				runGenerateContent(frm.doc.ai_feedback || "");
			}
		});

		// 2. Banner Generation / Regeneration Button (ALWAYS AVAILABLE regardless of status)
		let banner_btn_label = frm.doc.image ? __("🎨 Vẽ lại banner") : __("🎨 Tạo banner");
		frm.add_custom_button(banner_btn_label, function () {
			if (!frm.doc.course) {
				frappe.msgprint(__("Vui lòng chọn Khóa học trước khi tạo banner."));
				return;
			}

			let runGenerateBanner = function (feedback) {
				let doGenerateBanner = function () {
					frm.call({
						method: "generate_banner",
						doc: frm.doc,
						args: { user_feedback: feedback || "" },
						freeze: true,
						freeze_message: __("Đang thiết kế banner tự động..."),
						callback: function (r) {
							if (r.message && r.message.status === "success") {
								frm.set_value("image", r.message.image);
								if (feedback) {
									frm.set_value("ai_feedback", feedback);
								}
								frappe.show_alert({
									message: __("Đã tạo banner Facebook thành công! Bấm lại nút nếu bạn muốn gợi ý để thiết kế lại."),
									indicator: "green"
								});
							}
						}
					});
				};

				if (frm.is_new()) {
					frm.save().then(doGenerateBanner);
				} else {
					doGenerateBanner();
				}
			};

			if (frm.doc.image) {
				frappe.prompt(
					[
						{
							fieldname: "feedback",
							fieldtype: "Data",
							label: __("Ưu đãi / Gợi ý hiển thị trên banner"),
							default: frm.doc.ai_feedback || "",
							description: __(
								"Ví dụ: 'GIẢM 50% HÈ NÀY', 'TẶNG BALO VÀ BÌNH NƯỚC', 'HỌC THỬ MIỄN PHÍ'..."
							)
						}
					],
					function (values) {
						runGenerateBanner(values.feedback);
					},
					__("Gợi ý để vẽ lại banner"),
					__("Vẽ lại banner")
				);
			} else {
				runGenerateBanner(frm.doc.ai_feedback || "");
			}
		});

		// Autopilot approval / recall actions
		if (frm.doc.status === "Pending Approval") {
			frm.add_custom_button(__("✅ Duyệt bài này"), function () {
				frm.set_value("status", "Scheduled");
				frm.save();
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Scheduled") {
			frm.add_custom_button(__("⏪ Thu hồi lịch đăng"), function () {
				frappe.confirm(
					__("Bạn có chắc muốn thu hồi lịch đăng bài viết này về trạng thái Chờ duyệt không?"),
					function () {
						frappe.call({
							method: "mmm_custom.autopilot.recall_post",
							args: {
								post_name: frm.doc.name
							},
							freeze: true,
							freeze_message: __("Đang thu hồi lịch đăng..."),
							callback: function (r) {
								if (r.message && r.message.status === "success") {
									frm.reload_doc();
									frappe.show_alert({
										message: __("Đã thu hồi lịch đăng bài viết thành công."),
										indicator: "green"
									});
								}
							}
						});
					}
				);
			}).addClass("btn-warning");
		}

		// 3. Publishing and action buttons depending on status
		if (frm.doc.status !== "Posted") {
			frm.add_custom_button(__("🚀 Đăng ngay lên Fanpage"), function () {
				if (!frm.doc.content) {
					frappe.msgprint(__("Vui lòng nhập hoặc tạo nội dung bài viết trước khi đăng."));
					return;
				}

				frappe.confirm(
					__("Bạn có chắc chắn muốn đăng bài viết này lên Fanpage ngay bây giờ không?"),
					function () {
						let doPublish = function () {
							frm.call({
								method: "post_now",
								doc: frm.doc,
								freeze: true,
								freeze_message: __("Đang đẩy bài lên Facebook..."),
								callback: function (r) {
									if (r.message && r.message.status === "success") {
										frm.reload_doc();
									}
								}
							});
						};

						if (frm.is_new() || frm.is_dirty()) {
							frm.save().then(doPublish);
						} else {
							doPublish();
						}
					}
				);
			}).addClass("btn-primary");
		} else {
			// When status is "Posted"
			if (frm.doc.fb_post_url) {
				frm.add_custom_button(__("🔗 Xem trên Facebook"), function () {
					window.open(frm.doc.fb_post_url, "_blank");
				}).addClass("btn-info");
			}

			frm.add_custom_button(__("🚀 Đăng thành bài mới"), function () {
				if (!frm.doc.content) {
					frappe.msgprint(__("Vui lòng nhập hoặc tạo nội dung bài viết trước khi đăng."));
					return;
				}

				frappe.confirm(
					__("Bạn có muốn đăng nội dung/hình ảnh mới chỉnh sửa này thành một bài viết mới trên Fanpage không?"),
					function () {
						let doPublish = function () {
							frm.call({
								method: "post_now",
								doc: frm.doc,
								freeze: true,
								freeze_message: __("Đang đăng bài mới lên Facebook..."),
								callback: function (r) {
									if (r.message && r.message.status === "success") {
										frm.reload_doc();
									}
								}
							});
						};

						if (frm.is_new() || frm.is_dirty()) {
							frm.save().then(doPublish);
						} else {
							doPublish();
						}
					}
				);
			}).addClass("btn-primary");

			frm.add_custom_button(__("📝 Chuyển về Bản nháp"), function () {
				frappe.confirm(
					__("Bạn có muốn chuyển trạng thái bài viết này về 'Bản nháp' để tiếp tục chỉnh sửa hoặc lên lịch lại không?"),
					function () {
						frm.set_value("status", "Draft");
						frm.set_value("fb_post_id", "");
						frm.set_value("fb_post_url", "");
						frm.save();
						frappe.show_alert({ message: __("Đã chuyển bài viết về Bản nháp."), indicator: "green" });
					}
				);
			});
		}
	}
});
