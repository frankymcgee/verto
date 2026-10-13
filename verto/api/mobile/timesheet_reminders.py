"""Shift-end push reminders and a durable list of outstanding daily hours."""

from __future__ import annotations

import hashlib
from datetime import datetime, time, timedelta
from urllib.parse import urlencode

import frappe
from frappe.utils import cint, get_datetime, getdate, now_datetime

from verto.api.mobile import push_notifications as push

REMINDER_DOCTYPE = "Verto Timesheet Reminder"
SETTING_FIELD = "shift_missing_hours_reminders_enabled"
LAST_SCAN_FIELD = "shift_missing_hours_last_scan"
FIRST_SENT_FIELD = "first_notified_on"
FOLLOWUP_SENT_FIELD = "next_day_notified_on"


def reminders_enabled():
    if not frappe.db.exists("DocType", REMINDER_DOCTYPE):
        return False
    settings = frappe.get_cached_doc(push.SETTINGS_DOCTYPE)
    return bool(cint(settings.get(SETTING_FIELD)))


def _clock(value):
    if isinstance(value, timedelta):
        seconds = value.total_seconds()
        if not 0 <= seconds < 86400:
            raise ValueError("Shift time must be within a day")
        return (datetime.min + value).time()
    if isinstance(value, time):
        return value
    return time.fromisoformat(str(value))


def shift_reminder_due_at(work_date, shift_type):
    """Frappe Shift Type times are in the site's timezone, like now_datetime."""
    try:
        start = _clock(shift_type.get("start_time"))
        end = _clock(shift_type.get("end_time"))
    except (TypeError, ValueError):
        return None
    # Equal/absent times do not define a working shift; never guess DS/NS hours.
    if start == end:
        return None
    end_at = datetime.combine(getdate(work_date), end)
    if end < start:
        end_at += timedelta(days=1)
    return end_at + timedelta(hours=1)


def _unavailable(shift_type):
    code = str(shift_type or "").strip().upper().replace("_", "-").replace(" ", "-")
    return code in {"U", "UNAVAILABLE", "ON-LEAVE", "AL", "SL", "RNR", "RNR-LEAVE"} or code.endswith("-U")


def _employees_on_leave(work_date):
    employees = set()
    if frappe.db.exists("DocType", "Attendance"):
        employees.update(row.employee for row in frappe.get_all(
            "Attendance", filters={"attendance_date": work_date, "status": "On Leave", "docstatus": 1},
            fields=["employee"], limit_page_length=0,
        ))
    if frappe.db.exists("DocType", "Leave Application"):
        employees.update(row.employee for row in frappe.get_all(
            "Leave Application", filters={"from_date": ["<=", work_date], "to_date": [">=", work_date],
                                          "docstatus": 1, "status": "Approved", "half_day": 0},
            fields=["employee"], limit_page_length=0,
        ))
    return employees


def _timesheet_matches(timesheet, user_allocation, shift):
    # Explicit employee identity wins over the creator when an office user
    # enters somebody else's hours. Owner is only a legacy fallback.
    has_identity = any(timesheet.get(field) for field in ("employee", "employee_name", "current_user"))
    candidate = dict(timesheet)
    if has_identity:
        candidate["owner"] = ""
    if not push._timesheet_matches_user(candidate, user_allocation):
        return False
    allocation_id = str(timesheet.get("shift_allocation") or "").strip()
    if allocation_id:
        return allocation_id == shift["shift_assignment"]
    # Older records may have no allocation link. Require their project and
    # shift, where present, so another job/shift does not hide missing hours.
    timesheet_project = timesheet.get("_verto_project_id") or ""
    if shift.get("project") and timesheet_project != shift["project"]:
        return False
    if timesheet.get("shift") and timesheet["shift"] != shift["shift_type"]:
        return False
    return True


def _date_context(work_date, cache, user=None):
    key = (str(getdate(work_date)), user)
    if key not in cache:
        users, _ = push._get_allocated_users_for_date(getdate(work_date), user=user)
        timesheets = push._get_daily_timesheets_with_hours(getdate(work_date))
        cache[key] = (users, timesheets, _employees_on_leave(work_date))
    return cache[key]


def _outstanding_shift(reminder, contexts, shift_types, user=None):
    users, timesheets, on_leave = _date_context(reminder["work_date"], contexts, user=user)
    if timesheets is None:
        # An unavailable schema is not evidence that an outstanding shift was completed.
        return None, True
    allocation = users.get(reminder["user"])
    if not allocation:
        return None, False
    shift = next((row for row in allocation["allocations"]
                  if row["shift_assignment"] == reminder["shift_assignment"]), None)
    if not shift or _unavailable(shift["shift_type"]) or shift["employee"] in on_leave:
        return None, False
    if any(_timesheet_matches(row, allocation, shift) for row in timesheets):
        return None, False
    shift_type = shift["shift_type"]
    if shift_type not in shift_types:
        shift_types[shift_type] = frappe.db.get_value(
            "Shift Type", shift_type, ["start_time", "end_time"], as_dict=True,
        ) or {}
    due_at = shift_reminder_due_at(reminder["work_date"], shift_types[shift_type])
    if due_at is None:
        return None, True
    return {**shift, "due_at": due_at}, False


