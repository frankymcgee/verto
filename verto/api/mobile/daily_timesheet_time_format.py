from __future__ import annotations

import json
from datetime import datetime, time, timedelta

import frappe

from verto.api.mobile import documents as base


DAILY_TIMESHEET_DOCTYPE = "Daily Timesheet"
TIME_FIELDNAMES = {"start_time", "end_time"}


def _is_daily_timesheet(mobile_doctype: str) -> bool:
    return base.get_allowed_doctype(mobile_doctype) == DAILY_TIMESHEET_DOCTYPE


def _quarter_hour_options() -> list[str]:
    options: list[str] = []
    anchor = datetime(2000, 1, 1)

    for minutes in range(0, 24 * 60, 15):
        value = anchor + timedelta(minutes=minutes)
        options.append(value.strftime("%I:%M %p").lstrip("0"))

    return options


QUARTER_HOUR_OPTIONS = _quarter_hour_options()


def _format_time_for_mobile(value):
    if value in (None, ""):
        return value

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, time):
        parsed = datetime.combine(datetime(2000, 1, 1).date(), value)
    elif isinstance(value, timedelta):
        total_seconds = int(value.total_seconds()) % (24 * 60 * 60)
        parsed = datetime(2000, 1, 1) + timedelta(seconds=total_seconds)
    else:
        text = str(value).strip()
        parsed = None

        for fmt in ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue

        if parsed is None:
            return text

    return parsed.strftime("%I:%M %p").lstrip("0")


def _format_time_for_server(value):
    if value in (None, ""):
        return value

    if isinstance(value, datetime):
        return value.strftime("%H:%M:%S")
    if isinstance(value, time):
        return value.strftime("%H:%M:%S")
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds()) % (24 * 60 * 60)
        parsed = datetime(2000, 1, 1) + timedelta(seconds=total_seconds)
        return parsed.strftime("%H:%M:%S")

    text = str(value).strip()

    for fmt in ("%I:%M %p", "%I:%M:%S %p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).strftime("%H:%M:%S")
        except ValueError:
            continue

    return text


def _normalise_values_arg(values):
    if isinstance(values, str):
        return json.loads(values or "{}")
    return dict(values or {})


def _to_server_values(mobile_doctype: str, values):
    result = _normalise_values_arg(values)

    if not _is_daily_timesheet(mobile_doctype):
        return result

    for fieldname in TIME_FIELDNAMES:
        if fieldname in result:
            result[fieldname] = _format_time_for_server(result.get(fieldname))

    return result


def _to_mobile_values(values):
    result = dict(values or {})

    for fieldname in TIME_FIELDNAMES:
        if fieldname in result:
            result[fieldname] = _format_time_for_mobile(result.get(fieldname))

    return result


def _time_sort_key(value: str) -> int:
    try:
        parsed = datetime.strptime(value, "%I:%M %p")
        return (parsed.hour * 60) + parsed.minute
    except ValueError:
        return 24 * 60


def _transform_schema(schema: dict, current_values: dict | None = None) -> dict:
    if not schema or schema.get("doctype") != DAILY_TIMESHEET_DOCTYPE:
        return schema

    current_values = current_values or {}
    options = list(QUARTER_HOUR_OPTIONS)

    for fieldname in TIME_FIELDNAMES:
        current_value = _format_time_for_mobile(current_values.get(fieldname))
        if current_value and current_value not in options:
            options.append(current_value)

    options = sorted(set(options), key=_time_sort_key)
    options_text = "\n".join(options)

    for field in schema.get("fields") or []:
        if field.get("fieldname") not in TIME_FIELDNAMES:
            continue

        field["fieldtype"] = "Select"
        field["options"] = options_text

        if field.get("default") not in (None, ""):
            field["default"] = _format_time_for_mobile(field.get("default"))

    return schema


@frappe.whitelist()
def get_form_schema(mobile_doctype, permission_type="create"):
    result = base.get_form_schema(
        mobile_doctype=mobile_doctype,
        permission_type=permission_type,
    )

    if _is_daily_timesheet(mobile_doctype):
        _transform_schema(result)

    return result


@frappe.whitelist()
def get_mobile_doc_for_edit(mobile_doctype, docname):
    result = base.get_mobile_doc_for_edit(
        mobile_doctype=mobile_doctype,
        docname=docname,
    )

    if result.get("doctype") == DAILY_TIMESHEET_DOCTYPE:
        values = _to_mobile_values(result.get("values") or {})
        result["values"] = values
        result["schema"] = _transform_schema(result.get("schema") or {}, values)

    return result


@frappe.whitelist()
def get_prefill_values(
    mobile_doctype,
    date=None,
    project=None,
    link_task=None,
    work_order_number=None,
    project_scope_name=None,
    parent_task_name=None,
):
    result = base.get_prefill_values(
        mobile_doctype=mobile_doctype,
        date=date,
        project=project,
        link_task=link_task,
        work_order_number=work_order_number,
        project_scope_name=project_scope_name,
        parent_task_name=parent_task_name,
    )

    if _is_daily_timesheet(mobile_doctype):
        result["values"] = _to_mobile_values(result.get("values") or {})

    return result


@frappe.whitelist()
def process_field_change(mobile_doctype, changed_fieldname, values=None, docname=None):
    server_values = _to_server_values(mobile_doctype, values)

    result = base.process_field_change(
        mobile_doctype=mobile_doctype,
        changed_fieldname=changed_fieldname,
        values=server_values,
        docname=docname,
    )

    if _is_daily_timesheet(mobile_doctype):
        result["values"] = _to_mobile_values(result.get("values") or {})

    return result


@frappe.whitelist()
def create_mobile_doc(mobile_doctype, values=None):
    server_values = _to_server_values(mobile_doctype, values)
    return base.create_mobile_doc(
        mobile_doctype=mobile_doctype,
        values=server_values,
    )


@frappe.whitelist()
def update_mobile_doc(mobile_doctype, docname, values=None):
    server_values = _to_server_values(mobile_doctype, values)

    result = base.update_mobile_doc(
        mobile_doctype=mobile_doctype,
        docname=docname,
        values=server_values,
    )

    if result.get("doctype") == DAILY_TIMESHEET_DOCTYPE:
        result["values"] = _to_mobile_values(result.get("values") or {})

    return result
