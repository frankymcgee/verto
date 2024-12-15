import frappe
from datetime import datetime
from frappe.utils.pdf import get_pdf
from frappe.utils.print_format import download_pdf

@frappe.whitelist(allow_guest=True)
def fetch_created_records():
    # Define the DocTypes to include in the list
    doctypes = ["Commitment Interaction", "Critical Control Verification", "Field Interaction", 
                "Job Hazard Analysis Review", "Pre-Commencement Audit", "Workplace Inspection","Prohibited and Restricted Tooling Checklist"]
    start_date = frappe.form_dict.get("start_date") or "2000-01-01"
    end_date = frappe.form_dict.get("end_date") or frappe.utils.nowdate()

    # Check if the logged-in user is Administrator
    current_user = frappe.session.user
    is_admin = current_user == "Administrator"

    # List to store all records across DocTypes
    all_records = []

    for doctype in doctypes:
        # Check if the 'compliance_percentage' field exists for the current Doctype
        columns = frappe.db.get_table_columns(doctype)
        include_compliance = "compliance_percentage" in columns

        # Fields to fetch, include 'compliance_percentage' if it exists
        fields = ["name", "owner", "creation"]
        if include_compliance:
            fields.append("compliance_percentage")

        # Apply filters based on whether the user is Administrator
        filters = {"creation": ["between", [start_date, end_date]]}
        if not is_admin:
            filters["owner"] = current_user  # Restrict to records created by the current user

        # Fetch records for the current Doctype
        records = frappe.get_all(doctype, filters=filters, fields=fields)

        # Append each record with its Doctype for distinction
        for record in records:
            # Format creation datetime
            if isinstance(record.creation, datetime):
                formatted_creation = record.creation.strftime("%d-%b-%y %H:%M")
            else:
                formatted_creation = record.creation  # Fallback in case it's not a datetime

            # Format compliance percentage
            compliance_percentage = record.get("compliance_percentage")
            if compliance_percentage is not None:
                compliance_percentage = f"{round(float(compliance_percentage), 2)}%"
            else:
                compliance_percentage = "N/A"

            # Fetch full name of the owner
            full_name = frappe.db.get_value("User", record.owner, "full_name") or record.owner

            all_records.append({
                "doctype": doctype,
                "name": record.name,
                "owner": full_name,  # Use full name instead of email
                "creation": formatted_creation,
                "compliance_percentage": compliance_percentage
            })

    # Sort the combined list by 'creation' in descending order
    sorted_records = sorted(all_records, key=lambda x: datetime.strptime(x["creation"], "%d-%b-%y %H:%M"), reverse=True)

    return sorted_records
@frappe.whitelist(allow_guest=True)
def generate_record_pdf(doctype, name):
    """
    Generate and return a PDF for the given record.
    """
    try:
        # Fetch the HTML representation of the document
        html = frappe.get_print(doctype, name, print_format=None)
        
        # Generate the PDF from the HTML
        pdf = get_pdf(html)
        
        # Set the appropriate response headers for downloading the PDF
        frappe.local.response.filename = f"{name}.pdf"
        frappe.local.response.filecontent = pdf
        frappe.local.response.type = "download"
    except Exception as e:
        frappe.throw(f"Failed to generate PDF: {str(e)}")

@frappe.whitelist(allow_guest=True)
def open_pdf():
    """
    Generate and return a PDF for the given record using get_pdf.
    """
    doctype = frappe.form_dict.get("doctype")
    name = frappe.form_dict.get("name")

    if not doctype or not name:
        frappe.throw("Missing required parameters: doctype or name")

    try:
        # Validate document existence
        doc = frappe.get_doc(doctype, name)
        if not doc:
            frappe.throw(f"The document {doctype} {name} does not exist.")

        # Validate permissions
        if not frappe.has_permission(doctype, "read"):
            frappe.throw(f"You do not have permission to access {doctype}.")

        # Fetch the HTML representation of the document
        html = frappe.get_print(doctype, name, print_format=None)

        # Generate the PDF from the HTML
        pdf_data = get_pdf(html)

        # Set the response headers for downloading
        frappe.response['filename'] = f"{name}.pdf"
        frappe.response['filecontent'] = pdf_data
        frappe.response['type'] = 'binary'
    except Exception as e:
        # Log error details for debugging
        frappe.log_error(message=f"PDF Generation Error: {str(e)}", title="PDF Generation Error")
        frappe.throw(f"Could not generate PDF: {str(e)}")