"""Human field checks and authenticated, live revision status for JHA workpacks."""
from __future__ import annotations

import hashlib
import json
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime, today

from verto.api.mobile import voice_jha_review as review
from verto.api.mobile.voice_jha_permissions import user_can_access_work_summary

VERIFICATION_DOCTYPE = "JHA Control Verification"
CCV_DOCTYPE = "Critical Control Verification"
CCV_PREFIXES = {
    "Confined Space": "cs_", "Contact with Electricity": "cwe_", "Dropped Objects": "do_",
    "Entanglement & Crushing": "eac_", "Fall from Height": "ffh_", "Hot Works": "hw_",
    "Lifting Operations": "lo_", "Uncontrolled Release of Energy": "ure_",
    "Vehicle & Mobile Equipment": ("vme_", "vms_"), "Working near Water": "wnw_",
}


def locked_jha(jha_name, *, allow_closed=False):
    review._require_login()
    doc = review._get_jha(jha_name, require_write=True)
    frappe.db.sql("select name from `tabDigital Job Hazard Analysis` where name=%s for update", doc.name)
    doc.reload()
    if doc.mark_review_required_if_source_changed():
        doc.flags.allow_jha_review_mutation = True
        doc.save(ignore_permissions=True)
    if not allow_closed and (doc.jha_status not in {"Ready for Team Review", "Signed"} or doc.get("replacement_jha")):
        frappe.throw(_("Use the current reviewed JHA revision for field checks."), frappe.ValidationError)
    return doc


def workpack_path(doc):
    return f"/verto-mobile/jha/{quote(doc.name, safe='')}?revision={cint(doc.revision or 1)}"


def _ccv_for_jha(doc, name):
    ccv = frappe.get_doc(CCV_DOCTYPE, name)
    if not ccv.has_permission("read"):
        frappe.throw(_("You cannot access this CCV."), frappe.PermissionError)
    if ccv.link_task != doc.work_summary or ccv.link_project != doc.project or cint(ccv.docstatus) == 2:
        frappe.throw(_("Choose a CCV for this JHA's Work Summary and project."), frappe.ValidationError)
    return ccv


def ccv_snapshot(ccv, *, require_complete=False):
    prefix = CCV_PREFIXES.get(ccv.get("ccv_selected"))
    fields = [field for field in ccv.meta.fields if prefix and field.fieldname.startswith(prefix)
              and field.fieldtype == "Select" and "No" in (field.options or "").splitlines()]
    answers = {field.fieldname: str(ccv.get(field.fieldname) or "") for field in fields}
    if require_complete and (
        not fields or not ccv.get("signature") or ccv.get("safety_category") != "Good Controls"
        or any(value not in {"Yes", "Yes (Fixed on the spot)", "N/A"} for value in answers.values())
        or not any(value.startswith("Yes") for value in answers.values())
    ):
        frappe.throw(_("A verified result needs a signed CCV with Good Controls and all applicable checks answered without a No."), frappe.ValidationError)
    return {"name": ccv.name, "modified": str(ccv.modified), "type": ccv.get("ccv_selected"),
            "safety_category": ccv.get("safety_category"), "answers": answers}


def verification_rows(doc):
    return frappe.get_all(VERIFICATION_DOCTYPE, filters={"jha": doc.name},
        fields=["name", "hazard_row", "work_step", "critical_control", "result", "ccv", "ccv_modified", "verified_by", "verifier_name",
                "verified_at", "evidence", "notes"], order_by="creation desc, name desc")


