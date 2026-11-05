// Copyright (c) 2026, Webwire and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee", {
	setup(frm) {
		frm.set_query("qualification", "qualifications", () => ({
			filters: {
				is_qualification: 1,
			},
		}));
	},
});
