"""Revision-bound supporting records. These never alter the signed JHA content."""
from __future__ import annotations

import hashlib
import json
import math

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime

from verto.api.mobile import voice_jha_review as review
from verto.api.mobile.voice_jha_fieldwork import locked_jha

DOCTYPE = "JHA Step Resource"
KINDS = {"Permit", "Isolation", "Document", "Photo"}
FIELDS = ["name", "kind", "step_row", "work_step", "step_activity", "reference", "details", "evidence",
          "annotations", "expires_at", "status", "ehs_permit", "source_snapshot", "replaces", "recorded_by",
          "recorder_name", "recorded_at", "observed_at", "work_changed", "job_template", "stale_revision"]


def text(value, limit=4000, *, required=False):
    value = str(value or "").strip()
    if len(value) > limit or (required and not value):
        frappe.throw(_("Supply the required text within the displayed length limit."), frappe.ValidationError)
    return value


def json_value(value, default):
    try:
        return json.loads(value) if isinstance(value, str) else value if value is not None else default
    except (ValueError, TypeError):
        frappe.throw(_("Invalid JSON data."), frappe.ValidationError)


def _step(jha, step_row, *, optional=False):
    if optional and not step_row:
        return None
    row = next((s for s in jha.work_steps or [] if s.name == step_row), None)
    if not row:
        frappe.throw(_("Select a work step on this exact JHA revision."), frappe.ValidationError)
    return row


def _annotations(value):
    points = json_value(value, [])
    if not isinstance(points, list) or len(points) > 20:
        frappe.throw(_("A photo can have up to 20 annotation markers."), frappe.ValidationError)
    result = []
    for point in points:
        if not isinstance(point, dict):
            frappe.throw(_("Invalid photo annotation."), frappe.ValidationError)
        x, y = point.get("x"), point.get("y")
        if any(isinstance(n, bool) or not isinstance(n, (float, int)) or not math.isfinite(n) or not 0 <= n <= 1 for n in (x, y)):
            frappe.throw(_("Photo markers must be inside the image."), frappe.ValidationError)
        result.append({"x": x, "y": y, "label": text(point.get("label"), 180, required=True)})
    return result


