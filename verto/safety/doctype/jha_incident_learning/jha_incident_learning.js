frappe.ui.form.on("JHA Incident Learning", {
    refresh(frm) {
        if (!frappe.user.has_role("System Manager")) return;
        if (frm.doc.source_review_required) {
            frm.set_intro(__("Review the INX source and prepare a crew-facing summary without names or medical details. Check the risk tags and any recorded actions, then enable Available for JHA."), "orange");
        }
        if (frm.doc.inx_source) {
            frm.add_custom_button(__("Review INX Source"), () => {
                frappe.set_route("Form", "JHA INX Incident", frm.doc.inx_source);
            });
        }
    },
});
