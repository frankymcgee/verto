"""Authenticated, consolidated internal review and transactional bulk signing."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import time, timedelta

import frappe
from frappe.utils import cint, getdate, get_datetime, now_datetime, nowdate

APPROVER_ROLES = {"System Manager", "Accounts Manager", "HR Manager", "Projects Manager", "Verto Planner Manager"}
AUDIT_DOCTYPE = "Verto Internal Timesheet Approval"
MAX_TIMESHEETS = 200
HOURS_TOLERANCE = 1 / 60  # Accept rounding of elapsed time within one minute.
DAY_SHIFT_CUTOFF = time(16, 30)


def require_approver():
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)
    if user != "Administrator" and not APPROVER_ROLES.intersection(frappe.get_roles(user)):
        frappe.throw("An internal Timesheet approver role is required.", frappe.PermissionError)


def _names(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            frappe.throw("Timesheets must be a list of document names.")
    if not isinstance(value, list) or not value or len(value) > MAX_TIMESHEETS:
        frappe.throw(f"Select between 1 and {MAX_TIMESHEETS} Timesheets.")
    names = [str(name or "").strip() for name in value]
    if any(not name or len(name) > 140 for name in names) or len(set(names)) != len(names):
        frappe.throw("The Timesheet selection contains missing or duplicate names.")
    return names


def _number(value):
    try:
        result = float(value or 0)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def shift_kind(value, config=None):
    code = str(value or "").strip().upper().replace("_", "-").replace(" ", "-")
    if "NIGHT" in code or re.search(r"(?:^|-)NS$", code):
        return "NS"
    if "DAY" in code or re.search(r"(?:^|-)DS$", code):
        return "DS"
    if code in {"FLY-IN", "FLY-OUT"} or re.search(r"(?:^|-)(FI|FO)$", code):
        return "Fly"
    if code in {"U", "UNAVAILABLE", "ON-LEAVE", "AL", "SL", "RNR"} or code.endswith("-U"):
        return "Unavailable"
    if config and config.get("start_time") is not None and config.get("end_time") is not None:
        try:
            start, end = _clock(config["start_time"]), _clock(config["end_time"])
            if start != end:
                return "NS" if end < start else "DS"
        except (TypeError, ValueError):
            pass
    return ""


def _clock(value):
    if isinstance(value, timedelta):
        if not 0 <= value.total_seconds() < 86400:
            raise ValueError("Invalid time")
        seconds = int(value.total_seconds())
        return time(seconds // 3600, seconds % 3600 // 60, seconds % 60)
    return value if isinstance(value, time) else time.fromisoformat(str(value))


def _week(doc):
    monday = getdate(doc.get("custom_monday_date") or doc.get("start_date") or nowdate())
    monday -= timedelta(days=monday.weekday())
    return monday, monday + timedelta(days=6)


def _reviewed_content(doc):
    header = {field: str(doc.get(field) or "") for field in ("employee", "parent_project", "role", "note")}
    header.update({field: str(getdate(doc.get(field))) if doc.get(field) else "" for field in ("custom_monday_date", "custom_sunday_date")})
    header["total_hours"] = _number(doc.get("total_hours"))
    logs = []
    for log in doc.get("time_logs") or []:
        row = {field: str(log.get(field) or "") for field in ("shift_type", "project", "description", "daily_timesheet_id", "custom_daily_timesheet_id")}
        row.update({field: str(get_datetime(log.get(field))) if log.get(field) else "" for field in ("from_time", "to_time")})
        row.update({field: _number(log.get(field)) for field in ("hours", "billing_hours")})
        logs.append(row)
    return {"header": header, "time_logs": sorted(logs, key=lambda row: json.dumps(row, sort_keys=True))}


def invalidate_changed_internal_approval(doc, method=None):
    if not cint(doc.get("internal_approved")):
        return
    previous = doc.get_doc_before_save()
    if previous and _reviewed_content(previous) != _reviewed_content(doc):
        # The immutable audit retains the original approval, while the changed
        # draft needs review again. Client signature fields are unaffected.
        doc.internal_approved = 0
        doc.employee_approved = None
        doc.employee_approval_name = None
        doc.approved_signature = ""


def _fields(doctype, candidates):
    meta = frappe.get_meta(doctype)
    return [field for field in candidates if field in {"name", "modified", "owner", "docstatus"} or meta.has_field(field)]


def _load_context(docs):
    employee_ids = sorted({doc.get("employee") for doc in docs if doc.get("employee")})
    projects = sorted({project for doc in docs for project in
                       [doc.get("parent_project"), *[row.get("project") for row in doc.time_logs]] if project})
    daily_names = sorted({row.get("daily_timesheet_id") or row.get("custom_daily_timesheet_id")
                          for doc in docs for row in doc.time_logs
                          if row.get("daily_timesheet_id") or row.get("custom_daily_timesheet_id")})
    employees = frappe.get_all("Employee", filters={"name": ["in", employee_ids]},
                              fields=["name", "employee_name", "user_id"], limit_page_length=0) if employee_ids else []
    users = [row.user_id for row in employees if row.user_id]
    user_names = {row.name: row.full_name for row in frappe.get_all("User", filters={"name": ["in", users]},
                                                                  fields=["name", "full_name"], limit_page_length=0)} if users else {}
    daily = frappe.get_all("Daily Timesheet", filters={"name": ["in", daily_names]}, fields=_fields("Daily Timesheet", [
        "name", "modified", "owner", "docstatus", "current_user", "employee", "employee_name", "date",
        "start_time", "end_time", "duration", "comments", "shift_allocation", "shift", "project_id",
    ]), limit_page_length=0) if daily_names else []
    minimum = min(_week(doc)[0] for doc in docs)
    maximum = max(_week(doc)[1] for doc in docs)
    shift_fields = _fields("Shift Assignment", ["name", "modified", "docstatus", "employee", "start_date", "end_date",
                                                "status", "shift_type", "custom_project", "custom_project_name"])
    shifts = frappe.get_all("Shift Assignment", filters={"employee": ["in", employee_ids], "docstatus": 1,
                                                         "start_date": ["<=", maximum], "status": "Active"},
                            or_filters=[["end_date", ">=", minimum], ["end_date", "is", "not set"]],
                            fields=shift_fields, limit_page_length=0) if employee_ids else []
    missing_links = sorted({row.get("shift_allocation") for row in daily if row.get("shift_allocation")}
                           - {row.name for row in shifts})
    if missing_links and employee_ids:
        shifts.extend(frappe.get_all("Shift Assignment", filters={"name": ["in", missing_links], "employee": ["in", employee_ids]},
                                     fields=shift_fields, limit_page_length=0))
    shift_names = sorted({row.shift_type for row in shifts if row.shift_type}
                         | {row.get("shift_type") or row.get("shift") for doc in docs for row in doc.time_logs if row.get("shift_type") or row.get("shift")})
    types = frappe.get_all("Shift Type", filters={"name": ["in", shift_names]},
                           fields=["name", "modified", "start_time", "end_time"], limit_page_length=0) if shift_names else []
    project_rows = frappe.get_all("Project", filters={"name": ["in", projects]}, fields=_fields("Project", [
        "name", "modified", "project_name", "max_ds_hrs", "max_ns_hrs", "max_fly_hrs",
    ]), limit_page_length=0) if projects else []
    from verto.api.mobile.push_notifications import _get_timesheet_reminder_exclusions
    from verto.api.mobile.timesheet_reminders import _employees_on_leave

    work_dates = {monday + timedelta(days=offset) for monday, _ in [_week(doc) for doc in docs] for offset in range(7)}
    exclusions = {str(day): _get_timesheet_reminder_exclusions(day) for day in work_dates}
    leave = {str(day): _employees_on_leave(day) for day in work_dates}
    return {"employees": {row.name: row for row in employees}, "user_names": user_names, "exclusions": exclusions, "leave": leave,
            "daily": {row.name: row for row in daily}, "shifts": shifts, "types": {row.name: row for row in types},
            "projects": {row.name: row for row in project_rows}}


def _source_matches(doc, source, context):
    employee = context["employees"].get(doc.get("employee")) or {}
    if source.get("employee"):
        return source["employee"] == doc.get("employee")
    current = source.get("current_user") or source.get("employee_name")
    if current:
        return current in {doc.get("employee_name"), employee.get("employee_name"), employee.get("user_id"),
                           context["user_names"].get(employee.get("user_id"))}
    return bool(employee.get("user_id") and source.get("owner") == employee["user_id"])


def _covers(shift, work_date, employee, project):
    return (shift.get("employee") == employee and cint(shift.get("docstatus")) == 1
            and shift.get("status") == "Active" and getdate(shift.get("start_date")) <= work_date
            and (not shift.get("end_date") or getdate(shift["end_date"]) >= work_date)
            and (not project or shift.get("custom_project") == project))


def inspect_time_log(doc, log, index, context):
    flags = []
    def flag(code, message):
        flags.append({"code": code, "message": message})

    hours = _number(log.get("hours"))
    start = end = None
    try:
        if log.get("from_time") and log.get("to_time"):
            start, end = get_datetime(log["from_time"]), get_datetime(log["to_time"])
    except (TypeError, ValueError):
        pass
    actual_kind = "NS" if start and start.time() >= DAY_SHIFT_CUTOFF else "DS" if start else ""
    declared = str(log.get("shift_type") or log.get("shift") or "").strip()
    declared_kind = shift_kind(declared, context["types"].get(declared)) or actual_kind
    elapsed = (end - start).total_seconds() / 3600 if start and end else None
    if not start or not end or end <= start:
        flag("invalid_times", "Start and end times are missing or the end is not after the start.")
    elif elapsed > 24:
        flag("long_duration", f"The recorded period spans {elapsed:g} hours.")
    if hours is None or hours <= 0:
        flag("invalid_hours", "Claimed hours must be a positive number.")
    elif elapsed is not None and abs(hours - elapsed) > HOURS_TOLERANCE:
        flag("duration_mismatch", f"{hours:g} hours claimed, but the start/end period is {elapsed:.2f} hours.")
    if declared_kind in {"DS", "NS"} and actual_kind and declared_kind != actual_kind:
        flag("declared_shift_mismatch", f"Recorded as {declared_kind}, but the start time falls in {actual_kind}.")
    if declared and not shift_kind(declared, context["types"].get(declared)):
        flag("unknown_shift", f"Check the recorded shift label: {declared}.")

    project = log.get("project") or doc.get("parent_project") or ""
    if log.get("project") and doc.get("parent_project") and log.project != doc.parent_project:
        flag("project_mismatch", "The time-log project differs from the weekly Timesheet project.")
    work_date = start.date() if start else _week(doc)[0]
    if not (_week(doc)[0] <= work_date <= _week(doc)[1]):
        flag("outside_week", "The work date falls outside this Timesheet's week.")
    daily_id = log.get("daily_timesheet_id") or log.get("custom_daily_timesheet_id") or ""
    source = context["daily"].get(daily_id)
    source_safe = source and _source_matches(doc, source, context) and (not source.get("project_id") or source.get("project_id") == project)
    if daily_id and not source:
        flag("missing_daily", "The linked Daily Timesheet could not be found.")
    elif source and not source_safe:
        flag("daily_identity_mismatch", "The linked Daily Timesheet belongs to a different employee or project.")
    elif source_safe:
        if cint(source.get("docstatus")) == 2:
            flag("cancelled_daily", "The linked Daily Timesheet is cancelled.")
        if source.get("date") and getdate(source["date"]) != work_date:
            flag("daily_date_mismatch", "The weekly work date differs from the Daily Timesheet date.")
        duration = _number(source.get("duration"))
        if hours is not None and duration is not None and abs(hours - duration / 3600) > HOURS_TOLERANCE:
            flag("daily_hours_mismatch", "Daily hours have changed or differ from the weekly time log. Check that processing has finished.")
        if str(source.get("comments") or "") != str(log.get("description") or ""):
            flag("daily_comments_mismatch", "Current daily comments differ from the weekly time log. Check that processing has finished.")
        if start and end and source.get("date") and source.get("start_time") is not None and source.get("end_time") is not None:
            try:
                daily_start = get_datetime(f"{source['date']} {_clock(source['start_time'])}")
                daily_end = get_datetime(f"{source['date']} {_clock(source['end_time'])}")
                if daily_end < daily_start:
                    daily_end += timedelta(days=1)
                if abs((daily_start - start).total_seconds()) > 60 or abs((daily_end - end).total_seconds()) > 60:
                    flag("daily_times_mismatch", "Daily start/end times differ from the weekly time log.")
            except (TypeError, ValueError):
                flag("invalid_daily_times", "The linked Daily Timesheet has unusable start/end times.")

    candidates = [shift for shift in context["shifts"] if _covers(shift, work_date, doc.get("employee"), project)]
    allocated = None
    linked = source.get("shift_allocation") if source_safe else None
    if linked:
        allocated = next((shift for shift in candidates if shift.name == linked), None)
        if not allocated:
            flag("invalid_allocation", "The linked allocation does not match this employee, project, work date or active submitted status.")
    elif len(candidates) == 1:
        allocated = candidates[0]
    elif candidates:
        flag("ambiguous_allocation", "Multiple allocations cover this day. Check the Daily Timesheet's allocation link.")
    else:
        flag("missing_allocation", "No active submitted allocation matches this employee, project and work date.")
    allocated_label = allocated.shift_type if allocated else ""
    allocated_kind = shift_kind(allocated_label, context["types"].get(allocated_label))
    if allocated_kind == "Unavailable":
        flag("unavailable_allocation", "Hours have been entered against an unavailable shift.")
    elif allocated and not allocated_kind:
        flag("unknown_allocation_shift", "The allocated shift cannot be classified; check its Shift Type.")
    if allocated_kind in {"DS", "NS"}:
        if actual_kind and allocated_kind != actual_kind:
            flag("allocation_time_mismatch", f"Allocated {allocated_kind}, but the entered start time falls in {actual_kind}.")
        if declared_kind in {"DS", "NS", "Fly"} and declared_kind != allocated_kind:
            flag("allocation_label_mismatch", f"Allocated {allocated_kind}, but the hours are recorded as {declared_kind}.")
    elif allocated_kind == "Fly" and declared and declared_kind != "Fly":
        flag("fly_label_mismatch", "Allocated a fly day, but the recorded shift is not a fly shift.")
    limit_kind = allocated_kind if allocated_kind in {"DS", "NS", "Fly"} else declared_kind
    limit_field = {"DS": "max_ds_hrs", "NS": "max_ns_hrs", "Fly": "max_fly_hrs"}.get(limit_kind)
    maximum = _number((context["projects"].get(project) or {}).get(limit_field)) if limit_field else None
    return {"idx": log.get("idx") or index, "date": str(work_date), "from_time": str(start or log.get("from_time") or ""),
            "to_time": str(end or log.get("to_time") or ""), "hours": hours if hours is not None else 0,
            "elapsed_hours": round(elapsed, 4) if elapsed is not None else None, "declared_shift": declared or actual_kind,
            "recorded_shift": actual_kind, "display_shift": declared_kind if declared_kind in {"DS", "NS"} else actual_kind,
            "allocated_shift": allocated_label, "allocated_kind": allocated_kind, "allocation": allocated.name if allocated else "",
            "project": project, "daily_timesheet": daily_id if source_safe else "", "comments": str(log.get("description") or ""),
            "daily_comments": str(source.get("comments") or "") if source_safe else "", "flags": flags,
            "maximum": maximum if maximum and maximum > 0 else None, "limit_kind": limit_kind,
            "timesheet": doc.name, "employee": doc.get("employee")}


def _cross_checks(rows):
    entries = [entry for row in rows for entry in row["entries"]]
    totals = {}
    for entry in entries:
        key = (entry["employee"], entry["project"], entry["date"], entry["limit_kind"])
        totals[key] = totals.get(key, 0) + max(entry["hours"], 0)
    for entry in entries:
        key = (entry["employee"], entry["project"], entry["date"], entry["limit_kind"])
        if entry["maximum"] and totals[key] > entry["maximum"] + 0.000001:
            entry["flags"].append({"code": "hours_exceeded", "message": f"{totals[key]:g} hours claimed for this day/shift; project maximum is {entry['maximum']:g}."})
    # Detect overlaps/duplicate daily sources across all reviewed Timesheets.
    for index, entry in enumerate(entries):
        for other in entries[:index]:
            if entry["employee"] != other["employee"]:
                continue
            duplicate = entry["daily_timesheet"] and entry["daily_timesheet"] == other["daily_timesheet"]
            overlap = False
            try:
                overlap = (get_datetime(entry["from_time"]) < get_datetime(other["to_time"])
                           and get_datetime(other["from_time"]) < get_datetime(entry["to_time"]))
            except (TypeError, ValueError):
                pass
            if duplicate or overlap:
                for current, counterpart in ((entry, other), (other, entry)):
                    current["flags"].append({"code": "overlap", "message": f"Overlapping or duplicate hours with {counterpart['timesheet']} row {counterpart['idx']}."})


def _missing_days(rows, context):
    from verto.api.mobile.timesheet_reminders import shift_reminder_due_at

    current = now_datetime()
    recorded = {(entry["employee"], entry["project"], entry["date"]) for row in rows for entry in row["entries"]
                if entry["hours"] > 0 and entry["elapsed_hours"] and entry["elapsed_hours"] > 0}
    for row in rows:
        row["missing_days"] = []
        employee = context["employees"].get(row["employee"]) or {}
        user = str(employee.get("user_id") or "").casefold()
        for offset in range(7):
            date = getdate(row["week_start"]) + timedelta(days=offset)
            date_key = str(date)
            if (row["employee"], row["project"], date_key) in recorded:
                continue
            if row["employee"] in context.get("leave", {}).get(date_key, set()):
                continue
            if (user, str(row["project"]).casefold()) in context.get("exclusions", {}).get(date_key, set()):
                continue
            required = []
            for shift in context["shifts"]:
                if not _covers(shift, date, row["employee"], row["project"]):
                    continue
                kind = shift_kind(shift.shift_type, context["types"].get(shift.shift_type))
                if kind not in {"DS", "NS", "Fly"}:
                    continue
                due = shift_reminder_due_at(date, context["types"].get(shift.shift_type) or {})
                if due and due <= current:
                    required.append(shift.shift_type)
            if required:
                label = ", ".join(sorted(set(required)))
                row["missing_days"].append({"date": date_key, "allocated_shift": label})
                row["flags"].append({"code": "missing_hours", "message": f"No hours recorded for allocated {label} on {date_key}."})


def build_review(docs, context=None):
    context = context if context is not None else _load_context(docs)
    rows = []
    for doc in docs:
        monday, sunday = _week(doc)
        entries = [inspect_time_log(doc, log, index, context) for index, log in enumerate(doc.time_logs, 1)]
        flags = []
        if not entries:
            flags.append({"code": "no_hours", "message": "This Timesheet has no time logs."})
        if not doc.get("employee") or not doc.get("parent_project"):
            flags.append({"code": "missing_details", "message": "The Timesheet is missing its employee or parent project."})
        if (not doc.get("custom_monday_date") or not doc.get("custom_sunday_date")
                or getdate(doc.custom_monday_date) != monday or getdate(doc.custom_sunday_date) != sunday):
            flags.append({"code": "invalid_week", "message": "The Timesheet's Monday/Sunday dates need checking."})
        total = sum(entry["hours"] for entry in entries)
        saved_total = _number(doc.get("total_hours"))
        if saved_total is None or abs(saved_total - total) > HOURS_TOLERANCE:
            flags.append({"code": "total_mismatch", "message": "The saved total differs from the sum of time-log hours."})
        rows.append({"name": doc.name, "employee": doc.get("employee"), "employee_name": doc.get("employee_name") or doc.get("employee"),
                     "role": doc.get("role") or "", "project": doc.get("parent_project") or "",
                     "project_name": doc.get("project_name") or doc.get("parent_project") or "No project",
                     "week_start": str(monday), "week_end": str(sunday), "entries": entries, "flags": flags,
                     "total": round(total, 4), "docstatus": cint(doc.docstatus), "internal_approved": bool(cint(doc.get("internal_approved"))),
                     "approved_by": doc.get("employee_approval_name") or doc.get("employee_approved") or "",
                     "note": str(doc.get("note") or ""), "can_approve": bool(frappe.has_permission("Timesheet", "write", doc=doc))})
    _cross_checks(rows)
    _missing_days(rows, context)
    for doc, row in zip(docs, rows):
        row["flag_count"] = len(row["flags"]) + sum(len(entry["flags"]) for entry in row["entries"])
        row["days"] = {str(getdate(row["week_start"]) + timedelta(days=offset)): {"ds": 0, "ns": 0, "flag_count": 0, "allocations": []} for offset in range(7)}
        for entry in row["entries"]:
            day = row["days"].get(entry["date"])
            if day:
                day["ns" if entry["display_shift"] == "NS" else "ds"] += entry["hours"]
                day["flag_count"] += len(entry["flags"])
                if entry["allocated_shift"] and entry["allocated_shift"] not in day["allocations"]:
                    day["allocations"].append(entry["allocated_shift"])
        for missing in row["missing_days"]:
            row["days"][missing["date"]]["flag_count"] += 1
            row["days"][missing["date"]]["allocations"].append(missing["allocated_shift"])
        sources = [context["daily"].get(log.get("daily_timesheet_id") or log.get("custom_daily_timesheet_id")) for log in doc.time_logs]
        snapshot = {"timesheet": doc.as_dict(), "row": row, "daily": sources,
                    "shifts": [shift for shift in context["shifts"] if shift.get("employee") == doc.get("employee")],
                    "types": context["types"], "projects": {project: context["projects"].get(project) for project in
                                                             {doc.get("parent_project"), *[entry["project"] for entry in row["entries"]]}}}
        row["review_hash"] = hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()
    groups = {}
    for row in rows:
        key = (row["project"], row["week_start"])
        group = groups.setdefault(key, {"project": row["project"], "project_name": row["project_name"], "week_start": row["week_start"],
                                       "week_end": row["week_end"], "dates": list(row["days"]), "rows": [], "total": 0})
        group["rows"].append(row)
        group["total"] += row["total"]
    return {"groups": list(groups.values()), "timesheet_count": len(rows), "flagged_count": sum(row["flag_count"] > 0 for row in rows),
            "pending_count": sum(not row["internal_approved"] for row in rows)}


@frappe.whitelist()
def get_internal_timesheet_review(week_start=None, project=None, timesheets=None, include_approved=False):
    require_approver()
    if timesheets:
        names = _names(timesheets)
    else:
        monday = getdate(week_start or nowdate())
        if week_start and monday.weekday() != 0:
            frappe.throw("Choose a Monday for the week beginning date.")
        if not week_start:
            monday -= timedelta(days=monday.weekday() + 7)
        filters = {"custom_monday_date": monday, "docstatus": ["!=", 2]}
        if project:
            filters["parent_project"] = project
        if not cint(include_approved):
            filters["internal_approved"] = 0
        # get_list applies role and User Permissions; never list with get_all.
        names = [row.name for row in frappe.get_list("Timesheet", filters=filters, fields=["name"],
                                                    order_by="parent_project asc, employee_name asc, name asc", limit_page_length=MAX_TIMESHEETS + 1)]
        if len(names) > MAX_TIMESHEETS:
            frappe.throw(f"More than {MAX_TIMESHEETS} Timesheets match. Filter by project to review a smaller group.")
    docs = [frappe.get_doc("Timesheet", name) for name in sorted(names)]
    for doc in docs:
        doc.check_permission("read")
        if cint(doc.docstatus) == 2:
            frappe.throw(f"Timesheet {doc.name} is cancelled.")
    data = build_review(docs) if docs else {"groups": [], "timesheet_count": 0, "flagged_count": 0, "pending_count": 0}
    data.update(signer_name=frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
                signer_user=frappe.session.user, today=nowdate())
    return data


def ensure_internal_review_page_roles():
    """Add Verto's manager role after its creation on fresh installations."""
    if not frappe.db.exists("Page", "internal-timesheet-approval"):
        return False
    page = frappe.get_doc("Page", "internal-timesheet-approval")
    present = {row.role for row in page.roles}
    changed = False
    for role in sorted(APPROVER_ROLES - present):
        if frappe.db.exists("Role", role):
            page.append("roles", {"role": role})
            changed = True
    if changed:
        page.save(ignore_permissions=True)
    return changed


