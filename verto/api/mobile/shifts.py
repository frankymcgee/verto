import frappe
from frappe.utils import getdate


def require_login():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)


def get_user_fullname():
    return frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user


@frappe.whitelist()
def get_shift_calendar(start_date=None, end_date=None):
    require_login()

    if not start_date or not end_date:
        frappe.throw("start_date and end_date are required")

    start_date = getdate(start_date)
    end_date = getdate(end_date)
    user_fullname = get_user_fullname()

    shift_fields = [
        "name",
        "start_date",
        "end_date",
        "employee_name",
        "shift_type",
        "status",
    ]

    shift_meta = frappe.get_meta("Shift Assignment")
    shift_fieldnames = {df.fieldname for df in shift_meta.fields}

    optional_shift_fields = [
        "custom_project_name",
        "custom_color",
        "custom_client",
        "custom_location",
        "custom_shift_type_color",
        "custom_project",
    ]

    for fieldname in optional_shift_fields:
        if fieldname in shift_fieldnames:
            shift_fields.append(fieldname)

    shifts = frappe.get_all(
        "Shift Assignment",
        filters={
            "employee_name": user_fullname,
            "status": "Active",
            "start_date": ["<=", end_date],
            "end_date": [">=", start_date],
        },
        fields=shift_fields,
        limit_page_length=500,
        order_by="start_date asc",
    )

    attendance_rows = frappe.get_all(
        "Attendance",
        filters={
            "employee_name": user_fullname,
            "status": "On Leave",
            "attendance_date": ["between", [start_date, end_date]],
        },
        fields=["name", "attendance_date"],
        limit_page_length=500,
        order_by="attendance_date asc",
    )

    leave_entries = []

    for row in attendance_rows:
        leave_entries.append({
            "name": row.name,
            "start_date": row.attendance_date,
            "end_date": row.attendance_date,
            "employee_name": user_fullname,
            "shift_type": "U",
            "status": "Active",
            "custom_project_name": "On Leave",
            "custom_color": "#7c3aed",
            "custom_client": "",
            "custom_location": "",
            "custom_shift_type_color": "#7c3aed",
            "custom_project": None,
            "is_leave": 1,
        })

    timesheet_fields = [
        "name",
        "date",
        "start_time",
        "end_time",
        "duration",
        "current_user",
    ]

    ts_meta = frappe.get_meta("Daily Timesheet")
    ts_fieldnames = {df.fieldname for df in ts_meta.fields}

    for fieldname in ["project_name", "custom_project", "link_task"]:
        if fieldname in ts_fieldnames:
            timesheet_fields.append(fieldname)

    timesheets = frappe.get_all(
        "Daily Timesheet",
        filters={
            "current_user": user_fullname,
            "date": ["between", [start_date, end_date]],
        },
        fields=timesheet_fields,
        limit_page_length=500,
        order_by="date asc",
    )

    return {
        "user": frappe.session.user,
        "user_fullname": user_fullname,
        "shifts": shifts + leave_entries,
        "timesheets": timesheets,
    }