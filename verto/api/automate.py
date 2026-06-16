import frappe
from frappe.utils import add_days, nowdate, getdate
from urllib.parse import urlencode
import datetime
import time
import re
import html


SETTINGS_DOCTYPE = "Verto Mobile Settings"

DEFAULT_FOOTER_HTML = """
<p>Kind Regards,<br><strong>Mine Site Support</strong></p>

<table width="100%" cellpadding="0" cellspacing="0" style="padding-top: 10px;">
    <tr>
        <td align="center" style="font-family: sans-serif; font-size: 11px; color: #888;">
            <p>
                This email was sent via
                <a href="https://webwire.com.au"><strong>Verto ERP</strong></a>
            </p>
        </td>
    </tr>
</table>
"""


def get_timesheet_signing_url(timesheet_name):
    return frappe.utils.get_url(
        f"/sign-timesheet?{urlencode({'name': timesheet_name})}"
    )


def split_email_list(value):
    """
    Converts a comma / semicolon / newline separated Data field into a clean list
    that can be passed directly into frappe.sendmail.
    """
    if not value:
        return []

    if isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = re.split(r"[,;\n\r]+", str(value))

    emails = []
    seen = set()

    for raw_email in raw_values:
        email = str(raw_email).strip()
        if not email:
            continue

        email_key = email.lower()
        if email_key in seen:
            continue

        emails.append(email)
        seen.add(email_key)

    return emails


def get_default_email_alt_text():
    """
    Fallback label used when Verto Mobile Settings.image_alt_text is blank.
    """
    return (
        frappe.defaults.get_global_default("company")
        or frappe.local.site
        or "Verto"
    )


def get_verto_mobile_email_settings():
    """
    Pulls reusable email settings from the Verto Mobile Settings Single DocType.

    Expected fields:
    - email_header_image: Attach/Image field for the email header logo
    - image_alt_text: alt text/title for the email header image
    - bcc_email_list: comma / semicolon / newline separated email list
    - email_recipients: comma / semicolon / newline separated default recipient list
    - reply_to_email: single reply-to email address
    - footer_html: HTML editor content for the email footer
    """
    settings = frappe._dict({
        "email_header_image": None,
        "image_alt_text": get_default_email_alt_text(),
        "bcc_email_list": [],
        "email_recipients": [],
        "reply_to_email": None,
        "footer_html": DEFAULT_FOOTER_HTML,
    })

    try:
        doc = frappe.get_single(SETTINGS_DOCTYPE)
    except Exception:
        frappe.log_error(
            title="Verto Mobile Settings not available",
            message=frappe.get_traceback(),
        )
        return settings

    email_header_image = (doc.get("email_header_image") or "").strip()
    settings.email_header_image = (
        frappe.utils.get_url(email_header_image)
        if email_header_image
        else None
    )

    image_alt_text = (doc.get("image_alt_text") or "").strip()
    settings.image_alt_text = image_alt_text or get_default_email_alt_text()

    settings.bcc_email_list = split_email_list(doc.get("bcc_email_list"))
    settings.email_recipients = split_email_list(doc.get("email_recipients"))

    reply_to_email = (doc.get("reply_to_email") or "").strip()
    settings.reply_to_email = reply_to_email or None

    footer_html = (doc.get("footer_html") or "").strip()
    settings.footer_html = footer_html or DEFAULT_FOOTER_HTML

    return settings


def get_sendmail_options(email_settings):
    """
    Builds optional sendmail kwargs only when the setting has a value.
    This avoids passing blank BCC / Reply-To values into Frappe.
    """
    options = {}

    if email_settings.bcc_email_list:
        options["bcc"] = email_settings.bcc_email_list

    if email_settings.reply_to_email:
        options["reply_to"] = email_settings.reply_to_email

    return options


def get_project_or_default_recipients(project, email_settings):
    """
    Client-facing timesheets still prefer the Project's timesheet_email_list.
    If the project has no list, fall back to Verto Mobile Settings.email_recipients.
    """
    project_recipients = split_email_list(project.get("timesheet_email_list"))
    return project_recipients or email_settings.email_recipients


def log_missing_recipients(ts, source):
    frappe.log_error(
        title="Timesheet email skipped - no recipients",
        message=(
            f"No email recipients were found for Timesheet {ts.name}. "
            f"Source checked: {source}. "
            f"Add emails to Project.timesheet_email_list or "
            f"{SETTINGS_DOCTYPE}.email_recipients."
        ),
    )


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
    name_parts = re.split(r"\s+", employee_doc.employee_name.strip())

    if len(name_parts) >= 2:
        return name_parts[0][0], " ".join(name_parts[1:])

    return (
        employee_doc.employee_name[0],
        employee_doc.employee_name[1:] if len(employee_doc.employee_name) > 1 else "",
    )


