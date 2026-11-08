import frappe
from verto.api.mobile.profile import get_user_employee


def require_login():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)


@frappe.whitelist()
def get_navigation_access():
    require_login()

    employee_id = get_user_employee() or ""

    return {
        "has_employee_profile": bool(employee_id),
        "employee_id": employee_id,
    }
