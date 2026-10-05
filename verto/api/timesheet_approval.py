"""Client decisions belong to approval requests, never to Timesheet docstatus."""

import copy
import html
import json
from pathlib import Path

import frappe
from frappe.utils import now_datetime, validate_email_address

from verto.api import automate


REQUEST_DOCTYPE = "Weekly Timesheet Approval Request"
MAX_REJECTION_LENGTH = 5000


def request_names(request):
    return automate.normalise_grouped_timesheet_names(frappe.parse_json(request.timesheet_names))


def lock_project(project):
    # Send, resend, approval and rejection use the same lock order: Project,
    # approval request, then Timesheets. This also serializes the first request.
    rows = frappe.db.sql("SELECT name FROM `tabProject` WHERE name = %s FOR UPDATE", (project,))
    if not rows:
        frappe.throw("The approval request's Project could not be found.")


def latest_request(project, week_start, week_end, for_update=False):
    return frappe.db.get_value(
        REQUEST_DOCTYPE,
        {"project": project, "week_start": week_start, "week_end": week_end,
         "status": ["!=", "Superseded"]},
        "name", order_by="creation desc", for_update=for_update,
    )


def resolve_request(token, for_update=False):
    payload = automate.decode_grouped_timesheet_token_payload(token)
    name = payload.get("request")
    if not name:
        if for_update:
            project = frappe.db.get_value("Timesheet", payload["names"][0], "parent_project")
            lock_project(project)
        return None

    request = frappe.get_doc(REQUEST_DOCTYPE, name)
    if for_update:
        lock_project(request.project)
        request = frappe.get_doc(REQUEST_DOCTYPE, name, for_update=True)
    if request_names(request) != payload["names"]:
        frappe.throw("This approval link does not match its Timesheets.")
    return request


def assert_request_open(request):
    if request.status == "Rejected":
        frappe.throw("This week was rejected. Please wait for a corrected approval email.")
    if request.status == "Superseded":
        frappe.throw("This approval link has been replaced. Please use the latest approval email.")


def assert_legacy_link_current(docs, for_update=False):
    first = docs[0]
    if latest_request(first.parent_project, first.custom_monday_date, first.custom_sunday_date, for_update=for_update):
        frappe.throw("This approval link has been replaced. Please use the latest approval email.")


def assert_snapshot_matches(request, data):
    snapshot = frappe.parse_json(request.snapshot)
    for field in ("project", "week_start", "week_end", "dates", "employees", "day_totals", "totals", "timesheet_count"):
        if snapshot.get(field) != data.get(field):
            frappe.throw("These Timesheets have changed. Please ask the site team for a new approval email.")


def create_request(timesheet_names, email_settings, recipients):
    from verto.api import timesheet_signing as signing

    reply_to = str(email_settings.reply_to_email or "").strip()
    addresses = automate.split_email_list(validate_email_address(reply_to, throw=True)) if reply_to else []
    if len(addresses) != 1:
        frappe.throw("Set one Reply-To Email in Verto Mobile Settings before sending weekly approvals.")

    names = automate.normalise_grouped_timesheet_names(timesheet_names)
    docs = signing.get_grouped_timesheet_docs(
        automate.create_grouped_timesheet_token(names), check_request=False,
    )
    first = docs[0]
    lock_project(first.parent_project)
    expected_group = (first.parent_project, str(first.custom_monday_date), str(first.custom_sunday_date))
    previous = frappe.db.get_values(REQUEST_DOCTYPE, {
        "project": first.parent_project, "week_start": first.custom_monday_date,
        "week_end": first.custom_sunday_date, "status": ["!=", "Superseded"],
    }, "name", for_update=True)
    signing.lock_grouped_timesheets(names)
    # Reload after the row locks; cancellation or amendment may have happened
    # while this sender was waiting.
    docs = signing.get_grouped_timesheet_docs(
        automate.create_grouped_timesheet_token(names), check_request=False, for_update=True,
    )
    current_group = (docs[0].parent_project, str(docs[0].custom_monday_date), str(docs[0].custom_sunday_date))
    if current_group != expected_group:
        frappe.throw("The Timesheets' Project or week changed. Please resend the approval.")
    first = docs[0]
    for doc in docs:
        doc.check_permission("write")

    snapshot = signing.build_grouped_timesheet_data(docs)
    request = frappe.get_doc({
        "doctype": REQUEST_DOCTYPE,
        "project": first.parent_project,
        "project_name": first.project_name or first.parent_project,
        "week_start": first.custom_monday_date,
        "week_end": first.custom_sunday_date,
        "status": "Approved" if snapshot["is_already_signed"] else "Pending",
        "approved_by": snapshot["signed_by"] if snapshot["is_already_signed"] else None,
        "approval_details": json.dumps({"signed_by": snapshot["signed_by"], "date_signed": snapshot["date_signed"]}) if snapshot["is_already_signed"] else None,
        "reply_to_email": addresses[0],
        "recipient_emails": "\n".join(automate.split_email_list(recipients)),
        "timesheet_names": json.dumps(names),
        "snapshot": json.dumps(snapshot),
    }).insert(ignore_permissions=True)

    # Retain all previous decisions, reasons and notification references.
    for row in previous:
        frappe.db.set_value(REQUEST_DOCTYPE, row[0], {
            "status": "Superseded", "superseded_by": request.name,
        })
    return request


