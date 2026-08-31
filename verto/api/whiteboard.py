import frappe


@frappe.whitelist()
def save_user_whiteboard_state(state: str):
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("You must be logged in to save a whiteboard.")

    if not isinstance(state, str):
        frappe.throw("Invalid whiteboard state.")

    if frappe.db.exists("User Whiteboard State", user):
        frappe.db.set_value(
            "User Whiteboard State",
            user,
            "state",
            state,
            update_modified=False,
        )
    else:
        document = frappe.new_doc("User Whiteboard State")
        document.user = user
        document.state = state
        document.insert(ignore_permissions=True)

    return {"saved": True}