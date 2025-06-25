// Copyright (c) 2024, Webwire and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Prohibited and Restricted Tooling Checklist", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on('Prohibited and Restricted Tooling Checklist', {
    link_task: function (frm) {
        if (frm.doc.link_task && frm.doc.scope_or_wo == 'Work Scope') {
            frappe.call({// Fetch the Work Order Number from the selected Task
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Task',
                    filters: { 'name': frm.doc.link_task },
                    fieldname: 'work_order_number'
                },
                callback: function (response) {
                    if (response.message) {
                        frm.set_value('work_order_number', response.message.work_order_number);
                    } else {
                        frappe.msgprint(__('No Work Order Number found for this Task'));
                    }
                }
            });
        }
    },
    work_order_number: function (frm) {
        if (frm.doc.work_order_number && frm.doc.scope_or_wo == 'Work Order Number') {// Find the corresponding Task and set Task Selection
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Task',
                    filters: { 'work_order_number': frm.doc.work_order_number },
                    fieldname: 'name'
                },
                callback: function(response) {
                    if (response.message) {
                        frm.set_value('link_task', response.message.name);
                    } else {
                        frappe.msgprint(__('No task found for this Work Order Number'));
                        frm.set_value('task_selection', '');
                    }
                }
            });
        }
    },
    validate: function(frm) {
        
        let total_rating = 0;
        let rated_fields_count = 0;
        const rating_map = {
            'Compliant': 1,
            'Not Compliant': 0,
            'N/A': 1
        };

        // Iterate explicitly over Select-type fields only
        frm.meta.fields.forEach(field => {
            if (field.fieldtype === "Select" && !field.fieldname.includes('safety_category') && !field.fieldname.includes('improvement_required')) {
                const field_value = frm.doc[field.fieldname];
                if (field_value && rating_map.hasOwnProperty(field_value)) {
                    total_rating += rating_map[field_value];
                    rated_fields_count++;
                }
            }
        });
    

        const compliance_percentage = rated_fields_count 
            ? (total_rating / rated_fields_count) * 100 
            : 0;

        frm.set_value('compliance_percentage', compliance_percentage);
        setTimeout(() => {window.location.href = '/app/home';}, 2000);  // Redirect after 2 seconds
    }
});
