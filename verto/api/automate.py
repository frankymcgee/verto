import frappe
from frappe.utils import add_days, cint, flt, nowdate, getdate
from urllib.parse import urlencode
import base64
import binascii
import datetime
import hashlib
import hmac
import time
import re
import html
import json


SETTINGS_DOCTYPE = "Verto Mobile Settings"

GROUPED_TIMESHEET_ROUTE = "/weekly-timesheet-approval"
GROUPED_TIMESHEET_TOKEN_SALT = "verto-grouped-weekly-timesheet-approval-v1"
MAX_GROUPED_TIMESHEETS = 200

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


# -----------------------------------------------------------------------------
# Grouped weekly timesheet approval pilot
#
# These functions are intentionally separate from the existing individual
# timesheet email and reminder functions above. Nothing in the original workflow
# calls these functions automatically. This allows the grouped workflow to be
# tested before changing any scheduler hooks or List View actions.
# -----------------------------------------------------------------------------


def get_grouped_timesheet_secret():
    """Return the site-specific secret used for grouped approval links."""
    encryption_key = frappe.local.conf.get("encryption_key")

    if not encryption_key:
        frappe.throw(
            "The site encryption_key is not configured, so a secure grouped "
            "timesheet approval link cannot be generated."
        )

    return (
        f"{GROUPED_TIMESHEET_TOKEN_SALT}:{encryption_key}"
    ).encode("utf-8")


def encode_grouped_token_part(value):
    """Encode bytes using URL-safe Base64 without trailing padding."""
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def decode_grouped_token_part(value):
    """Decode a URL-safe Base64 value whose padding was removed."""
    encoded_value = str(value).encode("ascii")
    padding = b"=" * (-len(encoded_value) % 4)
    return base64.urlsafe_b64decode(encoded_value + padding)


def normalise_grouped_timesheet_names(timesheet_names):
    """Normalise a Frappe/JSON list of Timesheet names and remove duplicates."""
    if isinstance(timesheet_names, str):
        try:
            parsed_names = frappe.parse_json(timesheet_names)
        except Exception:
            parsed_names = [timesheet_names]
    else:
        parsed_names = timesheet_names

    if not isinstance(parsed_names, (list, tuple, set)):
        frappe.throw("Timesheet names must be supplied as a list.")

    clean_names = []
    seen = set()

    for value in parsed_names:
        name = str(value or "").strip()
        if not name or name in seen:
            continue
        clean_names.append(name)
        seen.add(name)

    if not clean_names:
        frappe.throw("No Timesheets were supplied for grouped approval.")

    if len(clean_names) > MAX_GROUPED_TIMESHEETS:
        frappe.throw(
            f"A grouped approval can contain no more than "
            f"{MAX_GROUPED_TIMESHEETS} Timesheets."
        )

    return sorted(clean_names)


