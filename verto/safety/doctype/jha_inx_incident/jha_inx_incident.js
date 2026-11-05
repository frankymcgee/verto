frappe.ui.form.on("JHA INX Incident", {
    refresh(frm) {
        if (frm.is_new()) return;
        frm.set_intro(__("Restricted INX source. Personnel columns were excluded, but observations may contain names or medical details. Prepare a reviewed crew-facing lesson before enabling PERI access."));
        frm.add_custom_button(__("Review Crew Lesson"), () => {
            frappe.set_route("Form", "JHA Incident Learning", frm.doc.source_key);
        });
    },
});