def _key(user, shift_assignment, work_date):
    return hashlib.sha256(f"{user}|{shift_assignment}|{getdate(work_date)}".encode()).hexdigest()


def _open_reminders(user=None):
    filters = {"status": "Open"}
    if user:
        filters["user"] = user
    return frappe.get_all(REMINDER_DOCTYPE, filters=filters,
                          fields=["name", "user", "shift_assignment", "work_date", "due_at",
                                  "first_notified_on", "next_day_notified_on"],
                          order_by="work_date asc, name asc", limit_page_length=0)


def _resolve(reminder):
    frappe.db.set_value(REMINDER_DOCTYPE, reminder["name"], {"status": "Resolved", "last_error": ""})


def _queue(reminder, follow_up=False):
    sent_field = FOLLOWUP_SENT_FIELD if follow_up else FIRST_SENT_FIELD
    if reminder.get(sent_field) or not push._get_vapid_config()["configured"]:
        return False
    if not frappe.db.exists(push.SUBSCRIPTION_DOCTYPE, {"user": reminder["user"], "enabled": 1}):
        return False
    frappe.enqueue(
        "verto.api.mobile.timesheet_reminders.deliver_missing_hours_reminder",
        queue="short", timeout=300, enqueue_after_commit=True,
        job_id=f"timesheet-reminder-{reminder['name']}-{sent_field}", deduplicate=True,
        reminder_name=reminder["name"], follow_up=follow_up,
    )
    # enqueue_after_commit deliberately returns None in Frappe v16. The
    # worker records actual delivery separately after a successful response.
    return True


def send_shift_missing_hours_reminders(reference_datetime=None, dry_run=False):
    """Discover newly due shifts, catch up after downtime, and retain older reminders."""
    current = get_datetime(reference_datetime) if reference_datetime else now_datetime()
    dry_run = bool(cint(dry_run))
    summary = {"enabled": reminders_enabled(), "due": 0, "created": 0, "resolved": 0,
               "queued": 0, "dry_run": dry_run, "skipped_shift_types": []}
    if not summary["enabled"]:
        return summary
    contexts, shift_types = {}, {}
    known = {row.name: row for row in _open_reminders()}
    candidates = dict(known)
    # Start with yesterday on rollout; subsequent runs catch up after downtime.
    # Include the prior day for night shifts that end the next morning.
    last_scan = frappe.db.get_single_value(push.SETTINGS_DOCTYPE, LAST_SCAN_FIELD)
    first_date = min(getdate(last_scan), current.date()) if last_scan else current.date()
    work_date = first_date - timedelta(days=1)
    while work_date <= current.date():
        users, _, _ = _date_context(work_date, contexts)
        for user, allocation in users.items():
            for shift in allocation["allocations"]:
                name = _key(user, shift["shift_assignment"], work_date)
                candidates.setdefault(name, {"name": name, "user": user,
                                             "work_date": work_date, **shift})
        work_date += timedelta(days=1)
    for name, reminder in candidates.items():
        shift, skipped = _outstanding_shift(reminder, contexts, shift_types)
        if skipped:
            continue
        if not shift:
            if name in known:
                summary["resolved"] += 1
                if not dry_run:
                    _resolve(reminder)
            continue
        if shift["due_at"] > current:
            # A shift edited to finish later remains pending, with its corrected due time.
            if name in known and not dry_run:
                frappe.db.set_value(REMINDER_DOCTYPE, name, "due_at", shift["due_at"])
            continue
        summary["due"] += 1
        if dry_run:
            continue
        if name not in known:
            values = {"user": reminder["user"], "shift_assignment": shift["shift_assignment"],
                      "work_date": getdate(reminder["work_date"]), "due_at": shift["due_at"], "status": "Open"}
            if frappe.db.exists(REMINDER_DOCTYPE, name):
                # A saved entry can subsequently be deleted or corrected to zero.
                frappe.db.set_value(REMINDER_DOCTYPE, name, values)
            else:
                frappe.get_doc({"doctype": REMINDER_DOCTYPE, "reminder_key": name, **values}).insert(ignore_permissions=True)
                summary["created"] += 1
            reminder = frappe.db.get_value(REMINDER_DOCTYPE, name, ["name", "user", "first_notified_on"], as_dict=True)
        elif get_datetime(reminder["due_at"]) != shift["due_at"]:
            frappe.db.set_value(REMINDER_DOCTYPE, name, "due_at", shift["due_at"])
        if _queue(reminder):
            summary["queued"] += 1
    summary["skipped_shift_types"] = sorted(name for name, value in shift_types.items()
                                             if shift_reminder_due_at(current.date(), value) is None)
    if not dry_run and all(value[1] is not None for value in contexts.values()):
        frappe.db.set_single_value(push.SETTINGS_DOCTYPE, LAST_SCAN_FIELD, current, update_modified=False)
    return summary