def create_grouped_timesheet_token(timesheet_names):
    """
    Create a signed token containing the exact Timesheets shown on the page.

    No new DocType or custom batch record is required. Because the list is
    signed with the site's encryption key, a recipient cannot add or replace a
    Timesheet by editing the URL.
    """
    names = normalise_grouped_timesheet_names(timesheet_names)
    payload = json.dumps(
        {"v": 1, "names": names},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded_payload = encode_grouped_token_part(payload)
    signature = hmac.new(
        get_grouped_timesheet_secret(),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()

    return f"{encoded_payload}.{encode_grouped_token_part(signature)}"


def decode_grouped_timesheet_token(token):
    """Validate a grouped approval token and return its Timesheet names."""
    if not token:
        frappe.throw("The grouped timesheet approval link is missing its token.")

    token_value = str(token).strip()

    # Prevent an unnecessarily large public request from reaching JSON parsing.
    if len(token_value) > 24000:
        frappe.throw("This grouped timesheet approval link is invalid.")

    try:
        encoded_payload, encoded_signature = token_value.split(".", 1)
        supplied_signature = decode_grouped_token_part(encoded_signature)
        expected_signature = hmac.new(
            get_grouped_timesheet_secret(),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("Signature mismatch")

        payload = json.loads(
            decode_grouped_token_part(encoded_payload).decode("utf-8")
        )
    except (
        ValueError,
        TypeError,
        UnicodeDecodeError,
        UnicodeEncodeError,
        binascii.Error,
        json.JSONDecodeError,
    ):
        frappe.throw("This grouped timesheet approval link is invalid.")

    if not isinstance(payload, dict) or cint(payload.get("v")) != 1:
        frappe.throw("This grouped timesheet approval link is invalid.")

    return normalise_grouped_timesheet_names(payload.get("names"))


def get_grouped_timesheet_signing_url(timesheet_names):
    token = create_grouped_timesheet_token(timesheet_names)
    return frappe.utils.get_url(
        f"{GROUPED_TIMESHEET_ROUTE}?{urlencode({'token': token})}"
    )


def get_grouped_timesheet_fields():
    return [
        "name",
        "employee",
        "employee_name",
        "parent_project",
        "project_name",
        "total_hours",
        "role",
        "custom_monday_date",
        "custom_sunday_date",
        "customer_abbreviation",
        "custom_client_signed",
        "docstatus",
    ]


def get_grouped_timesheet_candidates(
    project_id=None,
    docstatus=0,
    only_unsigned=False,
    include_draft_and_submitted=False,
):
    """
    For a manual project test, use the latest available week for that project.
    Otherwise, get every candidate in the normal scheduled date range.
    """
    if project_id:
        # Validate the supplied Project ID before looking for its Timesheets.
        frappe.get_doc("Project", project_id)

        allowed_docstatuses = (
            [0, 1]
            if include_draft_and_submitted
            else [cint(docstatus)]
        )
        latest_filters = {
            "parent_project": project_id,
            "docstatus": ["in", allowed_docstatuses],
        }

        if only_unsigned:
            latest_filters["custom_client_signed"] = 0

        latest_week = frappe.get_all(
            "Timesheet",
            filters=latest_filters,
            fields=[
                "custom_monday_date",
                "custom_sunday_date",
            ],
            order_by="custom_monday_date desc, modified desc",
            limit=1,
        )

        if not latest_week:
            status_description = (
                "Draft or Submitted"
                if include_draft_and_submitted
                else ("Draft" if cint(docstatus) == 0 else "Submitted")
            )
            signature_description = "unsigned " if only_unsigned else ""
            frappe.throw(
                f"No {signature_description}{status_description} Timesheets were found for "
                f"Project {project_id}."
            )

        week = latest_week[0]
        if not week.custom_monday_date or not week.custom_sunday_date:
            frappe.throw(
                f"The latest Timesheet week for Project {project_id} is missing "
                "its Monday or Sunday date."
            )

        filters = {
            "parent_project": project_id,
            "custom_monday_date": week.custom_monday_date,
            "custom_sunday_date": week.custom_sunday_date,
            "docstatus": ["in", allowed_docstatuses],
        }
    else:
        start_date, end_date, _allowed_days = get_timesheet_date_range()
        filters = {
            "custom_monday_date": start_date,
            "custom_sunday_date": end_date,
            "docstatus": docstatus,
        }

    if only_unsigned:
        filters["custom_client_signed"] = 0

    return frappe.get_all(
        "Timesheet",
        filters=filters,
        fields=get_grouped_timesheet_fields(),
        order_by="parent_project asc, employee_name asc, employee asc",
    )


def group_timesheets_by_project_and_week(timesheets):
    groups = {}

    for ts in timesheets:
        if not ts.parent_project:
            continue

        key = (
            ts.parent_project,
            str(ts.custom_monday_date),
            str(ts.custom_sunday_date),
        )
        groups.setdefault(key, []).append(ts)

    return groups


def get_grouped_week_summary(timesheets):
    first = timesheets[0]
    employee_count = len({ts.employee for ts in timesheets if ts.employee})
    total_hours = sum(flt(ts.total_hours) for ts in timesheets)
    start_fmt, end_fmt = format_date_range(first)

    return frappe._dict({
        "employee_count": employee_count,
        "total_hours": flt(total_hours, 2),
        "start_fmt": start_fmt,
        "end_fmt": end_fmt,
    })


def submit_grouped_timesheets(timesheets):
    """
    Submit Draft Timesheets and allow already Submitted Timesheets through.

    Cancelled Timesheets are never included in a grouped approval.
    """
    for ts in timesheets:
        doc = frappe.get_doc("Timesheet", ts.name)
        current_status = cint(doc.docstatus)

        if current_status == 0:
            doc.submit()
            continue

        if current_status == 1:
            continue

        if current_status == 2:
            frappe.throw(
                f"Timesheet {doc.name} is Cancelled and cannot be included."
            )

        frappe.throw(
            f"Timesheet {doc.name} has an unsupported document status."
        )


@frappe.whitelist()
def send_grouped_weekly_timesheets(project_id=None):
    """
    Send one grouped approval email for each project/week.

    Passing a Project ID is the recommended pilot/test action. The function
    selects that project's latest week and includes every Draft or Submitted
    Timesheet, regardless of its existing client signature status. It also
    bypasses the scheduled day-of-week check. Draft Timesheets are submitted
    before the email is sent; Submitted Timesheets are included without being
    changed. Calling the function without a Project ID keeps the existing
    scheduler date/day behaviour.
    """
    email_settings = get_verto_mobile_email_settings()
    sendmail_options = get_sendmail_options(email_settings)
    _start_date, _end_date, allowed_days = get_timesheet_date_range()
    is_manual_test = bool(project_id)

    candidates = get_grouped_timesheet_candidates(
        project_id=project_id,
        docstatus=0,
        only_unsigned=not is_manual_test,
        include_draft_and_submitted=is_manual_test,
    )
    groups = group_timesheets_by_project_and_week(candidates)
    results = []

    for (project_name, _monday, _sunday), timesheets in groups.items():
        savepoint_name = "before_grouped_timesheet_send"

        try:
            project = frappe.get_doc("Project", project_name)

            if not is_manual_test and project.day_of_the_week not in allowed_days:
                results.append({
                    "project": project_name,
                    "status": "Skipped",
                    "reason": "Project email day does not match this run.",
                })
                continue

            recipients = get_project_or_default_recipients(project, email_settings)

            if not recipients:
                log_missing_recipients(
                    timesheets[0],
                    "Project.timesheet_email_list and "
                    "Verto Mobile Settings.email_recipients",
                )
                results.append({
                    "project": project_name,
                    "status": "Skipped",
                    "reason": "No email recipients are configured.",
                })
                continue

            names = [ts.name for ts in timesheets]
            summary = get_grouped_week_summary(timesheets)
            signing_url = get_grouped_timesheet_signing_url(names)
            raw_project = (
                timesheets[0].project_name or project.project_name or project.name
            )
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

            # Keep the source Timesheets immutable while the client reviews them.
            # A savepoint lets us return them to Draft if the email send fails.
            frappe.db.savepoint(savepoint_name)
            submit_grouped_timesheets(timesheets)

            frappe.sendmail(
                recipients=recipients,
                subject=(
                    f"Weekly Timesheet Approval - {raw_project} - "
                    f"{summary.start_fmt} to {summary.end_fmt}"
                ),
                message=build_email_body(content_html, email_settings),
                delayed=False,
                **sendmail_options,
            )

            frappe.db.commit()
            results.append({
                "project": project_name,
                "status": "Sent",
                "timesheet_count": len(names),
                "employee_count": summary.employee_count,
                "total_hours": summary.total_hours,
            })
            time.sleep(1)

        except Exception:
            try:
                frappe.db.rollback(save_point=savepoint_name)
            except Exception:
                frappe.db.rollback()

            frappe.log_error(
                title=f"Grouped Timesheet email failed for {project_name}",
                message=frappe.get_traceback(),
            )
            results.append({
                "project": project_name,
                "status": "Failed",
                "reason": "See Error Log for details.",
            })

    return {
        "groups_found": len(groups),
        "results": results,
    }


@frappe.whitelist()
def send_grouped_timesheet_followup_reminders(project_id=None):
    """
    Send one reminder for each unsigned grouped project/week.

    Keep this method out of scheduler hooks during the pilot. Passing a Project
    ID finds and reminds its latest submitted, unsigned Timesheet week.
    """
    email_settings = get_verto_mobile_email_settings()
    sendmail_options = get_sendmail_options(email_settings)
    _start_date, _end_date, allowed_days = get_timesheet_date_range()
    is_manual_test = bool(project_id)

    candidates = get_grouped_timesheet_candidates(
        project_id=project_id,
        docstatus=1,
        only_unsigned=True,
    )
    groups = group_timesheets_by_project_and_week(candidates)
    results = []

    for (project_name, _monday, _sunday), timesheets in groups.items():
        try:
            project = frappe.get_doc("Project", project_name)

            if not is_manual_test and project.day_of_the_week not in allowed_days:
                continue

            recipients = get_project_or_default_recipients(project, email_settings)
            if not recipients:
                log_missing_recipients(
                    timesheets[0],
                    "Project.timesheet_email_list and "
                    "Verto Mobile Settings.email_recipients",
                )
                continue

            names = [ts.name for ts in timesheets]
            summary = get_grouped_week_summary(timesheets)
            signing_url = get_grouped_timesheet_signing_url(names)
            raw_project = (
                timesheets[0].project_name or project.project_name or project.name
            )
            display_project = html.escape(raw_project)

            content_html = f"""
                <p>This is a friendly reminder to review and sign the consolidated
                weekly timesheets for <strong>{display_project}</strong>.</p>
                <p><strong>Week Range:</strong>
                {summary.start_fmt} &rarr; {summary.end_fmt}</p>
                <p><strong>Employees Awaiting Approval:</strong>
                {summary.employee_count}</p>
                <p><strong>Total Hours Awaiting Approval:</strong>
                {summary.total_hours} Hours</p>
                <p><b><a href="{signing_url}">Click Here to Review and Sign</a></b></p>
            """

            frappe.sendmail(
                recipients=recipients,
                subject=(
                    f"[Reminder] Weekly Timesheet Approval - {raw_project} - "
                    f"{summary.start_fmt} to {summary.end_fmt}"
                ),
                message=build_email_body(content_html, email_settings),
                delayed=False,
                **sendmail_options,
            )

            results.append({
                "project": project_name,
                "status": "Sent",
                "timesheet_count": len(names),
            })
            time.sleep(1)

        except Exception:
            frappe.log_error(
                title=f"Grouped Timesheet reminder failed for {project_name}",
                message=frappe.get_traceback(),
            )
            results.append({
                "project": project_name,
                "status": "Failed",
                "reason": "See Error Log for details.",
            })

    return {
        "groups_found": len(groups),
        "results": results,
    }
