# Copyright (c) 2024, Webwire and contributors
# For license information, please see license.txt

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import flt, getdate

from verto.api.internal_timesheet_approval import last_completed_week, shift_from_start_time, shift_kind

REPORT_NAME = "Weekly Timesheet v2"
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
SHIFTS = ("DS", "NS")


def execute(filters=None):
    filters = filters or {}
    start, end = filters.get("start_date"), filters.get("end_date")
    if start or end:
        if not start or not end:
            frappe.throw(_("Set both Start Date and End Date."))
        start, end = getdate(start), getdate(end)
        if start > end:
            frappe.throw(_("Start Date must be on or before End Date."))
    else:
        start, end = last_completed_week()

    entries = frappe.db.sql(
        """
        SELECT dt.owner, u.full_name AS employee_name, dt.date AS work_date,
               dt.project_id, dt.project AS project_name, dt.shift AS shift_type,
               dt.start_time, dt.duration, st.start_time AS shift_start, st.end_time AS shift_end
          FROM `tabDaily Timesheet` dt
          JOIN `tabUser` u ON u.name = dt.owner
          LEFT JOIN `tabShift Type` st ON st.name = dt.shift
         WHERE dt.date BETWEEN %(start_date)s AND %(end_date)s
           AND (%(exclude_operations)s <> 'Yes' OR COALESCE(dt.project, '') NOT LIKE %(operations_pattern)s)
         ORDER BY dt.date, dt.name
        """,
        {
            "start_date": start,
            "end_date": end,
            "exclude_operations": filters.get("exclude_operations") or "No",
            "operations_pattern": "%Operations & Execution%",
        },
        as_dict=True,
    )

    columns = [
        {"fieldname": "employee_name", "label": _("Employee"), "fieldtype": "Data", "width": 170},
        {"fieldname": "project_name", "label": _("Project"), "fieldtype": "Data", "width": 180},
        {"fieldname": "week_start", "label": _("Week Starting"), "fieldtype": "Date", "width": 105},
    ]
    hour_fields = {}
    for weekday, day in enumerate(WEEKDAYS):
        for shift in SHIFTS:
            fieldname = f"{day.lower()}_{shift.lower()}"
            hour_fields[weekday, shift] = fieldname
            columns.append({
                "fieldname": fieldname,
                "label": _("{0} {1}").format(_(day), _(shift)),
                "fieldtype": "Float",
                "precision": 2,
                "width": 75,
            })
    columns.append({
        "fieldname": "hours_worked", "label": _("Total Hours"), "fieldtype": "Float", "precision": 2, "width": 90,
    })

    rows = {}
    for entry in entries:
        work_date = getdate(entry.work_date)
        weekday = work_date.weekday()
        monday = work_date - timedelta(days=weekday)
        project = entry.project_id or entry.project_name or ""
        key = (monday, entry.owner, project)
        if key not in rows:
            rows[key] = {
                "employee_name": entry.employee_name or entry.owner,
                "project_name": entry.project_name or project,
                "week_start": monday,
                "hours_worked": 0.0,
                **dict.fromkeys(hour_fields.values(), 0.0),
            }

        shift = shift_kind(entry.shift_type, {"start_time": entry.shift_start, "end_time": entry.shift_end})
        if shift not in SHIFTS:
            shift = shift_from_start_time(entry.start_time) or "DS"
        hours = flt(entry.duration) / 3600
        row = rows[key]
        row[hour_fields[weekday, shift]] += hours
        row["hours_worked"] += hours

    data = sorted(rows.values(), key=lambda row: (row["week_start"], row["project_name"], row["employee_name"]))
    return columns, data


class WeeklyTimesheetEmailMixin:
    def _uses_last_completed_week(self):
        return self.report == REPORT_NAME and self.frequency == "Weekly"

    def dynamic_date_filters_set(self):
        return self._uses_last_completed_week() or super().dynamic_date_filters_set()

    def prepare_dynamic_filters(self):
        if not self._uses_last_completed_week():
            return super().prepare_dynamic_filters()

        # Frappe parses the saved filters before calling this method.
        # Weekly delivery uses the report's calendar week and retains other filters.
        start, end = last_completed_week()
        self.filters.update(start_date=start.isoformat(), end_date=end.isoformat())