def send_next_day_missing_hours_reminders(dry_run=False):
    """One 09:00 follow-up on the calendar day after the first reminder is due."""
    summary = {"enabled": reminders_enabled(), "queued": 0, "dry_run": bool(cint(dry_run))}
    if not summary["enabled"]:
        return summary
    current = now_datetime()
    contexts, shift_types = {}, {}
    for reminder in _open_reminders():
        shift, skipped = _outstanding_shift(reminder, contexts, shift_types)
        if skipped:
            continue
        if not shift:
            if not summary["dry_run"]:
                _resolve(reminder)
            continue
        follow_up_at = datetime.combine(shift["due_at"].date() + timedelta(days=1), time(9))
        if current >= follow_up_at and not reminder.get(FOLLOWUP_SENT_FIELD):
            if summary["dry_run"] or _queue(reminder, follow_up=True):
                summary["queued"] += 1
    return summary


def deliver_missing_hours_reminder(reminder_name, follow_up=False):
    """Recheck hours immediately before delivery and lock against duplicate jobs."""
    if not reminders_enabled():
        return
    sent_field = FOLLOWUP_SENT_FIELD if follow_up else FIRST_SENT_FIELD
    reminder = frappe.db.get_value(REMINDER_DOCTYPE, reminder_name,
                                   ["name", "user", "status", "shift_assignment", "work_date", sent_field],
                                   as_dict=True, for_update=True)
    if not reminder or reminder["status"] != "Open" or reminder.get(sent_field):
        return
    shift, skipped = _outstanding_shift(reminder, {}, {})
    if skipped:
        return
    if not shift:
        _resolve(reminder)
        return
    current = now_datetime()
    due_at = (datetime.combine(shift["due_at"].date() + timedelta(days=1), time(9))
              if follow_up else shift["due_at"])
    if current < due_at:
        return
    date_label = getdate(reminder["work_date"]).strftime("%d %B")
    url = "/verto-mobile/shifts?" + urlencode({"date": str(getdate(reminder["work_date"])), "shift": shift["shift_assignment"]})
    try:
        result = push.send_push_to_users([reminder["user"]], {
            "title": "Timesheet still missing" if follow_up else "Timesheet Reminder",
            "body": f"No hours are recorded for your {shift['shift_type']} shift on {date_label}. Tap to enter them.",
            "url": url, "tag": f"missing-hours-{reminder_name}",
        }, notification_type="missing_hours")
        updates = {"last_error": "" if result["sent"] else f"Push sent: {result['sent']}; failed: {result['failed']}"}
        if result["sent"]:
            updates[sent_field] = current
        frappe.db.set_value(REMINDER_DOCTYPE, reminder_name, updates)
    except Exception:
        frappe.db.set_value(REMINDER_DOCTYPE, reminder_name, "last_error", frappe.get_traceback())
        frappe.log_error(title="Verto missing-hours push failed", message=frappe.get_traceback())


@frappe.whitelist()
def get_my_missing_hours_reminders():
    push._require_login()
    if not reminders_enabled():
        return {"enabled": False, "reminders": []}
    current = now_datetime()
    contexts, shift_types = {}, {}
    rows = []
    # Only the authenticated user's records are ever returned. Live validation
    # clears the banner immediately after a save, without waiting for the cron.
    for reminder in _open_reminders(user=frappe.session.user):
        shift, skipped = _outstanding_shift(reminder, contexts, shift_types, user=frappe.session.user)
        if skipped or not shift or shift["due_at"] > current:
            continue
        rows.append({"name": reminder["name"], "date": str(getdate(reminder["work_date"])),
                     "shift_type": shift["shift_type"], "project": shift["project"],
                     "project_name": shift.get("project_name") or shift["project"],
                     "shift_assignment": shift["shift_assignment"], "due_at": str(shift["due_at"])})
    return {"enabled": True, "reminders": rows}


@frappe.whitelist()
def preview_shift_missing_hours_reminders(reference_datetime=None):
    from verto.api.mobile.global_notifications import _ensure_system_manager_for_manual_call

    _ensure_system_manager_for_manual_call()
    return send_shift_missing_hours_reminders(reference_datetime=reference_datetime, dry_run=True)
