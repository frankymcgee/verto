import json
from datetime import timedelta

import frappe
from frappe.utils import add_days, getdate, now_datetime, today

from verto.api.mobile import documents, shifts


RECEIPT_DOCTYPE = "Verto Offline Receipt"


def require_login():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)


def _receipt_name(receipt_id):
    return str(receipt_id or "").strip()


def _get_receipt(receipt_id):
    receipt_id = _receipt_name(receipt_id)

    if not receipt_id or not frappe.db.exists(RECEIPT_DOCTYPE, receipt_id):
        return None

    receipt = frappe.get_doc(RECEIPT_DOCTYPE, receipt_id)

    if receipt.user != frappe.session.user:
        frappe.throw("Offline receipt belongs to another user.", frappe.PermissionError)

    try:
        result = json.loads(receipt.result_json or "{}")
    except Exception:
        result = {}

    return {
        "name": receipt.name,
        "receipt_type": receipt.receipt_type,
        "target_doctype": receipt.target_doctype,
        "target_name": receipt.target_name,
        "result": result,
    }


def _save_receipt(receipt_id, receipt_type, result=None, target_doctype=None, target_name=None):
    receipt_id = _receipt_name(receipt_id)

    if not receipt_id:
        frappe.throw("Offline operation ID is required.", frappe.ValidationError)

    existing = _get_receipt(receipt_id)

    if existing:
        return existing

    result = result or {}

    receipt = frappe.get_doc({
        "doctype": RECEIPT_DOCTYPE,
        "receipt_id": receipt_id,
        "receipt_type": receipt_type,
        "user": frappe.session.user,
        "target_doctype": target_doctype,
        "target_name": target_name,
        "result_json": json.dumps(result, default=str),
        "processed_at": now_datetime(),
    })
    receipt.insert(ignore_permissions=True)

    return {
        "name": receipt.name,
        "receipt_type": receipt.receipt_type,
        "target_doctype": receipt.target_doctype,
        "target_name": receipt.target_name,
        "result": result,
    }


def _serialise_edit_doc(doctype, docname):
    if not frappe.db.exists(doctype, docname):
        return None

    doc = frappe.get_doc(doctype, docname)

    if not documents.has_desk_read_permission(doc):
        return None

    mobile_doctype = documents.get_mobile_slug_for_doctype(doctype)

    return {
        "schema": documents.get_schema_response(mobile_doctype, doctype),
        "doctype": doctype,
        "name": doc.name,
        "docstatus": doc.docstatus,
        "values": documents.serialise_doc_for_mobile(doc, doctype),
        "files": documents.get_existing_files_for_doc(doctype, doc.name),
        "can_write": documents.has_desk_write_permission(doc),
    }


@frappe.whitelist()
def get_offline_bootstrap():
    """Return the minimum dataset needed to keep core Verto Mobile usable offline."""
    require_login()

    schemas = {}

    for mobile_doctype, doctype in documents.ALLOWED_MOBILE_DOCTYPES.items():
        if not (
            frappe.has_permission(doctype, "create")
            or frappe.has_permission(doctype, "read")
        ):
            continue

        schemas[mobile_doctype] = documents.get_schema_response(mobile_doctype, doctype)

    start_date = add_days(today(), -62)
    end_date = add_days(today(), 124)
    shift_calendar = shifts.get_shift_calendar(start_date=start_date, end_date=end_date)

    edit_docs = {}

    for timesheet in shift_calendar.get("timesheets") or []:
        name = timesheet.get("name")

        if not name:
            continue

        payload = _serialise_edit_doc("Daily Timesheet", name)

        if payload:
            edit_docs[f"daily-timesheet:{name}"] = payload

    return {
        "generated_at": now_datetime(),
        "schemas": schemas,
        "shift_calendar": shift_calendar,
        "shift_range": {
            "start_date": getdate(start_date),
            "end_date": getdate(end_date),
        },
        "edit_docs": edit_docs,
    }


@frappe.whitelist(methods=["POST"])
def sync_action(
    operation_id,
    action_type,
    mobile_doctype,
    values=None,
    docname=None,
    client_created_at=None,
):
    """Replay one queued create/update action exactly once per operation ID."""
    require_login()

    operation_id = _receipt_name(operation_id)
    existing = _get_receipt(operation_id)

    if existing:
        return {
            "ok": True,
            "duplicate": True,
            "result": existing.get("result") or {},
        }

    if isinstance(values, str):
        values = json.loads(values or "{}")

    values = values or {}
    action_type = str(action_type or "").strip().lower()

    if action_type == "create":
        result = documents.create_mobile_doc(
            mobile_doctype=mobile_doctype,
            values=json.dumps(values),
        )
    elif action_type == "update":
        if not docname:
            frappe.throw("Document name is required for offline updates.", frappe.ValidationError)

        result = documents.update_mobile_doc(
            mobile_doctype=mobile_doctype,
            docname=docname,
            values=json.dumps(values),
        )
    else:
        frappe.throw("Unsupported offline action type.", frappe.ValidationError)

    frappe.db.commit()

    _save_receipt(
        receipt_id=operation_id,
        receipt_type=f"document_{action_type}",
        result=result,
        target_doctype=result.get("doctype"),
        target_name=result.get("name"),
    )

    frappe.db.commit()

    return {
        "ok": True,
        "duplicate": False,
        "result": result,
    }


@frappe.whitelist(methods=["POST"])
def upload_attachment(
    operation_id,
    attachment_id,
    target_doctype,
    target_name,
):
    """Upload one offline attachment idempotently."""
    require_login()

    receipt_id = f"{_receipt_name(operation_id)}::{_receipt_name(attachment_id)}"
    existing = _get_receipt(receipt_id)

    if existing:
        return {
            "ok": True,
            "duplicate": True,
            "result": existing.get("result") or {},
        }

    if not target_doctype or not target_name:
        frappe.throw("Attachment target is required.", frappe.ValidationError)

    if not frappe.db.exists(target_doctype, target_name):
        frappe.throw("Attachment target no longer exists.", frappe.DoesNotExistError)

    target_doc = frappe.get_doc(target_doctype, target_name)

    if not documents.has_desk_write_permission(target_doc):
        frappe.throw("You do not have permission to attach files to this document.", frappe.PermissionError)

    uploaded = frappe.request.files.get("file")

    if not uploaded:
        frappe.throw("Attachment file is required.", frappe.ValidationError)

    from frappe.utils.file_manager import save_file

    file_doc = save_file(
        uploaded.filename,
        uploaded.stream.read(),
        target_doctype,
        target_name,
        is_private=1,
    )

    result = {
        "name": file_doc.name,
        "file_name": file_doc.file_name,
        "file_url": file_doc.file_url,
        "doctype": target_doctype,
        "docname": target_name,
    }

    _save_receipt(
        receipt_id=receipt_id,
        receipt_type="attachment",
        result=result,
        target_doctype=target_doctype,
        target_name=target_name,
    )

    frappe.db.commit()

    return {
        "ok": True,
        "duplicate": False,
        "result": result,
    }
