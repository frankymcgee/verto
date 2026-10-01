"""System Manager import of the INX Summary Events workbook."""

import hashlib

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from verto.safety.inx_import import SOURCE_SYSTEM, parse_workbook


SOURCE_DOCTYPE = "JHA INX Incident"
LEARNING_DOCTYPE = "JHA Incident Learning"


def _require_manager():
    if frappe.session.user == "Guest" or (
        frappe.session.user != "Administrator" and "System Manager" not in frappe.get_roles()
    ):
        frappe.throw(_("Only a System Manager can import INX incidents."), frappe.PermissionError)
    for doctype in (SOURCE_DOCTYPE, LEARNING_DOCTYPE):
        for permission in ("read", "create", "write"):
            frappe.has_permission(doctype, permission, throw=True)


def _existing(doctype, names, fields):
    return {row["name"]: row for row in frappe.get_list(
        doctype, filters={"name": ["in", names]}, fields=["name", *fields], limit_page_length=len(names),
    )}


@frappe.whitelist(methods=["POST"])
def import_inx_export(file_name, dry_run=True, expected_sha256=None):
    """Preview by default. An explicit import creates disabled lessons for review."""
    _require_manager()
    file_doc = frappe.get_doc("File", file_name)
    file_doc.check_permission("read")
    if not cint(file_doc.is_private) or not str(file_doc.file_url or "").startswith("/private/files/"):
        frappe.throw(_("Upload the INX export as a private local file."), frappe.ValidationError)
    if not str(file_doc.file_name or "").lower().endswith(".xlsx"):
        frappe.throw(_("Choose an INX XLSX export."), frappe.ValidationError)
    content = file_doc.get_content()
    digest = hashlib.sha256(content).hexdigest()
    if str(dry_run).lower() not in {"true", "false", "1", "0"}:
        frappe.throw(_("Dry run must be true or false."), frappe.ValidationError)
    preview = str(dry_run).lower() in {"true", "1"}
    if not preview and expected_sha256 != digest:
        frappe.throw(_("Preview this file before importing. The export has changed or its preview is missing."), frappe.ValidationError)
    try:
        parsed = parse_workbook(content)
    except ValueError as exc:
        frappe.throw(_(str(exc)), frappe.ValidationError)
    records = parsed["records"]
    names = [record["source_key"] for record in records]
    sources = _existing(SOURCE_DOCTYPE, names, ["source_fingerprint"])
    lessons = _existing(LEARNING_DOCTYPE, names, ["available_for_jha"])
    changed = {record["source_key"] for record in records
               if sources.get(record["source_key"], {}).get("source_fingerprint") != record["source_fingerprint"]}
    report = {
        "dry_run": preview, "file_sha256": digest, "row_count": len(records),
        "new_sources": len(set(names) - sources.keys()),
        "changed_sources": len(changed & sources.keys()),
        "unchanged_sources": len(names) - len(changed),
        "new_lessons": len(set(names) - lessons.keys()),
        "enabled_lessons_returning_to_review": sum(cint(lessons[key]["available_for_jha"]) for key in changed & lessons.keys()),
        "ignored_columns": parsed["ignored_columns"],
        "missing_review_summaries": parsed["missing_review_summaries"],
        "investigation_actions_provided": False,
    }
    if preview:
        return report
    frappe.db.savepoint("inx_incident_import")
    try:
        for record in sorted(records, key=lambda row: row["source_key"]):
            _upsert(record, file_doc.file_url)
        # The uploaded workbook inherits the restricted source record's attachment permissions.
        file_doc.attached_to_doctype = SOURCE_DOCTYPE
        file_doc.attached_to_name = records[0]["source_key"]
        file_doc.save()
    except Exception:
        frappe.db.rollback(save_point="inx_incident_import")
        raise
    return report


def _upsert(record, file_url):
    key = record["source_key"]
    # Match the lesson-save lock order before validating its restricted source.
    lesson_exists = frappe.db.get_value(LEARNING_DOCTYPE, key, "name", for_update=True)
    exists = frappe.db.get_value(SOURCE_DOCTYPE, key, "name", for_update=True)
    source = frappe.get_doc(SOURCE_DOCTYPE, key, for_update=True) if exists else frappe.new_doc(SOURCE_DOCTYPE)
    source_changed = not exists or source.source_fingerprint != record["source_fingerprint"]
    if source_changed:
        source.update(record)
        source.source_file = file_url
        source.imported_at = now_datetime()
        source.save()  # on_update withdraws an older lesson until its new source is reviewed.
    if lesson_exists and not source_changed:
        return
    lesson = frappe.get_doc(LEARNING_DOCTYPE, key, for_update=True) if lesson_exists else frappe.new_doc(LEARNING_DOCTYPE)
    if not lesson_exists:
        lesson.source_system = SOURCE_SYSTEM
        lesson.source_reference = record["source_reference"]
        lesson.title = f"INX incident {record['source_reference']}"[:140]
        lesson.incident_summary = ""
        lesson.critical_risks = source.suggested_critical_risks
        lesson.mechanisms = source.suggested_mechanisms
    # Source columns never overwrite curated summaries, actions, controls or risk tags.
    lesson.inx_source = key
    lesson.available_for_jha = 0
    lesson.source_review_required = 1
    lesson.save()
