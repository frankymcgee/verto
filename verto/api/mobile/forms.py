import frappe


@frappe.whitelist()
def get_mobile_forms():
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)

    forms = [
        {
            "label": "Field Interaction",
            "doctype": "Field Interaction",
            "description": "Capture field observations, conversations and safety interactions.",
            "icon": "clipboard-list",
            "route": "/verto-mobile/new/field-interaction",
            "category": "Safety"
        },
        {
            "label": "Commitment Interaction",
            "doctype": "Commitment Interaction",
            "description": "Record commitments, engagement and follow-up actions.",
            "icon": "handshake",
            "route": "/verto-mobile/new/commitment-interaction",
            "category": "Safety"
        },
        {
            "label": "Workplace Inspection",
            "doctype": "Workplace Inspection",
            "description": "Complete workplace inspections from the field.",
            "icon": "search-check",
            "route": "/verto-mobile/new/workplace-inspection",
            "category": "Inspection"
        },
        {
            "label": "Job Hazard Analysis Review",
            "doctype": "Job Hazard Analysis Review",
            "description": "Review JHAs and capture controls or improvement items.",
            "icon": "file-check",
            "route": "/verto-mobile/new/job-hazard-analysis-review",
            "category": "Review"
        },
        {
            "label": "Contractor Management Audit Checklist",
            "doctype": "Contractor Management Audit Checklist",
            "description": "Complete contractor management checks and audit questions.",
            "icon": "shield-check",
            "route": "/verto-mobile/new/contractor-management-audit-checklist",
            "category": "Audit"
        }
    ]

    return {
        "forms": forms
    }