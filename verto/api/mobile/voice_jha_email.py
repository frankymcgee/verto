"""Immediate, revision-bound print emails after team leader review and crew sign-on."""
from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from datetime import timedelta
from email.utils import parseaddr
from html import escape

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime, validate_email_address

from verto.api.mobile import voice_jha_review as review

DOCTYPE = "JHA Print Delivery"
PROJECT_FIELD = "custom_jha_print_email"
DEFAULT_FIELD = "default_jha_print_email"
BUSY_STATUSES = {"Pending", "Queued", "Sending"}


def printing_address(value):
    value = str(value or "").strip()
    if not value:
        return ""
    display, address = parseaddr(value)
    if display or address != value or any(c in value for c in "\r\n,;"):
        frappe.throw(_("Enter one printing email address without a display name."), frappe.ValidationError)
    return validate_email_address(value, throw=True)


def validate_destination(doc, method=None):
    field = PROJECT_FIELD if doc.doctype == "Project" else DEFAULT_FIELD
    if doc.meta.has_field(field):
        doc.set(field, printing_address(doc.get(field)))


def ensure_print_email_fields():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    if frappe.db.exists("DocType", "Project"):
        create_custom_fields({"Project": [{"fieldname": PROJECT_FIELD, "fieldtype": "Data", "options": "Email",
            "label": "JHA Printing Email", "insert_after": "project_name",
            "description": "Signed JHA PDFs are emailed here automatically after the final crew sign-on. Leave blank to use the default in Verto Mobile Settings."}]}, update=False)


def _destination(jha):
    project = frappe.get_doc("Project", jha.project)
    return printing_address(project.get(PROJECT_FIELD) or frappe.get_cached_doc("Verto Mobile Settings").get(DEFAULT_FIELD))


def _signed(jha):
    people = review._present_participants(jha)
    return bool(jha.jha_status == "Signed" and not jha.get("replacement_jha") and cint(jha.get("review_completed"))
                and jha.get("review_signature") and people
                and all(cint(row.acknowledged) and row.get("acknowledgement_signature") for row in people))


def _key(jha):
    return hashlib.sha256(f"{jha.name}|{cint(jha.revision)}".encode()).hexdigest()


def _record(jha):
    name = frappe.db.get_value(DOCTYPE, {"delivery_key": _key(jha)}, "name")
    return frappe.get_doc(DOCTYPE, name) if name else None


def _save(record):
    record.flags.allow_jha_print_mutation = True
    return record.save(ignore_permissions=True)


def _queue_info(record):
    return frappe.db.get_value("Email Queue", record.email_queue,
        ["name", "status", "modified", "error"], as_dict=True) if record and record.get("email_queue") else None


def _status(record):
    if not record:
        return "Not Requested"
    queue = _queue_info(record)
    if queue and queue.status in {"Sent", "Sending"}:
        return queue.status
    if record.status == "Cancelled":
        return "Cancelled"
    if queue:
        return "Failed" if queue.status == "Error" or queue.get("error") or record.status == "Failed" else "Queued"
    if record.status == "Sent":
        return "Sent"
    return "Failed" if record.get("email_queue") else record.status


def _can_manage(jha):
    user = frappe.session.user
    return bool(user == "Administrator" or user == jha.get("reviewed_by")
                or set(frappe.get_roles(user)) & {"System Manager", "Verto Mobile Manager"})


def _state(jha, record=None):
    record = record or _record(jha)
    status = _status(record)
    destination = _destination(jha)
    if not record and not destination:
        status = "Not Configured"
    elif status == "Not Configured" and destination:
        status = "Not Requested"
    queue = _queue_info(record)
    sent_at = record.get("sent_at") if record else None
    if status == "Sent" and not sent_at and queue:
        sent_at = queue.modified
    return {"jha": jha.name, "revision": cint(jha.revision), "status": status,
        "recipient": (record.get("recipient") if record else "") or destination,
        "configured_recipient": destination, "requested_at": str(record.creation) if record else None,
        "sent_at": str(sent_at) if status == "Sent" and sent_at else None,
        "resend_count": len(json.loads(record.get("request_history") or "[]")) if record else 0,
        "can_resend": bool(destination and _signed(jha) and jha.has_permission("write")
                           and _can_manage(jha) and status not in BUSY_STATUSES),
        "message": "A supervisor needs to check the email delivery and try again." if status == "Failed" else ""}


