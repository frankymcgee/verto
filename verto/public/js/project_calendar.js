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

frappe.views.calendar["Task"] = {
  gantt: {
    field_map: {
      id: "name",
      title: "subject",
      start: "exp_start_date",   // standard Task field
      end: "exp_end_date",       // standard Task field
      exp_start_time: "exp_start_time", // your custom time field
      exp_end_time: "exp_end_time",     // your custom time field
      progress: "progress"
    }
  }
};