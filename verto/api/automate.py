import frappe
from frappe.utils import add_days, nowdate, getdate
import datetime
import time
import re 

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

def get_employee_doc(ts):
    return frappe.get_doc("Employee", ts.employee)

def get_employee_name_parts(employee_doc):
    name_parts = re.split(r'\s+', employee_doc.employee_name.strip())
    if len(name_parts) >= 2:
        return name_parts[0][0], " ".join(name_parts[1:])
    return employee_doc.employee_name[0], employee_doc.employee_name[1:] if len(employee_doc.employee_name) > 1 else ""

def generate_attachment_name(ts, employee_doc, include_project=False):
    first_initial, last_name = get_employee_name_parts(employee_doc)
    attach_date_str = str(ts.custom_sunday_date).replace("-", "")
    if include_project:
        return f"{attach_date_str}_{ts.project_name}_{ts.customer_abbreviation}_MSS_{first_initial}_{last_name}"
    return f"{attach_date_str}_{first_initial}_{last_name}"

def generate_attachment(ts, file_name):
    return frappe.attach_print(
        doctype="Timesheet",
        name=ts.name,
        print_format="Weekly Timesheet",
        file_name=file_name
    )

def format_date_range(ts):
    return (
        frappe.utils.formatdate(ts.custom_monday_date, "dd-MMM-yyyy"),
        frappe.utils.formatdate(ts.custom_sunday_date, "dd-MMM-yyyy")
    )