def _new_record(jha):
    destination = _destination(jha)
    record = frappe.get_doc({"doctype": DOCTYPE, "jha": jha.name, "revision": cint(jha.revision),
        "project": jha.project, "work_summary": jha.work_summary, "delivery_key": _key(jha),
        "status": "Pending" if destination else "Not Configured", "recipient": destination,
        "request_history": "[]", "requested_by": frappe.session.user})
    record.flags.allow_jha_print_mutation = True
    record.insert(ignore_permissions=True)
    return record


def _enqueue(delivery_name):
    # This callback runs after the sign-on transaction commits. Redis failures
    # must not turn a successful signature into a failed response to the crew.
    try:
        frappe.enqueue("verto.api.mobile.voice_jha_email.prepare_print_email", queue="short", timeout=300,
            job_id=f"jha-print-prepare-{delivery_name}", deduplicate=True, delivery_name=delivery_name)
    except Exception:
        frappe.log_error(title="JHA print email could not be scheduled", message=frappe.get_traceback())


def _schedule(record):
    from functools import partial
    frappe.db.after_commit.add(partial(_enqueue, record.name))


def _send_after_commit(record):
    from functools import partial
    # Frappe's SMTP sender commits internally. Persist the PDF and queue link
    # first, then send in this job without waiting for the email scheduler.
    frappe.db.after_commit.add(partial(send_print_email, record.name, record.email_queue))


def jha_updated(doc, method=None):
    if not frappe.db.exists("DocType", DOCTYPE):
        return
    before = doc.get_doc_before_save()
    if not before or "Signed" not in {before.jha_status, doc.jha_status}:
        return
    frappe.db.savepoint("jha_print_delivery")
    try:
        if not _signed(doc):
            record = _record(doc)
            if record and _status(record) in {"Pending", "Queued", "Failed", "Not Configured"}:
                _cancel(record)
            return
        if before.jha_status == "Signed" or _record(doc):
            return
        record = _new_record(doc)
        if record.status == "Pending":
            _schedule(record)
    except Exception:
        frappe.db.rollback(save_point="jha_print_delivery")
        frappe.log_error(title="JHA print delivery could not be recorded", message=frappe.get_traceback())


def _cancel(record):
    queue = _queue_info(record)
    if queue and queue.status in {"Sent", "Sending"}:
        # Preserve an SMTP result even when work changes before reconciliation.
        # Queue retention must not later turn a successful delivery into Failed.
        record.status = queue.status
        if queue.status == "Sent" and not record.get("sent_at"):
            record.sent_at = queue.modified
        _save(record)
        return
    if queue:
        frappe.db.set_value("Email Queue", queue.name, {"status": "Error", "error": "JHA print delivery cancelled: this is no longer the current signed revision."})
    record.status = "Cancelled"
    _save(record)


@contextmanager
def _system_user():
    user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        yield
    finally:
        frappe.set_user(user)


def _locked_delivery(delivery_name):
    record = frappe.get_doc(DOCTYPE, delivery_name)
    frappe.db.sql("select name from `tabDigital Job Hazard Analysis` where name=%s for update", record.jha)
    frappe.db.sql("select name from `tabJHA Print Delivery` where name=%s for update", record.name)
    record.reload()
    jha = review._get_jha(record.jha)
    record.reload()  # Source-change detection may have cancelled this delivery.
    if cint(record.revision) != cint(jha.revision):
        frappe.throw(_("The print delivery revision does not match its JHA."), frappe.ValidationError)
    return record, jha


