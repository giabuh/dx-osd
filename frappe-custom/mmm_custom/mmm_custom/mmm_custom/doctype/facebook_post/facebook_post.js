// Copyright (c) 2026, MMM and contributors
// For license information, please see license.txt

frappe.ui.form.on("Facebook Post", {
	refresh: function (frm) {
		// 1. Content Generation / Regeneration Button (ALWAYS AVAILABLE regardless of status)
		let content_btn_label = frm.doc.content ? __("AI viết lại nội dung") : __("AI viết nội dung");
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
								message: __("Đã tạo nội dung bài viết thành công!"),
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
		let banner_btn_label = frm.doc.image ? __("Tạo lại banner") : __("Tạo banner");
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
			frm.add_custom_button(__("Duyệt bài này"), function () {
				frm.set_value("status", "Scheduled");
				frm.save();
			}).addClass("btn-primary");
		}

		if (frm.doc.status === "Scheduled") {
			frm.add_custom_button(__("Thu hồi lịch đăng"), function () {
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
			frm.add_custom_button(__("Đăng ngay lên Fanpage"), function () {
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
				frm.add_custom_button(__("Xem trên Facebook"), function () {
					window.open(frm.doc.fb_post_url, "_blank");
				}).addClass("btn-info");
			}

			frm.add_custom_button(__("Đề xuất chạy Ads (AI)"), function () {
				open_ai_ads_advice_dialog(frm);
			}).addClass("btn-warning");

			frm.add_custom_button(__("Cập nhật số liệu"), function () {
				frappe.show_alert({ message: __("Đang lấy số liệu tương tác từ Facebook..."), indicator: "blue" });
				frm.call({
					method: "sync_analytics",
					doc: frm.doc,
					freeze: true,
					freeze_message: __("Đang đồng bộ số liệu Facebook..."),
					callback: function (r) {
						if (r.message && r.message.status === "success") {
							frm.reload_doc();
							frappe.show_alert({
								message: __(
									`Đã cập nhật: ${r.message.likes} Thích, ${r.message.comments} Bình luận, ${r.message.shares} Chia sẻ, ${r.message.leads} Khách tiềm năng`
								),
								indicator: "green"
							});
						}
					}
				});
			}).addClass("btn-secondary");

			frm.add_custom_button(__("Đồng bộ bình luận"), function () {
				frappe.show_alert({ message: __("Đang tải danh sách bình luận từ Facebook..."), indicator: "blue" });
				frm.call({
					method: "sync_comments",
					doc: frm.doc,
					freeze: true,
					freeze_message: __("Đang đồng bộ bình luận Facebook..."),
					callback: function (r) {
						if (r.message && r.message.status === "success") {
							frm.reload_doc();
							frappe.show_alert({
								message: __(`Đã đồng bộ thành công ${r.message.count} bình luận từ Facebook!`),
								indicator: "green"
							});
						}
					}
				});
			}).addClass("btn-secondary");

			frm.add_custom_button(__("Đăng thành bài mới"), function () {
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

			frm.add_custom_button(__("Chuyển về Bản nháp"), function () {
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

/**
 * Open the AI Ads Recommendation Dialog
 * Displays score, verdict badge, target persona, budget plan, and optimization tips.
 */
function open_ai_ads_advice_dialog(frm) {
	frappe.show_alert({
		message: __("Đang phân tích tương tác & tạo kế hoạch Meta Ads..."),
		indicator: "blue"
	});

	frm.call({
		method: "get_ai_ads_advice",
		doc: frm.doc,
		freeze: true,
		freeze_message: __("AI đang phân tích tiềm năng chạy Ads và lên kế hoạch mục tiêu, ngân sách..."),
		callback: function (r) {
			if (!r.message || r.message.status !== "success") {
				frappe.msgprint(__("Không thể tạo tư vấn Ads: {0}", [r.message ? r.message.message : "Lỗi"]));
				return;
			}

			let adv = r.message;
			let rec = adv.recommendation;
			let is_recommended = rec === "Recommended";
			let is_review = rec === "Review";

			let badge_color = is_recommended ? "#03543F" : (is_review ? "#854D0E" : "#4B5563");
			let badge_bg = is_recommended ? "#DEF7EC" : (is_review ? "#FEF08A" : "#F3F4F6");
			let badge_border = is_recommended ? "#31C48D" : (is_review ? "#FACC15" : "#D1D5DB");
			let badge_icon = is_recommended ? "🔥" : (is_review ? "⚡" : "⏳");
			let badge_text = is_recommended
				? "KHUYÊN CHẠY ADS (Tiềm năng cao)"
				: (is_review ? "CÂN NHẮC / TEST THỬ (Tiềm năng vừa)" : "CHƯA NÊN CHẠY (Cần tối ưu bài viết)");

			let d = new frappe.ui.Dialog({
				title: `<div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
					<div style="display: flex; align-items: center; gap: 8px;">
						<span style="font-size: 18px;">🎯</span>
						<span style="font-weight: 700; font-size: 15px;">Đề xuất Chạy Quảng cáo Facebook (Meta Ads AI)</span>
					</div>
					<span class="badge" style="background: ${badge_bg}; color: ${badge_color}; border: 1px solid ${badge_border}; font-size: 11.5px; font-weight: 700; padding: 4px 10px; border-radius: 12px;">
						${badge_icon} ${badge_text}
					</span>
				</div>`,
				size: "large"
			});

			if (d.$wrapper) {
				d.$wrapper.find(".modal-dialog").css("max-width", "820px");
			}

			let tips_html = (adv.tips || []).map((tip) => `
				<div style="display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; font-size: 13px; color: #374151;">
					<span style="color: #2563EB; font-weight: 700; line-height: 1.4;">✓</span>
					<span style="line-height: 1.4;">${frappe.utils.escape_html(tip)}</span>
				</div>
			`).join("");

			let audience = adv.target_audience || {};
			let budget = adv.budget_plan || {};
			let metrics = adv.metrics || {};

			let html = `
			<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1F2937;">
				<!-- Top Metrics & Score Strip -->
				<div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 16px;">
					<div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 6px; padding: 8px 10px; text-align: center;">
						<div style="font-size: 11px; color: #6B7280; font-weight: 600;">LƯỢT THÍCH</div>
						<div style="font-size: 17px; font-weight: 700; color: #1E40AF; margin-top: 2px;">👍 ${metrics.likes || 0}</div>
					</div>
					<div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 6px; padding: 8px 10px; text-align: center;">
						<div style="font-size: 11px; color: #6B7280; font-weight: 600;">BÌNH LUẬN</div>
						<div style="font-size: 17px; font-weight: 700; color: #047857; margin-top: 2px;">💬 ${metrics.comments || 0}</div>
					</div>
					<div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 6px; padding: 8px 10px; text-align: center;">
						<div style="font-size: 11px; color: #6B7280; font-weight: 600;">CHIA SẺ</div>
						<div style="font-size: 17px; font-weight: 700; color: #6D28D9; margin-top: 2px;">↗ ${metrics.shares || 0}</div>
					</div>
					<div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 6px; padding: 8px 10px; text-align: center;">
						<div style="font-size: 11px; color: #6B7280; font-weight: 600;">CRM LEADS</div>
						<div style="font-size: 17px; font-weight: 700; color: #B45309; margin-top: 2px;">🎯 ${metrics.leads || 0}</div>
					</div>
					<div style="background: ${is_recommended ? '#ECFDF5' : (is_review ? '#FEFCE8' : '#F9FAFB')}; border: 1px solid ${is_recommended ? '#A7F3D0' : (is_review ? '#FEF08A' : '#E5E7EB')}; border-radius: 6px; padding: 8px 10px; text-align: center;">
						<div style="font-size: 11px; color: #6B7280; font-weight: 600;">ĐIỂM TIỀM NĂNG</div>
						<div style="font-size: 17px; font-weight: 700; color: ${is_recommended ? '#059669' : (is_review ? '#D97706' : '#6B7280')}; margin-top: 2px;">${adv.score || 0} pts</div>
					</div>
				</div>

				<!-- AI Assessment Rationale Box -->
				<div style="background: ${is_recommended ? '#F0FDF4' : (is_review ? '#FFFBEB' : '#F9FAFB')}; border: 1px solid ${is_recommended ? '#BBF7D0' : (is_review ? '#FDE68A' : '#E5E7EB')}; border-radius: 8px; padding: 12px 14px; margin-bottom: 16px;">
					<div style="display: flex; align-items: center; gap: 6px; font-weight: 700; font-size: 13px; color: ${is_recommended ? '#166534' : (is_review ? '#92400E' : '#374151')}; margin-bottom: 4px;">
						<span>💡 Đánh giá từ Chuyên gia Marketing AI:</span>
					</div>
					<div style="font-size: 13px; line-height: 1.5; color: #374151;">
						${frappe.utils.escape_html(adv.rationale || '')}
					</div>
				</div>

				<!-- Dual Column: Target Audience & Budget Strategy -->
				<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 16px;">
					<!-- Left: Target Persona -->
					<div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px;">
						<div style="display: flex; align-items: center; gap: 6px; font-weight: 700; font-size: 13.5px; color: #111827; margin-bottom: 10px; border-bottom: 1px solid #F3F4F6; padding-bottom: 6px;">
							<span>👥 Phân khúc Khách hàng Mục tiêu</span>
						</div>
						<div style="font-size: 12.5px; line-height: 1.5; display: flex; flex-direction: column; gap: 8px;">
							<div>
								<span style="font-weight: 600; color: #4B5563;">Độ tuổi:</span>
								<div style="color: #111827; margin-top: 1px;">${frappe.utils.escape_html(audience.age || 'N/A')}</div>
							</div>
							<div>
								<span style="font-weight: 600; color: #4B5563;">Khu vực địa lý:</span>
								<div style="color: #111827; margin-top: 1px;">${frappe.utils.escape_html(audience.location || 'N/A')}</div>
							</div>
							<div>
								<span style="font-weight: 600; color: #4B5563;">Sở thích & Hành vi:</span>
								<div style="color: #111827; margin-top: 1px;">${frappe.utils.escape_html(audience.interests || 'N/A')}</div>
							</div>
							<div>
								<span style="font-weight: 600; color: #4B5563;">Giới tính:</span>
								<div style="color: #111827; margin-top: 1px;">${frappe.utils.escape_html(audience.gender || 'Tất cả')}</div>
							</div>
						</div>
					</div>

					<!-- Right: Budget & Objective -->
					<div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px;">
						<div style="display: flex; align-items: center; gap: 6px; font-weight: 700; font-size: 13.5px; color: #111827; margin-bottom: 10px; border-bottom: 1px solid #F3F4F6; padding-bottom: 6px;">
							<span>💰 Kế hoạch Ngân sách & Mục tiêu</span>
						</div>
						<div style="font-size: 12.5px; line-height: 1.5; display: flex; flex-direction: column; gap: 8px;">
							<div>
								<span style="font-weight: 600; color: #4B5563;">Ngân sách đề xuất:</span>
								<div style="color: #059669; font-weight: 700; margin-top: 1px;">${frappe.utils.escape_html(budget.daily_budget || 'N/A')}</div>
							</div>
							<div>
								<span style="font-weight: 600; color: #4B5563;">Thời gian chạy:</span>
								<div style="color: #111827; margin-top: 1px;">${frappe.utils.escape_html(budget.duration || 'N/A')}</div>
							</div>
							<div>
								<span style="font-weight: 600; color: #4B5563;">Mục tiêu chiến dịch:</span>
								<div style="color: #1E40AF; font-weight: 600; margin-top: 1px;">${frappe.utils.escape_html(budget.objective || 'N/A')}</div>
							</div>
							<div>
								<span style="font-weight: 600; color: #4B5563;">Chi phí ước tính / Lead:</span>
								<div style="color: #111827; margin-top: 1px;">${frappe.utils.escape_html(budget.expected_cpl || 'N/A')}</div>
							</div>
						</div>
					</div>
				</div>

				<!-- Section: Optimization Tips -->
				<div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px; margin-bottom: 18px;">
					<div style="font-weight: 700; font-size: 13.5px; color: #111827; margin-bottom: 10px; border-bottom: 1px solid #F3F4F6; padding-bottom: 6px;">
						🚀 Chiến thuật & Mẹo Tối ưu Hiệu quả (Actionable Tips)
					</div>
					${tips_html || '<div style="color: #6B7280; font-size: 13px;">Chưa có mẹo cụ thể.</div>'}
				</div>

				<!-- Footer Controls -->
				<div style="display: flex; align-items: center; justify-content: space-between; border-top: 1px solid #E5E7EB; padding-top: 14px;">
					<div style="font-size: 12px; color: #6B7280;">
						💡 Khuyến nghị: Sử dụng tính năng <b>"Use Existing Post"</b> để tận dụng tương tác đã có!
					</div>
					<div style="display: flex; gap: 8px;">
						<button class="btn btn-default btn-sm btn-close-modal">Đóng</button>
						<a href="${adv.ads_manager_url || 'https://adsmanager.facebook.com/'}" target="_blank" class="btn btn-primary btn-sm" style="display: inline-flex; align-items: center; gap: 5px; text-decoration: none;">
							<span>Mở Meta Ads Manager ↗</span>
						</a>
					</div>
				</div>
			</div>
			`;

			d.$wrapper.find(".modal-body").html(html);
			d.$wrapper.find(".btn-close-modal").on("click", function () {
				d.hide();
			});
			d.show();
			frm.reload_doc();
		}
	});
}

