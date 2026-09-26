// Copyright (c) 2026, MMM and contributors
// For license information, please see license.txt

frappe.views.calendar["Facebook Post"] = {
	field_map: {
		start: "scheduled_time",
		end: "scheduled_time",
		id: "name",
		title: "title",
		status: "status"
	},
	style_map: {
		Draft: "warning",
		Scheduled: "info",
		Posted: "success",
		Failed: "danger"
	}
};
