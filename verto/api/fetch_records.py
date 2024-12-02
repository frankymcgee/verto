import frappe
from datetime import datetime
from frappe.utils.pdf import get_pdf

@frappe.whitelist()
def fetch_created_records():
    # Define the DocTypes to include in the list
    doctypes = ["Commitment Interaction", "Critical Control Verification", "Field Interaction", 
                "Job Hazard Analysis Review", "Pre-Commencement Audit", "Workplace Inspection"]
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
