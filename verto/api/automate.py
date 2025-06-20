import frappe
from frappe.utils import add_days, nowdate, getdate
from frappe.utils.pdf import get_pdf
import datetime
import time

def get_timesheet_date_range():
    today = getdate(nowdate())
    weekday = today.weekday()  # Monday = 0, Sunday = 6

    this_week_monday = today - datetime.timedelta(days=weekday)
    this_week_sunday = this_week_monday + datetime.timedelta(days=6)

    if weekday <= 3:  # Monday to Thursday
        start_date = add_days(this_week_monday, -7)
        end_date = add_days(this_week_monday, -1)
        allowed_days = ["Monday", "Tuesday", "Wednesday", "Thursday"]
    else:  # Friday to Sunday
        start_date = this_week_monday
        end_date = this_week_sunday
        allowed_days = ["Friday", "Saturday", "Sunday"]

    return start_date, end_date, allowed_days

def send_weekly_timesheets():
    start_date, end_date, allowed_days = get_timesheet_date_range()
    print(f"\n[Timesheet Emailer] Running for: {start_date} → {end_date}")
    
    timesheets = frappe.get_all("Timesheet",
        filters={
            "docstatus": 0,
            "custom_monday_date": ["=", start_date],
            "custom_sunday_date": ["=", end_date],
        },
        fields=["name", "employee", "parent_project", "project_name", "total_hours", "role","custom_monday_date", "custom_sunday_date"]
    )
    print(f"[Timesheet Emailer] Found {len(timesheets)} unsubmitted timesheets.")
    for ts in timesheets:
        print(f"\n→ Processing Timesheet: {ts.name}")

        if not ts.parent_project:
            print(f"  ⤷ Skipped (No parent_project)")
            continue
        try:
            project = frappe.get_doc("Project", ts.parent_project)

            if project.day_of_the_week not in allowed_days:
                print(f"  ⤷ Skipped (Project day {project.day_of_the_week} not in {allowed_days})")
                continue

            email_list = project.get("timesheet_email_list")

            if not email_list:
                print(f"  ⤷ Skipped (No email list in project {ts.parent_project})")
                continue

            attachment = frappe.attach_print(
                doctype="Timesheet",
                name=ts.name,
                print_format="Weekly Timesheet",
                file_name=f"{ts.name}.pdf"
            )
            employee_doc = frappe.get_doc("Employee", ts.employee)
            employee_name = employee_doc.employee_name
            logo_url = frappe.utils.get_url("/files/Company Logo.JPG")
            start_date_formatted = frappe.utils.formatdate(ts.custom_monday_date, "dd-MMM-yyyy")
            end_date_formatted = frappe.utils.formatdate(ts.custom_sunday_date, "dd-MMM-yyyy")
            frappe.sendmail(
                recipients=[email.strip() for email in email_list.split(",")],
                bcc=["sean@minesitesupport.com.au", "jess@minesitesupport.com.au", "enquiries@minesitesupport.com.au"],
                reply_to="enquiries@minesitesupport.com.au",
                subject=f"Timesheet for {employee_name} - {ts.project_name}",
                message = f"""
                <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4; padding: 20px;">
                <tr>
                    <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; padding: 40px; border-radius: 6px;">
                        <tr>
                        <td align="center" style="padding-bottom: 30px;">
                            <img src="{logo_url}" alt="Mine Site Support" style="max-width: 150px; height: auto;">
                        </td>
                        </tr>
                        <tr>
                        <td style="font-family: sans-serif; font-size: 14px; color: #333;">
                            <p>Hi there,</p>
                            <p>Please find attached the weekly timesheet for <strong>{employee_name}</strong>:</p>
                            <p><strong>Project:</strong> {ts.project_name}</p>
                            <p><strong>Role:</strong> {ts.role}</p>
                            <p><strong>Week Range:</strong> {start_date_formatted} → {end_date_formatted}</p>
                            <p><strong>Total Hours:</strong> {ts.total_hours} Hours</p>
                            <p>We kindly ask that you review and approve the timesheet at your earliest convenience. Once approved, please <b>reply directly to this email</b>.</p>
                            <p>Alternatively, to sign digitally, please <b><a href="https://dashboard.minesitesupport.com.au/sign-timesheet?name={ts.name}"> Click Here</b>.</a></p>
                            <p>If you have any questions or concerns, please reach out to our site team.</p>
                            <p>Kind Regards,<br><strong>Mine Site Support</strong></p>
                        </td>
                        </tr>
                    </table>

                    <table width="600" cellpadding="0" cellspacing="0" style="padding-top: 10px;">
                        <tr>
                        <td align="center" style="font-family: sans-serif; font-size: 11px; color: #888;">
                            <p>
                            This email was sent via <a href="https://webwire.com.au"><strong>Verto ERP</strong></a><br>
                            </p>
                        </td>
                        </tr>
                    </table>
                    </td>
                </tr>
                </table>
                """,
                delayed=False,
                attachments=[attachment]
            )
            time.sleep(1)  # Sleep to avoid overwhelming the email server
            print(f"  ✅ Sent to: {email_list}")
            # Only submit after successful send
            doc = frappe.get_doc("Timesheet", ts.name)
            doc.submit()
            frappe.db.commit()
            print(f"  📋 Submitted Timesheet: {ts.name}")
        except Exception as e:
            print(f"  ❌ Error on {ts.name}: {str(e)}")
            frappe.log_error(f"Failed to send Timesheet {ts.name}", str(e))