def generate_attachment_name(ts, employee_doc, include_project=False):
    first_initial, last_name = get_employee_name_parts(employee_doc)
    attach_date_str = str(ts.custom_sunday_date).replace("-", "")

    if include_project:
        return (
            f"{attach_date_str}_{ts.project_name}_"
            f"{ts.customer_abbreviation}_MSS_{first_initial}_{last_name}"
        )

    return f"{attach_date_str}_{first_initial}_{last_name}"


def generate_attachment(ts, file_name):
    return frappe.attach_print(
        doctype="Timesheet",
        name=ts.name,
        print_format="Weekly Timesheet",
        file_name=file_name,
    )


def format_date_range(ts):
    return (
        frappe.utils.formatdate(ts.custom_monday_date, "dd-MMM-yyyy"),
        frappe.utils.formatdate(ts.custom_sunday_date, "dd-MMM-yyyy"),
    )


def build_email_header_html(email_settings):
    """
    Builds the email header branding safely.

    If no image is configured, it falls back to text instead of rendering:
    <img src="None" alt="None">
    """
    image_alt_text = html.escape(email_settings.image_alt_text or "Verto", quote=True)

    if email_settings.email_header_image:
        image_url = html.escape(email_settings.email_header_image, quote=True)
        return (
            f'<img src="{image_url}" '
            f'alt="{image_alt_text}" '
            f'width="150" '
            f'style="width: 150px; max-width: 100%; height: auto; display: block;">'
        )

    return (
        f'<h2 style="font-family: sans-serif; color: #333; margin: 0;">'
        f'{image_alt_text}'
        f'</h2>'
    )


