"""Read-only, permission-scoped reconciliation of daily hours and weekly Timesheets."""
from __future__ import annotations

from datetime import timedelta

import frappe
from frappe.utils import cint, getdate, get_datetime, now_datetime

from verto.api import internal_timesheet_approval as review
from verto.api.timesheet_access import can_review_timesheets

LIMIT = 2000
WEEKLY_LIMIT = 200
PROCESSING_GRACE = timedelta(minutes=10)
CATEGORIES = {
    "missing": "Missing hours", "processing": "Weekly processing", "hours": "Hours and totals",
    "allocation": "Shift allocation", "conflict": "Attendance and leave",
}
DAILY_FIELDS = ["name", "modified", "owner", "docstatus", "current_user", "employee", "employee_name", "date",
                "start_time", "end_time", "duration", "comments", "shift_allocation", "shift", "project_id"]
ALLOCATION_CODES = {"invalid_allocation", "ambiguous_allocation", "missing_allocation", "unavailable_allocation",
                    "unknown_allocation_shift", "allocation_time_mismatch", "allocation_label_mismatch", "fly_label_mismatch"}


def _read(doctype, warnings, *, required=False, cap=LIMIT, **kwargs):
    """Never use get_all or truncate evidence used to infer a missing submission."""
    if not frappe.has_permission(doctype, "read"):
        if required:
            frappe.throw(f"Read permission for {doctype} is required.", frappe.PermissionError)
        warnings.append(f"{doctype} checks are unavailable with your current permissions.")
        return None
    try:
        rows = frappe.get_list(doctype, limit_page_length=cap + 1, order_by="name asc", **kwargs)
    except frappe.PermissionError:
        if required:
            raise
        warnings.append(f"{doctype} checks are unavailable with your current permissions.")
        return None
    if len(rows) > cap:
        frappe.throw(f"Too many {doctype} records for a complete check. Choose a project to narrow the check.")
    return rows


def _documents(names):
    docs = []
    for row in names:
        doc = frappe.get_doc("Timesheet", row.name)
        doc.check_permission("read")
        if cint(doc.docstatus) != 2:
            docs.append(doc)
    return docs


def _full_day_leave(row, day):
    if not (getdate(row.from_date) <= day <= getdate(row.to_date)):
        return False
    if not cint(row.get("half_day")):
        return True
    # A multi-day leave application can contain one half day.
    return bool(row.get("half_day_date") and getdate(row.half_day_date) != day)


def _daily_employee(source, employees, user_names=None):
    if source.get("employee"):
        return source.employee if source.employee in employees else None
    identity = source.get("current_user") or source.get("employee_name")
    matches = [employee.name for employee in employees.values()
               if (identity in {employee.get("employee_name"), employee.get("user_id"), (user_names or {}).get(employee.get("user_id"))} if identity
                   else source.get("owner") and source.owner == employee.get("user_id"))]
    return matches[0] if len(matches) == 1 else None


def _category(code):
    if code in ALLOCATION_CODES or code in {"declared_shift_mismatch", "unknown_shift"}:
        return "allocation"
    if code in {"attendance_conflict", "leave_conflict"}:
        return "conflict"
    if code in {"daily_hours_mismatch", "daily_comments_mismatch", "daily_times_mismatch", "weekly_processing", "processing_delayed"}:
        return "processing"
    return "hours"


def _link(doctype, name, label):
    return {"doctype": doctype, "name": name, "label": label}


def _item(key, employee, project, day, issues, context, *, title="Hours need review", hours=None, links=None, approved=False):
    categories = sorted({_category(issue["code"]) for issue in issues})
    if any(issue["code"] == "missing_hours" for issue in issues):
        categories = ["missing"]
    return {
        "id": key, "employee": employee or "", "employee_name": (context["employees"].get(employee) or {}).get("employee_name") or employee or "Unassigned employee",
        "project": project or "", "project_name": (context["projects"].get(project) or {}).get("project_name") or project or "No project",
        "date": str(day), "title": title, "hours": hours, "issues": issues, "categories": categories,
        "severity": "high" if any(issue["code"] in {"attendance_conflict", "leave_conflict", "overlap", "hours_exceeded", "processing_delayed"} for issue in issues) else "review",
        "links": links or [], "internal_approved": approved,
    }


def _source_links(entry, context, weekly=True):
    links = [_link("Timesheet", entry["timesheet"], "Open weekly timesheet")] if weekly else []
    if entry["daily_timesheet"] in context["daily"]:
        links.append(_link("Daily Timesheet", entry["daily_timesheet"], "Open daily timesheet"))
    if entry["allocation"]:
        links.append(_link("Shift Assignment", entry["allocation"], "Open allocation"))
    return links


