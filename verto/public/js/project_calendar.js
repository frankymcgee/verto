// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.views.calendar["Project"] = {
	field_map: {
		start: "expected_start_date",
		end: "expected_end_date",
		id: "name",
		title: "project_name",
		allDay: "allDay",
		progress: "percent_complete",
		color: "color",
	},
	gantt: true,
	filters: [
		{
			fieldtype: "Link",
			fieldname: "project_type",
			options: "Project Type",
			label: __("Project Type"),
		},
	],
	get_events_method: "frappe.desk.calendar.get_events",
};