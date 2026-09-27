// Bot Knowledge (edu lead engine, D-086): what the bot knows about every course and what is missing.
// Data comes from mmm_custom.engine.knowledge; the course data itself is edited on the CRM Product form.
frappe.pages["bot-knowledge"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Bot Knowledge"), single_column: true });
	wrapper.bot_knowledge = new BotKnowledge(page);
};

frappe.pages["bot-knowledge"].on_page_show = function (wrapper) {
	const course = frappe.route_options && frappe.route_options.course;
	frappe.route_options = null;
	wrapper.bot_knowledge.load(course);
};

const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));

class BotKnowledge {
	constructor(page) {
		this.page = page;
		page.set_primary_action(__("Refresh"), () => this.load(this.current), "refresh");
		page.add_inner_button(__("New course"), () => frappe.new_doc("CRM Product"));
		this.$root = $(`
			<div class="bk">
				<div class="bk-stats"></div>
				<div class="bk-grid">
					<div class="bk-list"></div>
					<div class="bk-detail"><p class="text-muted">${__("Pick a course to see what the bot answers about it.")}</p></div>
				</div>
			</div>`).appendTo(page.main);
		$(`<style>
			.bk-stats { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
			.bk-stat { border: 1px solid var(--border-color); border-radius: var(--border-radius-md); padding: 10px 16px;
				background: var(--card-bg); min-width: 150px; }
			.bk-stat b { display: block; font-size: 1.5em; }
			.bk-grid { display: grid; grid-template-columns: minmax(320px, 2fr) 3fr; gap: 16px; }
			@media (max-width: 900px) { .bk-grid { grid-template-columns: 1fr; } }
			.bk-list, .bk-detail { border: 1px solid var(--border-color); border-radius: var(--border-radius-md);
				background: var(--card-bg); padding: 12px; max-height: 75vh; overflow-y: auto; }
			.bk-row { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 6px; cursor: pointer; }
			.bk-row:hover, .bk-row.active { background: var(--control-bg); }
			.bk-row .bk-name { flex: 1; }
			.bk-bar { width: 70px; height: 6px; background: var(--border-color); border-radius: 3px; overflow: hidden; }
			.bk-bar i { display: block; height: 100%; }
			.bk-group { margin: 10px 0 4px; font-weight: 600; color: var(--text-muted); font-size: var(--text-sm); }
			.bk-detail h4 { margin-top: 0; }
			.bk-detail h5 { margin-top: 16px; }
			.bk-faq { border-left: 3px solid var(--primary); padding: 4px 10px; margin-bottom: 10px; }
			.bk-reply { background: var(--control-bg); border-radius: 10px; padding: 6px 10px; white-space: pre-wrap; margin-top: 4px; }
			.bk-gap { color: var(--red-600, #c0392b); }
		</style>`).appendTo(this.$root);
	}

	color(pct) {
		return pct >= 100 ? "var(--green-500, #2ecc71)" : pct >= 50 ? "var(--orange-500, #f39c12)" : "var(--red-500, #e74c3c)";
	}

	async load(course) {
		const rows = (await frappe.call({ method: "mmm_custom.engine.knowledge.overview" })).message || [];
		this.rows = rows;
		const full = rows.filter((r) => r.coverage >= 100).length;
		const withFaq = rows.filter((r) => r.faqs).length;
		const avg = rows.length ? Math.round(rows.reduce((s, r) => s + r.coverage, 0) / rows.length) : 0;
		const stat = (label, value) => `<div class="bk-stat"><b>${esc(value)}</b>${esc(label)}</div>`;
		this.$root.find(".bk-stats").html([
			stat(__("Courses the bot knows"), rows.length),
			stat(__("Average coverage"), `${avg}%`),
			stat(__("Fully covered"), full),
			stat(__("Courses with FAQs"), withFaq),
		].join(""));
		const groups = {};
		rows.forEach((r) => (groups[r.group] = groups[r.group] || []).push(r));
		const $list = this.$root.find(".bk-list").empty();
		Object.keys(groups).sort().forEach((g) => {
			$(`<div class="bk-group">${esc(g)}</div>`).appendTo($list);
			groups[g].forEach((r) => {
				$(`<div class="bk-row" data-code="${esc(r.code)}">
						<span class="bk-name">${esc(r.name)}</span>
						<span class="text-muted small">${r.faqs} FAQ</span>
						<span class="bk-bar" title="${r.coverage}%"><i style="width:${r.coverage}%;background:${this.color(r.coverage)}"></i></span>
					</div>`).on("click", () => this.show(r.code)).appendTo($list);
			});
		});
		const pick = course || this.current;
		if (pick) this.show(pick);
	}

	async show(code) {
		this.current = code;
		this.$root.find(".bk-row").removeClass("active").filter(`[data-code="${code}"]`).addClass("active");
		const c = (await frappe.call({ method: "mmm_custom.engine.knowledge.course", args: { product: code } })).message;
		const list = (items) => items.length ? `<ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : `<p class="text-muted">—</p>`;
		const fee = c.final_fee < c.fee
			? `${format_currency(c.fee, "VND")} → <b>${format_currency(c.final_fee, "VND")}</b> (${esc(c.promotions.join(", "))})`
			: format_currency(c.fee, "VND");
		const faqs = c.faqs.length ? c.faqs.map((f) => `
			<div class="bk-faq">
				<div><b>${esc(f.question)}</b></div>
				${f.examples.length ? `<div class="text-muted small">${__("Customers also ask")}: ${esc(f.examples.join(" · "))}</div>` : ""}
				${f.error ? `<div class="bk-gap">${esc(f.error)}</div>` : `<div class="bk-reply">${esc(f.reply)}</div>`}
			</div>`).join("") : `<p class="text-muted">${__("No FAQs yet: Jev cannot answer questions specific to this course.")}</p>`;
		const schedules = c.schedules.map((s) => `${s.weekday} ${frappe.datetime.str_to_user(s.date)} · ${s.shift} · ${s.branch}`);
		this.$root.find(".bk-detail").html(`
			<h4>${esc(c.name)} <span class="text-muted small">${esc(c.code)} · ${c.coverage}%</span></h4>
			<p><a href="/app/crm-product/${encodeURIComponent(c.code)}">${__("Edit course data")}</a></p>
			${c.gaps.length ? `<h5>${__("Missing")}</h5><ul>${c.gaps.map((g) => `<li class="bk-gap">${esc(g)}</li>`).join("")}</ul>` : ""}
			<h5>${__("Overview")}</h5><p>${esc(c.summary) || '<span class="text-muted">—</span>'}</p>
			<p>${__("Fee")}: ${fee} · ${__("Duration")}: ${esc(c.duration || "—")} · ${__("Audience")}: ${esc(c.audience || "—")}
				${c.min_age ? ` (${c.min_age}–${c.max_age} ${__("years")})` : ""}</p>
			<h5>${__("Syllabus")}</h5>${list(c.syllabus)}
			<h5>${__("Course FAQs — the reply the customer gets")}</h5>${faqs}
			<h5>${__("Next classes")} (${c.schedule_count})</h5>${list(schedules)}
			<h5>${__("How Jev recognises this course")}</h5><pre class="small">${esc(c.jev_reads)}</pre>
			<h5>${__("Next courses suggested")}</h5>${list(c.next_courses)}`);
	}
}