def build_email_body(content_html):
    footer_html = """
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
    """
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4; padding: 20px;">
    <tr>
        <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; padding: 40px; border-radius: 6px;">
            <tr>
            <td align="center" style="padding-bottom: 30px;">
                <img src="{frappe.utils.get_url("/files/Company Logo.JPG")}" alt="Mine Site Support" style="max-width: 150px; height: auto;">
            </td>
            </tr>
            <tr>
            <td style="font-family: sans-serif; font-size: 14px; color: #333;">
                <p>Hi there,</p>
                {content_html}
                {footer_html}
    """

@frappe.whitelist()
def send_weekly_timesheets(timesheet_name=None):
    start_date, end_date, allowed_days = get_timesheet_date_range()
    timesheets = []
    if timesheet_name:
        print(f"\n[Timesheet Follow-up] Forcing Timesheet email for: {timesheet_name}")
        ts = frappe.get_doc("Timesheet", timesheet_name)
        if not ts.parent_project:
            return
        timesheets = [ts]
    else:
        timesheets = frappe.get_all("Timesheet",
            filters={
                "docstatus": 0,
                "custom_monday_date": ["=", start_date],
                "custom_sunday_date": ["=", end_date],
            },
            fields=["name", "employee", "parent_project", "project_name", "total_hours", "role","custom_monday_date", "custom_sunday_date", "customer_abbreviation"]
        )
    for ts in timesheets:
        if not ts.parent_project:
            continue
        try:
            project = frappe.get_doc("Project", ts.parent_project)
            if project.day_of_the_week not in allowed_days:
                continue
            email_list = project.get("timesheet_email_list")
            if not email_list:
                continue
            
            employee_doc = get_employee_doc(ts)
            employee_name = employee_doc.employee_name
            file_name = generate_attachment_name(ts, employee_doc, include_project=True)
            attachment = generate_attachment(ts, file_name)
            start_fmt, end_fmt = format_date_range(ts)

            content_html = f"""                
                <p>Please find attached the weekly timesheet for <strong>{employee_name}</strong>:</p>
                <p><strong>Project:</strong> {ts.project_name}</p>
                <p><strong>Role:</strong> {ts.role}</p>
                <p><strong>Week Range:</strong> {start_fmt} → {end_fmt}</p>
                <p><strong>Total Hours:</strong> {ts.total_hours} Hours</p>
                <p>We kindly ask that you review and approve the timesheet at your earliest convenience. Once approved, please <b>reply directly to this email</b>.</p>
                <p>Alternatively, to sign digitally, please <b><a href="https://dashboard.minesitesupport.com.au/sign-timesheet?name={ts.name}"> Click Here</b>.</a></p>
                <p>If you have any questions or concerns, please reach out to our site team.</p>
                """
            frappe.sendmail(
                recipients=[email.strip() for email in email_list.split(",")],
                bcc=["enquiries@minesitesupport.com.au"],
                reply_to="enquiries@minesitesupport.com.au",
                subject=f"Timesheet for {employee_name} - {ts.project_name}",
                message=build_email_body(content_html),
                delayed=False,
                attachments=[attachment]
            )
            time.sleep(1)
            doc = frappe.get_doc("Timesheet", ts.name)
            doc.submit()
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Failed to send Timesheet {ts.name}", str(e))

def send_weekly_timesheet_verification():
    start_date, end_date, allowed_days = get_timesheet_date_range()
    timesheets = frappe.get_all("Timesheet",
        filters={
            "docstatus": 0,
            "custom_monday_date": ["=", start_date],
            "custom_sunday_date": ["=", end_date],
        },
        fields=["name", "employee", "parent_project", "project_name", "total_hours", "role", "custom_monday_date", "custom_sunday_date", "customer_abbreviation"]
    )

    for ts in timesheets:
        if not ts.parent_project:
            continue
        try:
            project = frappe.get_doc("Project", ts.parent_project)
            if project.day_of_the_week not in allowed_days:
                continue
         
            employee_doc = get_employee_doc(ts)
            employee_name = employee_doc.employee_name
            file_name = generate_attachment_name(ts, employee_doc, include_project=True)
            attachment = generate_attachment(ts, file_name)
            start_fmt, end_fmt = format_date_range(ts)

            content_html = f"""
                <p>Please find attached the weekly timesheet for <strong>{employee_name}</strong> for verification:</p>
                <p><strong>Project:</strong> {ts.project_name}</p>
                <p><strong>Role:</strong> {ts.role}</p>
                <p><strong>Week Range:</strong> {start_fmt} → {end_fmt}</p>
                <p><strong>Total Hours:</strong> {ts.total_hours} Hours</p>
                """
            frappe.sendmail(
                recipients=["enquiries@minesitesupport.com.au"],
                reply_to="enquiries@minesitesupport.com.au",
                subject=f"Timesheet for {employee_name} - {ts.project_name}",
                message=build_email_body(content_html),
                delayed=False,
                attachments=[attachment]
            )
            time.sleep(1)
        except Exception as e:
            frappe.log_error(f"Failed to send Timesheet {ts.name}", str(e))

def send_timesheet_followup_reminders(timesheet_name=None):
    start_date, end_date, allowed_days = get_timesheet_date_range()
    timesheets = []
    bcc_recipients = []

    if timesheet_name:
        print(f"\n[Timesheet Follow-up] Forcing reminder for: {timesheet_name}")
        ts = frappe.get_doc("Timesheet", timesheet_name)
        if not ts.parent_project:
            return
        timesheets = [ts]
        bcc_recipients = ["sean@minesitesupport.com.au"]
    else:
        print(f"\n[Timesheet Follow-up] Checking for unsigned timesheets from: {start_date} → {end_date}")
        timesheets = frappe.get_all("Timesheet", filters={
            "docstatus": 1,
            "custom_client_signed": 0,
            "custom_monday_date": ["=", start_date],
            "custom_sunday_date": ["=", end_date],
        }, fields=["name", "employee", "parent_project", "project_name", "total_hours", "role", "custom_monday_date", "custom_sunday_date", "customer_abbreviation"])
        bcc_recipients = ["enquiries@minesitesupport.com.au"]    

    for ts in timesheets:
        try:
            if not ts.parent_project:
                continue
            project = frappe.get_doc("Project", ts.parent_project)
            if project.day_of_the_week not in allowed_days:
                continue
            email_list = project.get("timesheet_email_list")
            if not email_list:
                continue
            
            employee_doc = get_employee_doc(ts)
            employee_name = employee_doc.employee_name
            file_name = generate_attachment_name(ts, employee_doc, include_project=True)
            attachment = generate_attachment(ts, file_name)
            start_fmt, end_fmt = format_date_range(ts)

            content_html = f"""
                <p>This is a friendly reminder to sign the weekly timesheet for <strong>{employee_name}</strong>.</p>
                <p><strong>Project:</strong> {ts.project_name}</p>
                <p><strong>Week Range:</strong> {start_fmt} → {end_fmt}</p>
                <p><strong>Total Hours:</strong> {ts.total_hours} Hours</p>
                <p>To sign the timesheet digitally, please click below:</p>
                <p><b><a href="https://dashboard.minesitesupport.com.au/sign-timesheet?name={ts.name}">Click Here to Sign</a></b></p>
                <p>Thank you and please reach out if you need any assistance.</p>
            """
            frappe.sendmail(
                recipients=[email.strip() for email in email_list.split(",")],
                bcc=bcc_recipients,
                reply_to="enquiries@minesitesupport.com.au",
                subject=f"[Reminder] Timesheet Pending Signature for {employee_name} - {ts.project_name}",
                message=build_email_body(content_html),
                delayed=False,
                attachments=[attachment]
            )
            time.sleep(1)
        except Exception as e:
            frappe.log_error(f"Follow-up send failed for {ts.name}", str(e))