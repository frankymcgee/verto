import frappe


def require_login():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)


@frappe.whitelist()
def get_navigation_access():
    require_login()

    has_employee_profile = bool(
        frappe.db.exists("DocType", "Employee")
        and frappe.db.exists(
            "Employee",
            {"user_id": frappe.session.user},
        )
    )

    return {
        "has_employee_profile": has_employee_profile,
    }
