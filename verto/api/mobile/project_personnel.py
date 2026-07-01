# Copyright (c) 2026, Webwire
# License: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

import frappe
from frappe import _


SHIFT_ASSIGNMENT_DOCTYPE = "Shift Assignment"
EMPLOYEE_DOCTYPE = "Employee"
USER_DOCTYPE = "User"


def _has_field(meta, fieldname: str) -> bool:
    return bool(meta and meta.has_field(fieldname))


def _clean(value) -> str:
    return str(value or "").strip()


def _unique(values) -> list[str]:
    seen = set()
    output = []

    for value in values:
        cleaned = _clean(value)

        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            output.append(cleaned)

    return output


def _date_to_string(value) -> str:
    if not value:
        return ""

    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    return str(value)


def _get_present_fields(doctype: str, candidate_fields: list[str]) -> list[str]:
    meta = frappe.get_meta(doctype)

    return [
        fieldname
        for fieldname in candidate_fields
        if fieldname == "name" or _has_field(meta, fieldname)
    ]


def _get_employee_map(employee_names: list[str]) -> dict[str, dict]:
    employee_names = _unique(employee_names)

    if not employee_names or not frappe.db.exists("DocType", EMPLOYEE_DOCTYPE):
        return {}

    candidate_fields = [
        "name",
        "employee_name",
        "user_id",
        "company_email",
        "personal_email",
        "cell_number",
        "prefered_email",
        "preferred_email",
        "designation",
        "department",
        "image",
    ]

    fields = _get_present_fields(EMPLOYEE_DOCTYPE, candidate_fields)

    employees = frappe.get_all(
        EMPLOYEE_DOCTYPE,
        fields=fields,
        filters={
            "name": ["in", employee_names],
        },
        ignore_permissions=True,
        limit_page_length=500,
    )

    return {
        employee.name: employee
        for employee in employees
    }


def _get_user_map(user_ids: list[str]) -> dict[str, dict]:
    user_ids = _unique(user_ids)

    if not user_ids or not frappe.db.exists("DocType", USER_DOCTYPE):
        return {}

    candidate_fields = [
        "name",
        "full_name",
        "email",
        "user_image",
        "phone",
        "mobile_no",
    ]

    fields = _get_present_fields(USER_DOCTYPE, candidate_fields)

    users = frappe.get_all(
        USER_DOCTYPE,
        fields=fields,
        filters={
            "name": ["in", user_ids],
        },
        ignore_permissions=True,
        limit_page_length=500,
    )

    return {
        user.name: user
        for user in users
    }


def _get_email(employee: dict | None, user: dict | None) -> str:
    employee = employee or {}
    user = user or {}

    for value in [
        employee.get("company_email"),
        employee.get("prefered_email"),
        employee.get("preferred_email"),
        employee.get("personal_email"),
        employee.get("user_id"),
        user.get("email"),
        user.get("name"),
    ]:
        cleaned = _clean(value)

        if cleaned and "@" in cleaned:
            return cleaned

    return ""


def _get_contact_number(employee: dict | None, user: dict | None) -> str:
    employee = employee or {}
    user = user or {}

    for value in [
        employee.get("cell_number"),
        user.get("mobile_no"),
        user.get("phone"),
    ]:
        cleaned = _clean(value)

        if cleaned:
            return cleaned

    return ""


def _get_image(employee: dict | None, user: dict | None) -> str:
    employee = employee or {}
    user = user or {}

    return _clean(employee.get("image") or user.get("user_image"))


def _get_shift_project_fields() -> list[str]:
    meta = frappe.get_meta(SHIFT_ASSIGNMENT_DOCTYPE)

    candidates = [
        "project",
        "custom_project",
        "custom_project_name",
        "project_name",
        "custom_project_id",
    ]

    return [
        fieldname
        for fieldname in candidates
        if _has_field(meta, fieldname)
    ]