def _pdf_file(record, jha):
    if record.get("pdf_file"):
        file = frappe.get_doc("File", record.pdf_file)
        if file.is_private and file.attached_to_doctype == DOCTYPE and file.attached_to_name == record.name:
            return file
        frappe.throw(_("The saved print copy is not attached to this delivery."), frappe.ValidationError)
    from verto.api.mobile.voice_jha_print import PRINT_FORMAT_NAME
    pdf = frappe.get_print(review.JHA_DOCTYPE, jha.name, doc=jha, print_format=PRINT_FORMAT_NAME, as_pdf=True)
    if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF-"):
        frappe.throw(_("A PDF could not be generated for this signed JHA."), frappe.ValidationError)
    filename = re.sub(r"[^A-Za-z0-9_.-]", "_", jha.name)[:100] + f"-Rev-{cint(jha.revision)}-Signed.pdf"
    file = frappe.get_doc({"doctype": "File", "file_name": filename, "content": pdf, "is_private": 1,
        "attached_to_doctype": DOCTYPE, "attached_to_name": record.name}).insert(ignore_permissions=True)
    record.pdf_file = file.name
    return file


def prepare_print_email(delivery_name):
    """Prepare one frozen PDF and Email Queue row atomically; never called by voice tools."""
    with _system_user():
        record, jha = _locked_delivery(delivery_name)
        if record.status != "Pending" or record.get("email_queue"):
            return
        if not _signed(jha):
            _cancel(record)
            return
        frappe.db.savepoint("jha_print_prepare")
        try:
            file = _pdf_file(record, jha)
            title = " ".join(str(jha.get("work_summary_title") or jha.work_summary).split())
            queue = frappe.sendmail(recipients=[printing_address(record.recipient)],
                subject=f"Signed JHA for printing: {jha.project} | {title} | {jha.name} | Rev {cint(jha.revision)}",
                message=f"<p>Team leader review (Supervisor or above) and crew sign-on are complete for <strong>{escape(title)}</strong>.</p>"
                        f"<p>Project: {escape(jha.project)}</p>"
                        f"<p>Attached: signed JHA {escape(jha.name)}, revision {cint(jha.revision)}, ready to print.</p>"
                        "<p>Use the QR code on the workpack to check its current revision before use.</p>",
                # Embed raw bytes now: File's default text decoding can corrupt
                # an otherwise valid PDF when a deferred attachment is read.
                delayed=True, attachments=[{"fname": file.file_name, "fcontent": file.get_content(encodings=[]),
                    "content_type": "application/pdf"}], add_unsubscribe_link=0,
                reference_doctype=DOCTYPE, reference_name=record.name)
            if not queue or not queue.name:
                frappe.throw(_("The printing email could not be added to Email Queue."), frappe.ValidationError)
            record.email_queue = queue.name
            record.status = "Queued"
            _save(record)
            _send_after_commit(record)
        except Exception:
            frappe.db.rollback(save_point="jha_print_prepare")
            record.reload()
            record.status = "Failed"
            _save(record)
            frappe.log_error(title="JHA print PDF/email preparation failed", message=frappe.get_traceback())


def send_print_email(delivery_name, email_queue=None):
    """Attempt SMTP immediately after preparation/retry has committed."""
    with _system_user():
        record, jha = _locked_delivery(delivery_name)
        if email_queue and email_queue != record.get("email_queue"):
            # A later manual request replaced this attempt with a fresh PDF.
            # A delayed callback must not act on the replacement delivery.
            frappe.db.commit()
            return
        if not _signed(jha) or record.status == "Cancelled":
            _cancel(record)
            frappe.db.commit()
            return
        info = _queue_info(record)
        if not info:
            record.status = "Failed"
            _save(record)
            frappe.db.commit()
            return
        if info.status in {"Sent", "Sending"}:
            record.status = info.status
            if info.status == "Sent":
                record.sent_at = record.get("sent_at") or info.modified
            _save(record)
            frappe.db.commit()
            return
        try:
            queue = frappe.get_doc("Email Queue", info.name)
            if not queue.can_send_now():
                frappe.throw(_("Email sending is suspended, muted or unavailable for this JHA."), frappe.ValidationError)
            record.status = "Sending"
            _save(record)
            # The sender commits Sending before SMTP, releasing our locks.
            # Repeated callbacks then observe Sending/Sent and do not resend.
            queue.send()
            info = _queue_info(record)
            record.status = info.status if info and info.status in {"Sent", "Sending"} else "Failed"
            if record.status == "Sent":
                record.sent_at = info.modified
            _save(record)
            frappe.db.commit()
        except Exception:
            # Do not roll back to a preparation savepoint: SMTP may already
            # have committed its result. Keep the same queue for a safe retry.
            info = _queue_info(record)
            record.status = "Sent" if info and info.status == "Sent" else "Failed"
            if record.status == "Sent":
                record.sent_at = info.modified
            _save(record)
            frappe.db.commit()
            frappe.log_error(title="JHA print immediate email delivery failed", message=frappe.get_traceback())


