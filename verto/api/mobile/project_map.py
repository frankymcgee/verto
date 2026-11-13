"""Read Work Summary locations for the Verto Mobile project map."""

import frappe
from frappe import _

from verto.api.mobile.boot import get_map_settings
from verto.api.mobile.home import get_mobile_form_buttons, require_login


@frappe.whitelist(methods=["GET"])
def get_locations(project: str):
    require_login()
    frappe.local.response_headers["Cache-Control"] = "no-store"
    project = (project or "").strip()

    if not project:
        frappe.throw(_("Project is required."), frappe.ValidationError)
    if not frappe.has_permission("Task", "read"):
        frappe.throw(_("You do not have permission to view task locations."), frappe.PermissionError)

    projects = frappe.get_list(
        "Project", filters={"name": project}, fields=["name", "project_name"], limit=1,
    )
    if not projects:
        frappe.throw(_("You do not have access to this project."), frappe.PermissionError)

    meta = frappe.get_meta("Task")
    location_field = meta.get_field("location")
    tasks = []
    if location_field and location_field.fieldtype == "Geolocation":
        fields = [
            "name", "subject", "type", "status", "progress", "is_milestone",
            "exp_start_date", "exp_end_date", "depends_on_tasks", "location",
        ]
        optional_fields = (
            "responsible_contractor", "exp_start_time", "exp_end_time", "parent_task_name",
        )
        fields.extend(field for field in optional_fields if meta.has_field(field))
        tasks = frappe.get_list(
            "Task",
            filters={
                "project": project,
                "type": "Work Summary",
                "status": ["not in", ["Completed", "Cancelled"]],
                "location": ["is", "set"],
            },
            fields=fields,
            order_by="subject asc, name asc",
            limit_page_length=0,
        )

    buttons = get_mobile_form_buttons()
    return {
        "project_name": projects[0].get("project_name") or projects[0]["name"],
        "tasks": tasks,
        "map_settings": get_map_settings(),
        "task_forms": buttons["task_forms"],
        "ccv_forms": buttons["ccv_forms"],
    }
