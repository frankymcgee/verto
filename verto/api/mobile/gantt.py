"""Read the project schedule shown by the Verto Mobile Gantt page."""

import frappe
from frappe import _
from frappe.utils import cint

from verto.api.mobile.home import require_login


PAGE_SIZE = 50
TASK_FIELDS = (
    "name", "subject", "status", "type", "progress", "is_group", "is_milestone",
    "exp_start_date", "exp_end_date", "depends_on_tasks", "color",
)
OPTIONAL_TASK_FIELDS = ("exp_start_time", "exp_end_time", "parent_task_name", "color_label")


@frappe.whitelist(methods=["GET"])
def get_schedule(project: str, area: str | None = None, start: int = 0):
    require_login()
    frappe.local.response_headers["Cache-Control"] = "no-store"
    project = (project or "").strip()
    area = (area or "").strip()
    start = max(cint(start), 0)

    if not project:
        frappe.throw(_("Project is required."), frappe.ValidationError)
    if not frappe.has_permission("Task", "read"):
        frappe.throw(_("You do not have permission to view the schedule."), frappe.PermissionError)

    projects = frappe.get_list(
        "Project", filters={"name": project}, fields=["name", "project_name"], limit=1,
    )
    if not projects:
        frappe.throw(_("You do not have access to this project."), frappe.PermissionError)

    filters = {
        "project": project,
        "status": ["not in", ["Completed", "Cancelled"]],
        "type": ["not in", ["Task Step", "Outline"]],
    }
    area_name = None
    if area:
        areas = frappe.get_list(
            "Task", filters={"name": area, "project": project},
            fields=["name", "subject", "lft", "rgt"], limit=1,
        )
        if not areas:
            frappe.throw(_("You do not have access to this area in the project."), frappe.PermissionError)

        root = areas[0]
        area_name = root.get("subject") or root["name"]
        left, right = cint(root.get("lft")), cint(root.get("rgt"))
        if 0 < left < right:
            filters.update(lft=[">=", left], rgt=["<=", right])
        else:
            filters["name"] = root["name"]

    meta = frappe.get_meta("Task")
    tasks = frappe.get_list(
        "Task",
        filters=filters,
        fields=[*TASK_FIELDS, *(field for field in OPTIONAL_TASK_FIELDS if meta.has_field(field))],
        order_by="exp_start_date asc, name asc",
        offset=start,
        limit=PAGE_SIZE + 1,
    )
    return {
        "project_name": projects[0].get("project_name") or projects[0]["name"],
        "area_name": area_name,
        "tasks": tasks[:PAGE_SIZE],
        "next_start": start + PAGE_SIZE if len(tasks) > PAGE_SIZE else None,
    }
