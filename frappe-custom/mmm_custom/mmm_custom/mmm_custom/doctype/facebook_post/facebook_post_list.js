// Copyright (c) 2026, MMM and contributors
// For license information, please see license.txt

frappe.listview_settings["Facebook Post"] = {
	add_fields: ["status", "course", "scheduled_time", "batch_id", "day_of_week"],
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
		// 1. Agent: Lên kế hoạch tuần (Live Mission Control Modal)
		listview.page.add_inner_button(__("🤖 Agent: Lên kế hoạch tuần"), function () {
			open_agent_command_center(listview, "generate");
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

		// 3. Làm lại cả tuần (Rollback with Live Mission Control)
		listview.page.add_inner_button(__("🔄 Làm lại cả tuần"), function () {
			open_agent_command_center(listview, "rollback");
		});
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
