import frappe

@frappe.whitelist()
def create_shift_assignment(
    employee: str,
    company: str,
    shift_type: str,
    start_date: str,
    end_date: str | None,
    status: str,
    custom_project: str | None = None,
    shift_location: str | None = None,
    shift_schedule_assignment: str | None = None,
) -> str:
    doc = frappe.new_doc("Shift Assignment")
    doc.employee = employee
    doc.company = company
    doc.shift_type = shift_type
    doc.start_date = start_date
    doc.end_date = end_date
    doc.status = status
    doc.shift_location = shift_location
    doc.shift_schedule_assignment = shift_schedule_assignment
    if custom_project:
        # trust ID; if subject was passed by mistake, resolve to name
        if not frappe.db.exists("Project", custom_project):
            resolved = frappe.db.get_value("Project", {"subject": custom_project}, "name")
            if not resolved:
                frappe.throw(f"Project '{custom_project}' not found as ID or subject.")
            custom_project = resolved
        doc.custom_project = custom_project
    doc.save()
    doc.submit()
    return doc.name
