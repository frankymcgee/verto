from __future__ import annotations

import json

import frappe

from verto.api.mobile.home import get_home_summary as get_base_home_summary


ACTIVE_JHA_STATUSES = (
    "Draft",
    "Voice Discussion in Progress",
    "Incomplete - Actions Required",
)


def _assigned_users(raw) -> set[str]:
    if not raw:
        return set()
    if isinstance(raw, (list, tuple, set)):
        return {str(value).strip() for value in raw if str(value).strip()}
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return set()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _task_fields() -> list[str]:
    fields = [
        "name",
        "subject",
        "status",
        "project",
        "priority",
        "progress",
        "parent_task",
        "exp_start_date",
        "exp_end_date",
        "exp_start_time",
        "exp_end_time",
        "modified",
        "_assign",
        "lft",
    ]
    meta = frappe.get_meta("Task")
    optional = [
        "type",
        "description",
        "responsible_contractor",
        "work_order_number",
        "project_scope_name",
    ]
    for fieldname in optional:
        if meta.has_field(fieldname):
            fields.append(fieldname)
    return fields


def get_work_summary_child_tasks(work_summary: str) -> list[dict]:
    """Return direct non-cancelled Task children in planned sequence order."""
    if not work_summary or not frappe.db.exists("Task", work_summary):
        return []

    rows = frappe.get_all(
        "Task",
        filters={
            "parent_task": work_summary,
            "status": ["!=", "Cancelled"],
        },
        fields=_task_fields(),
        order_by="lft asc, name asc",
        limit_page_length=500,
    )

    current_user = frappe.session.user
    result = []
    for row in rows:
        values = dict(row)
        assigned_users = sorted(_assigned_users(values.pop("_assign", None)))
        values["assigned_users"] = assigned_users
        values["assigned_to_current_user"] = current_user in assigned_users
        result.append(values)
    return result


def attach_child_tasks_to_home_summary(payload: dict) -> dict:
    """Attach child Tasks beneath each visible Work Summary in the mobile payload."""
    for scope in payload.get("grouped_tasks") or []:
        for parent in scope.get("parent_groups") or []:
            for task in parent.get("tasks") or []:
                if not task.get("name"):
                    continue
                child_tasks = get_work_summary_child_tasks(task.get("name"))
                task["child_tasks"] = child_tasks
                task["child_task_count"] = len(child_tasks)
    return payload


@frappe.whitelist()
def get_home_summary():
    payload = get_base_home_summary()
    return attach_child_tasks_to_home_summary(payload)


def sync_active_jha_planned_steps():
    """Resync existing editable JHAs after migration so child Tasks appear immediately."""
    if not frappe.db.exists("DocType", "Digital Job Hazard Analysis"):
        return

    names = frappe.get_all(
        "Digital Job Hazard Analysis",
        filters={"jha_status": ["in", list(ACTIVE_JHA_STATUSES)]},
        pluck="name",
        limit_page_length=1000,
    )

    for name in names:
        try:
            doc = frappe.get_doc("Digital Job Hazard Analysis", name)
            doc.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                title=f"Digital JHA planned-step sync failed: {name}",
                message=frappe.get_traceback(),
            )
