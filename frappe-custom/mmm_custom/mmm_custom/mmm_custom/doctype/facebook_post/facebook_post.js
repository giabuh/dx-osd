// Copyright (c) 2026, MMM and contributors
// For license information, please see license.txt

frappe.ui.form.on("Facebook Post", {
	refresh: function (frm) {
		// If not already posted, show AI generation and publishing buttons
		if (frm.doc.status !== "Posted") {
			frm.add_custom_button(__("🤖 AI Viết nội dung"), function () {
				if (!frm.doc.course) {
					frappe.msgprint(__("Vui lòng chọn Khóa học trước khi yêu cầu AI viết bài."));
					return;
				}

				frappe.show_alert({ message: __("Đang nhờ Gemini AI soạn bài..."), indicator: "blue" });

				frm.call({
					method: "generate_ai_content",
					doc: frm.doc,
					freeze: true,
					freeze_message: __("Gemini AI đang viết bài đăng..."),
					callback: function (r) {
						if (r.message && r.message.status === "success") {
							frm.set_value("content", r.message.content);
							frappe.show_alert({ message: __("Đã tạo nội dung bài viết thành công!"), indicator: "green" });
						}
					}
				});
			}, __("Thao tác"));

			frm.add_custom_button(__("🎨 Tạo banner"), function () {
				if (!frm.doc.course) {
					frappe.msgprint(__("Vui lòng chọn Khóa học trước khi tạo banner."));
					return;
				}

				let doGenerateBanner = function () {
					frm.call({
						method: "generate_banner",
						doc: frm.doc,
						freeze: true,
						freeze_message: __("Đang thiết kế banner tự động..."),
						callback: function (r) {
							if (r.message && r.message.status === "success") {
								frm.set_value("image", r.message.image);
								frappe.show_alert({ message: __("Đã tạo banner Facebook thành công!"), indicator: "green" });
							}
						}
					});
				};

				if (frm.is_new()) {
					frm.save().then(doGenerateBanner);
				} else {
					doGenerateBanner();
				}
			}, __("Thao tác"));

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
		}

		// If posted, show view on Facebook button
		if (frm.doc.status === "Posted" && frm.doc.fb_post_url) {
			frm.add_custom_button(__("🔗 Xem trên Facebook"), function () {
				window.open(frm.doc.fb_post_url, "_blank");
			}).addClass("btn-info");
		}
	}
});
