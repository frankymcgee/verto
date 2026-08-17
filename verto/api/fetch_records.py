import frappe
from datetime import datetime
from frappe.utils.pdf import get_pdf


@frappe.whitelist()
def fetch_created_records():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)

    # Define the DocTypes to include in the list
    doctypes = [
        "Commitment Interaction",
        "Critical Control Verification",
        "Field Interaction", 
        "Job Hazard Analysis Review",
        "Supervisor BATB",
        "Workplace Inspection",
        "Prohibited and Restricted Tooling Checklist",
        "Safety Identification Rectification",
        "CCV - Confined Space",
        "CCV - Contact with Electricity",
        "CCV - Dropped Objects",
        "CCV - Entanglement and Crushing",
        "CCV - Fall From Height",
        "CCV - Hot Works",
        "CCV - Lifting Operations",
        "CCV - Uncontrolled Release of Energy",
        "CCV - Vehicles and Mobile Equipment",
        "CCV - Working Near Water"
    ]
    start_date = frappe.form_dict.get("start_date") or "2000-01-01"
    end_date = frappe.form_dict.get("end_date") or frappe.utils.nowdate()

    # Check if the logged-in user is Administrator or Lead HSE Advisor
    current_user = frappe.session.user

    is_admin = (
        current_user == "Administrator"
        or "Lead HSE Advisor" in frappe.get_roles(current_user)
    )

    # List to store all records across DocTypes
    all_records = []
    owner_names = {}

    for doctype in doctypes:
        if not frappe.has_permission(doctype, "read"):
            continue

        columns = set(frappe.db.get_table_columns(doctype))

        fields = ["name", "owner", "creation"]

        optional_fields = [
            "project_name",
            "contractor",
            "supervisor",
            "compliance_percentage",
            "work_scope"
        ]

        for field in optional_fields:
            if field in columns:
                fields.append(field)

        filters = {"creation": ["between", [start_date, end_date]]}

        if not is_admin:
            filters["owner"] = current_user

        records = frappe.get_list(
            doctype,
            filters=filters,
            fields=fields
        )

        for record in records:
            if isinstance(record.creation, datetime):
                formatted_creation = record.creation.strftime("%d-%b-%y %H:%M")
            else:
                formatted_creation = record.creation

            # Default compliance to 100% if the field does not exist or has no value
            if "compliance_percentage" in columns:
                compliance_value = record.get("compliance_percentage")

                if compliance_value is not None and compliance_value != "":
                    compliance_percentage = f"{round(float(compliance_value), 2)}%"
                else:
                    compliance_percentage = "100%"
            else:
                compliance_percentage = "100%"

            if record.owner not in owner_names:
                owner_names[record.owner] = (
                    frappe.db.get_value("User", record.owner, "full_name")
                    or record.owner
                )

            full_name = owner_names[record.owner]

            link = f"/app/{doctype.replace(' ', '-').lower()}/{record.name}"

            all_records.append({
                "doctype": doctype,
                "name": record.name,
                "owner": full_name,
                "creation": formatted_creation,
                "compliance_percentage": compliance_percentage,
                "link": link,
                "project": record.get("project_name") or "N/A",
                "contractor": record.get("contractor") or "N/A",
                "supervisor": record.get("supervisor") or "N/A",
                "task": record.get("work_scope") or "N/A"
            })

    # Sort the combined list by 'creation' in descending order
    sorted_records = sorted(all_records, key=lambda x: datetime.strptime(x["creation"], "%d-%b-%y %H:%M"), reverse=True)

    return sorted_records


@frappe.whitelist()
def generate_record_pdf(doctype, name):
    """Generate a PDF only when the current user can read the document."""
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)

    if not doctype or not name:
        frappe.throw("Missing required parameters: doctype or name")

    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")

    html = frappe.get_print(doctype, name, print_format=doctype)
    pdf = get_pdf(html)

    frappe.local.response.filename = f"{name}.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "download"


@frappe.whitelist()
def open_pdf():
    """Generate and return a PDF when the current user can read the document."""
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)

    doctype = frappe.form_dict.get("doctype")
    name = frappe.form_dict.get("name")

    if not doctype or not name:
        frappe.throw("Missing required parameters: doctype or name")

    try:
        doc = frappe.get_doc(doctype, name)
        doc.check_permission("read")

        html = frappe.get_print(doctype, name, print_format=doctype)
        pdf_data = get_pdf(html)

        frappe.response["filename"] = f"{name}.pdf"
        frappe.response["filecontent"] = pdf_data
        frappe.response["type"] = "binary"
    except frappe.PermissionError:
        raise
    except Exception as error:
        frappe.log_error(
            message=f"PDF Generation Error: {str(error)}",
            title="PDF Generation Error",
        )
        frappe.throw(f"Could not generate PDF: {str(error)}")
