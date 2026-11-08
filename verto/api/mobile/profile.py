"""Read-only account and employment details for the signed-in mobile user."""
import frappe


EMPLOYEE_FIELDS = (
    "employee_name", "employee_number", "company", "department", "designation",
    "employment_type", "branch", "status", "date_of_joining", "company_email",
    "personal_email", "cell_number",
)


def require_login():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)


def get_user_employee(fields="name"):
    """Resolve only this session's employee, preferring an active record."""
    require_login()
    if not frappe.db.exists("DocType", "Employee"):
        return None

    filters = {"user_id": frappe.session.user}
    options = {"as_dict": isinstance(fields, (list, tuple)), "order_by": "creation desc"}
    return frappe.db.get_value("Employee", {**filters, "status": "Active"}, fields, **options) or (
        frappe.db.get_value("Employee", filters, fields, **options)
    )


@frappe.whitelist(methods=["GET"])
def get_my_profile():
    require_login()
    frappe.local.response_headers["Cache-Control"] = "no-store"

    # Explicit field lists keep payroll, identity documents and other HR data
    # out of this self-service response, including when custom fields exist.
    user = frappe.db.get_value(
        "User", frappe.session.user,
        ["full_name", "email", "mobile_no", "phone"], as_dict=True,
    ) or {}
    employee_fields = ["name"]
    if frappe.db.exists("DocType", "Employee"):
        meta = frappe.get_meta("Employee")
        employee_fields.extend(field for field in EMPLOYEE_FIELDS if meta.has_field(field))
    employee = get_user_employee(employee_fields)

    return {"user": user, "employee": employee}
