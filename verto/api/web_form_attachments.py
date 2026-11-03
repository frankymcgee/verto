"""Save public Field Interaction evidence in the Web Form's transaction."""

import base64
import binascii
import json
from pathlib import PurePath

import frappe
from frappe import _
from frappe.core.api.file import get_max_file_size
from frappe.rate_limiter import rate_limit
from frappe.utils import cint


DOCTYPE = "Field Interaction"
PAYLOAD_KEY = "_verto_attachments"
MAX_FILES = 10
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 25 * 1024 * 1024
EXTENSIONS = frozenset(("jpg", "jpeg", "png", "gif", "pdf", "txt", "csv", "doc", "docx", "xls", "xlsx", "odt", "ods"))


def _get_form(web_form, web_form_request_key=None):
    form = frappe.get_doc("Web Form", web_form)
    form.raise_if_unpublished()
    if form.doc_type != DOCTYPE:
        frappe.throw(_("Multiple attachments are only supported for Field Interaction."), frappe.PermissionError)
    if form.login_required and frappe.session.user == "Guest":
        frappe.throw(_("You must login to use this form"), frappe.PermissionError)
    form.get_web_form_request(web_form_request_key, allow_used=True)
    if frappe.session.user == "Guest" or form.anonymous:
        if not cint(frappe.get_system_settings("allow_guests_to_upload_files")):
            frappe.throw(_("Guest file uploads are disabled."), frappe.PermissionError)
        allowed = frappe.get_system_settings("allowed_doctypes_for_guest_uploads") or ""
        allowed = {line.strip() for line in allowed.splitlines() if line.strip()}
        if allowed and DOCTYPE not in allowed:
            frappe.throw(_("Guest uploads are not allowed for Field Interaction."), frappe.PermissionError)
    return form


def _options(form):
    max_size = min(MAX_FILE_BYTES, get_max_file_size())
    if cint(form.max_attachment_size) > 0:
        max_size = min(max_size, cint(form.max_attachment_size) * 1024 * 1024)
    max_files = MAX_FILES
    doctype_limit = cint(frappe.get_meta(DOCTYPE).max_attachments)
    if doctype_limit > 0:
        max_files = min(max_files, doctype_limit)
    extensions = EXTENSIONS
    configured = frappe.get_system_settings("allowed_file_extensions") or ""
    if configured.strip():
        extensions = extensions.intersection(line.strip().lstrip(".").lower() for line in configured.splitlines())
    return {
        "max_files": max_files,
        "max_file_bytes": max_size,
        "max_total_bytes": MAX_TOTAL_BYTES,
        "allowed_extensions": sorted(extensions),
    }


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="web_form", limit=30, seconds=60)
def get_upload_options(web_form: str, web_form_request_key: str | None = None):
    return _options(_get_form(web_form, web_form_request_key))


def _decode_attachments(attachments, options):
    if not isinstance(attachments, list) or len(attachments) > options["max_files"]:
        frappe.throw(_("Select up to {0} attachments.").format(options["max_files"]))
    decoded = []
    total_size = 0
    for attachment in attachments:
        if not isinstance(attachment, dict):
            frappe.throw(_("Invalid attachment."))
        name = attachment.get("file_name")
        content = attachment.get("content")
        if (
            not isinstance(name, str) or not name.strip() or len(name) > 140
            or any(character in name for character in ("/", "\\"))
            or any(ord(character) < 32 or ord(character) == 127 for character in name)
        ):
            frappe.throw(_("Invalid attachment filename."))
        if PurePath(name).suffix.lower().lstrip(".") not in options["allowed_extensions"]:
            frappe.throw(_("This attachment file type is not allowed."))
        if not isinstance(content, str) or not content:
            frappe.throw(_("An attachment has no file content."))
        # Bound decoding allocations before trusting the browser's size checks.
        if len(content) > 4 * ((options["max_file_bytes"] + 2) // 3):
            frappe.throw(_("An attachment exceeds the allowed file size."))
        try:
            content = base64.b64decode(content, validate=True)
        except (ValueError, binascii.Error):
            frappe.throw(_("Invalid attachment content."))
        if not content or len(content) > options["max_file_bytes"]:
            frappe.throw(_("An attachment is empty or exceeds the allowed file size."))
        total_size += len(content)
        if total_size > options["max_total_bytes"]:
            frappe.throw(_("The attachments exceed the total upload size limit."))
        decoded.append((name, content))
    return decoded


def _accept_web_form(web_form, data, web_form_request_key):
    from frappe.website.doctype.web_form.web_form import accept as core_accept

    # Delegate directly, retaining core publication, login/key, field validation,
    # permissions and rate limiting. Do not re-enter the whitelisted override.
    return core_accept(web_form=web_form, data=data, web_form_request_key=web_form_request_key)


@frappe.whitelist(allow_guest=True, methods=["POST", "PUT"])
@rate_limit(key="web_form", limit=10, seconds=60)
def accept(web_form: str, data: str | dict, web_form_request_key: str | None = None):
    values = frappe.parse_json(data) if isinstance(data, str) else data
    if not isinstance(values, dict):
        frappe.throw(_("Invalid Web Form data."))
    values = dict(values)
    attachments = values.pop(PAYLOAD_KEY, [])
    if not isinstance(attachments, list):
        frappe.throw(_("Invalid attachments."))
    if not attachments:
        return _accept_web_form(web_form, json.dumps(values), web_form_request_key)

    form = _get_form(web_form, web_form_request_key)
    # A document name or shared Guest owner is never proof that this visitor
    # may attach files to an existing record. This flow only creates records.
    if values.get("name"):
        frappe.throw(_("Attachments can only be added with a new submission."), frappe.PermissionError)
    files = _decode_attachments(attachments, _options(form))
    doc = _accept_web_form(web_form, json.dumps(values), web_form_request_key)
    if doc.doctype != DOCTYPE:
        frappe.throw(_("The Web Form's DocType has changed. Please reload the form."), frappe.PermissionError)

    for filename, content in files:
        file = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "content": content,
            "is_private": 1,
            "attached_to_doctype": DOCTYPE,
            "attached_to_name": doc.name,
        })
        file.insert(ignore_permissions=True)

    # No commit, follow-up upload request or guest-visible URLs: any validation
    # or File failure rolls back the form and its files together.
    return doc