def record_approval_email(request, email_queue):
    if not email_queue or not email_queue.name:
        frappe.throw("The approval email was not added to Email Queue.")
    request.db_set("approval_email", email_queue.name)


def public_request_data(request):
    # A rejected/replaced request remains readable after its Timesheets are
    # cancelled and amended. Never expose internal email addresses to guests.
    data = copy.deepcopy(frappe.parse_json(request.snapshot))
    data.update({
        "approval_request": request.name,
        "can_sign": request.status == "Pending" and not data["is_already_signed"],
        "can_reject": request.status == "Pending" and not data["is_already_signed"],
        "rejection_reason": request.rejection_reason,
        "rejected_by": request.rejected_by,
        "rejected_on": str(request.rejected_on) if request.rejected_on else None,
        "notification_failed": request.notification_status == "Failed",
    })
    if request.status == "Approved":
        data.update(frappe.parse_json(request.approval_details) or {})
        data.update(approval_status="Signed", is_already_signed=True, signed_count=data["timesheet_count"])
    elif request.status in ("Rejected", "Superseded"):
        data.update(approval_status=request.status, is_already_signed=False)
    return data


def mark_approved(request, data):
    request.db_set({
        "status": "Approved", "approved_on": now_datetime(),
        "approved_by": data.get("signed_by"),
        "approval_details": json.dumps({"signed_by": data.get("signed_by"), "date_signed": data.get("date_signed")}),
    })


def queue_rejection_notification(request):
    if request.notification_status == "Queued":
        return True

    savepoint = "before_timesheet_rejection_email"
    frappe.db.savepoint(savepoint)
    try:
        settings = automate.get_verto_mobile_email_settings()
        snapshot = frappe.parse_json(request.snapshot)
        reason = html.escape(request.rejection_reason).replace("\n", "<br>")
        url = automate.get_grouped_timesheet_signing_url(request_names(request), request_name=request.name)
        desk_url = frappe.utils.get_url(f"/app/weekly-timesheet-approval-request/{request.name}")
        content = f"""
            <p>The client has rejected the weekly timesheets for
            <strong>{html.escape(request.project_name)}</strong>.</p>
            <p><strong>Week:</strong> {html.escape(snapshot['week_label'])}</p>
            <p><strong>Rejected by:</strong> {html.escape(request.rejected_by)}</p>
            <p><strong>Rejected on:</strong> {html.escape(str(request.rejected_on))}</p>
            <p><strong>Reason:</strong><br>{reason}</p>
            <p><strong>Timesheets:</strong> {html.escape(', '.join(request_names(request)))}</p>
            <p>The Timesheets remain submitted. Review the reason, cancel and amend
            any affected Timesheets as needed, then resend the corrected week.</p>
            <p><a href="{url}">View Rejected Week</a> &middot;
            <a href="{desk_url}">Open Approval Request</a></p>
        """
        queue = frappe.sendmail(
            recipients=[request.reply_to_email],
            subject=f"Weekly Timesheets Rejected - {request.project_name} - {snapshot['week_label']}",
            message=automate.build_email_body(content, settings),
            reply_to=request.reply_to_email,
            reference_doctype=REQUEST_DOCTYPE, reference_name=request.name,
            delayed=True, add_unsubscribe_link=0,
        )
        if not queue or not queue.name:
            frappe.throw("The rejection notification was not added to Email Queue.")
        request.db_set({"notification_status": "Queued", "rejection_email": queue.name})
        return True
    except Exception:
        frappe.db.rollback(save_point=savepoint)
        request.db_set("notification_status", "Failed")
        frappe.log_error(title="Weekly Timesheet rejection email failed", message=frappe.get_traceback())
        return False


