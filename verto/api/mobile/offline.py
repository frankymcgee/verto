import json

import frappe
from frappe.utils import add_days, getdate, now_datetime, today

from verto.api import fetch_records
from verto.api.mobile import documents, shifts


RECEIPT_DOCTYPE = "Verto Offline Receipt"
OFFLINE_USER_KEY = "__verto_offline_user"
MAX_LINK_OPTIONS_PER_DOCTYPE = 250


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


def _collect_link_doctypes_from_field(field, result):
    if not isinstance(field, dict):
        return

    if field.get("fieldtype") == "Link" and field.get("options"):
        result.add(str(field.get("options")).strip())

    for child_field in field.get("child_fields") or []:
        _collect_link_doctypes_from_field(child_field, result)


def _get_link_options(schemas):
    link_doctypes = set()

    for schema in schemas.values():
        for field in schema.get("fields") or []:
            _collect_link_doctypes_from_field(field, link_doctypes)

    options = {}

    for doctype in sorted(link_doctypes):
        if not doctype or not frappe.db.exists("DocType", doctype):
            continue

        if not frappe.has_permission(doctype, "read"):
            continue

        fields = ["name"]
        meta = frappe.get_meta(doctype)
        title_field = meta.title_field

        if title_field and title_field != "name":
            fields.append(title_field)

        rows = frappe.get_list(
            doctype,
            fields=fields,
            order_by="modified desc",
            limit_page_length=MAX_LINK_OPTIONS_PER_DOCTYPE,
        )

        values = []

        for row in rows:
            name = row.get("name")

            if not name:
                continue

            description = row.get(title_field) if title_field else None

            values.append({
                "name": name,
                "description": description if description and description != name else None,
            })

        options[doctype] = values

    return options


def _validate_offline_actor(values):
    client_user = str(values.pop(OFFLINE_USER_KEY, "") or "").strip()

    if not client_user:
        frappe.throw(
            "Offline operation is missing its original user. Reconnect and submit again.",
            frappe.PermissionError,
        )

    if client_user != frappe.session.user:
        frappe.throw(
            "This offline operation belongs to another signed-in user and will not be synced.",
            frappe.PermissionError,
        )


@frappe.whitelist()
def get_offline_bootstrap():
    """Return the dataset needed to keep core Verto Mobile functions available offline."""
    require_login()

    schemas = {}

    for mobile_doctype, doctype in documents.get_allowed_mobile_doctypes().items():
        if not (
            frappe.has_permission(doctype, "create")
            or frappe.has_permission(doctype, "read")
        ):
            continue

        schemas[mobile_doctype] = documents.get_schema_response(mobile_doctype, doctype)

    start_date = add_days(today(), -62)
    end_date = add_days(today(), 124)
    shift_calendar = shifts.get_shift_calendar(start_date=start_date, end_date=end_date)
    completed_forms_start = add_days(today(), -28)
    completed_forms_end = today()
    completed_forms = fetch_records.fetch_created_records(
        start_date=completed_forms_start,
        end_date=completed_forms_end,
    )

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
        "user": frappe.session.user,
        "schemas": schemas,
        "shift_calendar": shift_calendar,
        "shift_range": {
            "start_date": getdate(start_date),
            "end_date": getdate(end_date),
        },
        "completed_forms": completed_forms,
        "completed_forms_range": {
            "start_date": getdate(completed_forms_start),
            "end_date": getdate(completed_forms_end),
        },
        "edit_docs": edit_docs,
        "link_options": _get_link_options(schemas),
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

    values = dict(values or {})
    _validate_offline_actor(values)
    action_type = str(action_type or "").strip().lower()

    if action_type not in ("create", "update"):
        frappe.throw("Unsupported offline action type.", frappe.ValidationError)

    if action_type == "update" and not docname:
        frappe.throw("Document name is required for offline updates.", frappe.ValidationError)

    # Fetch fields that the online form normally resolves as Link values change.
    # This keeps offline submissions consistent even though those client-side
    # lookups cannot run while the device has no connection.
    fetched = documents.apply_fetch_from(
        mobile_doctype=mobile_doctype,
        values=values,
        docname=docname if action_type == "update" else None,
    ) or {}
    values.update(fetched.get("values") or {})

    if action_type == "create":
        result = documents.create_mobile_doc(
            mobile_doctype=mobile_doctype,
            values=json.dumps(values),
        )
    else:
        result = documents.update_mobile_doc(
            mobile_doctype=mobile_doctype,
            docname=docname,
            values=json.dumps(values),
        )

    # Keep the document write and its idempotency receipt in one transaction.
    # If two tabs replay the same operation concurrently, the unique receipt ID
    # rolls the losing transaction back instead of leaving a duplicate document.
    try:
        _save_receipt(
            receipt_id=operation_id,
            receipt_type=f"document_{action_type}",
            result=result,
            target_doctype=result.get("doctype"),
            target_name=result.get("name"),
        )
    except frappe.DuplicateEntryError:
        # Another tab/device won the same operation ID race. Roll back this
        # transaction (including its document write), then return the winner.
        frappe.db.rollback()
        existing = _get_receipt(operation_id)

        if existing:
            return {
                "ok": True,
                "duplicate": True,
                "result": existing.get("result") or {},
            }

        raise

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
    """Upload one attachment for a previously replayed offline document action."""
    require_login()

    operation_id = _receipt_name(operation_id)
    parent_receipt = _get_receipt(operation_id)

    if not parent_receipt:
        frappe.throw(
            "The parent offline document has not been synced yet.",
            frappe.ValidationError,
        )

    if (
        parent_receipt.get("target_doctype") != target_doctype
        or parent_receipt.get("target_name") != target_name
    ):
        frappe.throw(
            "Offline attachment target does not match the synced document.",
            frappe.PermissionError,
        )

    receipt_id = f"{operation_id}::{_receipt_name(attachment_id)}"
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
