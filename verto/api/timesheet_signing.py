import base64
import binascii
import datetime
import html
import re

import frappe
from frappe.utils import add_days, cint, flt, formatdate, getdate, get_datetime

from verto.api.automate import (
    build_email_body,
    decode_grouped_timesheet_token,
    generate_attachment,
    generate_attachment_name,
    get_employee_doc,
    get_grouped_timesheet_signing_url,
    get_sendmail_options,
    get_verto_mobile_email_settings,
)


MAX_SIGNATURE_BYTES = 1_500_000
DAY_SHIFT_CUTOFF = datetime.time(16, 30)


# -----------------------------------------------------------------------------
# Existing individual Timesheet signing workflow
#
# These methods are intentionally unchanged so the original sign-timesheet page
# and individual email workflow continue to work during the grouped pilot.
# -----------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def sign_timesheet(timesheet_name, signature_base64, full_name=None, date_signed=None):
    if not timesheet_name or not signature_base64:
        frappe.throw("Missing timesheet or signature.")

    ts = frappe.get_doc("Timesheet", timesheet_name)

    if ts.custom_client_signed == 1:
        return "Already signed"

    ts.db_set("custom_client_signature", signature_base64)
    ts.db_set("custom_client_signed", 1)

    if full_name:
        ts.db_set("custom_signed_full_name", full_name)

    if date_signed:
        ts.db_set("custom_date_signed", date_signed)

    frappe.db.commit()

    email_settings = get_verto_mobile_email_settings()
    recipients = email_settings.email_recipients

    # Do not fail the public signing action if notification recipients are not configured.
    # The timesheet has already been signed successfully at this point.
    if not recipients:
        frappe.log_error(
            title="Signed Timesheet email skipped - no recipients",
            message=(
                f"No recipients were configured for signed Timesheet {ts.name}. "
                "Add recipients to Verto Mobile Settings.email_recipients."
            ),
        )
        return "Success"

    employee_doc = get_employee_doc(ts)
    employee_name = employee_doc.employee_name

    file_name = generate_attachment_name(ts, employee_doc, include_project=True)
    attachment = generate_attachment(ts, file_name)

    content_html = f"""
        <p>Please find attached the signed weekly timesheet for <strong>{employee_name}</strong>.</p>
        <p><strong>Project:</strong> {ts.project_name}</p>
        <p>Kind Regards,<br><strong>{frappe.defaults.get_global_default("company") or "Mine Site Support"}</strong></p>
    """

    sendmail_options = get_sendmail_options(email_settings)

    frappe.sendmail(
        recipients=recipients,
        subject=f"Signed Timesheet for {employee_name} - {ts.project_name}",
        message=build_email_body(content_html, email_settings=email_settings),
        delayed=False,
        attachments=[attachment],
        **sendmail_options,
    )

    return "Success"


@frappe.whitelist(allow_guest=True)
def get_timesheet_public(name):
    # Limit fields to avoid leaking sensitive info.
    return frappe.get_value(
        "Timesheet",
        name,
        [
            "employee",
            "employee_name",
            "project_name",
            "total_hours",
            "custom_monday_date",
            "custom_sunday_date",
            "custom_client_signed",
        ],
        as_dict=True,
    )


@frappe.whitelist()
def approve_timesheet_with_signature(timesheet, signature_dataurl, approved_by):
    doc = frappe.get_doc("Timesheet", timesheet)
    doc.internal_approved = 1
    doc.employee_approved = approved_by
    doc.approved_signature = signature_dataurl
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success", "message": f"{timesheet} updated"}


# -----------------------------------------------------------------------------
# Grouped weekly Timesheet signing workflow
# -----------------------------------------------------------------------------


