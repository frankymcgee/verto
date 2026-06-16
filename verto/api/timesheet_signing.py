import frappe
from verto.api.automate import (
    get_employee_doc,
    generate_attachment_name,
    generate_attachment,
    get_verto_mobile_email_settings,
    get_sendmail_options,
    build_email_body,
)


@frappe.whitelist(allow_guest=True)
def sign_timesheet(timesheet_name, signature_base64, full_name=None, date_signed=None):
    if not timesheet_name or not signature_base64:
        frappe.throw("Missing timesheet or signature.")

    ts = frappe.get_doc("Timesheet", timesheet_name)

    if ts.custom_client_signed == 1:
        return "Already signed"

    ts.db_set("custom_client_signature", signature_base64)
    ts.db_set("custom_client_signed", 1)

    if full_name:
        ts.db_set("custom_signed_full_name", full_name)

    if date_signed:
        ts.db_set("custom_date_signed", date_signed)

    frappe.db.commit()

    email_settings = get_verto_mobile_email_settings()
    recipients = email_settings.email_recipients

    # Do not fail the public signing action if notification recipients are not configured.
    # The timesheet has already been signed successfully at this point.
    if not recipients:
        frappe.log_error(
            title="Signed Timesheet email skipped - no recipients",
            message=(
                f"No recipients were configured for signed Timesheet {ts.name}. "
                "Add recipients to Verto Mobile Settings.email_recipients."
            ),
        )
        return "Success"

    employee_doc = get_employee_doc(ts)
    employee_name = employee_doc.employee_name

    file_name = generate_attachment_name(ts, employee_doc, include_project=True)
    attachment = generate_attachment(ts, file_name)

    content_html = f"""
        <p>Please find attached the signed weekly timesheet for <strong>{employee_name}</strong>.</p>
        <p><strong>Project:</strong> {ts.project_name}</p>
        <p>Kind Regards,<br><strong>{frappe.defaults.get_global_default("company") or "Mine Site Support"}</strong></p>
    """

    sendmail_options = get_sendmail_options(email_settings)

    frappe.sendmail(
        recipients=recipients,
        subject=f"Signed Timesheet for {employee_name} - {ts.project_name}",
        message=build_email_body(content_html, email_settings=email_settings),
        delayed=False,
        attachments=[attachment],
        **sendmail_options,
    )

    return "Success"


@frappe.whitelist(allow_guest=True)
def get_timesheet_public(name):
    # Limit fields to avoid leaking sensitive info.
    return frappe.get_value(
        "Timesheet",
        name,
        [
            "employee",
            "employee_name",
            "project_name",
            "total_hours",
            "custom_monday_date",
            "custom_sunday_date",
            "custom_client_signed",
        ],
        as_dict=True,
    )


@frappe.whitelist()
def approve_timesheet_with_signature(timesheet, signature_dataurl, approved_by):
    doc = frappe.get_doc("Timesheet", timesheet)
    doc.internal_approved = 1
    doc.employee_approved = approved_by
    doc.approved_signature = signature_dataurl
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success", "message": f"{timesheet} updated"}
