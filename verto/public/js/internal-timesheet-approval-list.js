(function () {
    // Frappe evaluates the standard/hook list script before the site's Client
    // Script. Append our onload after both, preserving the existing actions.
    queueMicrotask(function () {
        const settings = frappe.listview_settings.Timesheet || {};
        const previous = settings.onload;
        settings.onload = function (listview) {
            if (previous) previous.call(this, listview);
            const roles = ["System Manager", "Accounts Manager", "HR Manager", "Projects Manager", "Verto Planner Manager"];
            if (frappe.session.user !== "Administrator" && !roles.some(role => (frappe.user_roles || []).includes(role))) return;
            listview.page.add_inner_button(__("Internal Review"), () => frappe.set_route("internal-timesheet-approval"));
            listview.page.add_action_item(__("Review & Approve Selected"), function () {
                const names = listview.get_checked_items().map(row => row.name);
                if (!names.length) return frappe.msgprint(__("Select at least one Timesheet."));
                frappe.route_options = { timesheets: names };
                frappe.set_route("internal-timesheet-approval");
            });
        };
        frappe.listview_settings.Timesheet = settings;
    });
})();
