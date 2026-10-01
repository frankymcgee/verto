frappe.listview_settings["JHA Incident Learning"] = {
    onload(listview) {
        if (!frappe.user.has_role("System Manager")) return;
        listview.page.add_inner_button(__("Import INX Export"), () => {
            frappe.require("/assets/verto/js/inx_incident_import.js", () => {
                verto.inx_incidents.open_import(() => listview.refresh());
            });
        });
    },
};
