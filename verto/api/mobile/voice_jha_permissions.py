import json

import frappe


JHA_DOCTYPE = "Digital Job Hazard Analysis"
TASK_DOCTYPE = "Task"


def _is_privileged_user(user: str) -> bool:
    return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def get_assigned_users(work_summary: str) -> set[str]:
    if not work_summary:
        return set()

    raw = frappe.db.get_value(TASK_DOCTYPE, work_summary, "_assign")
    if not raw:
        return set()

    if isinstance(raw, (list, tuple, set)):
        return {str(value).strip() for value in raw if str(value).strip()}

    try:
        values = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return set()

    if isinstance(values, str):
        values = [values]

    if not isinstance(values, list):
        return set()

    return {str(value).strip() for value in values if str(value).strip()}


def user_can_access_work_summary(work_summary: str, user: str | None = None) -> bool:
    user = user or frappe.session.user

    if not user or user == "Guest":
        return False

    if _is_privileged_user(user):
        return True

    if not work_summary or not frappe.db.exists(TASK_DOCTYPE, work_summary):
        return False

    return user in get_assigned_users(work_summary)


def has_permission(doc, user=None, ptype=None, permission_type=None, **kwargs):
    """Restrict Digital JHAs to users assigned to the linked Work Summary.

    The DocType grants the authenticated `All` role the minimum base permissions
    required by Frappe. This hook then narrows those permissions to the linked
    Work Summary assignment. System Managers retain normal administrative access.
    """
    user = user or frappe.session.user
    ptype = ptype or permission_type or "read"

    if not user or user == "Guest":
        return False

    if _is_privileged_user(user):
        return True

    if ptype not in {"read", "write", "create", "print", "email"}:
        return False

    work_summary = doc.get("work_summary") if doc else ""
    return user_can_access_work_summary(work_summary, user)


def get_permission_query_conditions(user=None):
    user = user or frappe.session.user

    if not user or user == "Guest":
        return "1=0"

    if _is_privileged_user(user):
        return ""

    # Task._assign is stored as a JSON array. JSON_CONTAINS gives an exact
    # assignment match rather than a substring match against an email address.
    user_json = frappe.db.escape(json.dumps(user))
    return f"""
        EXISTS (
            SELECT 1
            FROM `tabTask` AS assigned_task
            WHERE assigned_task.name = `tab{JHA_DOCTYPE}`.work_summary
              AND JSON_CONTAINS(
                    COALESCE(NULLIF(assigned_task._assign, ''), '[]'),
                    {user_json}
                  )
        )
    """