def control_state(doc):
    rows = verification_rows(doc)
    latest = {}
    for row in rows:
        latest.setdefault(row.hazard_row, row)
    controls = []
    for hazard in doc.hazards_and_controls or []:
        if not (cint(hazard.get("critical_risk")) or hazard.get("critical_control")):
            continue
        record = latest.get(hazard.name)
        status = record.result if record else "Pending"
        # A mutable CCV cannot silently change the evidence behind an old check.
        if record and record.result == "Verified":
            current = frappe.db.get_value(CCV_DOCTYPE, record.ccv,
                ["modified", "docstatus", "link_task", "link_project"], as_dict=True) if record.ccv else None
            if (not current or cint(current.docstatus) == 2 or current.link_task != doc.work_summary
                or current.link_project != doc.project
                or get_datetime(current.modified) != get_datetime(record.ccv_modified)):
                status = "Recheck Required"
        controls.append({"name": hazard.name, "step": hazard.work_step_sequence,
            "hazard": hazard.hazard_or_energy_source, "control": hazard.get("critical_control") or hazard.get("existing_controls"),
            "owner": hazard.get("control_owner"), "method": hazard.get("verification_method"),
            "status": status, "latest": dict(record) if record else None,
            "history": [dict(row) for row in rows if row.hazard_row == hazard.name]})
    return controls


@frappe.whitelist(methods=["GET"])
def get_jha_fieldwork(jha_name: str):
    from verto.api.mobile.voice_jha_revalidation import shift_reviews
    from verto.api.mobile.documents import get_allowed_mobile_doctypes, get_mobile_slug_for_doctype
    review._require_login()
    doc = review._get_jha(jha_name)
    frappe.local.response_headers["Cache-Control"] = "no-store"
    ccv_options = frappe.get_list(CCV_DOCTYPE,
        filters={"link_task": doc.work_summary, "link_project": doc.project, "docstatus": ["!=", 2]},
        fields=["name", "ccv_selected", "safety_category", "modified"], order_by="modified desc", page_length=200
    ) if frappe.has_permission(CCV_DOCTYPE, "read") else []
    can_write = doc.has_permission("write") and not doc.get("replacement_jha")
    create_path = None
    if (CCV_DOCTYPE in get_allowed_mobile_doctypes().values() and frappe.has_permission(CCV_DOCTYPE, "create")):
        slug = get_mobile_slug_for_doctype(CCV_DOCTYPE)
        create_path = f"/verto-mobile/new/{quote(slug, safe='')}?link_task={quote(doc.work_summary, safe='')}&project={quote(doc.project or '', safe='')}"
    return {"name": doc.name, "revision": doc.revision, "status": doc.jha_status, "today": today(),
            "workpack_path": workpack_path(doc), "controls": control_state(doc), "ccv_options": ccv_options,
            "ccv_create_path": create_path,
            "can_verify": bool(can_write and doc.jha_status in {"Ready for Team Review", "Signed"}),
            "can_revalidate": bool(can_write and doc.jha_status == "Signed"), "shift_reviews": shift_reviews(doc)}


