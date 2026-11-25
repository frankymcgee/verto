import frappe
from verto.api.mobile.profile import get_user_employee
from verto.api.timesheet_access import can_review_timesheets


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
        "can_review_timesheets": can_review_timesheets(),
    }