def send_weekly_timesheet_verification():
    start_date, end_date, allowed_days = get_timesheet_date_range()
    print(f"\n[Timesheet Emailer] Running for: {start_date} → {end_date}")

    timesheets = frappe.get_all("Timesheet",
        filters={
            "docstatus": 0,
            "custom_monday_date": ["=", start_date],
            "custom_sunday_date": ["=", end_date],
        },
        fields=["name", "employee", "parent_project", "project_name", "total_hours", "role","custom_monday_date", "custom_sunday_date"]
    )
    print(f"[Timesheet Emailer] Found {len(timesheets)} unsubmitted timesheets.")
    for ts in timesheets:
        print(f"\n→ Processing Timesheet: {ts.name}")
        if not ts.parent_project:
            print(f"  ⤷ Skipped (No parent_project)")
            continue
        try:
            project = frappe.get_doc("Project", ts.parent_project)
            if project.day_of_the_week not in allowed_days:
                print(f"  ⤷ Skipped (Project day {project.day_of_the_week} not in {allowed_days})")
                continue
         
            attachment = frappe.attach_print(
                doctype="Timesheet",
                name=ts.name,
                print_format="Weekly Timesheet",
                file_name=f"{ts.name}.pdf"
            )
            employee_doc = frappe.get_doc("Employee", ts.employee)
            employee_name = employee_doc.employee_name
            logo_url = frappe.utils.get_url("/files/Company Logo.JPG")
            start_date_formatted = frappe.utils.formatdate(ts.custom_monday_date, "dd-MMM-yyyy")
            end_date_formatted = frappe.utils.formatdate(ts.custom_sunday_date, "dd-MMM-yyyy")
            frappe.sendmail(
                recipients=["sean@minesitesupport.com.au", "jess@minesitesupport.com.au", "enquiries@minesitesupport.com.au"],
                reply_to="enquiries@minesitesupport.com.au",
                subject=f"Timesheet for {employee_name} - {ts.project_name}",
                message = f"""
                <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4; padding: 20px;">
                <tr>
                    <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; padding: 40px; border-radius: 6px;">
                        <tr>
                        <td align="center" style="padding-bottom: 30px;">
                            <img src="{logo_url}" alt="Mine Site Support" style="max-width: 150px; height: auto;">
                        </td>
                        </tr>
                        <tr>
                        <td style="font-family: sans-serif; font-size: 14px; color: #333;">
                            <p>Hi there,</p>
                            <p>Please find attached the weekly timesheet for <strong>{employee_name}</strong> for verification:</p>
                            <p><strong>Project:</strong> {ts.project_name}</p>
                            <p><strong>Role:</strong> {ts.role}</p>
                            <p><strong>Week Range:</strong> {start_date_formatted} → {end_date_formatted}</p>
                            <p><strong>Total Hours:</strong> {ts.total_hours} Hours</p>                            
                            <p>Kind Regards,<br><strong>Mine Site Support</strong></p>
                        </td>
                        </tr>
                    </table>

                    <table width="600" cellpadding="0" cellspacing="0" style="padding-top: 10px;">
                        <tr>
                        <td align="center" style="font-family: sans-serif; font-size: 11px; color: #888;">
                            <p>
                            This email was sent via <a href="https://webwire.com.au"><strong>Verto ERP</strong></a><br>
                            </p>
                        </td>
                        </tr>
                    </table>
                    </td>
                </tr>
                </table>
                """,
                delayed=False,
                attachments=[attachment]
            )
            time.sleep(1)  # Sleep to avoid overwhelming the email server
            print(f"  ✅ Email verification Sent.")
        except Exception as e:
            print(f"  ❌ Error on {ts.name}: {str(e)}")
            frappe.log_error(f"Failed to send Timesheet {ts.name}", str(e))