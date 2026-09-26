// Copyright (c) 2026, MMM and contributors
// For license information, please see license.txt

frappe.listview_settings["Facebook Post"] = {
	add_fields: ["status", "course", "scheduled_time"],
	get_indicator: function (doc) {
		if (doc.status === "Posted") {
			return [__("Đã đăng"), "green", "status,=,Posted"];
		} else if (doc.status === "Scheduled") {
			return [__("Chờ đăng"), "blue", "status,=,Scheduled"];
		} else if (doc.status === "Failed") {
			return [__("Lỗi"), "red", "status,=,Failed"];
		} else {
			return [__("Nháp"), "orange", "status,=,Draft"];
		}
	}
};
