// Copyright (c) 2026, Webwire and contributors
// For license information, please see license.txt

frappe.ui.form.on("CCV - Vehicles and Mobile Equipment", {
	refresh: function (frm) {
        const add_button = function (location, class_name, label, style, callback, prepend = false) {// Function to add a button
            if (!$(location).find(`.${class_name}`).length) {// Check if the button already exists
                const button_html = `
                    <button class="btn btn-primary btn-xs ${class_name}" style="${style}">
                        ${label}
                    </button>
                `;
                if (prepend) {// Append or prepend the button based on the `prepend` flag
                    $(location).prepend(button_html);
                } else {
                    $(location).append(button_html);
                }
                $(`.${class_name}`).on('click', callback);// Attach the click event to the button
            }
        };
        if (!frm.is_new()) {// Add the "+" button only if the form is not new
            add_button(
                frm.page.page_actions,
                'custom-new-record-btn',
                '+',
                'display: flex; width: auto; align-items: center; justify-content: center;',
                function () {
                    // Create a new record
                    frappe.new_doc(frm.doc.doctype);
                },
                true // Prepend to place it to the left of the "Save" button
            );
        }
        let custom_container = frm.$wrapper.find('.form-page').next('.custom-action-container');// Create a custom container after the form-page element if it doesn't already exist
        if (!custom_container.length) {
            custom_container = $(`
                <div class="custom-action-container" style="width: 100%; margin-top: 20px; margin-bottom: 20px;"></div>
            `).insertAfter(frm.$wrapper.find('.form-page'));
        }
        add_button(// Add the "Add Attachment" button before the Save button
            custom_container,
            'custom-attach-btn',
            'Add Attachment',
            'width: 100%; padding: 12px 0; font-size: 16px; text-align: center; display: block; margin-bottom: 10px;',
            function () {
                if (frm.is_new()) {
                    frm.save().then(() => {
                        frm.attachments.new_attachment();
                    });
                } else {
                    frm.attachments.new_attachment();
                }
            }
        );
        add_button(// Add the "Save" button to the custom container
            custom_container,
            'custom-save-bottom-btn',
            'Save',
            'width: 100%; padding: 12px 0; font-size: 16px; text-align: center; display: block;',
            function () {
                frm.save().then(() => {
                    window.location.href = '/app/home';
                }).catch((err) => {
                    frappe.msgprint(__('Failed to save the form. Please check for required fields or validation issues.'));
                });
            }
        );
    }
});