def get_grouped_timesheet_docs(token, require_submitted=True):
    """Resolve and validate the exact Timesheets embedded in a signed token."""
    timesheet_names = decode_grouped_timesheet_token(token)
    docs = [frappe.get_doc("Timesheet", name) for name in timesheet_names]

    if not docs:
        frappe.throw("No Timesheets were found for this approval link.")

    first = docs[0]
    if (
        not first.parent_project
        or not first.custom_monday_date
        or not first.custom_sunday_date
    ):
        frappe.throw("The Timesheets in this approval link are missing project or week details.")

    expected_group = (
        first.parent_project,
        str(first.custom_monday_date),
        str(first.custom_sunday_date),
    )

    for doc in docs:
        if (
            not doc.parent_project
            or not doc.custom_monday_date
            or not doc.custom_sunday_date
        ):
            frappe.throw(
                "The Timesheets in this approval link are missing project or week details."
            )

        current_group = (
            doc.parent_project,
            str(doc.custom_monday_date),
            str(doc.custom_sunday_date),
        )

        if current_group != expected_group:
            frappe.throw(
                "The grouped approval link contains Timesheets from different "
                "projects or weeks."
            )

        if require_submitted and cint(doc.docstatus) != 1:
            frappe.throw(
                f"Timesheet {doc.name} is not submitted and cannot be approved."
            )

    return docs


def get_shift_code(time_log):
    """
    Return DS or NS from the time log's shift value.

    The 16:30 cutoff preserves the existing fallback rule for older time logs
    that do not contain shift_type.
    """
    raw_shift = str(
        time_log.get("shift_type")
        or time_log.get("shift")
        or ""
    ).strip().lower()

    if "night" in raw_shift or re.search(r"\bns\b", raw_shift):
        return "NS"

    if "day" in raw_shift or re.search(r"\bds\b", raw_shift):
        return "DS"

    if time_log.get("from_time"):
        start_time = get_datetime(time_log.from_time).time()
        return "NS" if start_time >= DAY_SHIFT_CUTOFF else "DS"

    return "DS"


def round_hours(value):
    return flt(value, 2)


