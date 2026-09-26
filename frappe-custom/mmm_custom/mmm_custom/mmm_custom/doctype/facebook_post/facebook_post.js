// Copyright (c) 2026, MMM and contributors
// For license information, please see license.txt

frappe.ui.form.on("Facebook Post", {
	refresh: function (frm) {
		// If not already posted, show AI generation and publishing buttons
		if (frm.doc.status !== "Posted") {
			frm.add_custom_button(__("🤖 AI Viết nội dung"), function () {
				frappe.show_alert({ message: __("Đang nhờ Gemini AI soạn bài..."), indicator: "blue" });
				frm.call({
					method: "generate_ai_content",
					doc: frm.doc,
					freeze: true,
					freeze_message: __("Gemini AI đang viết bài đăng..."),
					callback: function (r) {
						if (r.message && r.message.status === "success") {
							frm.reload_doc();
							frappe.show_alert({ message: __("Đã tạo nội dung bài viết thành công!"), indicator: "green" });
						}
					}
				});
			}, __("Thao tác"));

			frm.add_custom_button(__("🎨 Tạo banner"), function () {
				frm.call({
					method: "generate_banner",
					doc: frm.doc,
					freeze: true,
					freeze_message: __("Đang thiết kế banner tự động..."),
					callback: function (r) {
						if (r.message && r.message.status === "success") {
							frm.reload_doc();
							frappe.show_alert({ message: __("Đã tạo banner Facebook thành công!"), indicator: "green" });
						}
					}
				});
			}, __("Thao tác"));

			frm.add_custom_button(__("🚀 Đăng ngay lên Fanpage"), function () {
				frappe.confirm(
					__("Bạn có chắc chắn muốn đăng bài viết này lên Fanpage ngay bây giờ không?"),
					function () {
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
