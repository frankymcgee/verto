// Copyright (c) 2026, Webwire Pty Ltd and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Shutdown Incident Tracker", {
// 	refresh(frm) {

// 	},
// });

frappe.listview_settings["Shutdown Incident Tracker"] = {
    add_fields: [
        "current_status"
    ],

    get_indicator(doc) {
        if (!doc.current_status) {
            return [__("No Status"), "gray", "current_status,is,not set"];
        }

        const status_map = {
            "Evidence Gathering": {
                color: "blue",
                filter: "current_status,=,Evidence Gathering"
            },
            "Investigation": {
                color: "orange",
                filter: "current_status,=,Investigation"
            },
            "Finalising": {
                color: "yellow",
                filter: "current_status,=,Finalising"
            },
            "Closed": {
                color: "green",
                filter: "current_status,=,Closed"
            }
        };

        const status = status_map[doc.current_status];

        if (!status) {
            return [__(doc.current_status), "gray", `current_status,=,${doc.current_status}`];
        }

        return [
            __(doc.current_status),
            status.color,
            status.filter
        ];
    }
};