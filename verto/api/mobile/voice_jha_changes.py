"""Human-started, scoped amendments of reviewed JHAs."""
from __future__ import annotations

import json
from uuid import uuid4

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from verto.api.mobile import voice_jha_tools as tools
from verto.api.mobile.voice_jha_progress import calculate_facilitation_progress, serialize_jha


CHANGE_TOOLS = {"record_jha_change_request", "add_jha_change_step", "confirm_jha_changes"}


def target_steps(doc) -> list[int]:
    try:
        values = json.loads(doc.get("change_target_steps") or "[]")
    except (TypeError, ValueError):
        values = []
    return sorted({cint(value) for value in values if cint(value) > 0}) if isinstance(values, list) else []


@frappe.whitelist(methods=["POST"])
def begin_jha_change(jha_name: str, confirmation=0):
    from verto.api.mobile import voice_jha_review as review

    review._require_login()
    if not cint(confirmation):
        frappe.throw(_("Confirm that a new change revision should be started."), frappe.ValidationError)
    original = review._get_jha(jha_name, require_write=True)
    # Serialize duplicate taps/requests against this reviewed revision.
    frappe.db.sql("select name from `tabDigital Job Hazard Analysis` where name=%s for update", original.name)
    original.reload()
    if original.get("replacement_jha"):
        replacement = review._get_jha(original.replacement_jha, require_write=True)
        if replacement.get("previous_jha") != original.name or replacement.work_summary != original.work_summary:
            frappe.throw(_("The linked change revision is invalid."), frappe.ValidationError)
        return serialize_jha(replacement)
    if original.jha_status not in {"Ready for Team Review", "Signed", "Review Required - Work Changed"}:
        frappe.throw(_("Start change management from a reviewed JHA."), frappe.ValidationError)

    revision = frappe.copy_doc(original)
    revision.revision = cint(original.revision or 1) + 1
    revision.previous_jha = original.name
    revision.replacement_jha = None
    revision.jha_status = "Incomplete - Actions Required"
    revision.change_management_stage = "Describe Change"
    revision.change_summary = ""
    revision.change_target_steps = "[]"
    revision.change_participants = 0
    revision.change_requested_by = frappe.session.user
    revision.change_requested_at = now_datetime()
    for field in ("reviewed_by", "reviewer_name", "reviewed_at", "review_signature", "review_notes",
                  "signed_at", "signed_by_user", "voice_model", "voice_started_at", "voice_session_reference",
                  "voice_transcription_consent_confirmed_by", "voice_transcription_consent_confirmed_at",
                  "voice_tool_audit_log", "review_audit_log"):
        revision.set(field, None)
    revision.review_completed = 0
    revision.voice_transcription_consent_confirmed = 0
    for row in revision.work_steps or []:
        row.source_step_identifier = row.get("source_step_identifier") or f"step-{row.sequence}"
    hazard_ids = {}
    for index, (before, row) in enumerate(zip(original.hazards_and_controls or [], revision.hazards_and_controls or []), 1):
        row.source_hazard_identifier = row.get("source_hazard_identifier") or f"hazard-{index}"
        hazard_ids[before.get("source_hazard_identifier") or before.name] = row.source_hazard_identifier
        step = next((s for s in revision.work_steps if cint(s.sequence) == cint(row.work_step_sequence)), None)
        if step:
            row.work_step_reference = step.source_step_identifier
    for row in revision.incident_references or []:
        row.jha_revision = revision.revision
        row.hazard_identifier = hazard_ids.get(row.hazard_identifier, row.hazard_identifier)
    for index, row in enumerate(revision.participants or [], 1):
        row.source_participant_identifier = row.get("source_participant_identifier") or f"participant-{index}"
        row.acknowledged = 0
        row.transcription_consent = 0
        row.acknowledged_at = row.acknowledged_by_user = row.acknowledgement_signature = None
    revision.flags.allow_jha_review_mutation = True
    revision.flags.allow_jha_change_mutation = True
    revision.flags.allow_jha_incident_mutation = True
    review._append_review_audit(revision, "change_revision_started", {
        "previous_jha": original.name, "from_revision": original.revision, "to_revision": revision.revision,
    })
    revision.insert()

    # Retain the original content and signatures; prevent reuse of its workpack
    # while changed work is being assessed in the separate revision.
    original.replacement_jha = revision.name
    original.jha_status = "Review Required - Work Changed"
    original.flags.allow_jha_review_mutation = True
    original.flags.allow_jha_change_mutation = True
    review._append_review_audit(original, "change_revision_opened", {"replacement_jha": revision.name})
    original.save()
    return serialize_jha(revision)