def build_grouped_timesheet_data(docs):
    first = docs[0]
    monday = getdate(first.custom_monday_date)
    sunday = getdate(first.custom_sunday_date)
    dates = []
    date_keys = []

    for offset in range(7):
        current_date = getdate(add_days(monday, offset))
        date_key = str(current_date)
        date_keys.append(date_key)
        dates.append({
            "date": date_key,
            "day": current_date.strftime("%A"),
            "day_short": current_date.strftime("%a"),
            "label": formatdate(current_date, "dd MMM"),
        })

    rows_by_employee = {}

    for doc in docs:
        employee_key = doc.employee or doc.employee_name or doc.name

        if employee_key not in rows_by_employee:
            rows_by_employee[employee_key] = {
                "employee": doc.employee,
                "employee_name": doc.employee_name or doc.employee,
                "roles": [],
                "days": {
                    date_key: {"ds": 0.0, "ns": 0.0, "total": 0.0}
                    for date_key in date_keys
                },
                "total_ds": 0.0,
                "total_ns": 0.0,
                "total": 0.0,
            }

        row = rows_by_employee[employee_key]

        if doc.role and doc.role not in row["roles"]:
            row["roles"].append(doc.role)

        for time_log in doc.time_logs:
            if not time_log.from_time:
                continue

            date_key = str(getdate(time_log.from_time))
            if date_key not in row["days"]:
                continue

            hours = flt(time_log.hours)
            shift_code = get_shift_code(time_log)
            shift_key = shift_code.lower()

            row["days"][date_key][shift_key] += hours

    rows = list(rows_by_employee.values())

    for row in rows:
        for date_key in date_keys:
            day_values = row["days"][date_key]
            day_values["ds"] = round_hours(day_values["ds"])
            day_values["ns"] = round_hours(day_values["ns"])
            day_values["total"] = round_hours(
                day_values["ds"] + day_values["ns"]
            )
            row["total_ds"] += day_values["ds"]
            row["total_ns"] += day_values["ns"]

        row["total_ds"] = round_hours(row["total_ds"])
        row["total_ns"] = round_hours(row["total_ns"])
        row["total"] = round_hours(row["total_ds"] + row["total_ns"])
        row["role"] = ", ".join(row.pop("roles"))

    rows.sort(key=lambda row: (row["employee_name"] or "").lower())

    day_totals = {
        date_key: {"ds": 0.0, "ns": 0.0, "total": 0.0}
        for date_key in date_keys
    }

    for row in rows:
        for date_key in date_keys:
            day_totals[date_key]["ds"] += row["days"][date_key]["ds"]
            day_totals[date_key]["ns"] += row["days"][date_key]["ns"]

    for date_key in date_keys:
        day_totals[date_key]["ds"] = round_hours(day_totals[date_key]["ds"])
        day_totals[date_key]["ns"] = round_hours(day_totals[date_key]["ns"])
        day_totals[date_key]["total"] = round_hours(
            day_totals[date_key]["ds"] + day_totals[date_key]["ns"]
        )

    total_ds = round_hours(sum(row["total_ds"] for row in rows))
    total_ns = round_hours(sum(row["total_ns"] for row in rows))
    signed_docs = [doc for doc in docs if cint(doc.custom_client_signed) == 1]

    if len(signed_docs) == len(docs):
        approval_status = "Signed"
    elif signed_docs:
        approval_status = "Partially Signed"
    else:
        approval_status = "Awaiting Signature"

    signed_by = None
    date_signed = None
    if len(signed_docs) == len(docs):
        signed_names = sorted({
            str(doc.custom_signed_full_name).strip()
            for doc in signed_docs
            if doc.custom_signed_full_name
        })
        signed_dates = sorted({
            str(doc.custom_date_signed)
            for doc in signed_docs
            if doc.custom_date_signed
        })

        if len(signed_names) == 1:
            signed_by = signed_names[0]
        elif len(signed_names) > 1:
            signed_by = "Multiple signatories"

        if len(signed_dates) == 1:
            date_signed = signed_dates[0]

    project_label = first.project_name or first.parent_project

    return {
        "project": first.parent_project,
        "project_name": project_label,
        "week_start": str(monday),
        "week_end": str(sunday),
        "week_label": (
            f"{formatdate(monday, 'dd MMM yyyy')} - "
            f"{formatdate(sunday, 'dd MMM yyyy')}"
        ),
        "dates": dates,
        "employees": rows,
        "day_totals": day_totals,
        "totals": {
            "ds": total_ds,
            "ns": total_ns,
            "total": round_hours(total_ds + total_ns),
        },
        "timesheet_count": len(docs),
        "employee_count": len(rows),
        "signed_count": len(signed_docs),
        "approval_status": approval_status,
        "is_already_signed": len(signed_docs) == len(docs),
        "signed_by": signed_by,
        "date_signed": str(date_signed) if date_signed else None,
    }


@frappe.whitelist(allow_guest=True)
def get_grouped_timesheets_public(token):
    """Return only the client-facing fields needed by the grouped web page."""
    docs = get_grouped_timesheet_docs(token, require_submitted=True)
    return build_grouped_timesheet_data(docs)


def validate_signature(signature_base64):
    if not signature_base64 or not isinstance(signature_base64, str):
        frappe.throw("Please provide a signature.")

    prefix = "data:image/png;base64,"
    if not signature_base64.startswith(prefix):
        frappe.throw("The signature image is not in the expected PNG format.")

    encoded_data = signature_base64[len(prefix):]

    try:
        decoded_data = base64.b64decode(encoded_data, validate=True)
    except (binascii.Error, ValueError):
        frappe.throw("The signature image is invalid.")

    if not decoded_data:
        frappe.throw("Please provide a signature.")

    if len(decoded_data) > MAX_SIGNATURE_BYTES:
        frappe.throw("The signature image is too large. Please clear it and try again.")

    return signature_base64


def validate_signatory(full_name, date_signed):
    clean_name = str(full_name or "").strip()

    if not clean_name:
        frappe.throw("Please enter the signatory's full name.")

    if len(clean_name) > 140:
        frappe.throw("The signatory's full name is too long.")

    if not date_signed:
        frappe.throw("Please enter the date signed.")

    try:
        clean_date = getdate(date_signed)
    except Exception:
        frappe.throw("Please enter a valid signing date.")

    return clean_name, clean_date


