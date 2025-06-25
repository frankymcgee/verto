// Copyright (c) 2024, Webwire and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Job Hazard Analysis Review", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('Job Hazard Analysis Review', {
    refresh: function(frm) {
        // Function to add a button
        const add_button = function (location, class_name, label, style, callback, prepend = false) {
            // Check if the button already exists
            if (!$(location).find(`.${class_name}`).length) {
                // Create the button HTML
                const button_html = `
                    <button class="btn btn-primary btn-xs ${class_name}" style="${style}">
                        ${label}
                    </button>
                `;

                // Append or prepend the button based on the `prepend` flag
                if (prepend) {
                    $(location).prepend(button_html);
                } else {
                    $(location).append(button_html);
                }

                // Attach the click event to the button
                $(`.${class_name}`).on('click', callback);
            }
        };

        // Add the "+" button only if the form is not new
        if (!frm.is_new()) {
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

        // Create a custom container after the form-page element if it doesn't already exist
        let custom_container = frm.$wrapper.find('.form-page').next('.custom-action-container');
        if (!custom_container.length) {
            custom_container = $(
                '<div class="custom-action-container" style="width: 100%; margin-top: 20px; margin-bottom: 20px;"></div>'
            ).insertAfter(frm.$wrapper.find('.form-page'));
        }
        
        // Add the "Add Attachment" button before the Save button
        add_button(
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

        // Add the "Save" button to the custom container
        add_button(
            custom_container,
            'custom-save-bottom-btn',
            'Save',
            'width: 100%; padding: 12px 0; font-size: 16px; text-align: center; display: block;',
            function () {
                // Save the form
                frm.save_or_update();
                setTimeout(() => {
                    window.location.href = '/app/home';
                    }, 2000);  // Redirect after 2 seconds
            }
        );
    },
    link_task: function (frm) {
        if (frm.doc.link_task && frm.doc.scope_or_wo == 'Work Scope') {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Task',
                    filters: { 'name': frm.doc.link_task },
                    fieldname: 'work_order_number'
                },
                callback: function (response) {
                    const work_order_number = response.message?.work_order_number;
                    if (work_order_number) {
                        frm.set_value('work_order_number', work_order_number);
                    }
                }
            });
        }
    },
    work_order_number: function (frm) {
        if (frm.doc.work_order_number && frm.doc.scope_or_wo == 'Work Order Number') {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Task',
                    filters: { 'work_order_number': frm.doc.work_order_number },
                    fieldname: 'name'
                },
                callback: function(response) {
                    const task_name = response.message?.name;
                    if (task_name) {
                        frm.set_value('link_task', task_name);
                    }
                }
            });
        }
    },
    validate: function(frm) {
        let total_rating = 0;
        let count = 0;
        $.each(frm.fields_dict, function(fieldname, field) {// Iterate through all fields in the form
            if (fieldname.includes('safety_category') || fieldname.includes('improvement_required') || field.df.fieldtype !== "Select") { // Skip fields containing 'safety_category' or 'improvement_required' and non-Select fields
                return;  // Skip this iteration
            }
            let field_value = frm.doc[fieldname];
            if (!field_value) return; // Disregard the field if field_value is blank
            let rating_map = {// Assign values based on the selected option
                'Yes': 1,
                'Yes (fixed on the spot)': 0.75,
                'No': 0,
                'N/A': 1
            };
            if (rating_map.hasOwnProperty(field_value)) {
                total_rating += rating_map[field_value];
                count++;
            }
        });
        
        let average_percentage = count ? (total_rating / count) * 100 : 0; // Calculate the average rating and set the compliance percentage
        frm.set_value('compliance_percentage', average_percentage); // Set the Compliance Percentage
    }
});