def get_change_tools() -> list[dict]:
    def tool(name, description, properties, required):
        return {"type": "function", "name": name, "description": description,
                "parameters": {"type": "object", "properties": properties, "required": required,
                               "additionalProperties": False}}
    return [
        tool("record_jha_change_request",
             "For a human-started change revision only: record what changed and the existing step numbers "
             "the crew explicitly confirmed are affected. Use an empty step list if a new step must be added "
             "next. Set participant_changes only when the crew identifies a participant change. "
             "Only these affected steps will be reassessed; this never approves work.",
             {"summary": {"type": "string"}, "affected_step_sequences": {"type": "array", "items": {"type": "integer", "minimum": 1}},
              "participant_changes": {"type": "boolean"}}, ["summary", "affected_step_sequences"]),
        tool("add_jha_change_step",
             "Insert a new work step into a change revision only after the crew confirms its activity and "
             "placement. after_step_sequence=0 inserts first. Existing steps and hazard references are "
             "renumbered together. Do not use record_work_step to insert a new change step.",
             {"activity": {"type": "string"}, "after_step_sequence": {"type": "integer", "minimum": 0}},
             ["activity", "after_step_sequence"]),
        tool("confirm_jha_changes",
             "After all affected steps have been reassessed, briefly read back the requested changes and "
             "call only after the crew explicitly confirms they are captured correctly. Human review and "
             "sign-on are still required; this never signs, approves or authorises work.", {}, []),
    ]


def validate_change_scope(doc, name: str, args: dict):
    if not doc.get("previous_jha"):
        return False
    if doc.get("change_management_stage") == "Describe Change":
        frappe.throw(_("First confirm what changed and which JHA steps are affected."), frappe.ValidationError)
    if name == "confirm_job_steps":
        frappe.throw(_("Use the confirmed change scope; the original step list does not need restarting."), frappe.ValidationError)
    if name == "record_participant":
        row = tools._find_participant(doc, str(args.get("participant_identifier") or ""))
        return doc.get("change_management_stage") == "Confirmed" and (not row or any(
            field in args and str(args[field] or "") != str(row.get(field) or "")
            for field in ("participant_name", "role", "present_for_discussion")
        ))
    if name not in {"record_work_step", "record_hazard_and_control"}:
        return False
    sequence = cint(args.get("sequence" if name == "record_work_step" else "work_step_sequence"))
    if sequence not in target_steps(doc):
        frappe.throw(_("Confirm this step as part of the change scope before editing it."), frappe.PermissionError)
    if name == "record_work_step":
        row = tools._find_step(doc, str(args.get("step_identifier") or ""), sequence)
        if not row or cint(row.sequence) != sequence:
            frappe.throw(_("Use add_jha_change_step to insert a new change step."), frappe.ValidationError)
    else:
        row = tools._find_hazard(doc, str(args.get("hazard_identifier") or ""))
        if row and cint(row.work_step_sequence) not in target_steps(doc):
            frappe.throw(_("This hazard belongs to a step outside the confirmed change scope."), frappe.PermissionError)
    # A subsequent correction requires another explicit change read-back.
    return doc.get("change_management_stage") == "Confirmed"