def _daily_entry(source, employee, monday, context):
    project = source.get("project_id") or ""
    start = end = None
    try:
        start = get_datetime(f"{source.date} {review._clock(source.start_time)}")
        end = get_datetime(f"{source.date} {review._clock(source.end_time)}")
        if end < start:
            end += timedelta(days=1)
    except (ValueError, TypeError):
        pass
    doc = frappe._dict(name=f"Daily {source.name}", employee=employee, employee_name=context["employees"][employee].get("employee_name"),
                       parent_project=project, custom_monday_date=monday)
    log = frappe._dict(from_time=start, to_time=end, hours=(review._number(source.get("duration")) or 0) / 3600,
                       shift_type=source.get("shift"), project=project, description=source.get("comments"), daily_timesheet_id=source.name)
    return review.inspect_time_log(doc, log, 1, context)


def _sanitize_flags(entry, access, context):
    flags = []
    for flag in entry["flags"]:
        code = flag["code"]
        if not access["daily"] and (code.startswith("daily_") or code in {"missing_daily", "cancelled_daily", "invalid_daily_times"}):
            continue
        if entry["employee"] not in context["employees"] and code == "daily_identity_mismatch":
            continue
        if not access["shifts"] and code in ALLOCATION_CODES:
            continue
        if not access.get("types", True) and code in {"unknown_shift", "unknown_allocation_shift"}:
            continue
        if code == "missing_daily":
            flag = {"code": "daily_unavailable", "message": "The linked daily record is missing or outside your read access; its contents could not be checked."}
        elif code == "invalid_allocation":
            flag = {"code": code, "message": "The linked allocation could not be verified against the accessible active allocations for this employee, project and work date."}
        flags.append(flag)
    entry["flags"] = flags


def build_queue(docs, context, monday, current, *, project=None, attendance=None, leave=None, exclusions=None, access=None):
    """Pure reconciliation; related records in context have already passed list permissions."""
    access = access or {"daily": True, "shifts": True, "attendance": True, "leave": True, "employees": True, "types": True}
    attendance, leave, exclusions = attendance or [], leave or [], exclusions or {}
    weekly_rows = [row for group in review.build_review(docs, context, check_missing_days=False)["groups"] for row in group["rows"]] if docs else []
    linked = {entry["daily_timesheet"] for row in weekly_rows for entry in row["entries"] if entry["daily_timesheet"]}
    daily_rows = []
    for source in context["daily"].values():
        if source.name in linked or cint(source.get("docstatus")) == 2 or not source.get("date") or not monday <= getdate(source.date) <= monday + timedelta(days=6):
            continue
        employee = _daily_employee(source, context["employees"], context["user_names"])
        if not employee or (project and source.get("project_id") != project):
            continue
        entry = _daily_entry(source, employee, monday, context)
        entry["source_name"] = source.name
        entry["flags"].append({"code": "weekly_processing", "message": "This daily submission is not linked to an accessible weekly time log yet. Refresh after background processing."})
        if source.get("modified") and get_datetime(source.modified) + PROCESSING_GRACE <= current:
            entry["flags"].append({"code": "processing_delayed", "message": "The daily entry has been waiting at least 10 minutes. Check weekly processing and the background worker before entering another copy."})
        daily_rows.append({"entries": [entry], "internal_approved": False, "name": "", "flags": []})
    rows = weekly_rows + daily_rows
    # Reconcile weekly and unprocessed daily records together without counting a linked daily twice.
    for row in rows:
        for entry in row["entries"]:
            entry["flags"] = [flag for flag in entry["flags"] if flag["code"] not in {"overlap", "hours_exceeded"}]
    review._cross_checks(rows)
    items = []
    for row in rows:
        selected_week = not row["name"] or getdate(row["week_start"]) == monday
        if row["name"] and selected_week and (not project or row["project"] == project) and row["flags"]:
            items.append(_item(f"weekly:{row['name']}", row["employee"], row["project"], monday, row["flags"], context,
                               title="Weekly timesheet needs review", links=[_link("Timesheet", row["name"], "Open weekly timesheet")], approved=row["internal_approved"]))
        for entry in row["entries"]:
            _sanitize_flags(entry, access, context)
            if not selected_week or (project and entry["project"] != project):
                continue
            links = _source_links(entry, context, weekly=bool(row["name"]))
            if entry["hours"] > 0:
                for record in attendance:
                    if record.employee == entry["employee"] and str(getdate(record.attendance_date)) == entry["date"] and record.status in {"Absent", "On Leave"}:
                        entry["flags"].append({"code": "attendance_conflict", "message": f"Hours are recorded while submitted Attendance is marked {record.status}."})
                        links.append(_link("Attendance", record.name, "Open attendance"))
                for record in leave:
                    if record.employee == entry["employee"] and _full_day_leave(record, getdate(entry["date"])):
                        entry["flags"].append({"code": "leave_conflict", "message": "Hours are recorded on approved full-day leave."})
                        links.append(_link("Leave Application", record.name, "Open leave application"))
            if entry["flags"]:
                items.append(_item(f"entry:{row['name'] or entry['source_name']}:{entry['idx']}", entry["employee"], entry["project"], entry["date"], entry["flags"], context,
                                   hours=entry["hours"], links=links, approved=row["internal_approved"]))
    # Absence is only meaningful if all sources needed to suppress it could be read.
    if all(access.get(key) for key in ("daily", "shifts", "attendance", "leave", "employees", "types")):
        from verto.api.mobile.timesheet_reminders import shift_reminder_due_at
        entries = [entry for row in rows for entry in row["entries"] if entry["hours"] > 0 and (entry["elapsed_hours"] or 0) > 0]
        for shift in context["shifts"]:
            employee = context["employees"].get(shift.employee)
            shift_project = shift.get("custom_project")
            kind = review.shift_kind(shift.shift_type, context["types"].get(shift.shift_type))
            if not employee or kind not in {"DS", "NS", "SD", "Fly"} or not shift_project or (project and shift_project != project):
                continue
            for offset in range(7):
                day = monday + timedelta(days=offset)
                if not review._covers(shift, day, shift.employee, shift_project):
                    continue
                due = shift_reminder_due_at(day, context["types"].get(shift.shift_type) or {})
                if not due or due > current:
                    continue
                if any(record.employee == shift.employee and _full_day_leave(record, day) for record in leave):
                    continue
                if any(record.employee == shift.employee and getdate(record.attendance_date) == day and record.status == "On Leave" for record in attendance):
                    continue
                if (str(employee.get("user_id") or "").casefold(), str(shift_project).casefold()) in exclusions.get(str(day), set()):
                    continue
                candidates = [entry for entry in entries if entry["employee"] == shift.employee and entry["project"] == shift_project and entry["date"] == str(day)]
                if any(entry["allocation"] == shift.name or (not entry["allocation"] and (kind in {"SD", "Fly"} or entry["recorded_shift"] == kind)) for entry in candidates):
                    continue
                items.append(_item(f"missing:{shift.name}:{day}", shift.employee, shift_project, day,
                                   [{"code": "missing_hours", "message": f"No accessible valid hours for allocated {shift.shift_type}; hours were due {due:%d %b %H:%M}."}], context,
                                   title="Allocated shift has no hours", links=[_link("Shift Assignment", shift.name, "Open allocation")]))
    return sorted(items, key=lambda item: (item["severity"] != "high", item["date"], item["employee_name"], item["id"]))


