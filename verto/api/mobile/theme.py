"""The signed-in user's existing Desk theme, shared with Verto Mobile."""

import frappe


def normalise_theme(value):
    return value if value in ("Light", "Dark", "Automatic") else "Light"


@frappe.whitelist()
def get_user_theme():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)
    return {
        "user": frappe.session.user,
        "theme": normalise_theme(frappe.db.get_value("User", frappe.session.user, "desk_theme")),
    }