@frappe.whitelist(methods=["POST"])
def record_jha_control_verification(jha_name: str, hazard_row: str, result: str, request_id: str,
                                    ccv: str = "", evidence: str = "", notes: str = "", confirmation=0):
    doc = locked_jha(jha_name)
    if not cint(confirmation) or result not in {"Verified", "Failed"}:
        frappe.throw(_("Confirm your on-site check and choose Verified or Failed."), frappe.ValidationError)
    if not request_id or len(request_id) > 100 or len(notes) > 4000:
        frappe.throw(_("Supply a request ID and notes of no more than 4,000 characters."), frappe.ValidationError)
    hazard = next((row for row in doc.hazards_and_controls or [] if row.name == hazard_row), None)
    if not hazard or not (cint(hazard.get("critical_risk")) or hazard.get("critical_control")):
        frappe.throw(_("Choose a critical control on this JHA revision."), frappe.ValidationError)
    key = hashlib.sha256(f"{frappe.session.user}|{doc.name}|{request_id}".encode()).hexdigest()
    fingerprint = hashlib.sha256(json.dumps([hazard_row, result, ccv, evidence, notes]).encode()).hexdigest()
    existing = frappe.db.get_value(VERIFICATION_DOCTYPE, {"request_key": key}, ["name", "request_fingerprint"], as_dict=True)
    if existing:
        if existing.request_fingerprint != fingerprint:
            frappe.throw(_("This request ID was already used for a different check."), frappe.ValidationError)
        return {"name": existing.name, "replayed": True}
    if result == "Verified" and not ccv:
        frappe.throw(_("Link the completed CCV supporting your verification."), frappe.ValidationError)
    if result == "Failed" and not notes.strip():
        frappe.throw(_("Describe the failed control and action needed."), frappe.ValidationError)
    if ccv:
        frappe.db.sql("select name from `tabCritical Control Verification` where name=%s for update", ccv)
    source = _ccv_for_jha(doc, ccv) if ccv else None
    snapshot = ccv_snapshot(source, require_complete=result == "Verified") if source else {}
    if evidence:
        if not evidence.startswith(("/files/", "/private/files/")):
            frappe.throw(_("Choose an attached evidence file."), frappe.ValidationError)
        files = frappe.get_all("File", filters={"file_url": evidence},
            fields=["name", "attached_to_doctype", "attached_to_name"])
        allowed = {(review.JHA_DOCTYPE, doc.name), (CCV_DOCTYPE, ccv)}
        if not any((file.attached_to_doctype, file.attached_to_name) in allowed
                   and frappe.get_doc("File", file.name).has_permission("read") for file in files):
            frappe.throw(_("Evidence must be attached to this JHA or its selected CCV."), frappe.PermissionError)
    record = frappe.get_doc({"doctype": VERIFICATION_DOCTYPE, "jha": doc.name, "revision": doc.revision,
        "work_summary": doc.work_summary, "project": doc.project, "hazard_row": hazard.name,
        "work_step": hazard.work_step_sequence, "critical_control": hazard.get("critical_control") or hazard.get("existing_controls"),
        "result": result, "ccv": ccv or None, "ccv_modified": source.modified if source else None,
        "ccv_snapshot": json.dumps(snapshot), "verified_by": frappe.session.user,
        "verifier_name": review._reviewer_name(frappe.session.user), "verified_at": now_datetime(),
        "evidence": evidence, "notes": notes.strip(), "request_key": key, "request_fingerprint": fingerprint})
    record.flags.allow_jha_field_mutation = True
    record.insert(ignore_permissions=True)
    return {"name": record.name, "replayed": False}


@frappe.whitelist(methods=["GET"])
def get_jha_workpack_status(jha_name: str, revision=None):
    review._require_login()
    original = review._get_jha(jha_name)
    current = original
    seen = {original.name}
    while current.get("replacement_jha"):
        name = current.replacement_jha
        if name in seen or len(seen) >= 100:
            frappe.throw(_("The JHA revision chain needs administrator review."), frappe.ValidationError)
        seen.add(name)
        replacement = review._get_jha(name)
        if replacement.work_summary != original.work_summary or replacement.get("previous_jha") != current.name:
            frappe.throw(_("The JHA revision link is invalid."), frappe.ValidationError)
        current = replacement
    frappe.local.response_headers["Cache-Control"] = "no-store"
    mismatch = revision is not None and cint(revision) != cint(original.revision or 1)
    return {"requested": {"name": original.name, "revision": original.revision, "status": original.jha_status},
        "is_current": original.name == current.name and not mismatch, "revision_mismatch": mismatch,
        "current": {"name": current.name, "revision": current.revision, "status": current.jha_status,
                    "title": current.work_summary_title, "work_summary": current.work_summary},
        "controls": control_state(current), "checked_at": str(now_datetime()),
        "requires_review": mismatch or current.jha_status != "Signed"}


def field_record_has_permission(doc, user=None, ptype=None, permission_type=None, **kwargs):
    user = user or frappe.session.user
    if (ptype or permission_type or "read") not in {"read", "print", "report", "export"}:
        return False
    return bool(doc and user_can_access_work_summary(doc.get("work_summary"), user)
                and frappe.has_permission(review.JHA_DOCTYPE, "read", doc=doc.get("jha"), user=user))


def _query_conditions(doctype, user=None):
    from verto.api.mobile.voice_jha_permissions import get_permission_query_conditions
    return get_permission_query_conditions(user).replace(f"`tab{review.JHA_DOCTYPE}`", f"`tab{doctype}`")


def verification_query_conditions(user=None):
    return _query_conditions(VERIFICATION_DOCTYPE, user)


def shift_query_conditions(user=None):
    return _query_conditions("JHA Shift Revalidation", user)