def lock_grouped_timesheets(timesheet_names):
    placeholders = ", ".join(["%s"] * len(timesheet_names))
    return frappe.db.sql(
        f"""
            SELECT name, custom_client_signed
            FROM `tabTimesheet`
            WHERE name IN ({placeholders})
            FOR UPDATE
        """,
        tuple(timesheet_names),
        as_dict=True,
    )


def send_grouped_signed_notification(docs, grouped_data):
    """Send one internal confirmation without changing the signing result."""
    email_settings = get_verto_mobile_email_settings()
    recipients = email_settings.email_recipients

    if not recipients:
        frappe.log_error(
            title="Grouped signed Timesheet email skipped - no recipients",
            message=(
                f"No recipients were configured for grouped Timesheets "
                f"{', '.join(doc.name for doc in docs)}. Add recipients to "
                "Verto Mobile Settings.email_recipients."
            ),
        )
        return

    approval_url = get_grouped_timesheet_signing_url([doc.name for doc in docs])
    project_name = html.escape(grouped_data["project_name"] or "")
    week_label = html.escape(grouped_data["week_label"] or "")

    content_html = f"""
        <p>The consolidated weekly timesheets for
        <strong>{project_name}</strong> have been signed.</p>
        <p><strong>Week:</strong> {week_label}</p>
        <p><strong>Employees:</strong> {grouped_data['employee_count']}</p>
        <p><strong>Total Day Shift Hours:</strong> {grouped_data['totals']['ds']}</p>
        <p><strong>Total Night Shift Hours:</strong> {grouped_data['totals']['ns']}</p>
        <p><strong>Total Hours:</strong> {grouped_data['totals']['total']}</p>
        <p><b><a href="{approval_url}">View Signed Weekly Timesheets</a></b></p>
    """

    frappe.sendmail(
        recipients=recipients,
        subject=(
            f"Signed Weekly Timesheets - {project_name} - {week_label}"
        ),
        message=build_email_body(content_html, email_settings=email_settings),
        delayed=False,
        **get_sendmail_options(email_settings),
    )


@frappe.whitelist(allow_guest=True)
def sign_grouped_timesheets(
    token,
    signature_base64,
    full_name=None,
    date_signed=None,
):
    """Apply one client signature to every Timesheet in the signed group token."""
    clean_signature = validate_signature(signature_base64)
    clean_name, clean_date = validate_signatory(full_name, date_signed)
    docs = get_grouped_timesheet_docs(token, require_submitted=True)
    timesheet_names = [doc.name for doc in docs]

    locked_rows = lock_grouped_timesheets(timesheet_names)

    if len(locked_rows) != len(timesheet_names):
        frappe.throw("One or more Timesheets in this approval could not be found.")

    already_signed = {
        row.name for row in locked_rows if cint(row.custom_client_signed) == 1
    }

    if len(already_signed) == len(timesheet_names):
        return {
            "status": "Already signed",
            "message": "These weekly Timesheets have already been signed.",
        }

    unsigned_docs = [doc for doc in docs if doc.name not in already_signed]

    for doc in unsigned_docs:
        doc.db_set("custom_client_signature", clean_signature)
        doc.db_set("custom_client_signed", 1)
        doc.db_set("custom_signed_full_name", clean_name)
        doc.db_set("custom_date_signed", clean_date)

    frappe.db.commit()

    grouped_data = build_grouped_timesheet_data(docs)

    try:
        send_grouped_signed_notification(docs, grouped_data)
    except Exception:
        # The signature is already committed. A notification problem must not
        # make the client think the approval failed and encourage a second sign.
        frappe.log_error(
            title="Grouped signed Timesheet notification failed",
            message=frappe.get_traceback(),
        )

    return {
        "status": "Success",
        "message": "Weekly Timesheets signed successfully.",
        "timesheets_signed": len(unsigned_docs),
    }
