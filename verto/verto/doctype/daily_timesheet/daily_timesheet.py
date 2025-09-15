# Copyright (c) 2024, Webwire
# For license information, please see license.txt

import json
import traceback
import frappe
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
from frappe.utils import add_days, getdate, get_datetime, add_to_date

# Structured logger for this doctype. Logs land in site logs and are easy to tail.
logger = frappe.logger("verto.daily_timesheet", allow_site=True, file_count=20)

class DailyTimesheet(Document):
    def before_insert(self):
        user = frappe.get_doc("User", self.owner)
        self.current_user = user.full_name

    def validate(self):
        # --- Fill in current_user (full name of the owner) ---
        if not self.current_user and self.owner:
            user_full_name = frappe.db.get_value("User", self.owner, "full_name")
            if user_full_name:
                self.current_user = user_full_name

        # --- Calculate duration if start/end time provided ---
        if self.start_time and self.end_time:
            start = get_datetime(f"{self.date} {self.start_time}")
            end = get_datetime(f"{self.date} {self.end_time}")

            if end < start:  # Handle overnight (crossing midnight)
                end = add_to_date(end, days=1)

            self.duration = (end - start).total_seconds()

        # --- Find shift allocation for this employee & date ---
        if self.date and self.current_user and not self.shift_allocation:
            shift_name = frappe.db.get_value(
                "Shift Assignment",
                {
                    "employee_name": self.current_user,
                    "docstatus": 1,
                    "start_date": ("<=", self.date),
                    "end_date": (">=", self.date),
                },
                "name"
            )
            if shift_name:
                self.shift_allocation = shift_name
            else:
                frappe.msgprint(
                    "You have no allocated shifts available to fill out a timesheet. "
                    "Please contact the office for a shift allocation."
                )

    def on_update(self):
        """Enqueue background job so it runs even if the user closes the page."""
        try:
            payload = self.as_dict()
            job_name = f"Process Timesheet for DailyTimesheet {self.name}"
            enqueue(
                "verto.verto.doctype.daily_timesheet.daily_timesheet.process_timesheet",
                queue="default",
                job_name=job_name,
                doc=payload,
            )
            logger.info(
                "Enqueued timesheet processing job",
                extra={
                    "daily_timesheet": self.name,
                    "job_name": job_name,
                    "queue": "default",
                    "doc_preview": {
                        "name": payload.get("name"),
                        "date": payload.get("date"),
                        "user_full_name": payload.get("user_full_name"),
                        "project_id": payload.get("project_id"),
                        "duration": payload.get("duration"),
                        "start_time": payload.get("start_time"),
                        "end_time": payload.get("end_time"),
                    },
                },
            )
        except Exception:
            logger.exception("Failed to enqueue timesheet processing job")
            # Don't raise — we don't want to block the save


