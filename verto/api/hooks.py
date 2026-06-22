import re

import frappe
from frappe.exceptions import ValidationError


SETTINGS_DOCTYPE = "Verto Mobile Settings"
DEFAULT_RAVEN_WORKSPACE = "Mine Site Support"


def get_project_title(doc):
    return (doc.project_name or doc.name or "").strip()


def get_default_raven_workspace():
    workspace = None

    try:
        workspace = frappe.db.get_single_value(SETTINGS_DOCTYPE, "default_workspace")
    except Exception:
        workspace = None

    if not workspace:
        workspace = DEFAULT_RAVEN_WORKSPACE

    return (workspace or "").strip()


def make_raven_channel_slug(channel_name):
    value = (channel_name or "").strip().lower()

    # Remove characters that commonly break slugs
    value = re.sub(r"[^a-z0-9\s_-]", "", value)

    # Convert spaces/underscores to hyphens
    value = re.sub(r"[\s_]+", "-", value)

    # Collapse duplicate hyphens
    value = re.sub(r"-+", "-", value)

    return value.strip("-")


def get_or_create_safety_handover(doc):
    existing = frappe.db.get_value(
        "Safety Handover",
        {"project": doc.name},
        "name"
    )

    if existing:
        return existing

    new_doc = frappe.get_doc({
        "doctype": "Safety Handover",
        "project": doc.name
    })
    new_doc.insert(ignore_permissions=True)

    return new_doc.name


def get_or_create_lead_safety_handover(doc):
    existing = frappe.db.get_value(
        "Lead Safety Handover",
        {"project": doc.name},
        "name"
    )

    if existing:
        return existing

    new_doc = frappe.get_doc({
        "doctype": "Lead Safety Handover",
        "project": doc.name
    })
    new_doc.insert(ignore_permissions=True)

    return new_doc.name


def get_or_create_gp_project(doc):
    project_title = get_project_title(doc)
    team = getattr(doc, "roster_or_shutdown", None)

    existing_gp_project = None

    if getattr(doc, "gameplan_project", None):
        existing_gp_project = frappe.db.exists("GP Project", doc.gameplan_project)

    if not existing_gp_project:
        existing_gp_project = frappe.db.get_value(
            "GP Project",
            {"title": project_title},
            "name"
        )

    if existing_gp_project:
        return existing_gp_project

    gp_project = frappe.get_doc({
        "doctype": "GP Project",
        "title": project_title,
        "team": team,
        "progress": 0,
        "status": "Open",
        "readme": f"""<p>Welcome to the {project_title} page!</p>
<p>You can add a brief introduction about this project, links, resources, and other important information here.</p>"""
    })
    gp_project.insert(ignore_permissions=True)

    return gp_project.name


def find_raven_channel(project_title, workspace=None):
    project_title = (project_title or "").strip()
    workspace = (workspace or get_default_raven_workspace()).strip()

    if not project_title:
        return None

    channel_slug = make_raven_channel_slug(project_title)

    # 1. Exact match by channel_name and workspace.
    existing_channel = frappe.db.get_value(
        "Raven Channel",
        {
            "channel_name": project_title,
            "workspace": workspace
        },
        "name"
    )

    if existing_channel:
        return existing_channel

    # 2. Exact match by generated Raven Channel document name/slug and workspace.
    if channel_slug:
        existing_channel = frappe.db.get_value(
            "Raven Channel",
            {
                "name": channel_slug,
                "workspace": workspace
            },
            "name"
        )

        if existing_channel:
            return existing_channel

    # 3. Case-insensitive match by channel_name or document name in the configured workspace.
    existing_channel = frappe.db.sql(
        """
        SELECT name
        FROM `tabRaven Channel`
        WHERE workspace = %s
          AND (
                LOWER(TRIM(channel_name)) = LOWER(TRIM(%s))
                OR LOWER(TRIM(name)) = LOWER(TRIM(%s))
              )
        ORDER BY modified DESC
        LIMIT 1
        """,
        (workspace, project_title, channel_slug),
        as_dict=True
    )

    if existing_channel:
        return existing_channel[0].name

    # 4. Final fallback by slug/name only.
    # This helps if the Raven Workspace value is stored differently than expected.
    if channel_slug:
        existing_channel = frappe.db.sql(
            """
            SELECT name
            FROM `tabRaven Channel`
            WHERE LOWER(TRIM(name)) = LOWER(TRIM(%s))
            ORDER BY modified DESC
            LIMIT 1
            """,
            (channel_slug,),
            as_dict=True
        )

        if existing_channel:
            return existing_channel[0].name

    return None


def get_or_create_raven_channel(doc):
    project_title = get_project_title(doc)
    workspace = get_default_raven_workspace()

    if not project_title:
        return None

    # If Project already has a Raven Channel and that record exists, reuse it
    # only if it matches this project channel, not a default/general channel.
    if getattr(doc, "raven_channel", None):
        linked_channel = frappe.db.get_value(
            "Raven Channel",
            doc.raven_channel,
            ["name", "channel_name", "workspace"],
            as_dict=True
        )

        if linked_channel:
            linked_channel_display_name = (linked_channel.channel_name or "").strip()
            linked_channel_slug = make_raven_channel_slug(linked_channel_display_name)
            project_slug = make_raven_channel_slug(project_title)

            if (
                linked_channel_display_name.lower() == project_title.lower()
                or linked_channel.name == project_slug
                or linked_channel_slug == project_slug
            ):
                return linked_channel.name

    existing_channel = find_raven_channel(project_title, workspace)

    if existing_channel:
        return existing_channel

    try:
        raven_channel = frappe.get_doc({
            "doctype": "Raven Channel",
            "channel_name": project_title,
            "workspace": workspace,
            "type": "Open"
        })
        raven_channel.insert(ignore_permissions=True)

        return raven_channel.name

    except ValidationError as e:
        error_message = str(e)

        if "A channel with this name already exists in this workspace" in error_message:
            frappe.clear_messages()

            existing_channel = find_raven_channel(project_title, workspace)

            if existing_channel:
                return existing_channel

        raise


def save_project_link_fields(doc, field_updates):
    field_updates = {
        fieldname: value
        for fieldname, value in (field_updates or {}).items()
        if value and getattr(doc, fieldname, None) != value
    }

    if not field_updates:
        return

    for fieldname, value in field_updates.items():
        doc.set(fieldname, value)

    # This intentionally saves the Project so other fields that depend on
    # gameplan_project and raven_channel can be refreshed by the normal save flow.
    # The frappe flag in create_project_handover_records prevents this nested
    # save from recursively creating linked records again.
    doc.flags.ignore_permissions = True
    doc.flags.ignore_version = True
    doc.save(ignore_permissions=True)


@frappe.whitelist(allow_guest=True)
def create_project_handover_records(doc, method=None):
    if getattr(frappe.flags, "creating_project_linked_records", False):
        return

    frappe.flags.creating_project_linked_records = True

    try:
        get_or_create_safety_handover(doc)
        get_or_create_lead_safety_handover(doc)

        gp_project_name = get_or_create_gp_project(doc)
        raven_channel_name = get_or_create_raven_channel(doc)

        save_project_link_fields(
            doc,
            {
                "gameplan_project": gp_project_name,
                "raven_channel": raven_channel_name
            }
        )

    finally:
        frappe.flags.creating_project_linked_records = False
