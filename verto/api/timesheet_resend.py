"""Manual grouped weekly Timesheet resend helpers.

This module deliberately leaves the normal scheduled grouped Timesheet workflow
unchanged. It adds a System Console/API-friendly entry point that can target an
explicit Monday date when a historical approval email needs to be resent.
"""

import html
import time

import frappe
from frappe.utils import add_days, getdate

from verto.api import automate


@frappe.whitelist()
def send_grouped_weekly_timesheets(project_id=None, week_start=None):
    """Send a grouped approval email for a specific Project/week.

    When ``week_start`` is omitted, delegate to the existing grouped sender so
    its current "latest week" manual behaviour and scheduled behaviour remain
    unchanged.

    When ``week_start`` is supplied, ``project_id`` is required. The date must
    be the Monday for the desired week. Draft and Submitted Timesheets for that
    exact Monday-Sunday range are included, regardless of existing client
    signature state, matching the existing manual resend behaviour.
    """
    if not week_start:
        return automate.send_grouped_weekly_timesheets(project_id=project_id)

    if not project_id:
        frappe.throw("Project ID is required when selecting a specific Timesheet week.")

    # Validate the Project before doing any Timesheet work.
    project = frappe.get_doc("Project", project_id)

    try:
        monday = getdate(week_start)
    except Exception:
        frappe.throw("Week start must be a valid date in YYYY-MM-DD format.")

    if monday.weekday() != 0:
        frappe.throw(
            f"Week start must be a Monday. {monday} is a {monday.strftime('%A')}."
        )

    sunday = add_days(monday, 6)
    timesheets = frappe.get_all(
        "Timesheet",
        filters={
            "parent_project": project_id,
            "custom_monday_date": monday,
            "custom_sunday_date": sunday,
            "docstatus": ["in", [0, 1]],
        },
        fields=automate.get_grouped_timesheet_fields(),
        order_by="employee_name asc, employee asc",
    )

    if not timesheets:
        frappe.throw(
            f"No Draft or Submitted Timesheets were found for Project "
            f"{project_id} from {monday} to {sunday}."
        )

    email_settings = automate.get_verto_mobile_email_settings()
    sendmail_options = automate.get_sendmail_options(email_settings)
    recipients = automate.get_project_or_default_recipients(project, email_settings)

    if not recipients:
        automate.log_missing_recipients(
            timesheets[0],
            "Project.timesheet_email_list and Verto Mobile Settings.email_recipients",
        )
        return {
            "groups_found": 1,
            "results": [{
                "project": project_id,
                "week_start": str(monday),
                "week_end": str(sunday),
                "status": "Skipped",
                "reason": "No email recipients are configured.",
            }],
        }

    names = [ts.name for ts in timesheets]
    summary = automate.get_grouped_week_summary(timesheets)
    signing_url = automate.get_grouped_timesheet_signing_url(names)
    raw_project = timesheets[0].project_name or project.project_name or project.name
    display_project = html.escape(raw_project)

    content_html = f"""
        <p>Please review the consolidated weekly timesheets for
        <strong>{display_project}</strong>.</p>
        <p><strong>Week Range:</strong>
        {summary.start_fmt} &rarr; {summary.end_fmt}</p>
        <p><strong>Employees:</strong> {summary.employee_count}</p>
        <p><strong>Total Hours:</strong> {summary.total_hours} Hours</p>
        <p>The approval page shows Day Shift and Night Shift hours for
        every employee on each day of the week.</p>
        <p><b><a href="{signing_url}">Click Here to Review and Sign</a></b></p>
        <p>One signature will approve all unsigned Timesheets displayed
        on the page. Any existing signatures will remain unchanged.</p>
        <p>If you have any questions or concerns, please contact our site team.</p>
    """

    savepoint_name = "before_grouped_historical_timesheet_resend"

    try:
        frappe.db.savepoint(savepoint_name)
        automate.submit_grouped_timesheets(timesheets)

        frappe.sendmail(
            recipients=recipients,
            subject=(
                f"Weekly Timesheet Approval - {raw_project} - "
                f"{summary.start_fmt} to {summary.end_fmt}"
            ),
            message=automate.build_email_body(content_html, email_settings),
            delayed=False,
            **sendmail_options,
        )

        frappe.db.commit()
        time.sleep(1)
    except Exception:
        try:
            frappe.db.rollback(save_point=savepoint_name)
        except Exception:
            frappe.db.rollback()

        frappe.log_error(
            title=f"Historical grouped Timesheet resend failed for {project_id}",
            message=frappe.get_traceback(),
        )
        return {
            "groups_found": 1,
            "results": [{
                "project": project_id,
                "week_start": str(monday),
                "week_end": str(sunday),
                "status": "Failed",
                "reason": "See Error Log for details.",
            }],
        }

    return {
        "groups_found": 1,
        "results": [{
            "project": project_id,
            "week_start": str(monday),
            "week_end": str(sunday),
            "status": "Sent",
            "timesheet_count": len(names),
            "employee_count": summary.employee_count,
            "total_hours": summary.total_hours,
        }],
    }
