// Paste into Web Form → Scripting / Style → Client Script.
// Keep any existing Client Script code; this does not replace after_load.
frappe.require('/assets/verto/js/web_form_attachments.js').then(() => {
    verto.web_form_attachments.setup();
});
