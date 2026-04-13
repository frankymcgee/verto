import frappe

PROJECT_DOCTYPE_MAP = [
    {"doctype": "CCV - Confined Space", "project_field": "project_name"},
    {"doctype": "CCV - Contact with Electricity", "project_field": "project_name"},
    {"doctype": "CCV - Dropped Objects", "project_field": "project_name"},
    {"doctype": "CCV - Entanglement and Crushing", "project_field": "project_name"},
    {"doctype": "CCV - Fall From Height", "project_field": "project_name"},
    {"doctype": "CCV - Hot Works", "project_field": "project_name"},
    {"doctype": "CCV - Lifting Operations", "project_field": "project_name"},
    {"doctype": "CCV - Uncontrolled Release of Energy", "project_field": "project_name"},
    {"doctype": "CCV - Vehicles and Mobile Equipment", "project_field": "project_name"},
    {"doctype": "CCV - Working Near Water", "project_field": "project_name"},
    {"doctype": "Commitment Interaction", "project_field": "project_name"},
    {"doctype": "Field Interaction", "project_field": "project_name"},
    {"doctype": "Job Hazard Analysis Review", "project_field": "project_name"},
    {"doctype": "Supervisor BATB", "project_field": "project_name"},
    {"doctype": "Workplace Inspection", "project_field": "project_name"},
]

@frappe.whitelist(allow_guest=True)
def get_project_documents_for_swot(project_value, limit_per_doctype=500):
    """
    Return records across configured DocTypes where the project field matches project_value.
    Intended for AI SWOT analysis.
    """

    try:
        limit_per_doctype = int(limit_per_doctype)
    except Exception:
        limit_per_doctype = 50

    results = []

    for config in PROJECT_DOCTYPE_MAP:
        doctype = config["doctype"]
        project_field = config["project_field"]

        try:
            matches = frappe.get_all(
                doctype,
                filters={project_field: project_value},
                fields=["name"],
                limit_page_length=limit_per_doctype,
            )

            for row in matches:
                doc = frappe.get_doc(doctype, row.name)

                results.append({
                    "doctype": doctype,
                    "name": row.name,
                    "project_field": project_field,
                    "data": doc.as_dict(),
                })

        except Exception as e:
            results.append({
                "doctype": doctype,
                "error": str(e),
            })

    return {
        "project_value": project_value,
        "total_records": len([r for r in results if not r.get("error")]),
        "records": results,
    }