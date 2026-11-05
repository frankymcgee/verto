import frappe

from verto.api.mobile.documents import get_allowed_mobile_doctypes


@frappe.whitelist()
def get_mobile_forms():
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)

    forms = [
        {
            "label": doctype,
            "doctype": doctype,
            "route": f"/verto-mobile/new/{mobile_doctype}",
        }
        for mobile_doctype, doctype in get_allowed_mobile_doctypes().items()
        if frappe.has_permission(doctype, "create")
    ]

    return {
        "forms": forms
    }