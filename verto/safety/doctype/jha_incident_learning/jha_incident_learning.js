frappe.ui.form.on("JHA Incident Learning", {
    refresh(frm) {
        if (!frappe.user.has_role("System Manager")) return;
        if (frm.doc.source_review_required) {
            frm.set_intro(__("Prepare a sanitised draft from the INX source. Check for missed or indirect identifiers, verify the safety facts, risk tags and recorded actions, then enable Available for JHA."), "orange");
        }
        if (frm.doc.inx_source) {
            frm.add_custom_button(__("Review INX Source"), () => {
                frappe.set_route("Form", "JHA INX Incident", frm.doc.inx_source);
            });
            if (!frm.doc.available_for_jha && !frm.is_new()) {
                frm.add_custom_button(__("Prepare Sanitised Draft"), () => {
                    if (frm.is_dirty()) {
                        frappe.msgprint(__("Save the lesson before preparing its sanitised draft."));
                        return;
                    }
                    frappe.require("/assets/verto/js/inx_incident_import.js", () => {
                        verto.inx_incidents.prepare_drafts([frm.doc.name], () => frm.reload_doc());
                    });
                });
            }
        }
    },
});
