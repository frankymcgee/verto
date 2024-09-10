// Copyright (c) 2024, Webwire and contributors
// For license information, please see license.txt

frappe.query_reports["Weekly Timesheet v2"] = {
    "filters": [
        {
            "fieldname": "start_date",
            "label": __("Start Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_days(frappe.datetime.get_today(), -7),
            "reqd": 1
        },
        {
            "fieldname": "end_date",
            "label": __("End Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "exclude_operations",
            "label": __("Exclude Operations & Execution"),
            "fieldtype": "Select",
            "options": ["Yes", "No"],
            "default": "No"
        }
    ]
};