@frappe.whitelist(methods=["GET"])
def get_jha_print_delivery(jha_name: str):
    review._require_login()
    jha = review._get_jha(jha_name)
    frappe.local.response_headers["Cache-Control"] = "no-store"
    return _state(jha)


@frappe.whitelist(methods=["POST"])
def resend_jha_print_email(jha_name: str, request_id: str, confirmation=0):
    from verto.api.mobile.voice_jha_fieldwork import locked_jha
    jha = locked_jha(jha_name)
    if not _signed(jha) or not _can_manage(jha):
        frappe.throw(_("Only the reviewer or a mobile/system manager can resend the current signed JHA."), frappe.PermissionError)
    if not cint(confirmation) or not request_id or len(request_id) > 100:
        frappe.throw(_("Confirm the printing email and provide a resend request ID."), frappe.ValidationError)
    destination = _destination(jha)
    if not destination:
        frappe.throw(_("Set a JHA printing email on the Project or in Verto Mobile Settings first."), frappe.ValidationError)
    record = _record(jha)
    existing = bool(record)
    record = record or _new_record(jha)
    history = json.loads(record.get("request_history") or "[]")
    key = hashlib.sha256(f"{frappe.session.user}|{request_id}".encode()).hexdigest()
    if any(row["request_key"] == key for row in history):
        return _state(jha, record)
    status = _status(record)
    if existing and status in BUSY_STATUSES:
        frappe.throw(_("The print email is already being prepared or sent. Check its status before retrying."), frappe.ValidationError)
    old_queue = _queue_info(record)
    history.append({"request_key": key, "requested_by": frappe.session.user, "requested_at": str(now_datetime()),
                    "recipient": destination, "previous_queue": record.get("email_queue"),
                    "previous_pdf_file": record.get("pdf_file"),
                    "previous_recipient": record.get("recipient"), "previous_status": status,
                    "previous_sent_at": str(record.get("sent_at") or old_queue.modified) if status == "Sent" and (record.get("sent_at") or old_queue) else None})
    record.request_history = json.dumps(history)
    record.requested_by = frappe.session.user
    record.recipient = destination
    record.sent_at = None
    if old_queue and old_queue.status in {"Not Sent", "Partially Sent"}:
        frappe.db.set_value("Email Queue", old_queue.name, {
            "status": "Error", "error": "Replaced by a manually requested fresh JHA print copy."
        })
    # Each new explicit request uses the currently installed print format and
    # branding. Retain the old private File and email attachments as history;
    # repeated request IDs return above and reuse this request's prepared copy.
    record.pdf_file = None
    record.email_queue = None
    record.status = "Pending"
    _save(record)
    _schedule(record)
    return _state(jha, record)


def reconcile_print_deliveries():
    """Recover unscheduled preparation and keep Desk status in sync with SMTP."""
    with _system_user():
        rows = frappe.get_all(DOCTYPE, filters={"status": ["in", ["Pending", "Queued", "Sending", "Failed"]]},
            fields=["name", "status", "modified"], order_by="modified asc", limit_page_length=200)
        for row in rows:
            record, jha = _locked_delivery(row.name)
            if not _signed(jha):
                _cancel(record)
            elif record.status == "Pending" and get_datetime(row.modified) < now_datetime() - timedelta(minutes=2):
                _schedule(record)
            else:
                status = _status(record)
                if status != record.status or status == "Sent" and not record.get("sent_at"):
                    record.status = status
                    if status == "Sent":
                        record.sent_at = _queue_info(record).modified
                    _save(record)
                if status == "Queued":
                    _send_after_commit(record)


def delivery_query_conditions(user=None):
    from verto.api.mobile.voice_jha_fieldwork import _query_conditions
    return _query_conditions(DOCTYPE, user)