def evidence_file(jha, url, *, photo=False):
    if not str(url).startswith("/private/files/"):
        frappe.throw(_("Upload a private file attached to this JHA."), frappe.ValidationError)
    files = frappe.get_all("File", filters={"file_url": url, "attached_to_doctype": review.JHA_DOCTYPE,
                                           "attached_to_name": jha.name, "is_private": 1}, pluck="name")
    file = next((doc for name in files if (doc := frappe.get_doc("File", name)).has_permission("read")), None)
    if not file:
        frappe.throw(_("The supporting file must be readable and attached to this JHA."), frappe.PermissionError)
    if photo:
        from io import BytesIO
        from PIL import Image, UnidentifiedImageError
        try:
            content = file.get_content()
            if not isinstance(content, bytes) or len(content) > 10 * 1024 * 1024:
                raise ValueError
            with Image.open(BytesIO(content)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > 40_000_000:
                    raise ValueError
                image.verify()
        except (ValueError, OSError, UnidentifiedImageError):
            frappe.throw(_("Use a valid JPG, PNG or WebP photo up to 10 MB and 40 megapixels."), frappe.ValidationError)
    return file


def _insert(jha, request_id, values):
    request_id = text(request_id, 100, required=True)
    key = hashlib.sha256(f"{frappe.session.user}|{jha.name}|{request_id}".encode()).hexdigest()
    fingerprint = hashlib.sha256(json.dumps({key: value for key, value in values.items()
        if key not in {"source_snapshot", "step_activity", "work_step", "stale_revision"}}, sort_keys=True, default=str).encode()).hexdigest()
    previous = frappe.db.get_value(DOCTYPE, {"request_key": key}, ["name", "request_fingerprint"], as_dict=True)
    if previous:
        if previous.request_fingerprint != fingerprint:
            frappe.throw(_("This request ID has already been used for a different record."), frappe.ValidationError)
        return frappe.get_doc(DOCTYPE, previous.name), True
    doc = frappe.get_doc({"doctype": DOCTYPE, "jha": jha.name, "revision": jha.revision,
        "work_summary": jha.work_summary, "project": jha.project, **values,
        "recorded_by": frappe.session.user, "recorder_name": review._reviewer_name(frappe.session.user),
        "recorded_at": now_datetime(), "request_key": key, "request_fingerprint": fingerprint})
    doc.flags.allow_jha_workpack_mutation = True
    doc.insert(ignore_permissions=True)
    return doc, False


def _mark_changed(jha, description):
    if jha.jha_status in {"Signed", "Ready for Team Review"}:
        jha.jha_status = "Review Required - Work Changed"
        review._append_review_audit(jha, "workpack_change_reported", {"description": description[:1000]})
        jha.flags.allow_jha_review_mutation = True
        jha.save(ignore_permissions=True)


def resource_rows(jha):
    return frappe.get_all(DOCTYPE, filters={"jha": jha.name}, fields=FIELDS,
                          order_by="creation desc, name desc", limit_page_length=0)


def resource_state(jha):
    rows = resource_rows(jha)
    steps = {row.name: row for row in jha.work_steps or []}
    replaced = {row.replaces for row in rows if row.replaces}
    result = []
    for row in rows:
        item = dict(row)
        item["annotations"] = json_value(row.annotations, [])
        item["historical"] = row.name in replaced
        item["effective_status"] = row.status
        if not item["historical"] and row.kind in {"Permit", "Isolation", "Document"} and row.status != "Withdrawn":
            if row.expires_at and get_datetime(row.expires_at) <= now_datetime():
                item["effective_status"] = "Expired"
            if row.ehs_permit:
                source = frappe.db.get_value("EHS Permit", row.ehs_permit,
                    ["modified", "docstatus", "permit_status", "start", "end"], as_dict=True)
                saved = json_value(row.source_snapshot, {})
                if (not source or cint(source.docstatus) == 2 or source.permit_status not in {"Active", "Approved"}
                    or str(source.modified) != saved.get("modified")):
                    item["effective_status"] = "Recheck Required"
                elif source.end and get_datetime(source.end) <= now_datetime():
                    item["effective_status"] = "Expired"
                elif source.start and get_datetime(source.start) > now_datetime():
                    item["effective_status"] = "Not Yet Valid"
        if row.kind in KINDS:
            step = steps.get(row.step_row)
            item["recorded_work_step"] = row.work_step
            if not step:
                item["historical"] = True
                item["step_changed"] = True
            else:
                item["work_step"] = step.sequence
                item["step_changed"] = step.activity != row.step_activity
                if item["step_changed"] and row.status != "Withdrawn":
                    item["effective_status"] = "Recheck Required"
        # Only expose a file URL while the current user can still read it.
        if row.evidence:
            try:
                evidence_file(jha, row.evidence)
            except (frappe.PermissionError, frappe.ValidationError):
                item["evidence"] = None
                item["evidence_unavailable"] = True
        item.pop("source_snapshot", None)
        result.append(item)
    return result


def earlier_photos(jha):
    result, current, seen = [], jha, {jha.name}
    while current.get("previous_jha") and len(seen) < 20:
        if current.previous_jha in seen:
            break
        previous = review._get_jha(current.previous_jha)
        if previous.work_summary != jha.work_summary:
            break
        seen.add(previous.name)
        for row in resource_state(previous):
            if row["kind"] == "Photo" and not row["historical"]:
                result.append({**row, "source_jha": previous.name, "source_revision": previous.revision})
        current = previous
    return result


@frappe.whitelist(methods=["GET"])
def get_jha_resources(jha_name: str):
    review._require_login()
    jha = review._get_jha(jha_name)
    frappe.local.response_headers["Cache-Control"] = "no-store"
    old_observations = frappe.get_all(DOCTYPE, filters={"work_summary": jha.work_summary, "kind": "Observation",
        "jha": ["!=", jha.name]}, fields=["name", "jha", "revision", "work_step", "step_activity", "details", "recorded_by", "recorded_at", "work_changed"],
        order_by="creation desc", limit_page_length=100)
    return {"items": resource_state(jha), "earlier_photos": earlier_photos(jha), "earlier_observations": old_observations, "can_record": bool(jha.has_permission("write")
        and not jha.get("replacement_jha") and jha.jha_status not in {"Superseded", "Cancelled"}),
        "can_observe": bool(jha.has_permission("write")), "server_time": str(now_datetime())}


@frappe.whitelist(methods=["POST"])
def record_jha_resource(jha_name: str, step_row: str, kind: str, request_id: str, reference: str = "",
                        details: str = "", evidence: str = "", annotations="[]", expires_at=None,
                        status: str = "Pending", ehs_permit: str = "", replaces: str = "", confirmation=0, work_changed=0):
    jha = locked_jha(jha_name, allow_closed=True)
    if jha.get("replacement_jha") or jha.jha_status in {"Cancelled", "Superseded"}:
        frappe.throw(_("Add supporting records to the current JHA revision."), frappe.ValidationError)
    if kind not in KINDS or status not in {"Pending", "Confirmed", "Withdrawn"}:
        frappe.throw(_("Choose a valid supporting record and confirmation state."), frappe.ValidationError)
    if not cint(confirmation):
        frappe.throw(_("Confirm that you checked the supporting record."), frappe.ValidationError)
    step = _step(jha, step_row)
    if kind == "Photo" and status != "Confirmed":
        frappe.throw(_("Record a photo with its description."), frappe.ValidationError)
    points = _annotations(annotations) if kind == "Photo" else []
    if evidence:
        evidence_file(jha, evidence, photo=kind == "Photo")
    if kind == "Photo" and not evidence:
        frappe.throw(_("Attach the photo before saving."), frappe.ValidationError)
    if kind == "Document" and not evidence:
        frappe.throw(_("Attach the relevant document."), frappe.ValidationError)
    if kind in {"Permit", "Isolation"} and not (reference or ehs_permit):
        frappe.throw(_("Enter the actual permit or isolation record number."), frappe.ValidationError)
    expiry = None
    if expires_at:
        try:
            expiry = str(get_datetime(expires_at))
        except (ValueError, TypeError):
            frappe.throw(_("Enter a valid expiry date and time."), frappe.ValidationError)
    snapshot = {}
    if ehs_permit:
        if kind != "Permit":
            frappe.throw(_("Only a permit record can link an EHS Permit."), frappe.ValidationError)
        source = frappe.get_doc("EHS Permit", ehs_permit)
        if not source.has_permission("read"):
            frappe.throw(_("You cannot access that EHS Permit."), frappe.PermissionError)
        snapshot = {key: str(source.get(key) or "") for key in ("modified", "start", "end", "permit_status", "docstatus")}
    substantive_change = False
    if replaces:
        previous = frappe.get_doc(DOCTYPE, replaces)
        if previous.jha != jha.name or previous.step_row != step.name or previous.kind != kind:
            frappe.throw(_("Replace a supporting record for the same revision and step."), frappe.ValidationError)
        substantive_change = kind in {"Permit", "Isolation"} and (status == "Withdrawn" or any(
            str(previous.get(key) or "") != str(value or "") for key, value in
            (("reference", reference), ("ehs_permit", ehs_permit), ("evidence", evidence), ("expires_at", expiry))))
        if frappe.db.exists(DOCTYPE, {"replaces": replaces}):
            existing = frappe.db.get_value(DOCTYPE, {"request_key": hashlib.sha256(f"{frappe.session.user}|{jha.name}|{request_id}".encode()).hexdigest()}, "name")
            if not existing:
                frappe.throw(_("This record has already been replaced. Refresh the workpack."), frappe.ValidationError)
    if status == "Withdrawn" and not replaces:
        frappe.throw(_("Choose the record being withdrawn."), frappe.ValidationError)
    values = {"kind": kind, "step_row": step.name, "work_step": step.sequence, "step_activity": step.activity,
        "reference": text(reference, 140), "details": text(details, required=True), "evidence": evidence or None,
        "annotations": json.dumps(points), "expires_at": expiry, "status": status, "ehs_permit": ehs_permit or None,
        "source_snapshot": json.dumps(snapshot, sort_keys=True), "replaces": replaces or None, "work_changed": cint(work_changed)}
    doc, replayed = _insert(jha, request_id, values)
    if not replayed and (cint(work_changed) or substantive_change):
        _mark_changed(jha, values["details"])
    return {"name": doc.name, "replayed": replayed, "jha_status": jha.jha_status}


@frappe.whitelist(methods=["POST"])
def record_jha_observation(jha_name: str, revision: int, request_id: str, actor: str, notes: str,
                           step_row: str = "", work_changed=0, observed_at: str = ""):
    # Also used by the durable offline queue. The authenticated actor and exact
    # old revision are checked again on every retry; never rebase an observation.
    review._require_login()
    if actor != frappe.session.user:
        frappe.throw(_("Sign in as the person who recorded this offline observation."), frappe.PermissionError)
    jha = locked_jha(jha_name, allow_closed=True)
    if cint(revision) != cint(jha.revision):
        frappe.throw(_("The observation revision does not match the selected JHA."), frappe.ValidationError)
    step = _step(jha, step_row, optional=True)
    values = {"kind": "Observation", "status": "Recorded", "details": text(notes, required=True),
        "step_row": step.name if step else None, "work_step": step.sequence if step else 0,
        "step_activity": step.activity if step else "Whole job", "work_changed": cint(work_changed),
        "observed_at": text(observed_at, 80), "stale_revision": cint(bool(jha.get("replacement_jha") or jha.jha_status == "Superseded"))}
    doc, replayed = _insert(jha, request_id, values)
    if not replayed and cint(work_changed):
        _mark_changed(jha, values["details"])
        current, seen = jha, {jha.name}
        while current.get("replacement_jha"):
            if current.replacement_jha in seen or len(seen) >= 100:
                frappe.throw(_("The JHA revision chain needs administrator review."), frappe.ValidationError)
            replacement = review._get_jha(current.replacement_jha, require_write=True)
            if replacement.work_summary != jha.work_summary or replacement.previous_jha != current.name:
                frappe.throw(_("The linked JHA revision is invalid."), frappe.ValidationError)
            seen.add(replacement.name)
            frappe.db.sql("select name from `tabDigital Job Hazard Analysis` where name=%s for update", replacement.name)
            replacement.reload()
            current = replacement
        if current.name != jha.name:
            _mark_changed(current, f"Reported on {jha.name} revision {jha.revision}: {values['details']}")
    return {"name": doc.name, "replayed": replayed, "stale_revision": bool(values["stale_revision"]),
        "jha_status": jha.jha_status, "message": "Recorded against an old revision. Review this observation on the current JHA."
        if values["stale_revision"] else "Observation recorded; review any reported work change before continuing affected work."}


@frappe.whitelist(methods=["GET"])
def download_jha_offline(jha_name: str):
    from verto.api.mobile.voice_jha_progress import serialize_jha
    review._require_login()
    jha = review._get_jha(jha_name)
    if jha.jha_status != "Signed" or jha.get("replacement_jha"):
        frappe.throw(_("Download the current signed revision for offline reference."), frappe.ValidationError)
    frappe.local.response_headers["Cache-Control"] = "no-store"
    snapshot = serialize_jha(jha)
    return {"user": frappe.session.user, "saved_at": str(now_datetime()), "jha": {key: snapshot.get(key) for key in
        ("name", "revision", "status", "project", "work_summary", "work_summary_title", "work_area", "work_order_number",
         "work_steps", "hazards_and_controls", "participants")}, "review": review._serialize_review(jha),
        "resources": [row for row in resource_state(jha) if row["kind"] in KINDS],
        "notice": "Downloaded signed copy. Current revision, permits and field conditions cannot be confirmed offline."}


def resource_query_conditions(user=None):
    from verto.api.mobile.voice_jha_fieldwork import _query_conditions
    return _query_conditions(DOCTYPE, user)


def outstanding_references(jha):
    if not frappe.db.exists("DocType", DOCTYPE):
        return []
    return [row for row in resource_state(jha) if not row["historical"]
            and row["kind"] in {"Permit", "Isolation"} and row["effective_status"] != "Confirmed"]


@frappe.whitelist(methods=["POST"])
def begin_workpack_change(jha_name: str, confirmation=0):
    from verto.api.mobile.voice_jha_changes import begin_jha_change
    from verto.api.mobile.voice_jha_progress import serialize_jha
    review._require_login()
    original = review._get_jha(jha_name, require_write=True)
    # The normal change workflow serializes duplicate taps and retains signatures.
    snapshot = begin_jha_change(jha_name, confirmation=confirmation)
    revision = frappe.get_doc(review.JHA_DOCTYPE, snapshot["name"])
    if revision.change_management_stage == "Describe Change" and not revision.change_summary:
        rows = resource_rows(original)
        changed = [f"Step {row.work_step or 'all'}: {row.details}" for row in rows
                   if cint(row.work_changed) or row.replaces and row.kind in {"Permit", "Isolation"}]
        filters = {"work_summary": original.work_summary, "kind": "Observation", "jha": ["!=", original.name], "work_changed": 1}
        if original.get("signed_at"):
            filters["recorded_at"] = [">", original.signed_at]
        older = frappe.get_all(DOCTYPE, filters=filters, fields=["jha", "revision", "work_step", "details"],
            order_by="creation desc", limit_page_length=20)
        changed.extend(f"Observation on {row.jha} revision {row.revision}, step {row.work_step or 'all'}: {row.details}" for row in older)
        revision.change_summary = "\n".join(changed)[:10000]
        revision.flags.allow_jha_change_mutation = True
        revision.save()
    return serialize_jha(revision)
