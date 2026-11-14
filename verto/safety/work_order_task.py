import frappe
from frappe import _


def apply_work_order_task(doc, *, strict=True):
    """Keep an exact Task selection or resolve a work order within its Project."""
    if doc.get("scope_or_wo") != "Work Order Number":
        return {}, None
    if not all(doc.meta.has_field(field) for field in ("link_task", "link_project", "work_order_number")):
        return {}, None

    selected_task = doc.get("link_task")
    project = doc.get("link_project")
    work_order = doc.get("work_order_number")
    task = None
    warning = None

    if project and work_order:
        filters = {"project": project, "work_order_number": work_order}
        fields = ["name", "subject", "parent_task_name"]
        if selected_task:
            matches = frappe.get_list("Task", filters={**filters, "name": selected_task}, fields=fields, limit=1)
            if matches:
                return {}, None

        matches = frappe.get_list("Task", filters=filters, fields=fields, limit=2)
        if len(matches) == 1:
            task = matches[0]
        elif matches:
            warning = _("This work order matches multiple tasks in the selected project. Select the task under Work Scope.")
            if strict:
                frappe.throw(warning)
            # Keep the current selection until the user picks the intended task.
            return {}, warning
        else:
            warning = _("No task was found for this work order in the selected project.")
    elif work_order:
        warning = _("Select a project to look up this work order.")

    task_name = task["name"] if task else ""
    if (selected_task or "") == task_name:
        return {}, warning

    updates = {"link_task": task_name}
    for fieldname, source in (("work_scope", "subject"), ("work_area", "parent_task_name")):
        field = doc.meta.get_field(fieldname)
        if field and field.get("fetch_from") == f"link_task.{source}":
            updates[fieldname] = (task.get(source) or "") if task else ""

    doc.update(updates)
    return updates, warning


def validate_work_scope_project(doc):
    if doc.get("scope_or_wo") != "Work Scope":
        return
    project = doc.get("link_project")
    task = doc.get("link_task")
    if project and task and not frappe.db.exists("Task", {"name": task, "project": project}):
        frappe.throw(_("The selected task does not belong to the selected project. Choose a task from this project."))
