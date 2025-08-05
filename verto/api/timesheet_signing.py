import frappe

@frappe.whitelist(allow_guest=True)
def sign_timesheet(timesheet_name, signature_base64, full_name=None, date_signed=None):
    if not timesheet_name or not signature_base64:
        frappe.throw("Missing timesheet or signature.")
    ts = frappe.get_doc("Timesheet", timesheet_name)
    if ts.custom_client_signed == 1:
        return "Already signed"    
    ts.db_set('custom_client_signature', signature_base64)
    ts.db_set('custom_client_signed', 1)    
    if full_name:
        ts.db_set('custom_signed_full_name', full_name)
    if date_signed:
        ts.db_set('custom_date_signed', date_signed)
    frappe.db.commit()    
    logo_url = frappe.utils.get_url("/files/Company Logo.JPG")
    attachment = frappe.attach_print(
                doctype="Timesheet",
                name=ts.name,
                print_format="Weekly Timesheet",
                file_name=f"{ts.name}.pdf"
            )    
    frappe.sendmail(
                recipients=["jess@minesitesupport.com.au", "enquiries@minesitesupport.com.au"],
                reply_to="enquiries@minesitesupport.com.au",
                subject=f"Signed Timesheet for {ts.employee_name} - {ts.project_name}",
                message = f"""
                <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4; padding: 20px;">
                <tr>
                    <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; padding: 40px; border-radius: 6px;">
                        <tr>
                        <td align="center" style="padding-bottom: 30px;">
                            <img src="{logo_url}" alt="Mine Site Support" style="max-width: 150px; height: auto;">
                        </td>
                        </tr>
                        <tr>
                        <td style="font-family: sans-serif; font-size: 14px; color: #333;">
                            <p>Hi there,</p>
                            <p>Please find attached the signed weekly timesheet for <strong>{ts.employee_name}</strong>.</p>
                            <p>Kind Regards,<br><strong>Mine Site Support</strong></p>
                        </td>
                        </tr>
                    </table>

                    <table width="600" cellpadding="0" cellspacing="0" style="padding-top: 10px;">
                        <tr>
                        <td align="center" style="font-family: sans-serif; font-size: 11px; color: #888;">
                            <p>
                            This email was sent via <a href="https://webwire.com.au"><strong>Verto ERP</strong></a><br>
                            </p>
                        </td>
                        </tr>
                    </table>
                    </td>
                </tr>
                </table>
                """,
                delayed=False,
                attachments=[attachment]
            )
    return "Success"

@frappe.whitelist(allow_guest=True)
def get_timesheet_public(name):
    # Limit fields to avoid leaking sensitive info
    return frappe.get_value("Timesheet", name, [
        "employee",
        "employee_name",
        "project_name",
        "total_hours",
        "custom_monday_date",
        "custom_sunday_date"
    ], as_dict=True)

@frappe.whitelist()
def approve_timesheet_with_signature(timesheet, signature_dataurl, approved_by):
    doc = frappe.get_doc("Timesheet", timesheet)
    doc.internal_approved = 1
    doc.employee_approved = approved_by
    doc.approved_signature = signature_dataurl
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "success", "message": f"{timesheet} updated"}