import json
import traceback
import frappe
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
from frappe.utils import add_days, getdate, get_datetime, add_to_date
from datetime import datetime

logger = frappe.logger("verto.daily_timesheet", allow_site=True, file_count=20)


class DailyTimesheet(Document):
    def before_insert(self):
        if not self.current_user:
            # Fill current_user from the User doc
            user = frappe.get_doc("User", self.owner)
            self.current_user = user.full_name

    def validate(self):
        # Fill current_user if not set
        if not self.current_user and self.owner:
            user_full_name = frappe.db.get_value("User", self.owner, "full_name")
            if user_full_name:
                self.current_user = user_full_name

        # Calculate duration
        if self.start_time and self.end_time:
            start = get_datetime(f"{self.date} {self.start_time}")
            end = get_datetime(f"{self.date} {self.end_time}")
            if end < start:  # overnight shift
                end = add_to_date(end, days=1)
            self.duration = (end - start).total_seconds()

        # Auto-fill shift allocation
        if self.date and self.current_user and not self.shift_allocation:
            shift_name = frappe.db.get_value(
                "Shift Assignment",
                {
                    "employee_name": self.current_user,
                    "docstatus": 1,
                    "start_date": ("<=", self.date),
                    "end_date": (">=", self.date),
                },
                "name",
            )
            if shift_name:
                self.shift_allocation = shift_name
            else:
                frappe.msgprint(
                    "You have no allocated shifts available to fill out a timesheet. "
                    "Please contact the office for a shift allocation."
                )

    def on_update(self):
        """Enqueue background job AFTER COMMIT so the Daily Timesheet doc exists."""
        payload = self.as_dict()
        job_name = f"Daily TS Process for: {self.name}"

        frappe.db.after_commit(
            lambda: enqueue(
                "verto.verto.doctype.daily_timesheet.daily_timesheet.process_timesheet",
                queue="default",
                job_name=job_name,
                doc=payload,
            )
        )

        logger.info(
            "Scheduled timesheet processing job after commit",
            extra={
                "daily_timesheet": self.name,
                "job_name": job_name,
                "queue": "default",
                "doc_preview": {
                    "name": payload.get("name"),
                    "date": payload.get("date"),
                    "current_user": payload.get("current_user"),
                    "project_id": payload.get("project_id"),
                    "duration": payload.get("duration"),
                },
            },
        )


