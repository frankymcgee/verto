frappe.ui.form.on("Weekly Timesheet Approval Request", {
    refresh(frm) {
        if (frm.doc.rejection_reason && frm.doc.notification_status === "Failed" && frappe.user_roles.includes("System Manager")) {
            frm.add_custom_button(__("Retry Rejection Email"), () => {
                frappe.call({
                    method: "verto.api.timesheet_approval.retry_rejection_notification",
                    args: {request_name: frm.doc.name},
                    freeze: true,
                    callback(response) {
                        frappe.msgprint(response.message.message);
                        frm.reload_doc();
                    }
                });
            });
        }
    }
});
