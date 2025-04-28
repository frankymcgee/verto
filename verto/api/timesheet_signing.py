import frappe
import base64
from frappe.utils.file_manager import save_file

@frappe.whitelist(allow_guest=True)
def sign_timesheet(timesheet_name, signature_base64, full_name=None, date_signed=None):
    if not timesheet_name or not signature_base64:
        frappe.throw("Missing timesheet or signature.")

    # Update Timesheet with signature link
    ts = frappe.get_doc("Timesheet", timesheet_name)
    ts.db_set('custom_client_signature', signature_base64)
    ts.db_set('custom_signature_signed', 1)
    
    if full_name:
        ts.db_set('custom_signed_full_name', full_name)
    if date_signed:
        ts.db_set('custom_date_signed', date_signed)

    frappe.db.commit()

    return "Success"