@frappe.whitelist(methods=["POST"])
def approve_internal_timesheets(selections, signature_dataurl, signature_mode="draw", full_name=None,
                                acknowledge_flags=False, review_note=None, review_timesheets=None):
    require_approver()
    from verto.api.timesheet_signing import validate_signature

    clean_signature = validate_signature(signature_dataurl)
    if signature_mode not in {"draw", "type"}:
        frappe.throw("Choose a typed or drawn signature.")
    clean_name = str(full_name or frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user).strip()
    if not clean_name or len(clean_name) > 140:
        frappe.throw("Enter a signatory name of no more than 140 characters.")
    selected = frappe.parse_json(selections) if isinstance(selections, str) else selections
    if not isinstance(selected, list) or any(not isinstance(row, dict) for row in selected):
        frappe.throw("The reviewed Timesheet selection is invalid.")
    names = _names([row.get("name") for row in selected])
    review_names = _names(review_timesheets) if review_timesheets else names
    if not set(names).issubset(review_names):
        frappe.throw("The selected Timesheets are not in the reviewed group.")
    hashes = {row["name"]: row.get("review_hash") for row in selected}
    frappe.db.savepoint("verto_internal_approval")
    try:
        docs = [frappe.get_doc("Timesheet", name, for_update=True) for name in sorted(review_names)]
        for doc in docs:
            doc.check_permission("read")
            if doc.name in names:
                doc.check_permission("write")
            if cint(doc.docstatus) == 2:
                frappe.throw(f"Timesheet {doc.name} is cancelled.")
        data = build_review(docs)
        rows = [row for group in data["groups"] for row in group["rows"]]
        pending = [row for row in rows if row["name"] in names and not row["internal_approved"]]
        for row in pending:
            if hashes.get(row["name"]) != row["review_hash"]:
                frappe.throw(f"Timesheet {row['name']} or its hours/allocation has changed. Reload and review it before signing.")
        flagged = [row for row in pending if row["flag_count"]]
        note = str(review_note or "").strip()
        if len(note) > 4000:
            frappe.throw("The review note must be no more than 4000 characters.")
        if flagged and (not cint(acknowledge_flags) or not note):
            frappe.throw("Selected Timesheets have validation flags. Confirm you reviewed them and enter a review note, or exclude them.")
        if not pending:
            return {"status": "Already approved", "approved": [], "skipped": names}
        pending_names = {row["name"] for row in pending}
        audit = frappe.get_doc({"doctype": AUDIT_DOCTYPE, "approved_by": frappe.session.user, "signer_name": clean_name,
                                "approved_at": now_datetime(), "signature_mode": signature_mode, "signature": clean_signature,
                                "timesheet_names": json.dumps(sorted(pending_names)), "review_note": note,
                                "review_details": json.dumps(pending, sort_keys=True, default=str)}).insert(ignore_permissions=True)
        for doc in docs:
            if doc.name in pending_names:
                # Only signature/approval fields change. Draft/submitted status
                # and existing client signatures are preserved.
                doc.db_set({"internal_approved": 1, "employee_approved": frappe.session.user,
                            "employee_approval_name": clean_name, "approved_signature": clean_signature})
        return {"status": "Approved", "approved": sorted(pending_names), "skipped": sorted(set(names) - pending_names), "approval": audit.name}
    except Exception:
        frappe.db.rollback(save_point="verto_internal_approval")
        raise