def process_timesheet(doc: dict):
    """Background job: create or update the correct weekly Timesheet."""
    ctx = {"daily_timesheet": doc.get("name")}
    logger.info("Started process_timesheet", extra=ctx)

    try:
        # --- Input sanity + computed range ---
        doc_date = getdate(doc["date"])
        week_start = get_monday(doc_date)
        week_end = add_days(week_start, 6)
        ctx.update({
            "date": str(doc_date),
            "week_start": str(week_start),
            "week_end": str(week_end),
            "user_full_name": doc.get("user_full_name"),
            "project_id": doc.get("project_id"),
        })
        logger.info("Computed week window", extra=ctx)

        # --- Resolve Employee link ---
        # Prefer the doc.owner; fallback to modified_by/session if ever needed
        employee = frappe.db.get_value("Employee", {"user_id": doc.get("owner")}, "name")
        if not employee:
            employee = frappe.db.get_value("Employee", {"employee_name": doc.get("user_full_name")}, "name")
        ctx["employee"] = employee
        logger.info("Resolved employee", extra=ctx)

        # --- Compute from_time / to_time (handles cross-midnight) ---
        start_time_str = doc.get("start_time")
        end_time_str = doc.get("end_time")
        duration_seconds = float(doc.get("duration") or 0)

        if not start_time_str:
            raise frappe.ValidationError("DailyTimesheet.start_time is required to create a Timesheet log")

        from_dt = get_datetime(f"{doc['date']} {start_time_str}")

        if duration_seconds > 0:
            to_dt = add_to_date(from_dt, seconds=duration_seconds)
            hours_in_float = duration_seconds / 3600.0
            source = "duration_seconds"
        elif end_time_str:
            to_dt = get_datetime(f"{doc['date']} {end_time_str}")
            # If user worked past midnight, advance end by 1 day
            if to_dt < from_dt:
                to_dt = add_to_date(to_dt, days=1)
            delta = to_dt - from_dt
            hours_in_float = round(delta.total_seconds() / 3600.0, 6)
            source = "start_end"
        else:
            raise frappe.ValidationError("Either DailyTimesheet.duration or end_time must be present")

        ctx.update({
            "from_time": str(from_dt),
            "to_time": str(to_dt),
            "hours_in_float": hours_in_float,
            "compute_source": source
        })
        logger.info("Calculated time window for log", extra=ctx)

        # --- Find existing weekly Timesheet for this project/employee/week ---
        existing = frappe.get_all(
            "Timesheet",
            filters={
                "employee_name": doc.get("current_user"),
                "parent_project": doc.get("project_id"),
                "start_date": ["between", [str(week_start), str(week_end)]],
            },
            pluck="name",
            limit=1,
        )
        existing_timesheet = existing[0] if existing else None
        ctx["existing_timesheet"] = existing_timesheet
        logger.info("Lookup existing weekly Timesheet", extra=ctx)

        # --- Build the time log row (idempotent via daily_timesheet_id) ---
        work_day_name = get_day_name(doc["date"])
        timesheet_entry = {
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
            "daily_timesheet_id": doc.get("name"),
        }
        logger.info("Prepared timesheet entry", extra={"daily_timesheet": doc.get("name"), "entry_preview": safe_preview(timesheet_entry)})

        # --- Upsert into Timesheet ---
        if existing_timesheet:
            ts = frappe.get_doc("Timesheet", existing_timesheet)
            before_count = len(ts.time_logs or [])
            # Remove any previous log for this Daily Timesheet (idempotency)
            ts.time_logs = [log for log in (ts.time_logs or []) if log.daily_timesheet_id != doc.get("name")]
            removed = before_count - len(ts.time_logs or [])
            ts.append("time_logs", timesheet_entry)
            # Sort by from_time (ensures nice order in UI)
            ts.time_logs.sort(key=lambda x: x.from_time)
            ts.save(ignore_permissions=True)
            ctx.update({"updated_timesheet": ts.name, "removed_existing_rows": removed, "final_rows": len(ts.time_logs or [])})
            logger.info("Updated existing Timesheet", extra=ctx)
        else:
            if not employee:
                raise frappe.ValidationError("Could not resolve Employee link for this user")
            ts = frappe.get_doc({
                "doctype": "Timesheet",
                "employee": employee,
                "employee_name": doc.get("user_full_name"),
                "start_date": week_start,
                "custom_monday_date": week_start,
                "custom_sunday_date": week_end,
                "customer": doc.get("customer"),
                "parent_project": doc.get("project_id"),
                "time_logs": [timesheet_entry],
            })
            ts.insert(ignore_permissions=True)
            ctx.update({"created_timesheet": ts.name})
            logger.info("Created new Timesheet", extra=ctx)

        logger.info("Finished process_timesheet OK", extra={"daily_timesheet": doc.get("name")})

    except Exception:
        # Dump a rich error with context; stays in your site logs
        logger.exception("process_timesheet failed")
        # Optionally persist failure details to an Error Log doctype:
        try:
            frappe.log_error(
                title=f"DailyTimesheet background job failed: {doc.get('name')}",
                message=json.dumps({
                    "doc": safe_preview(doc),
                    "traceback": traceback.format_exc(),
                }, default=str, indent=2)
            )
        except Exception:
            # Don't let secondary logging explode
            pass
        # Re-raise so the RQ Job shows as failed (useful during testing)
        raise


def get_monday(any_date):
    d = getdate(any_date)
    return add_days(d, -d.weekday())


def get_day_name(date_str):
    return getdate(date_str).strftime("%A")


def safe_preview(obj, maxlen=500):
    """
    Compact the preview so logs remain readable.
    """
    try:
        s = json.dumps(obj, default=str)
        return (s[:maxlen] + "...") if len(s) > maxlen else s
    except Exception:
        return str(obj)[:maxlen]