def _get_shift_fields(project_fields: list[str]) -> list[str]:
    candidates = [
        "name",
        "employee",
        "employee_name",
        "shift_type",
        "start_date",
        "end_date",
        "docstatus",
        *project_fields,
    ]

    return _get_present_fields(SHIFT_ASSIGNMENT_DOCTYPE, candidates)


def _build_personnel_from_shifts(shifts: list[dict]) -> list[dict]:
    employee_names = [
        shift.get("employee")
        for shift in shifts
        if shift.get("employee")
    ]

    employees = _get_employee_map(employee_names)

    user_ids = []
    for employee in employees.values():
        user_id = _clean(employee.get("user_id"))

        if user_id:
            user_ids.append(user_id)

    users = _get_user_map(user_ids)

    grouped = {}

    for shift in shifts:
        employee_id = _clean(shift.get("employee"))
        employee_name = _clean(shift.get("employee_name"))
        key = employee_id or employee_name or _clean(shift.get("name"))

        if not key:
            continue

        if key not in grouped:
            employee = employees.get(employee_id, {})
            user_id = _clean(employee.get("user_id"))
            user = users.get(user_id, {})

            grouped[key] = {
                "employee": employee_id,
                "employee_name": employee_name or _clean(employee.get("employee_name")) or employee_id,
                "user_id": user_id,
                "email": _get_email(employee, user),
                "contact_number": _get_contact_number(employee, user),
                "image": _get_image(employee, user),
                "designation": _clean(employee.get("designation")),
                "department": _clean(employee.get("department")),
                "shift_types": set(),
                "start_dates": [],
                "end_dates": [],
            }

        shift_type = _clean(shift.get("shift_type"))

        if shift_type:
            grouped[key]["shift_types"].add(shift_type)

        start_date = _date_to_string(shift.get("start_date"))
        end_date = _date_to_string(shift.get("end_date"))

        if start_date:
            grouped[key]["start_dates"].append(start_date)

        if end_date:
            grouped[key]["end_dates"].append(end_date)

    personnel = []

    for item in grouped.values():
        start_dates = sorted(set(item.pop("start_dates")))
        end_dates = sorted(set(item.pop("end_dates")))
        shift_types = sorted(item.pop("shift_types"))

        item["shift_type"] = ", ".join(shift_types)
        item["start_date"] = start_dates[0] if start_dates else ""
        item["end_date"] = end_dates[-1] if end_dates else ""

        personnel.append(item)

    return sorted(
        personnel,
        key=lambda row: (
            _clean(row.get("employee_name")).lower(),
            _clean(row.get("employee")).lower(),
        ),
    )


@frappe.whitelist()
def get_project_personnel(project: str | None = None, project_name: str | None = None, scope_name: str | None = None):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    if not frappe.db.exists("DocType", SHIFT_ASSIGNMENT_DOCTYPE):
        return {
            "personnel": [],
            "project": _clean(project),
            "project_name": _clean(project_name or scope_name),
            "matched_shift_count": 0,
        }

    match_values = _unique([
        project,
        project_name,
        scope_name,
    ])

    if not match_values:
        frappe.throw(_("Project is required."))

    project_fields = _get_shift_project_fields()

    if not project_fields:
        return {
            "personnel": [],
            "project": _clean(project),
            "project_name": _clean(project_name or scope_name),
            "matched_shift_count": 0,
        }

    fields = _get_shift_fields(project_fields)

    or_filters = [
        [fieldname, "in", match_values]
        for fieldname in project_fields
    ]

    shifts = frappe.get_all(
        SHIFT_ASSIGNMENT_DOCTYPE,
        fields=fields,
        filters={
            "docstatus": 1,
        },
        or_filters=or_filters,
        order_by="start_date asc, employee_name asc",
        ignore_permissions=True,
        limit_page_length=1000,
    )

    personnel = _build_personnel_from_shifts(shifts)

    return {
        "personnel": personnel,
        "project": _clean(project),
        "project_name": _clean(project_name or scope_name),
        "matched_shift_count": len(shifts),
    }