def execute_change_tool(jha_name: str, name: str, arguments, call_id: str):
    from verto.api.mobile.voice_jha_tools_streamlined import _mutation_context

    doc, replay = _mutation_context(jha_name, call_id, name)
    if not doc.get("previous_jha"):
        frappe.throw(_("Start a change revision before using change-management tools."), frappe.PermissionError)
    if replay:
        return replay
    args = tools._load_arguments(arguments)
    if name == "record_jha_change_request":
        summary = str(args.get("summary") or "").strip()
        values = args.get("affected_step_sequences")
        if not summary or len(summary) > 5000 or not isinstance(values, list) or len(values) > 200:
            frappe.throw(_("Supply a change description and a valid affected-step list."), frappe.ValidationError)
        sequences = {cint(row.sequence) for row in doc.work_steps or []}
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in values):
            frappe.throw(_("Each affected step must be a step number."), frappe.ValidationError)
        requested = sorted(set(values))
        if any(v not in sequences for v in requested):
            frappe.throw(_("Each affected step must exist in this JHA."), frappe.ValidationError)
        targets = sorted(set(target_steps(doc)) | set(requested))
        doc.change_summary = summary
        doc.change_target_steps = json.dumps(targets)
        doc.change_participants = cint(bool(doc.get("change_participants") or args.get("participant_changes")))
        doc.change_management_stage = "Assess Change"
        for row in doc.work_steps or []:
            if cint(row.sequence) in requested:
                row.step_discussion_complete = row.critical_controls_reviewed = row.hold_point_confirmed = 0
        result = {"changed": True, "message": "Change scope recorded. Reassess only the affected steps."}
    elif name == "add_jha_change_step":
        if doc.get("change_management_stage") == "Describe Change":
            frappe.throw(_("Record the change request before inserting a step."), frappe.ValidationError)
        activity = str(args.get("activity") or "").strip()
        after = args.get("after_step_sequence")
        if not activity or len(activity) > 5000 or isinstance(after, bool) or not isinstance(after, int) or (after != 0 and after not in {cint(s.sequence) for s in doc.work_steps or []}):
            frappe.throw(_("Confirm the new activity and its position in the JHA."), frappe.ValidationError)
        sequence = after + 1
        targets = [n + 1 if n >= sequence else n for n in target_steps(doc)]
        for row in doc.work_steps or []:
            if cint(row.sequence) >= sequence:
                row.sequence = cint(row.sequence) + 1
        for row in doc.hazards_and_controls or []:
            if cint(row.work_step_sequence) >= sequence:
                row.work_step_sequence = cint(row.work_step_sequence) + 1
        for row in doc.incident_references or []:
            if cint(row.work_step_sequence) >= sequence:
                row.work_step_sequence = cint(row.work_step_sequence) + 1
        doc.append("work_steps", {"sequence": sequence, "activity": activity, "step_origin": "Voice-derived",
                                  "source_step_identifier": f"change-{uuid4().hex}", "hold_point_confirmed": 0,
                                  "critical_controls_reviewed": 0, "step_discussion_complete": 0})
        doc.change_target_steps = json.dumps(sorted(set(targets + [sequence])))
        doc.change_management_stage = "Assess Change"
        doc.job_steps_confirmed = 1
        doc.flags.allow_jha_incident_mutation = True
        result = {"changed": True, "sequence": sequence, "message": "New step inserted. Assess its hazards and controls."}
    elif name == "confirm_jha_changes":
        targets = target_steps(doc)
        progress = calculate_facilitation_progress(doc)
        if not doc.get("change_summary") or (not targets and not cint(doc.get("change_participants"))):
            frappe.throw(_("Record the requested changes and their affected steps or participants first."), frappe.ValidationError)
        if any(not step["discussion_complete"] for step in progress["steps"] if step["sequence"] in targets):
            frappe.throw(_("Finish reassessing every affected step before confirming the changes."), frappe.ValidationError)
        if cint(doc.get("change_participants")) and not any(entry.get("tool_name") == "record_participant" for entry in tools._audit_entries(doc)):
            frappe.throw(_("Record the requested participant changes before confirming them."), frappe.ValidationError)
        doc.change_management_stage = "Confirmed"
        result = {"changed": True, "message": "Crew confirmed the changes. Check the development team and completeness, then return the revision for human review."}
    else:
        frappe.throw(_("Unknown JHA change tool."), frappe.PermissionError)
    doc.flags.allow_jha_change_mutation = True
    from verto.api.mobile.voice_jha_progress import sync_facilitation_fields
    result["facilitation"] = sync_facilitation_fields(doc)
    result["change_summary"] = doc.get("change_summary")
    result["affected_step_sequences"] = target_steps(doc)
    result["change_management_stage"] = doc.get("change_management_stage")
    tools._append_audit(doc, call_id, name, args, result)
    doc.save()
    return {"ok": True, "replayed": False, "tool_name": name, "result": result, "jha": serialize_jha(doc)}


def supersede_previous_revision(doc):
    if not doc.get("previous_jha"):
        return
    previous = frappe.get_doc("Digital Job Hazard Analysis", doc.previous_jha)
    if previous.get("replacement_jha") != doc.name or previous.work_summary != doc.work_summary:
        frappe.throw(_("The previous JHA revision link is invalid."), frappe.ValidationError)
    previous.jha_status = "Superseded"
    previous.flags.allow_jha_review_mutation = True
    previous.save()
