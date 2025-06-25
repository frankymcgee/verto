// Copyright (c) 2024, Webwire and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Generated Documents", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('Generated Documents', {
    before_save: function(frm) {
        let input_file = frm.doc.input_file;
        let company_name = frm.doc.company_name;
        let managing_director = frm.doc.managing_director;
        let company_logo = frm.doc.company_logo;
        let replacement_id = frm.doc.replacement_id;
        let abbreviation = frm.abbreviation;
        let publish_date = frm.publish_date;
        let review_date = frm.review_date;

        if (!input_file || !company_name || !managing_director || !company_logo || !replacement_id) {
            frappe.msgprint(__('Please make sure all fields are filled.'));
            frappe.validated = false;
            return;
        }

        frappe.call({
            method: 'verto.api.process.generate_document',
            args: {
                input_file: input_file,
                company_name: company_name,
                managing_director: managing_director,
                company_logo: company_logo,
                replacement_id: replacement_id,
                abbreviation: abbreviation,
                publish_date: publish_date,
                review_date: review_date
            },
            callback: function(response) {
                if (response.message && response.message.url) {
                    let generated_url = response.message.url; // Extract the URL from the response
                    frappe.msgprint(__('Document generated successfully.'));
                    frm.set_value('generated_document_url', generated_url); // Set the URL to the field
                } else {
                    frappe.msgprint(__('An error occurred while generating the document.'));
                }
            }
        });
    }
});
