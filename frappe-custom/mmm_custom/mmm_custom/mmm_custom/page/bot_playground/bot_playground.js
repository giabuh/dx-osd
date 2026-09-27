// Bot Playground (edu lead engine, D-038/D-060): chat as a customer and inspect every step of each turn.
// Runs dry: mmm_custom.engine.playground never sends to Chatwoot and never writes Leads.
frappe.pages["bot-playground"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Bot Playground"), single_column: true });
	new BotPlayground(page);
};

class BotPlayground {
	constructor(page) {
		this.page = page;
		this.session = frappe.utils.get_random(10);
		this.lead = page.add_field({
			fieldname: "lead", label: __("Returning customer (Lead)"), fieldtype: "Link", options: "CRM Lead",
			change: () => this.reset(),
		});
		this.jev = page.add_field({
			fieldname: "jev", label: __("Use Jev"), fieldtype: "Check",
			description: __("Ask TypeSafe Jev in this sandbox even when it is not live for customers"),
		});
		page.set_primary_action(__("New conversation"), () => this.reset(), "refresh");
		page.add_inner_button(__("Replay a logged decision"), () => this.ask_replay());
		this.$root = $(`
			<div class="bot-pg">
				<div class="bot-pg-chat">
					<div class="bot-pg-log"></div>
					<form class="bot-pg-form">
						<input class="form-control" autocomplete="off" placeholder="${__("Type as the customer…")}">
						<button class="btn btn-primary btn-sm" type="submit">${__("Send")}</button>
					</form>
				</div>
				<div class="bot-pg-inspector">
					<p class="text-muted">${__("Send a message to see how the bot understands, decides and replies.")}</p>
				</div>
			</div>`).appendTo(page.main);
		$(`<style>
			.bot-pg { display: grid; grid-template-columns: minmax(280px, 2fr) 3fr; gap: 16px; }
			@media (max-width: 900px) { .bot-pg { grid-template-columns: 1fr; } }
			.bot-pg-chat, .bot-pg-inspector { border: 1px solid var(--border-color); border-radius: var(--border-radius-md);
				padding: 12px; background: var(--card-bg); }
			.bot-pg-log { height: 60vh; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; margin-bottom: 8px; }
			.bot-pg-msg { max-width: 85%; padding: 8px 12px; border-radius: 12px; white-space: pre-wrap; }
			.bot-pg-msg.customer { align-self: flex-end; background: var(--primary); color: var(--white); }
			.bot-pg-msg.bot { align-self: flex-start; background: var(--control-bg); }
			.bot-pg-chips { display: flex; flex-wrap: wrap; gap: 6px; }
			.bot-pg-form { display: flex; gap: 8px; }
			.bot-pg-inspector { max-height: 70vh; overflow-y: auto; }
			.bot-pg-inspector pre { white-space: pre-wrap; font-size: var(--text-xs); }
		</style>`).appendTo(this.$root);
		this.$log = this.$root.find(".bot-pg-log");
		this.$inspector = this.$root.find(".bot-pg-inspector");
		this.$root.find("form").on("submit", (e) => {
			e.preventDefault();
			const $input = this.$root.find("input");
			const text = $input.val().trim();
			if (text) {
				$input.val("");
				this.send(text);
			}
		});
	}

	bubble(text, who) {
		$(`<div class="bot-pg-msg ${who}"></div>`).text(text).appendTo(this.$log);
		this.$log.scrollTop(this.$log[0].scrollHeight);
	}

	chips(titles) {
		const $chips = $('<div class="bot-pg-chips"></div>').appendTo(this.$log);
		titles.forEach((title) => {
			$('<button class="btn btn-default btn-xs"></button>').text(title).on("click", () => this.send(title)).appendTo($chips);
		});
		this.$log.scrollTop(this.$log[0].scrollHeight);
	}

	async send(text) {
		this.bubble(text, "customer");
		const r = await frappe.call({
			method: "mmm_custom.engine.playground.simulate",
			args: { session: this.session, text, lead: this.lead.get_value() || null, jev: this.jev.get_value() ? 1 : 0 },
		});
		const out = r.message;
		if (out.duplicate) return;
		out.reply.messages.forEach((m) => this.bubble(m, "bot"));
		if (out.reply.buttons.length) this.chips(out.reply.buttons);
		this.show(out);
	}

	section(title, data) {
		return `<h5>${frappe.utils.escape_html(title)}</h5><pre>${frappe.utils.escape_html(JSON.stringify(data, null, 2))}</pre>`;
	}

	show(out) {
		this.$inspector.html([
			this.section(__("1 · Keyword matches"), out.understanding),
			this.section(__("2 · Jev"), out.jev),
			this.section(__("3 · Decision"), out.decision),
			this.section(__("4 · Reply and template variants"), out.reply),
			this.section(__("5 · Events that would fire"), out.events),
			this.section(__("6 · Side effects (not executed)"), out.effects),
			this.section(__("State after this turn"), out.state),
		].join(""));
	}

	async reset() {
		await frappe.call({ method: "mmm_custom.engine.playground.reset", args: { session: this.session } });
		this.session = frappe.utils.get_random(10);
		this.$log.empty();
		this.$inspector.html(`<p class="text-muted">${__("New conversation.")}</p>`);
	}

	ask_replay() {
		frappe.prompt(
			{ fieldname: "log", fieldtype: "Link", options: "AI Decision Log", label: __("AI Decision Log"), reqd: 1 },
			async (values) => {
				const r = await frappe.call({ method: "mmm_custom.engine.playground.replay", args: { log_name: values.log, jev: this.jev.get_value() ? 1 : 0 } });
				this.$inspector.html(
					this.section(__("Then (as logged)"), r.message.then) +
					this.section(__("Now (current data, templates and settings)"), r.message.now)
				);
			},
			__("Replay a decision"),
			__("Replay")
		);
	}
}
