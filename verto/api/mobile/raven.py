import frappe


PERI_WORKSPACE = "Mine Site Support"


def require_login():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)


def get_channel_workspace_field():
    meta = frappe.get_meta("Raven Channel")
    fieldnames = {df.fieldname for df in meta.fields}

    if "workspace" in fieldnames:
        return "workspace"

    if "raven_workspace" in fieldnames:
        return "raven_workspace"

    return None


@frappe.whitelist()
def get_or_create_peri_channel():
    require_login()

    user_email = frappe.session.user
    channel_name = f"{user_email} _ P.E.R.I."

    existing_channel = frappe.db.get_value(
        "Raven Channel",
        {"channel_name": channel_name},
        "name",
    )

    if existing_channel:
        return {
            "channel": existing_channel,
            "url": f"/raven/{frappe.utils.quote(PERI_WORKSPACE)}/{frappe.utils.quote(existing_channel)}",
        }

    doc_data = {
        "doctype": "Raven Channel",
        "channel_name": channel_name,
        "type": "Private",
        "is_direct_message": 1,
    }

    workspace_field = get_channel_workspace_field()

    if workspace_field:
        doc_data[workspace_field] = PERI_WORKSPACE

    channel = frappe.get_doc(doc_data)
    channel.insert(ignore_permissions=False)

    return {
        "channel": channel.name,
        "url": f"/raven/{frappe.utils.quote(PERI_WORKSPACE)}/{frappe.utils.quote(channel.name)}",
    }