def build_email_body(content_html, email_settings=None):
    if email_settings is None:
        email_settings = get_verto_mobile_email_settings()

    footer_html = email_settings.footer_html or DEFAULT_FOOTER_HTML
    header_html = build_email_header_html(email_settings)

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4; padding: 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; padding: 40px; border-radius: 6px;">
                    <tr>
                        <td align="center" style="padding-bottom: 30px;">
                            {header_html}
                        </td>
                    </tr>
                    <tr>
                        <td style="font-family: sans-serif; font-size: 14px; color: #333;">
                            <p>Hi there,</p>
                            {content_html}
                            {footer_html}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
    """


@frappe.whitelist()
def send_weekly_timesheets(timesheet_name=None):
    email_settings = get_verto_mobile_email_settings()
    sendmail_options = get_sendmail_options(email_settings)

    start_date, end_date, allowed_days = get_timesheet_date_range()
    timesheets = []

    if timesheet_name:
        print(f"\n[Timesheet Follow-up] Forcing Timesheet email for: {timesheet_name}")
        ts = frappe.get_doc("Timesheet", timesheet_name)

        if not ts.parent_project:
            return

        timesheets = [ts]
    else:
        timesheets = frappe.get_all(
            "Timesheet",
            filters={
                "docstatus": 0,
                "custom_monday_date": ["=", start_date],
                "custom_sunday_date": ["=", end_date],
            },
            fields=[
                "name",
                "employee",
                "parent_project",
                "project_name",
                "total_hours",
                "role",
                "custom_monday_date",
                "custom_sunday_date",
                "customer_abbreviation",
            ],
        )

    for ts in timesheets:
        if not ts.parent_project:
            continue

        try:
            project = frappe.get_doc("Project", ts.parent_project)

            if project.day_of_the_week not in allowed_days:
                continue

            recipients = get_project_or_default_recipients(project, email_settings)

            if not recipients:
                log_missing_recipients(
                    ts,
                    "Project.timesheet_email_list and Verto Mobile Settings.email_recipients",
                )
                continue

            employee_doc = get_employee_doc(ts)
            employee_name = employee_doc.employee_name
            file_name = generate_attachment_name(ts, employee_doc, include_project=True)
            attachment = generate_attachment(ts, file_name)
            start_fmt, end_fmt = format_date_range(ts)
            signing_url = get_timesheet_signing_url(ts.name)

            content_html = f"""
                <p>Please find attached the weekly timesheet for <strong>{employee_name}</strong>:</p>
                <p><strong>Project:</strong> {ts.project_name}</p>
                <p><strong>Role:</strong> {ts.role}</p>
                <p><strong>Week Range:</strong> {start_fmt} → {end_fmt}</p>
                <p><strong>Total Hours:</strong> {ts.total_hours} Hours</p>
                <p>We kindly ask that you review and approve the timesheet at your earliest convenience. Once approved, please <b>reply directly to this email</b>.</p>
                <p>Alternatively, to sign digitally, please <b><a href="{signing_url}"> Click Here</a></b>.</p>
                <p>If you have any questions or concerns, please reach out to our site team.</p>
            """

            frappe.sendmail(
                recipients=recipients,
                subject=f"Timesheet for {employee_name} - {ts.project_name}",
                message=build_email_body(content_html, email_settings),
                delayed=False,
                attachments=[attachment],
                **sendmail_options,
            )

            time.sleep(1)

            doc = frappe.get_doc("Timesheet", ts.name)
            doc.submit()
            frappe.db.commit()

        except Exception:
            frappe.log_error(
                title=f"Failed to send Timesheet {ts.name}",
                message=frappe.get_traceback(),
            )


def send_weekly_timesheet_verification():
    email_settings = get_verto_mobile_email_settings()
    sendmail_options = get_sendmail_options(email_settings)

    if not email_settings.email_recipients:
        frappe.log_error(
            title="Timesheet verification skipped - no recipients",
            message=(
                f"No recipients are configured in "
                f"{SETTINGS_DOCTYPE}.email_recipients."
            ),
        )
        return

    start_date, end_date, allowed_days = get_timesheet_date_range()

    timesheets = frappe.get_all(
        "Timesheet",
        filters={
            "docstatus": 0,
            "custom_monday_date": ["=", start_date],
            "custom_sunday_date": ["=", end_date],
        },
        fields=[
            "name",
            "employee",
            "parent_project",
            "project_name",
            "total_hours",
            "role",
            "custom_monday_date",
            "custom_sunday_date",
            "customer_abbreviation",
        ],
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
                recipients=email_settings.email_recipients,
                subject=f"Timesheet for {employee_name} - {ts.project_name}",
                message=build_email_body(content_html, email_settings),
                delayed=False,
                attachments=[attachment],
                **sendmail_options,
            )

            time.sleep(1)

        except Exception:
            frappe.log_error(
                title=f"Failed to send Timesheet {ts.name}",
                message=frappe.get_traceback(),
            )


def send_timesheet_followup_reminders(timesheet_name=None):
    email_settings = get_verto_mobile_email_settings()
    sendmail_options = get_sendmail_options(email_settings)

    start_date, end_date, allowed_days = get_timesheet_date_range()
    timesheets = []

    if timesheet_name:
        print(f"\n[Timesheet Follow-up] Forcing reminder for: {timesheet_name}")
        ts = frappe.get_doc("Timesheet", timesheet_name)

        if not ts.parent_project:
            return

        timesheets = [ts]
    else:
        print(f"\n[Timesheet Follow-up] Checking for unsigned timesheets from: {start_date} → {end_date}")

        timesheets = frappe.get_all(
            "Timesheet",
            filters={
                "docstatus": 1,
                "custom_client_signed": 0,
                "custom_monday_date": ["=", start_date],
                "custom_sunday_date": ["=", end_date],
            },
            fields=[
                "name",
                "employee",
                "parent_project",
                "project_name",
                "total_hours",
                "role",
                "custom_monday_date",
                "custom_sunday_date",
                "customer_abbreviation",
            ],
        )

    for ts in timesheets:
        try:
            if not ts.parent_project:
                continue

            project = frappe.get_doc("Project", ts.parent_project)

            if project.day_of_the_week not in allowed_days:
                continue

            recipients = get_project_or_default_recipients(project, email_settings)

            if not recipients:
                log_missing_recipients(
                    ts,
                    "Project.timesheet_email_list and Verto Mobile Settings.email_recipients",
                )
                continue

            employee_doc = get_employee_doc(ts)
            employee_name = employee_doc.employee_name
            file_name = generate_attachment_name(ts, employee_doc, include_project=True)
            attachment = generate_attachment(ts, file_name)
            start_fmt, end_fmt = format_date_range(ts)
            signing_url = get_timesheet_signing_url(ts.name)

            content_html = f"""
                <p>This is a friendly reminder to sign the weekly timesheet for <strong>{employee_name}</strong>.</p>
                <p><strong>Project:</strong> {ts.project_name}</p>
                <p><strong>Week Range:</strong> {start_fmt} → {end_fmt}</p>
                <p><strong>Total Hours:</strong> {ts.total_hours} Hours</p>
                <p>To sign the timesheet digitally, please click below:</p>
                <p><b><a href="{signing_url}">Click Here to Sign</a></b></p>
                <p>Thank you and please reach out if you need any assistance.</p>
            """

            frappe.sendmail(
                recipients=recipients,
                subject=f"[Reminder] Timesheet Pending Signature for {employee_name} - {ts.project_name}",
                message=build_email_body(content_html, email_settings),
                delayed=False,
                attachments=[attachment],
                **sendmail_options,
            )

            time.sleep(1)

        except Exception:
            frappe.log_error(
                title=f"Follow-up send failed for {ts.name}",
                message=frappe.get_traceback(),
            )