@frappe.whitelist()
def get_timesheet_exceptions(week_start=None, project=None):
    if not can_review_timesheets():
        frappe.throw("An internal Timesheet approver role and Timesheet read permission are required.", frappe.PermissionError)
    monday = getdate(week_start) if week_start else review.last_completed_week()[0]
    if monday.weekday() != 0:
        frappe.throw("Choose a Monday for the week beginning date.")
    sunday = monday + timedelta(days=6)
    warnings = ["Checks cover records you can read. Restricted records may require an administrator to verify a missing submission."]
    if project:
        project = str(project).strip()
        frappe.get_doc("Project", project).check_permission("read")
    filters = {"docstatus": ["!=", 2]}
    if project:
        filters["parent_project"] = project
    names = _read("Timesheet", warnings, required=True, cap=WEEKLY_LIMIT, filters=filters, or_filters=[["custom_monday_date", "between", [monday, sunday]], ["start_date", "between", [monday, sunday]]], fields=["name"])
    docs = _documents(names)
    shift_filters = {"docstatus": 1, "status": "Active", "start_date": ["<=", sunday]}
    if project:
        shift_filters["custom_project"] = project
    shifts = _read("Shift Assignment", warnings, filters=shift_filters,
                   or_filters=[["end_date", ">=", monday], ["end_date", "is", "not set"]],
                   fields=review._fields("Shift Assignment", ["name", "modified", "docstatus", "employee", "start_date", "end_date", "status", "shift_type", "custom_project"]))
    daily_filters = {"date": ["between", [monday, sunday]], "docstatus": ["!=", 2]}
    if project:
        daily_filters["project_id"] = project
    daily = _read("Daily Timesheet", warnings, filters=daily_filters, fields=review._fields("Daily Timesheet", DAILY_FIELDS))
    employee_ids = sorted({doc.get("employee") for doc in docs if doc.get("employee")} | {row.employee for row in shifts or [] if row.employee})
    context = {"employees": {}, "daily": {}, "shifts": shifts or [], "types": {}, "projects": {}, "user_names": {}}
    access = {"shifts": shifts is not None, "daily": daily is not None}
    identities = sorted({str(row.get("current_user") or row.get("employee_name")) for row in daily or [] if row.get("current_user") or row.get("employee_name")})
    daily_users = sorted({row.get("owner") for row in daily or [] if row.get("owner")} | set(identities))
    if employee_ids or identities or daily_users:
        employees = _read("Employee", warnings, or_filters=[["name", "in", employee_ids], ["employee_name", "in", identities], ["user_id", "in", daily_users]], fields=["name", "employee_name", "user_id"])
        context["employees"] = {row.name: row for row in employees or []}
        access["employees"] = employees is not None
        employee_ids = sorted(set(employee_ids) | set(context["employees"]))
        users = sorted({row.get("user_id") for row in employees or [] if row.get("user_id")})
        if users and frappe.has_permission("User", "read"):
            user_rows = _read("User", warnings, filters={"name": ["in", users]}, fields=["name", "full_name"])
            context["user_names"] = {row.name: row.full_name for row in user_rows or []}
        # Other readable weeks/projects for the same staff participate in overlap checks.
        related = _read("Timesheet", warnings, required=True, cap=3 * WEEKLY_LIMIT, filters={"docstatus": ["!=", 2], "employee": ["in", employee_ids],
                        "custom_monday_date": ["between", [monday - timedelta(days=7), monday + timedelta(days=7)]]}, fields=["name"])
        known = {doc.name for doc in docs}
        docs.extend(_documents([row for row in related if row.name not in known]))
        context["daily"] = {row.name: row for row in daily or [] if _daily_employee(row, context["employees"], context["user_names"]) in employee_ids}
        if daily and len(context["daily"]) != len(daily):
            warnings.append("Some daily submissions could not be matched to a unique readable employee. Check their current user identity and employee mapping.")
        linked_names = {log.get("daily_timesheet_id") or log.get("custom_daily_timesheet_id") for doc in docs for log in doc.time_logs} - {None, "", *context["daily"]}
        if linked_names and access["daily"]:
            sources = _read("Daily Timesheet", warnings, filters={"name": ["in", sorted(linked_names)]}, fields=review._fields("Daily Timesheet", DAILY_FIELDS))
            context["daily"].update({row.name: row for row in sources or []})
        attendance = _read("Attendance", warnings, filters={"employee": ["in", employee_ids], "attendance_date": ["between", [monday, sunday]], "docstatus": 1}, fields=["name", "employee", "attendance_date", "status"])
        leave = _read("Leave Application", warnings, filters={"employee": ["in", employee_ids], "docstatus": 1, "status": "Approved", "from_date": ["<=", sunday], "to_date": [">=", monday]}, fields=["name", "employee", "from_date", "to_date", "half_day", "half_day_date"])
        access.update(attendance=attendance is not None, leave=leave is not None)
    else:
        attendance, leave = [], []
        access.update(employees=True, attendance=True, leave=True)
    type_names = sorted({row.shift_type for row in context["shifts"] if row.shift_type} | {log.get("shift_type") for doc in docs for log in doc.time_logs if log.get("shift_type")} | {row.get("shift") for row in context["daily"].values() if row.get("shift")})
    types = _read("Shift Type", warnings, filters={"name": ["in", type_names]}, fields=["name", "start_time", "end_time"]) if type_names else []
    access["types"] = types is not None
    context["types"] = {row.name: row for row in types or []}
    project_ids = sorted({row.get("custom_project") for row in context["shifts"] if row.get("custom_project")} | {p for doc in docs for p in [doc.get("parent_project"), *[log.get("project") for log in doc.time_logs]] if p} | {row.get("project_id") for row in context["daily"].values() if row.get("project_id")})
    projects = _read("Project", warnings, filters={"name": ["in", project_ids]}, fields=review._fields("Project", ["name", "project_name", "max_ds_hrs", "max_ns_hrs", "max_fly_hrs"])) if project_ids else []
    context["projects"] = {row.name: row for row in projects or []}
    from verto.api.mobile.push_notifications import _get_timesheet_reminder_exclusions
    exclusions = {str(monday + timedelta(days=offset)): _get_timesheet_reminder_exclusions(monday + timedelta(days=offset)) for offset in range(7)}
    current = now_datetime()
    items = build_queue(docs, context, monday, current, project=project, attendance=attendance, leave=leave, exclusions=exclusions, access=access)
    frappe.local.response_headers["Cache-Control"] = "no-store"
    return {"week_start": str(monday), "week_end": str(sunday), "generated_at": str(current), "items": items,
            "categories": [{"value": key, "label": label, "count": sum(key in item["categories"] for item in items)} for key, label in CATEGORIES.items()],
            "projects": [{"value": row.name, "label": row.get("project_name") or row.name} for row in projects or []],
            "warnings": list(dict.fromkeys(warnings))}