@frappe.whitelist(allow_guest=True, methods=["POST"])
def reject_grouped_timesheets(token, reason, full_name=None):
    from verto.api import timesheet_signing as signing

    clean_name = str(full_name or "").strip()
    clean_reason = str(reason or "").strip()
    if not clean_name or len(clean_name) > 140:
        frappe.throw("Please enter your full name (up to 140 characters).")
    if not clean_reason or len(clean_reason) > MAX_REJECTION_LENGTH:
        frappe.throw(f"Please enter a rejection reason (up to {MAX_REJECTION_LENGTH} characters).")

    request = resolve_request(token, for_update=True)
    if not request:
        frappe.throw("Please ask the site team for a new approval email to reject this week online.")
    if request.status == "Superseded":
        assert_request_open(request)
    if request.status == "Rejected":
        return rejection_result(request, already_rejected=True)
    if request.status == "Approved":
        frappe.throw("These weekly Timesheets have already been signed and cannot be rejected.")

    names = request_names(request)
    signing.lock_grouped_timesheets(names)
    docs = signing.get_grouped_timesheet_docs(token, for_update=True)
    data = signing.build_grouped_timesheet_data(docs)
    assert_snapshot_matches(request, data)
    if data["is_already_signed"]:
        frappe.throw("These weekly Timesheets have already been signed and cannot be rejected.")

    request.db_set({
        "status": "Rejected", "rejection_reason": clean_reason,
        "rejected_by": clean_name, "rejected_on": now_datetime(),
    })
    queue_rejection_notification(request)
    # The decision and queued email are one transaction. A repeat POST cannot
    # send a second notification or overwrite the original reason.
    frappe.db.commit()
    return rejection_result(request)


def rejection_result(request, already_rejected=False):
    queued = request.notification_status == "Queued"
    return {
        "status": "Already rejected" if already_rejected else "Rejected",
        "notification_queued": queued,
        "message": ("Your rejection has been recorded. Its reason will be emailed to the site team."
                    if queued else "Your rejection has been recorded, but its email could not be queued. Please contact the site team."),
    }


@frappe.whitelist(methods=["POST"])
def retry_rejection_notification(request_name):
    request = frappe.get_doc(REQUEST_DOCTYPE, request_name)
    request.check_permission("read")
    frappe.only_for("System Manager")
    lock_project(request.project)
    request = frappe.get_doc(REQUEST_DOCTYPE, request_name, for_update=True)
    if not request.rejection_reason:
        frappe.throw("This approval request has no rejection to notify.")
    queue_rejection_notification(request)
    return rejection_result(request)


def ensure_approval_page():
    """Install/update the existing site-level public Web Page during migration."""
    route = automate.GROUPED_TIMESHEET_ROUTE.lstrip("/")
    name = frappe.db.get_value("Web Page", {"route": route}, "name")
    page = frappe.get_doc("Web Page", name) if name else frappe.new_doc("Web Page")
    app_path = Path(frappe.get_app_path("verto"))
    values = {
        "title": "Weekly Timesheet Approval", "route": route, "published": 1,
        "content_type": "HTML", "show_title": 0,
        "main_section_html": (app_path / "templates" / "timesheets" / "weekly-timesheet-approval.html").read_text(encoding="utf-8"),
        "javascript": (app_path / "public" / "js" / "weekly-timesheet-approval.js").read_text(encoding="utf-8"),
    }
    if all(page.get(field) == value for field, value in values.items()):
        return False
    page.update(values)
    page.save(ignore_permissions=True)
    return True