def process_timesheet(doc: dict):
    """Background job: create or update the correct weekly Timesheet."""
    ctx = {"daily_timesheet": doc.get("name")}
    logger.info("Started process_timesheet", extra=ctx)

    try:
        # --- Input + computed week window ---
        doc_date = getdate(doc["date"])
        week_start = get_monday(doc_date)
        week_end = add_days(week_start, 6)
        ctx.update(
            {
                "date": str(doc_date),
                "week_start": str(week_start),
                "week_end": str(week_end),
                "current_user": doc.get("current_user"),
                "project_id": doc.get("project_id"),
            }
        )

        # --- Resolve Employee link ---
        employee = frappe.db.get_value("Employee", {"user_id": doc.get("owner")}, "name")
        if not employee and doc.get("current_user"):
            employee = frappe.db.get_value(
                "Employee", {"employee_name": doc.get("current_user")}, "name"
            )
        ctx["employee"] = employee
        logger.info("Resolved employee", extra=ctx)

        # --- Compute from_time / to_time ---
        start_time_str = doc.get("start_time")
        end_time_str = doc.get("end_time")
        duration_seconds = float(doc.get("duration") or 0)

        if not start_time_str:
            raise frappe.ValidationError(
                "DailyTimesheet.start_time is required to create a Timesheet log"
            )

        from_dt = get_datetime(f"{doc['date']} {start_time_str}")

        if duration_seconds > 0:
            to_dt = add_to_date(from_dt, seconds=duration_seconds)
            hours_in_float = duration_seconds / 3600.0
        elif end_time_str:
            to_dt = get_datetime(f"{doc['date']} {end_time_str}")
            if to_dt < from_dt:  # overnight
                to_dt = add_to_date(to_dt, days=1)
            delta = to_dt - from_dt
            hours_in_float = round(delta.total_seconds() / 3600.0, 6)
        else:
            raise frappe.ValidationError(
                "Either DailyTimesheet.duration or end_time must be present"
            )

        ctx.update(
            {"from_time": str(from_dt), "to_time": str(to_dt), "hours": hours_in_float}
        )

        # --- Lookup existing weekly Timesheet ---
        filters = {
            "employee": employee,
            "start_date": str(week_start),
        }
        if doc.get("project_id"):
            filters["parent_project"] = doc.get("project_id")

        # --- Find existing weekly Timesheet for this project/employee/week ---
        existing = frappe.get_all(
            "Timesheet",
            filters={
                # Rule 1: Timesheet.employee_name == DailyTimesheet.current_user
                "employee_name": doc.get("current_user"),

                # Rule 2: DailyTimesheet.date is between Timesheet.custom_monday_date & custom_sunday_date
                "custom_monday_date": ("<=", doc.get("date")),
                "custom_sunday_date": (">=", doc.get("date")),

                # Rule 3: Timesheet.parent_project == DailyTimesheet.project_id
                "parent_project": doc.get("project_id"),
            },
            pluck="name",
            limit=1,
        )
        existing_timesheet = existing[0] if existing else None
        ctx["existing_timesheet"] = existing_timesheet
        logger.info("Lookup existing weekly Timesheet (strict rules)", extra=ctx)

        # --- Build time log entry ---
        work_day_name = get_day_name(doc["date"])
        timesheet_entry = {
            "doctype": "Timesheet Detail",
            "activity_type": "Execution",
            "from_time": from_dt,
            "to_time": to_dt,
            "hours": hours_in_float,
            "is_billable": 1,
            "billing_hours": hours_in_float,
            "project": doc.get("project_id"),
            "shift_type": doc.get("shift"),
            "work_day": work_day_name,
            "description": doc.get("comments"),
        }

        # Link back only if the Daily Timesheet exists
        if frappe.db.exists("Daily Timesheet", doc.get("name")):
            timesheet_entry["daily_timesheet_id"] = doc.get("name")

        logger.info(
            "Prepared timesheet entry",
            extra={"daily_timesheet": doc.get("name"), "entry": safe_preview(timesheet_entry)},
        )

        # --- Upsert into Timesheet ---
        if existing_timesheet:
            ts = frappe.get_doc("Timesheet", existing_timesheet)
            before_count = len(ts.time_logs or [])
            ts.time_logs = [
                log
                for log in (ts.time_logs or [])
                if log.daily_timesheet_id != doc.get("name")
            ]
            ts.append("time_logs", timesheet_entry)
            reorder_time_logs(ts)
            ts.time_logs.sort(key=lambda x: x.from_time)
            ts.save(ignore_permissions=True)
            ctx.update(
                {
                    "updated_timesheet": ts.name,
                    "removed_existing": before_count - len(ts.time_logs or []),
                    "final_rows": len(ts.time_logs or []),
                }
            )
            logger.info("Updated existing Timesheet", extra=ctx)
        else:
            if not employee:
                raise frappe.ValidationError("Could not resolve Employee link for this user")

            ts = frappe.get_doc(
                {
                    "doctype": "Timesheet",
                    "employee": employee,
                    "employee_name": doc.get("current_user"),
                    "start_date": week_start,
                    "custom_monday_date": week_start,
                    "custom_sunday_date": week_end,
                    "customer": doc.get("customer"),
                    "parent_project": doc.get("project_id"),
                    "project": doc.get("project_id"),
                    "company": doc.get("company"),
                    "shift_type": doc.get("shift"),
                    "comments": doc.get("comments"),
                    "time_logs": [timesheet_entry],
                }
            )
            reorder_time_logs(ts)
            ts.insert(ignore_permissions=True)
            ctx.update({"created_timesheet": ts.name})
            logger.info("Created new Timesheet", extra=ctx)

        logger.info("Finished process_timesheet OK", extra=ctx)

    except Exception:
        logger.exception("process_timesheet failed")
        try:
            frappe.log_error(
                title=f"DailyTimesheet background job failed: {doc.get('name')}",
                message=json.dumps(
                    {"doc": safe_preview(doc), "traceback": traceback.format_exc()},
                    default=str,
                    indent=2,
                ),
            )
        except Exception:
            pass
        raise

def reorder_time_logs(ts):
    """Ensure time_logs flow Monday → Sunday, sorted by start time"""
    ts.time_logs.sort(
        key=lambda log: (
            getdate(log.from_time).weekday(),
            get_datetime(log.from_time)
        )
    )
    for idx, log in enumerate(ts.time_logs, start=1):
        log.idx = idx

def get_monday(any_date):
    d = getdate(any_date)
    return add_days(d, -d.weekday())


def get_day_name(date_str):
    return getdate(date_str).strftime("%A")


def safe_preview(obj, maxlen=500):
    try:
        s = json.dumps(obj, default=str)
        return (s[:maxlen] + "...") if len(s) > maxlen else s
    except Exception:
        return str(obj)[:maxlen]
