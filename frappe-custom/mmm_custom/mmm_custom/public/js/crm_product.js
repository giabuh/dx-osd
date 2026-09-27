// CRM Product form: open the course in the Bot Knowledge page (D-086).
frappe.ui.form.on("CRM Product", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Bot Knowledge"), () => {
			frappe.route_options = { course: frm.doc.name };
			frappe.set_route("bot-knowledge");
		});
	},
});
