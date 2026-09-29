// Copyright (c) 2026, MMM and contributors
// For license information, please see license.txt

frappe.listview_settings["Facebook Post"] = {
	add_fields: [
		"name",
		"title",
		"status",
		"course",
		"scheduled_time",
		"batch_id",
		"day_of_week",
		"likes_count",
		"comments_count",
		"shares_count",
		"reach_count",
		"leads_count",
		"image",
		"content",
		"fb_post_url",
		"fb_post_id"
	],
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
	button: {
		show: function (doc) {
			return true;
		},
		get_label: function (doc) {
			return __("Xem & Sửa");
		},
		get_description: function (doc) {
			return __("Xem chi tiết và chỉnh sửa bài viết");
		},
		action: function (doc) {
			frappe.set_route("Form", "Facebook Post", doc.name);
		}
	},
	formatters: {
		likes_count: function (val, df, doc) {
			if (doc.status === "Posted") {
				return `<span style="display: inline-flex; align-items: center; gap: 4px; font-weight: 700; color: #1D4ED8; background: #EFF6FF; border: 1px solid #BFDBFE; padding: 2px 8px; border-radius: 12px; font-size: 12px;" title="${val || 0} Lượt thích từ Facebook">👍 ${val || 0}</span>`;
			}
			return `<span style="color: #9CA3AF; font-size: 11px;">-</span>`;
		},
		comments_count: function (val, df, doc) {
			if (doc.status === "Posted") {
				return `<span style="display: inline-flex; align-items: center; gap: 4px; font-weight: 700; color: #047857; background: #ECFDF5; border: 1px solid #A7F3D0; padding: 2px 8px; border-radius: 12px; font-size: 12px;" title="${val || 0} Bình luận từ Facebook">💬 ${val || 0}</span>`;
			}
			return `<span style="color: #9CA3AF; font-size: 11px;">-</span>`;
		},
		leads_count: function (val, df, doc) {
			if (val > 0) {
				return `<span class="badge" style="background: #E6F4EA; color: #137333; font-weight: 700; padding: 3px 8px; font-size: 12px;" title="${val} Leads CRM thu về">🎯 ${val} Leads</span>`;
			}
			return `<span style="color: #9CA3AF; font-size: 11px;">0 Leads</span>`;
		},
		course: function (val, df, doc) {
			return `<span class="badge" style="background: #EEF2FF; color: #4F46E5; font-weight: 600; padding: 3px 8px;">${frappe.utils.escape_html(val || 'Chung')}</span>`;
		}
	},
	onload: function (listview) {
		// Explicitly configure table columns so Facebook interaction metrics are always visible
		const get_df = frappe.meta.get_docfield.bind(null, "Facebook Post");
		listview.columns = [
			{ type: "Subject", df: get_df("title") },
			{ type: "Status" },
			{ type: "Field", df: get_df("course") },
			{ type: "Field", df: get_df("likes_count") },
			{ type: "Field", df: get_df("comments_count") },
			{ type: "Field", df: get_df("leads_count") }
		];
		if (!listview.list_view_settings) listview.list_view_settings = {};
		listview.list_view_settings.disable_comment_count = 1;
		listview.render_header();

		// Auto-clear stale filter if status is Pending Approval
		if (listview.filter_area) {
			let current_filters = listview.filter_area.get() || [];
			let status_filter = current_filters.find(f => f[1] === "status");
			if (status_filter && status_filter[3] === "Pending Approval") {
				listview.filter_area.remove("status");
			}
		}

		// 1. Lên kế hoạch tuần
		listview.page.add_inner_button(__("Lên kế hoạch tuần"), function () {
			open_agent_command_center(listview, "generate");
		});

		// 2. Duyệt tất cả tuần này
		let approve_btn = listview.page.add_inner_button(
			__("Duyệt tất cả tuần này"),
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
										message: __(
											`Đã duyệt và lên lịch thành công ${r.message.approved_count} bài viết!`
										),
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
		listview.page.add_inner_button(__("Làm lại cả tuần"), function () {
			open_agent_command_center(listview, "rollback");
		});

		// 4. Đồng bộ tương tác FB
		listview.page.add_inner_button(__("Đồng bộ tương tác FB"), function () {
			frappe.show_alert({ message: __("Đang đồng bộ số liệu tương tác từ Facebook..."), indicator: "blue" });
			frappe.call({
				method: "mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.sync_all_posted_analytics",
				freeze: true,
				freeze_message: __("Đang lấy số liệu tương tác (Thích, Bình luận, Chia sẻ, Leads)..."),
				callback: function (r) {
					if (r.message && r.message.status === "success") {
						frappe.show_alert({
							message: __(
								`Đã cập nhật số liệu tương tác cho ${r.message.synced_count} bài viết!`
							),
							indicator: "green"
						});
						listview.refresh();
					} else {
						listview.refresh();
					}
				}
			});
		});

		// 5. Báo cáo & Xếp hạng tổng thể
		listview.page.add_inner_button(__("Báo cáo & Xếp hạng"), function () {
			open_marketing_overview_modal(listview);
		});
	},
	refresh: function (listview) {
		const get_df = frappe.meta.get_docfield.bind(null, "Facebook Post");
		listview.columns = [
			{ type: "Subject", df: get_df("title") },
			{ type: "Status" },
			{ type: "Field", df: get_df("course") },
			{ type: "Field", df: get_df("likes_count") },
			{ type: "Field", df: get_df("comments_count") },
			{ type: "Field", df: get_df("leads_count") }
		];
		listview.render_header(true);
		render_kpi_summary_bar(listview);
		enhance_list_rows(listview);
	}
};

/**
 * Open the EduFlow AI Agent Command Center Modal
 * Displays real-time progress, multi-agent status cards, and live terminal stream.
 */
function open_agent_command_center(listview, mode) {
	let is_rollback = mode === "rollback";
	let modal_title = is_rollback
		? __("🔄 EduFlow Agent Command Center — Làm lại cả tuần")
		: __("🤖 EduFlow AI Agent Command Center");

	let d = new frappe.ui.Dialog({
		title: `<div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
			<div style="display: flex; align-items: center; gap: 8px;">
				<span style="font-size: 18px;">${is_rollback ? "🔄" : "🤖"}</span>
				<span style="font-weight: 700; font-size: 15px;">${modal_title}</span>
			</div>
			<span class="badge" style="background: #10B981; color: white; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">● MULTI-AGENT LIVE</span>
		</div>`,
		size: "large"
	});

	if (d.$wrapper) {
		d.$wrapper.find(".modal-dialog").css("max-width", "820px");
	}

	let html = `
	<style>
		.agent-modal-container {
			font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
			color: #1F2937;
		}
		.agent-chip {
			display: inline-block;
			padding: 4px 10px;
			margin: 2px 4px 6px 0;
			background: #F3F4F6;
			border: 1px solid #E5E7EB;
			border-radius: 16px;
			font-size: 12px;
			cursor: pointer;
			transition: all 0.2s;
			color: #374151;
		}
		.agent-chip:hover {
			background: #E0E7FF;
			border-color: #6366F1;
			color: #4338CA;
		}
		.agent-pipeline-grid {
			display: grid;
			grid-template-columns: repeat(5, 1fr);
			gap: 8px;
			margin: 14px 0;
		}
		.agent-card {
			background: #FFFFFF;
			border: 1px solid #E5E7EB;
			border-radius: 8px;
			padding: 10px 8px;
			text-align: center;
			transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
			position: relative;
		}
		.agent-card-icon {
			font-size: 22px;
			margin-bottom: 4px;
		}
		.agent-card-title {
			font-weight: 700;
			font-size: 11.5px;
			margin-bottom: 2px;
			color: #111827;
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.agent-card-role {
			font-size: 10px;
			color: #6B7280;
			margin-bottom: 6px;
			height: 24px;
			line-height: 1.2;
			overflow: hidden;
		}
		.agent-status-badge {
			display: inline-block;
			font-size: 9.5px;
			font-weight: 600;
			padding: 2px 6px;
			border-radius: 10px;
			background: #F3F4F6;
			color: #6B7280;
			transition: all 0.3s;
		}
		@keyframes agent-pulse {
			0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.5); }
			70% { box-shadow: 0 0 0 8px rgba(59, 130, 246, 0); }
			100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
		}
		.agent-card-active {
			border-color: #3B82F6 !important;
			background-color: #EFF6FF !important;
			animation: agent-pulse 1.8s infinite;
		}
		.agent-card-done {
			border-color: #10B981 !important;
			background-color: #F0FDF4 !important;
		}
		.agent-terminal-box {
			background: #0F172A;
			border: 1px solid #1E293B;
			border-radius: 8px;
			padding: 12px 14px;
			font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
			font-size: 12px;
			color: #E2E8F0;
			height: 175px;
			overflow-y: auto;
			box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5);
		}
	</style>

	<div class="agent-modal-container">
		<!-- Section 1: User Directive Input (Initial Stage) -->
		<div id="agent-input-section">
			<label style="font-weight: 600; font-size: 13px; margin-bottom: 6px; display: block;">
				${
					is_rollback
						? __("Góp ý / Yêu cầu điều chỉnh lại cho Agent (Redesign Directive):")
						: __("Chỉ đạo trọng tâm tuần của Giám đốc (Boss Directive - Tùy chọn):")
				}
			</label>
			<textarea id="agent-directive-input" class="form-control" rows="3" style="font-size: 13px; border-radius: 6px; margin-bottom: 8px;"
				placeholder="${
					is_rollback
						? __(
								'Ví dụ: Viết lại theo hướng kể chuyện xúc động hơn, tập trung gói kèm 1-1, bỏ bớt emoji...'
						  )
						: __(
								'Ví dụ: Tuần lễ vàng bơi lội hè, tặng mũ và kính bơi cho 50 bé đăng ký sớm, ưu đãi 35%...'
						  )
				}"></textarea>
			
			<div style="margin-bottom: 14px;">
				<span style="font-size: 11.5px; color: #6B7280; margin-right: 6px;">💡 Gợi ý nhanh:</span>
				<span class="agent-chip" data-text="Tuần lễ vàng Bơi lội hè cho bé (Giảm 30% + Tặng mũ kính)">🏊 Bơi lội hè giảm 30%</span>
				<span class="agent-chip" data-text="Khai giảng Tiếng Anh Giao tiếp bứt phá (Học thử 1-1 miễn phí)">🇬🇧 Tiếng Anh giao tiếp</span>
				<span class="agent-chip" data-text="Toán tư duy Logic & Sáng tạo (Tặng buổi test IQ & Đánh giá năng lực)">🧮 Toán tư duy logic</span>
				<span class="agent-chip" data-text="Ngày hội Tuyển sinh & Học bổng EduFlow Academy 2026">🎓 Tuyển sinh toàn diện</span>
			</div>

			<div style="text-align: right;">
				<button id="btn-launch-agents" class="btn btn-primary" style="font-weight: 600; padding: 7px 18px; border-radius: 6px;">
					${is_rollback ? __("🔄 Thu hồi & Làm lại cả tuần") : __("🚀 Khởi chạy hệ thống Multi-Agent")}
				</button>
			</div>
		</div>

		<!-- Section 2: Real-time Execution Pipeline (Hidden initially) -->
		<div id="agent-execution-section" style="display: none;">
			<!-- Directive Summary Header -->
			<div id="agent-directive-summary" style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 6px 12px; margin-bottom: 12px; font-size: 12px; color: #475569; display: flex; align-items: center; justify-content: space-between;">
				<div><strong>🎯 Chỉ đạo:</strong> <span id="agent-active-directive-text" style="color: #1E293B;">...</span></div>
				<span id="agent-batch-badge" class="badge badge-info" style="font-size: 11px;">Mã đợt: Đang tạo...</span>
			</div>

			<!-- Stepper Progress Bar -->
			<div style="margin-bottom: 12px;">
				<div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: 600; margin-bottom: 4px;">
					<span id="agent-progress-status-text" style="color: #2563EB;">Đang khởi động hệ thống tác tử...</span>
					<span id="agent-progress-percent" style="color: #2563EB;">0%</span>
				</div>
				<div class="progress" style="height: 8px; border-radius: 4px; background: #E2E8F0; overflow: hidden; margin-bottom: 0;">
					<div id="agent-progress-bar" style="width: 0%; height: 100%; background: linear-gradient(90deg, #3B82F6 0%, #10B981 100%); transition: width 0.4s ease;"></div>
				</div>
			</div>

			<!-- 5 Agent Cards Pipeline -->
			<div class="agent-pipeline-grid">
				<div class="agent-card" data-agent="strategy" data-index="0">
					<div class="agent-card-icon">🧭</div>
					<div class="agent-card-title">Strategy Agent</div>
					<div class="agent-card-role">Phân tích mục tiêu & Persona</div>
					<span class="agent-status-badge">⏳ Chờ</span>
				</div>

				<div class="agent-card" data-agent="crm" data-index="1">
					<div class="agent-card-icon">📊</div>
					<div class="agent-card-title">CRM Agent</div>
					<div class="agent-card-role">API Khóa học & Ưu đãi</div>
					<span class="agent-status-badge">⏳ Chờ</span>
				</div>

				<div class="agent-card" data-agent="copywriter" data-index="2">
					<div class="agent-card-icon">✍️</div>
					<div class="agent-card-title">Copywriter</div>
					<div class="agent-card-role">Gemini AI (Anti-Cliché)</div>
					<span class="agent-status-badge">⏳ Chờ</span>
				</div>

				<div class="agent-card" data-agent="scheduler" data-index="3">
					<div class="agent-card-icon">📅</div>
					<div class="agent-card-title">Scheduler</div>
					<div class="agent-card-role">Khung giờ vàng T2,4,6,CN</div>
					<span class="agent-status-badge">⏳ Chờ</span>
				</div>

				<div class="agent-card" data-agent="quality" data-index="4">
					<div class="agent-card-icon">🛡️</div>
					<div class="agent-card-title">Quality Guard</div>
					<div class="agent-card-role">Meta Policy & Chờ duyệt</div>
					<span class="agent-status-badge">⏳ Chờ</span>
				</div>
			</div>

			<!-- Live Activity Stream Console -->
			<div class="agent-terminal-box" id="agent-terminal-stream">
				<div style="color: #64748B; margin-bottom: 6px;">[SYSTEM READY] Multi-Agent Pipeline initialized with Gemini 3.8 Flash...</div>
			</div>

			<!-- Completion Screen (Appears when 100% finished) -->
			<div id="agent-completion-box" style="display: none; margin-top: 14px; background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 12px 16px; text-align: center;">
				<div style="font-size: 14px; font-weight: 700; color: #15803D; margin-bottom: 4px;">
					🎉 Đã tạo thành công 4 bài viết cho cả tuần!
				</div>
				<div id="agent-completion-details" style="font-size: 12px; color: #166534; margin-bottom: 10px;">
					Các bài viết đã được xếp lịch tự động và lưu ở trạng thái <strong>Chờ duyệt (Pending Approval)</strong>.
				</div>
				<button id="btn-view-posts" class="btn btn-success btn-sm" style="font-weight: 600; padding: 6px 16px; border-radius: 6px;">
					👀 Xem danh sách bài viết vừa tạo
				</button>
			</div>
		</div>
	</div>
	`;

	$(d.body).html(html);

	// Handle quick suggestion chips
	$(d.body).find(".agent-chip").on("click", function () {
		let text = $(this).attr("data-text");
		$(d.body).find("#agent-directive-input").val(text);
	});

	// Handle Launch button
	$(d.body).find("#btn-launch-agents").on("click", function () {
		let directive = $(d.body).find("#agent-directive-input").val().trim();
		$(d.body).find("#agent-input-section").slideUp(200);
		$(d.body).find("#agent-execution-section").slideDown(300);

		$(d.body).find("#agent-active-directive-text").text(
			directive || "Tuyển sinh tổng lực đa kênh 4 khóa học trọng điểm"
		);

		execute_multi_agent_pipeline(listview, d, directive, is_rollback);
	});

	d.show();
}

/**
 * Execute the multi-agent pipeline with animated telemetry and Frappe API call
 */
function execute_multi_agent_pipeline(listview, dialog, directive, is_rollback) {
	let term = $(dialog.body).find("#agent-terminal-stream");
	let pbar = $(dialog.body).find("#agent-progress-bar");
	let ptext = $(dialog.body).find("#agent-progress-status-text");
	let ppercent = $(dialog.body).find("#agent-progress-percent");

	function add_log(icon, name, message, color) {
		let now = new Date();
		let time = now.toTimeString().split(" ")[0];
		let log_item = $(`
			<div style="margin-bottom: 5px; color: ${color || "#E2E8F0"}; line-height: 1.5;">
				<span style="color: #64748B;">[${time}]</span> 
				<span style="font-weight: 600; color: #38BDF8;">${icon} ${name}:</span> 
				<span>${message}</span>
			</div>
		`);
		term.append(log_item);
		term.scrollTop(term[0].scrollHeight);
	}

	function update_agent_ui(index, status) {
		let card = $(dialog.body).find(`.agent-card[data-index="${index}"]`);
		let badge = card.find(".agent-status-badge");
		if (status === "active") {
			card.addClass("agent-card-active").removeClass("agent-card-done");
			badge.html("⚡ Đang xử lý").css({ background: "#FEF3C7", color: "#D97706" });
		} else if (status === "done") {
			card.removeClass("agent-card-active").addClass("agent-card-done");
			badge.html("✅ Hoàn tất").css({ background: "#D1FAE5", color: "#059669" });
		} else {
			card.removeClass("agent-card-active agent-card-done");
			badge.html("⏳ Chờ").css({ background: "#F3F4F6", color: "#6B7280" });
		}
	}

	function update_progress(percent, text) {
		pbar.css("width", percent + "%");
		ppercent.text(percent + "%");
		if (text) {
			ptext.text(text);
		}
	}

	// Step 0: Immediate - Strategy Agent starts
	update_agent_ui(0, "active");
	update_progress(15, "Strategy Agent đang phân tích chỉ đạo & xây dựng phễu...");
	add_log(
		"🧭",
		"Strategy Agent",
		is_rollback
			? `Tiếp nhận phản hồi điều chỉnh: "${directive || 'Cải tiến nội dung mới'}"`
			: `Phân tích chỉ đạo sếp: "${directive || 'Tuyển sinh 4 khóa học trọng điểm'}"`
	);

	// Step 1: After 1s - CRM Data Agent starts
	setTimeout(function () {
		update_agent_ui(0, "done");
		update_agent_ui(1, "active");
		update_progress(35, "CRM Agent đang đồng bộ dữ liệu khóa học & ưu đãi...");
		add_log(
			"📊",
			"CRM Agent",
			"API GET /api/resource/Course: Đồng bộ thành công 4 khóa học (Tiếng Anh, Toán, Bơi lội, Chung)"
		);
	}, 1100);

	// Step 2: After 2.3s - Copywriter Agent starts
	setTimeout(function () {
		update_agent_ui(1, "done");
		update_agent_ui(2, "active");
		update_progress(55, "Copywriter Agent đang gọi Gemini AI sáng tạo nội dung...");
		add_log(
			"✍️",
			"Copywriter Agent",
			"Kích hoạt Gemini 3.8 Flash: Soạn 4 bài theo 4 góc độ (Storytelling, Educational Insight, Humor, FOMO Offer) kèm bộ lọc Anti-Cliché..."
		);
	}, 2300);

	// Parallel: Dispatch the real backend API call
	let method_name = is_rollback
		? "mmm_custom.autopilot.rollback_weekly_batch"
		: "mmm_custom.autopilot.generate_weekly_batch";
	let method_args = is_rollback
		? { new_directive: directive }
		: { boss_directive: directive };

	frappe.call({
		method: method_name,
		args: method_args,
		callback: function (r) {
			if (r.message && r.message.status === "success") {
				let result = r.message;
				let batch_id = result.batch_id || (result.new_batch && result.new_batch.batch_id) || "BATCH-2026";
				let post_count = result.count || (result.new_batch && result.new_batch.count) || 4;

				// Update Batch badge in UI
				$(dialog.body).find("#agent-batch-badge").text("Mã đợt: " + batch_id);

				// Step 3: Copywriter finishes, Scheduler Agent takes over
				setTimeout(function () {
					update_agent_ui(2, "done");
					update_agent_ui(3, "active");
					update_progress(80, "Scheduler Agent đang phân bổ khung giờ vàng...");
					add_log(
						"📅",
						"Scheduler Agent",
						`Đã phân bổ 4 khung giờ vàng cho tuần ${batch_id}: T2 (08:30), T4 (11:30), T6 (19:30), CN (09:00)`
					);

					// Step 4: Quality Guard takes over
					setTimeout(function () {
						update_agent_ui(3, "done");
						update_agent_ui(4, "active");
						update_progress(95, "Quality Guard đang rà soát chính sách Meta...");
						add_log(
							"🛡️",
							"Quality Guard",
							"Rà soát từ khóa quảng cáo & chính sách Facebook: 100% hợp lệ! Lưu trạng thái Pending Approval."
						);

						// Step 5: Final completion
						setTimeout(function () {
							update_agent_ui(4, "done");
							update_progress(100, "Hoàn tất 100%! Đã sẵn sàng.");
							add_log("🎉", "SYSTEM", `Toàn bộ ${post_count} bài viết đã sẵn sàng chờ sếp duyệt!`, "#4ADE80");

							$(dialog.body).find("#agent-completion-box").slideDown(300);

							// Bind view posts button
							$(dialog.body).find("#btn-view-posts").on("click", function () {
								dialog.hide();
								listview.refresh();
								frappe.show_alert({
									message: __(`Đã tạo thành công ${post_count} bài viết cho đợt ${batch_id}!`),
									indicator: "green"
								});
							});
						}, 700);
					}, 800);
				}, 600);
			} else {
				add_log("❌", "ERROR", "Có lỗi xảy ra trong quá trình sinh bài: " + JSON.stringify(r.message || r), "#EF4444");
				update_progress(100, "Quá trình gặp sự cố");
			}
		},
		error: function (err) {
			add_log("❌", "ERROR", "Lỗi kết nối máy chủ: " + (err.message || err.statusText || "Vui lòng thử lại"), "#EF4444");
		}
	});
}

/**
 * Render the Top KPI Summary Bar directly on the Facebook Post List View
 */
function render_kpi_summary_bar(listview) {
	if (!listview || !listview.page || !listview.page.main) return;

	let container = listview.page.main.find('.facebook-marketing-kpi-bar');
	if (!container.length) {
		container = $('<div class="facebook-marketing-kpi-bar" style="margin-bottom: 16px;"></div>');
		let target = listview.page.main.find('.frappe-list');
		if (target.length) {
			target.before(container);
		} else {
			listview.page.main.prepend(container);
		}
	}

	frappe.call({
		method: "mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.get_marketing_overview",
		callback: function (r) {
			if (!r.message || r.message.status !== "success") return;
			let kpis = r.message.kpis || {};
			let total_eng = (kpis.total_likes || 0) + (kpis.total_comments || 0) + (kpis.total_shares || 0);

			let current_filters = (listview.filter_area && listview.filter_area.get()) || [];
			let active_status = "";
			for (let f of current_filters) {
				if (f[1] === "status") {
					active_status = f[3];
					break;
				}
			}

			let html = `
			<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
				<div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
					<div style="font-size: 11px; font-weight: 600; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px;">ĐỘ PHỦ BÀI VIẾT</div>
					<div style="font-size: 22px; font-weight: 700; color: #111827; margin: 4px 0;">${kpis.posted_count || 0} <span style="font-size: 13px; font-weight: 500; color: #6B7280;">/ ${kpis.total_posts || 0} bài</span></div>
					<div style="font-size: 12px; color: #6B7280;">${kpis.scheduled_count || 0} lên lịch · ${kpis.pending_count || 0} chờ duyệt</div>
				</div>

				<div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
					<div style="font-size: 11px; font-weight: 600; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px;">TỔNG TƯƠNG TÁC</div>
					<div style="font-size: 22px; font-weight: 700; color: #111827; margin: 4px 0;">${total_eng.toLocaleString()} <span style="font-size: 13px; font-weight: 500; color: #6B7280;">lượt</span></div>
					<div style="font-size: 12px; color: #6B7280;">${kpis.total_likes || 0} Thích · ${kpis.total_comments || 0} Bình luận · ${kpis.total_shares || 0} Chia sẻ</div>
				</div>

				<div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
					<div style="font-size: 11px; font-weight: 600; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px;">CRM LEADS THU VỀ</div>
					<div style="font-size: 22px; font-weight: 700; color: #059669; margin: 4px 0;">${kpis.total_leads || 0} <span style="font-size: 13px; font-weight: 500; color: #6B7280;">khách</span></div>
					<div style="font-size: 12px; color: #6B7280;">Tiếp cận: ${(kpis.total_reach || 0).toLocaleString()} người</div>
				</div>

				<div class="kpi-action-card" style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px 16px; cursor: pointer; transition: all 0.15s; display: flex; flex-direction: column; justify-content: center;"
					onmouseover="this.style.background='#F3F4F6'; this.style.borderColor='#D1D5DB';"
					onmouseout="this.style.background='#F9FAFB'; this.style.borderColor='#E5E7EB';">
					<div style="display: flex; align-items: center; justify-content: space-between;">
						<div style="font-size: 11px; font-weight: 600; color: #4F46E5; text-transform: uppercase; letter-spacing: 0.5px;">BÁO CÁO TỔNG THỂ</div>
						<span style="font-size: 14px; color: #4F46E5;">→</span>
					</div>
					<div style="font-size: 14px; font-weight: 600; color: #111827; margin: 4px 0;">Xem xếp hạng bài viết</div>
					<div style="font-size: 12px; color: #6B7280;">Thống kê bài hút lead & tương tác cao</div>
				</div>
			</div>

			<!-- Quick Status Filter Bar -->
			<div class="facebook-status-filter-pills" style="display: flex; align-items: center; justify-content: space-between; margin-top: 12px; padding: 10px 14px; background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.02); flex-wrap: wrap; gap: 8px;">
				<div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
					<span style="font-size: 12px; font-weight: 600; color: #4B5563; margin-right: 4px;">Lọc trạng thái:</span>
					<button class="btn btn-xs filter-pill ${!active_status ? 'btn-primary' : 'btn-default'}" data-status="" style="font-weight: 500; border-radius: 14px; padding: 3px 12px;">
						Tất cả (${kpis.total_posts || 0})
					</button>
					<button class="btn btn-xs filter-pill ${active_status === 'Posted' ? 'btn-primary' : 'btn-default'}" data-status="Posted" style="font-weight: 500; border-radius: 14px; padding: 3px 12px;">
						Đã đăng (${kpis.posted_count || 0})
					</button>
					<button class="btn btn-xs filter-pill ${active_status === 'Scheduled' ? 'btn-primary' : 'btn-default'}" data-status="Scheduled" style="font-weight: 500; border-radius: 14px; padding: 3px 12px;">
						Đã lên lịch (${kpis.scheduled_count || 0})
					</button>
					<button class="btn btn-xs filter-pill ${active_status === 'Pending Approval' ? 'btn-primary' : 'btn-default'}" data-status="Pending Approval" style="font-weight: 500; border-radius: 14px; padding: 3px 12px;">
						Chờ duyệt (${kpis.pending_count || 0})
					</button>
					<button class="btn btn-xs filter-pill ${active_status === 'Draft' ? 'btn-primary' : 'btn-default'}" data-status="Draft" style="font-weight: 500; border-radius: 14px; padding: 3px 12px;">
						Bản nháp (${kpis.draft_count || 0})
					</button>
				</div>
				<div style="font-size: 12px; color: #6B7280;">
					Bấm vào bất kỳ bài viết nào để xem chi tiết & chỉnh sửa
				</div>
			</div>
			`;
			container.html(html);

			container.find('.kpi-action-card').on('click', function () {
				open_marketing_overview_modal(listview);
			});

			container.find('.filter-pill').on('click', function () {
				let target = $(this).attr('data-status');
				if (listview.filter_area) {
					listview.filter_area.remove("status");
					if (target) {
						listview.filter_area.add([["Facebook Post", "status", "=", target]]);
					} else {
						listview.refresh();
					}
				}
			});
		}
	});
}

/**
 * Enhance List View rows with visual post preview (Thumbnail, Title, Caption snippet, Actions)
 */
function enhance_list_rows(listview) {
	if (!listview || !listview.$result) return;

	setTimeout(function () {
		let rows = listview.$result.find('.list-row-container');
		if (!rows.length) return;

		rows.each(function (idx) {
			let doc = listview.data && listview.data[idx];
			if (!doc) return;
			let $row = $(this);

			if ($row.attr('data-enhanced-post') === String(doc.name)) return;
			$row.attr('data-enhanced-post', String(doc.name));

			$row.find('.list-row').css({
				'min-height': '64px',
				'padding-top': '8px',
				'padding-bottom': '8px',
				'align-items': 'center'
			});

			let $subject = $row.find('.list-subject');
			if (!$subject.length) return;

			let form_link = listview.get_form_link(doc);
			let img_src = doc.image ? frappe.utils.escape_html(doc.image) : '';
			let thumb_html = img_src
				? `<a href="${form_link}" style="display: block; width: 48px; height: 48px; min-width: 48px; margin-right: 12px; border-radius: 6px; overflow: hidden; border: 1px solid #E5E7EB; box-shadow: 0 1px 2px rgba(0,0,0,0.06); flex-shrink: 0;" title="${__('Xem chi tiết & Chỉnh sửa')}">
					<img src="${img_src}" style="width: 100%; height: 100%; object-fit: cover;" alt="Banner" />
				   </a>`
				: `<a href="${form_link}" style="display: flex; width: 48px; height: 48px; min-width: 48px; margin-right: 12px; border-radius: 6px; background: #F3F4F6; border: 1px solid #E5E7EB; align-items: center; justify-content: center; color: #9CA3AF; flex-shrink: 0;" title="${__('Xem chi tiết & Chỉnh sửa')}">
					<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
				   </a>`;

			let raw_title = doc.title || ('Bài viết #' + doc.name);
			let clean_content = (doc.content || '').replace(/\s+/g, ' ').trim();
			let snippet = clean_content.length > 80 ? clean_content.substring(0, 80) + '...' : clean_content;

			let info_html = `
				<div style="display: flex; flex-direction: column; justify-content: center; min-width: 0; overflow: hidden; line-height: 1.4;">
					<div style="display: flex; align-items: center; gap: 8px;">
						<a href="${form_link}" style="font-weight: 600; font-size: 13.5px; color: #111827; text-decoration: none;" class="ellipsis" title="${frappe.utils.escape_html(raw_title)}">
							${frappe.utils.escape_html(raw_title)}
						</a>
					</div>
					${snippet ? `<div style="font-size: 12px; color: #6B7280; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 440px; margin-top: 2px;" title="${frappe.utils.escape_html(clean_content)}">
						${frappe.utils.escape_html(snippet)}
					</div>` : ''}
				</div>
			`;

			let $wrapper = $(`<div style="display: flex; align-items: center; min-width: 0; flex: 1;"></div>`);
			$wrapper.append(thumb_html);
			$wrapper.append(info_html);

			$subject.find('span.ellipsis, a[data-name]').remove();
			$subject.append($wrapper);

			// Hide Frappe internal desk comment count to prevent confusion with Facebook comments
			$row.find('.comment-count, .list-row-like, .level-right span.mx-2').hide();

			if (doc.fb_post_url) {
				let $actions = $row.find('.level-right');
				if ($actions.length && !$actions.find('.fb-external-link').length) {
					$actions.prepend(`
						<a href="${doc.fb_post_url}" target="_blank" class="fb-external-link btn btn-default btn-xs" style="margin-right: 6px; color: #1877F2; text-decoration: none; display: inline-flex; align-items: center; gap: 4px;" title="${__('Xem trực tiếp trên Facebook')}">
							<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
							FB ↗
						</a>
					`);
				}
			}
		});
	}, 50);
}

/**
 * Open Executive Marketing Analytics & Top Performing Posts Modal
 */
function open_marketing_overview_modal(listview) {
	let d = new frappe.ui.Dialog({
		title: `<div style="display: flex; align-items: center; gap: 8px;">
			<span style="font-weight: 700; font-size: 16px;">Báo cáo Tổng thể & Hiệu quả Facebook Marketing</span>
		</div>`,
		size: "large"
	});

	if (d.$wrapper) {
		d.$wrapper.find(".modal-dialog").css("max-width", "880px");
	}

	d.show();
	d.$wrapper.find('.modal-body').html(`
		<div style="text-align: center; padding: 40px;">
			<div class="spinner-border text-primary" role="status"></div>
			<div style="margin-top: 12px; color: #6B7280; font-size: 13px;">Đang tải dữ liệu tổng thể...</div>
		</div>
	`);

	frappe.call({
		method: "mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.get_marketing_overview",
		callback: function (r) {
			if (!r.message || r.message.status !== "success") {
				d.$wrapper.find('.modal-body').html(`<div class="alert alert-danger">Không thể tải dữ liệu báo cáo: ${r.message ? r.message.message : 'Lỗi'}</div>`);
				return;
			}

			let kpis = r.message.kpis || {};
			let top_leads = r.message.top_leads || [];
			let top_eng = r.message.top_engagement || [];

			let lead_rows = top_leads.map((p, idx) => {
				let linkBtn = p.fb_post_url 
					? `<a href="${p.fb_post_url}" target="_blank" class="btn btn-xs btn-default" style="font-size: 11px; padding: 2px 6px;">Xem trên FB</a>`
					: `<span class="text-muted" style="font-size: 11px;">Chưa đăng</span>`;
				return `
					<tr style="border-bottom: 1px solid #F3F4F6;">
						<td style="padding: 10px 8px; font-weight: 700; font-size: 13px; text-align: center; width: 44px; color: #4B5563;">${idx + 1}</td>
						<td style="padding: 10px 8px;">
							<div style="font-weight: 600; color: #111827; font-size: 13px;">${frappe.utils.escape_html(p.title || 'Bài viết #' + p.name)}</div>
							<div style="font-size: 11px; color: #6B7280;">Khóa học: <span class="badge badge-light" style="font-weight: 600;">${p.course || 'Chung'}</span> • ${p.day_of_week || ''}</div>
						</td>
						<td style="padding: 10px 8px; text-align: center;">
							<span class="badge" style="background: #E6F4EA; color: #137333; font-size: 12px; font-weight: 600; padding: 4px 8px; border-radius: 4px;">
								${p.leads_count || 0} Leads
							</span>
						</td>
						<td style="padding: 10px 8px; font-size: 12px; color: #4B5563; text-align: center;">
							${p.likes_count || 0} Thích · ${p.comments_count || 0} Bình luận
						</td>
						<td style="padding: 10px 8px; text-align: right;">
							${linkBtn}
						</td>
					</tr>
				`;
			}).join('');

			let eng_rows = top_eng.map((p, idx) => {
				let linkBtn = p.fb_post_url 
					? `<a href="${p.fb_post_url}" target="_blank" class="btn btn-xs btn-default" style="font-size: 11px; padding: 2px 6px;">Xem trên FB</a>`
					: `<span class="text-muted" style="font-size: 11px;">Chưa đăng</span>`;
				return `
					<tr style="border-bottom: 1px solid #F3F4F6;">
						<td style="padding: 10px 8px; font-weight: 700; font-size: 13px; text-align: center; width: 44px; color: #4B5563;">${idx + 1}</td>
						<td style="padding: 10px 8px;">
							<div style="font-weight: 600; color: #111827; font-size: 13px;">${frappe.utils.escape_html(p.title || 'Bài viết #' + p.name)}</div>
							<div style="font-size: 11px; color: #6B7280;">Khóa học: <span class="badge badge-light" style="font-weight: 600;">${p.course || 'Chung'}</span></div>
						</td>
						<td style="padding: 10px 8px; text-align: center;">
							<span style="font-weight: 600; color: #111827; font-size: 13px;">${p.likes_count || 0}</span>
						</td>
						<td style="padding: 10px 8px; text-align: center;">
							<span style="font-weight: 600; color: #111827; font-size: 13px;">${p.comments_count || 0}</span>
						</td>
						<td style="padding: 10px 8px; text-align: center;">
							<span class="badge badge-light" style="font-size: 11px;">${p.leads_count || 0} Leads</span>
						</td>
						<td style="padding: 10px 8px; text-align: right;">
							${linkBtn}
						</td>
					</tr>
				`;
			}).join('');

			let modalHtml = `
				<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
					<!-- Quick Metric Strip -->
					<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px;">
						<div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 6px; padding: 12px; text-align: center;">
							<div style="font-size: 11px; color: #6B7280; font-weight: 600; text-transform: uppercase;">Tổng bài viết</div>
							<div style="font-size: 20px; font-weight: 700; color: #111827; margin-top: 2px;">${kpis.total_posts || 0}</div>
							<div style="font-size: 11px; color: #6B7280;">${kpis.posted_count || 0} đã đăng</div>
						</div>
						<div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 6px; padding: 12px; text-align: center;">
							<div style="font-size: 11px; color: #6B7280; font-weight: 600; text-transform: uppercase;">Lượt thích</div>
							<div style="font-size: 20px; font-weight: 700; color: #111827; margin-top: 2px;">${(kpis.total_likes || 0).toLocaleString()}</div>
							<div style="font-size: 11px; color: #6B7280;">Reactions</div>
						</div>
						<div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 6px; padding: 12px; text-align: center;">
							<div style="font-size: 11px; color: #6B7280; font-weight: 600; text-transform: uppercase;">Bình luận</div>
							<div style="font-size: 20px; font-weight: 700; color: #111827; margin-top: 2px;">${(kpis.total_comments || 0).toLocaleString()}</div>
							<div style="font-size: 11px; color: #6B7280;">Bình luận & phản hồi</div>
						</div>
						<div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 6px; padding: 12px; text-align: center;">
							<div style="font-size: 11px; color: #6B7280; font-weight: 600; text-transform: uppercase;">CRM Leads</div>
							<div style="font-size: 20px; font-weight: 700; color: #059669; margin-top: 2px;">${kpis.total_leads || 0}</div>
							<div style="font-size: 11px; color: #6B7280;">Khách chuyển đổi</div>
						</div>
					</div>

					<!-- Section: Top Leads -->
					<div style="margin-bottom: 24px;">
						<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
							<div style="font-weight: 600; font-size: 13px; color: #111827;">Top bài viết thu hút khách hàng (Leads)</div>
							<span style="font-size: 12px; color: #6B7280;">Xếp theo số Lead trong CRM</span>
						</div>
						<div style="border: 1px solid #E5E7EB; border-radius: 6px; overflow: hidden; background: white;">
							<table style="width: 100%; border-collapse: collapse;">
								<thead>
									<tr style="background: #F9FAFB; border-bottom: 1px solid #E5E7EB; font-size: 11px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px;">
										<th style="padding: 8px; text-align: center;">Hạng</th>
										<th style="padding: 8px; text-align: left;">Nội dung bài viết</th>
										<th style="padding: 8px; text-align: center;">Leads</th>
										<th style="padding: 8px; text-align: center;">Tương tác</th>
										<th style="padding: 8px; text-align: right;">Facebook</th>
									</tr>
								</thead>
								<tbody>
									${lead_rows || '<tr><td colspan="5" style="text-align: center; padding: 16px; color: #9CA3AF;">Chưa có bài viết nào</td></tr>'}
								</tbody>
							</table>
						</div>
					</div>

					<!-- Section: Top Engagement -->
					<div style="margin-bottom: 20px;">
						<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
							<div style="font-weight: 600; font-size: 13px; color: #111827;">Top bài viết tương tác cao nhất</div>
							<span style="font-size: 12px; color: #6B7280;">Xếp theo lượt Thích & Bình luận</span>
						</div>
						<div style="border: 1px solid #E5E7EB; border-radius: 6px; overflow: hidden; background: white;">
							<table style="width: 100%; border-collapse: collapse;">
								<thead>
									<tr style="background: #F9FAFB; border-bottom: 1px solid #E5E7EB; font-size: 11px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px;">
										<th style="padding: 8px; text-align: center;">Hạng</th>
										<th style="padding: 8px; text-align: left;">Nội dung bài viết</th>
										<th style="padding: 8px; text-align: center;">Thích</th>
										<th style="padding: 8px; text-align: center;">Bình luận</th>
										<th style="padding: 8px; text-align: center;">Leads</th>
										<th style="padding: 8px; text-align: right;">Facebook</th>
									</tr>
								</thead>
								<tbody>
									${eng_rows || '<tr><td colspan="6" style="text-align: center; padding: 16px; color: #9CA3AF;">Chưa có bài viết nào</td></tr>'}
								</tbody>
							</table>
						</div>
					</div>

					<!-- Bottom Action Buttons -->
					<div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; border-top: 1px solid #E5E7EB; padding-top: 14px;">
						<button class="btn btn-default btn-sm modal-sync-btn">
							Đồng bộ số liệu từ Facebook
						</button>
						<button class="btn btn-primary btn-sm modal-plan-btn">
							Lên kế hoạch tuần mới
						</button>
					</div>
				</div>
			`;

			d.$wrapper.find('.modal-body').html(modalHtml);

			d.$wrapper.find('.modal-sync-btn').on('click', function () {
				frappe.show_alert({ message: __("Đang đồng bộ số liệu từ Facebook..."), indicator: "blue" });
				frappe.call({
					method: "mmm_custom.mmm_custom.doctype.facebook_post.facebook_post.sync_all_posted_analytics",
					freeze: true,
					freeze_message: __("Đang lấy số liệu tương tác mới nhất..."),
					callback: function (sync_r) {
						if (sync_r.message && sync_r.message.status === "success") {
							frappe.show_alert({
								message: __(`Đã cập nhật ${sync_r.message.synced_count} bài viết!`),
								indicator: "green"
							});
							d.hide();
							listview.refresh();
							open_marketing_overview_modal(listview);
						}
					}
				});
			});

			d.$wrapper.find('.modal-plan-btn').on('click', function () {
				d.hide();
				open_agent_command_center(listview, "generate");
			});
		}
	});
}

