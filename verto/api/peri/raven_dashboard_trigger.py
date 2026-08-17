import frappe


@frappe.whitelist()
def send_dashboard_analysis_command(project_scope_name):
    """
    Sends a dashboard analysis command into the current user's PERI Raven channel,
    then returns the Raven channel URL.

    Called from an ERPNext Custom HTML Block button.
    """

    project_scope_name = clean_value(project_scope_name)

    if not project_scope_name:
        frappe.throw("Project Scope Name is required.")

    user_email = frappe.session.user

    if user_email == "Guest":
        frappe.throw("You must be logged in to use PERI dashboard analysis.")

    workspace = "Mine Site Support"
    bot_name = "P.E.R.I."
    channel_name = f"{user_email} _ {bot_name}"
    command = f"Analyse the dashboard for {project_scope_name}"

    channel_id = get_or_create_peri_channel(
        channel_name=channel_name,
        workspace=workspace,
        user_email=user_email,
    )

    message_name = send_raven_message(
        channel_id=channel_id,
        text=command,
    )

    return {
        "ok": True,
        "project_scope_name": project_scope_name,
        "command": command,
        "channel_id": channel_id,
        "message_name": message_name,
        "raven_url": f"/raven/{frappe.utils.quote(workspace)}/{frappe.utils.quote(channel_id)}",
    }


def clean_value(value):
    if value in [None, "", "null", "undefined", "None"]:
        return None

    return str(value).strip()


def get_or_create_peri_channel(channel_name, workspace, user_email):
    existing_channel = frappe.db.get_value(
        "Raven Channel",
        {
            "channel_name": channel_name,
        },
        "name",
    )

    if existing_channel:
        return existing_channel

    channel = frappe.get_doc({
        "doctype": "Raven Channel",
        "channel_name": channel_name,
        "type": "Private",
        "is_direct_message": 1,
        "workspace": workspace,
    })

    channel.insert(ignore_permissions=True)

    add_channel_member(channel.name, user_email)

    return channel.name


def add_channel_member(channel_id, user_email):
    """
    Best-effort member insert.
    Fieldnames can vary slightly by Raven version, so this checks metadata first.
    """

    if not frappe.db.exists("DocType", "Raven Channel Member"):
        return

    meta = frappe.get_meta("Raven Channel Member")

    channel_field = None
    user_field = None

    for fieldname in ["channel_id", "channel", "raven_channel"]:
        if meta.get_field(fieldname):
            channel_field = fieldname
            break

    for fieldname in ["user_id", "user", "raven_user"]:
        if meta.get_field(fieldname):
            user_field = fieldname
            break

    if not channel_field or not user_field:
        return

    filters = {
        channel_field: channel_id,
        user_field: user_email,
    }

    if frappe.db.exists("Raven Channel Member", filters):
        return

    doc = {
        "doctype": "Raven Channel Member",
        channel_field: channel_id,
        user_field: user_email,
    }

    frappe.get_doc(doc).insert(ignore_permissions=True)


def send_raven_message(channel_id, text):
    """
    Inserts a Raven Message directly.

    If your Raven version has slightly different fieldnames, the metadata checks below
    will adapt for the common variants.
    """

    meta = frappe.get_meta("Raven Message")

    doc = {
        "doctype": "Raven Message",
    }

    # Channel field
    if meta.get_field("channel_id"):
        doc["channel_id"] = channel_id
    elif meta.get_field("channel"):
        doc["channel"] = channel_id
    elif meta.get_field("raven_channel"):
        doc["raven_channel"] = channel_id
    else:
        frappe.throw("Could not find channel field on Raven Message.")

    # Message content field
    if meta.get_field("text"):
        doc["text"] = text
    elif meta.get_field("message"):
        doc["message"] = text
    elif meta.get_field("content"):
        doc["content"] = text
    else:
        frappe.throw("Could not find message content field on Raven Message.")

    # Message type if available
    if meta.get_field("message_type"):
        doc["message_type"] = "Text"

    # Owner/sender style fields if available
    if meta.get_field("sender"):
        doc["sender"] = frappe.session.user

    if meta.get_field("user"):
        doc["user"] = frappe.session.user

    if meta.get_field("owner"):
        doc["owner"] = frappe.session.user

    message = frappe.get_doc(doc)
    message.insert(ignore_permissions=True)

    frappe.db.commit()

    return message.name