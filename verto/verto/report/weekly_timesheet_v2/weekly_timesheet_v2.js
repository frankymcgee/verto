// Copyright (c) 2024, Webwire and contributors
// For license information, please see license.txt

{
    const timezone = frappe.boot.time_zone?.system || frappe.sys_defaults.time_zone;
    const lastMonday = moment.tz(timezone).startOf("isoWeek").subtract(1, "week");
    const lastSunday = lastMonday.clone().add(6, "days");

    frappe.query_reports["Weekly Timesheet v2"] = {
        filters: [
            {
                fieldname: "start_date",
                label: __("Start Date"),
                fieldtype: "Date",
                default: lastMonday.format("YYYY-MM-DD"),
            },
            {
                fieldname: "end_date",
                label: __("End Date"),
                fieldtype: "Date",
                default: lastSunday.format("YYYY-MM-DD"),
            },
            {
                fieldname: "exclude_operations",
                label: __("Exclude Operations & Execution"),
                fieldtype: "Select",
                options: ["Yes", "No"],
                default: "No",
            },
        ],
    };
}
