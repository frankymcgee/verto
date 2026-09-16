from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from verto.api.mobile import voice_jha_tools as base
from verto.api.mobile.voice_jha_progress import (
    STAGE_STEP_ANALYSIS,
    calculate_facilitation_progress,
    persist_facilitation_fields,
    serialize_jha,
)


def _step_hazards(step, hazards):
    sequence = cint(step.sequence or step.idx or 0)
    identifier = base._text(step.get("source_step_identifier"), limit=140)
    return [
        row
        for row in hazards
        if (
            (identifier and row.work_step_reference == identifier)
            or cint(row.work_step_sequence) == sequence
        )
    ]


def _streamlined_completeness(doc) -> dict:
    issues: list[str] = []
    progress = calculate_facilitation_progress(doc)
    participants = list(doc.participants or [])

    if not progress["total_step_count"]:
        issues.append("No job steps have been recorded.")
    if progress["total_step_count"] and not progress["job_steps_confirmed"]:
        issues.append("The complete ordered job-step list has not been confirmed by the team.")

    for step in progress["steps"]:
        label = f"Step {step['sequence']}"
        if not step["hazards_complete"]:
            issues.append(f"{label}: no hazard has been recorded.")
        if not step["controls_complete"]:
            issues.append(f"{label}: specific controls are incomplete.")
        if step["critical_control_required"] and not step["critical_owner_complete"]:
            issues.append(f"{label}: a critical control is missing its owner.")
        if not step["critical_controls_reviewed"]:
            issues.append(f"{label}: critical controls have not been explicitly reviewed with the team.")
        if not step["hold_point_complete"]:
            issues.append(f"{label}: hold point has not been explicitly confirmed yes or no.")
        if not step["discussion_complete"]:
            issues.append(f"{label}: facilitator discussion has not been closed out.")

    if not participants:
        issues.append("No JHA development-team participants have been recorded.")
    for row in participants:
        if cint(row.present_for_discussion) and not cint(row.transcription_consent):
            issues.append(
                f"Participant '{row.participant_name or 'unnamed'}': transcription consent is not recorded."
            )

    return {
        "complete": not issues,
        "issues": issues,
        "work_step_count": progress["total_step_count"],
        "completed_step_count": progress["completed_step_count"],
        "participant_count": len(participants),
        "facilitation": progress,
        "message": (
            "Field JHA completeness checks passed; human review is still required."
            if not issues
            else f"Field JHA has {len(issues)} outstanding completeness item(s)."
        ),
    }


def _mutation_context(jha_name: str, call_id: str, tool_name: str):
    base._require_login()
    doc = base._get_jha(jha_name)
    if doc.jha_status not in base.WRITEABLE_STATUSES:
        frappe.throw(
            _("PERI cannot modify this JHA after it has been marked ready for human review."),
            frappe.PermissionError,
        )
    if not doc.has_permission("write"):
        frappe.throw(_("You cannot modify this Digital JHA."), frappe.PermissionError)
    if not call_id:
        frappe.throw(_("A Realtime tool call ID is required for draft writes."), frappe.ValidationError)

    replay = base._find_audit_result(doc, call_id)
    if replay is not None:
        return doc, {
            "ok": True,
            "replayed": True,
            "tool_name": tool_name,
            "result": replay,
            "jha": serialize_jha(doc),
        }
    return doc, None


def _execute_confirm_job_steps(jha_name: str, arguments, call_id: str):
    doc, replay_response = _mutation_context(jha_name, call_id, "confirm_job_steps")
    if replay_response:
        return replay_response

    args = base._load_arguments(arguments)
    if not list(doc.work_steps or []):
        frappe.throw(
            _("Record the complete job-step list before confirming it."),
            frappe.ValidationError,
        )

    doc.job_steps_confirmed = 1
    progress = persist_facilitation_fields(doc)
    result = {
        "changed": True,
        "facilitation": progress,
        "message": (
            f"Job-step list confirmed. Continue with Step {progress['current_step_sequence']}: "
            f"{progress['current_step_activity']}."
            if progress["current_step_sequence"]
            else "Job-step list confirmed. Continue with the development team."
        ),
    }
    base._append_audit(doc, call_id, "confirm_job_steps", args, result)
    doc.save()
    return {
        "ok": True,
        "replayed": False,
        "tool_name": "confirm_job_steps",
        "result": result,
        "jha": serialize_jha(doc),
    }


def _execute_complete_current_step(jha_name: str, arguments, call_id: str):
    doc, replay_response = _mutation_context(jha_name, call_id, "complete_current_step")
    if replay_response:
        return replay_response

    args = base._load_arguments(arguments)
    step_sequence = base._positive_int(args.get("step_sequence"), "Step sequence")
    progress = calculate_facilitation_progress(doc)

    if not progress["job_steps_confirmed"]:
        frappe.throw(_("Confirm the complete job-step list before analysing steps."), frappe.ValidationError)
    if progress["stage"] != STAGE_STEP_ANALYSIS:
        frappe.throw(_("The facilitator is not currently in step analysis."), frappe.ValidationError)
    if step_sequence != cint(progress["current_step_sequence"]):
        frappe.throw(
            _(f"Step {progress['current_step_sequence']} is the current step. Complete it before advancing."),
            frappe.ValidationError,
        )

    step = next(
        (row for row in (doc.work_steps or []) if cint(row.sequence or row.idx) == step_sequence),
        None,
    )
    if not step:
        frappe.throw(_("The current JHA step was not found."), frappe.DoesNotExistError)

    rows = _step_hazards(step, list(doc.hazards_and_controls or []))
    issues = []
    if not rows:
        issues.append("No hazard has been recorded for this step.")
    if rows and not all(
        base._text(row.existing_controls) or base._text(row.additional_controls)
        for row in rows
    ):
        issues.append("One or more hazards are missing specific controls.")

    critical_rows = [row for row in rows if cint(row.critical_risk) or base._text(row.critical_control)]
    for row in critical_rows:
        if not base._text(row.critical_control):
            issues.append(
                f"Critical hazard '{base._text(row.hazard_or_energy_source, limit=80)}' is missing its critical control."
            )
        if not base._text(row.control_owner):
            issues.append(
                f"Critical hazard '{base._text(row.hazard_or_energy_source, limit=80)}' is missing its critical-control owner."
            )

    if not cint(step.get("hold_point_confirmed")):
        issues.append("The crew has not explicitly answered the hold-point question yes or no.")

    if issues:
        result = {
            "changed": False,
            "issues": issues,
            "facilitation": progress,
            "message": "Current step cannot be completed until the listed items are resolved.",
        }
        base._append_audit(doc, call_id, "complete_current_step", args, result)
        doc.save()
        return {
            "ok": True,
            "replayed": False,
            "tool_name": "complete_current_step",
            "result": result,
            "jha": serialize_jha(doc),
        }

    step.critical_controls_reviewed = 1
    step.step_discussion_complete = 1
    progress = persist_facilitation_fields(doc)
    result = {
        "changed": True,
        "completed_step_sequence": step_sequence,
        "facilitation": progress,
        "message": (
            f"Step {step_sequence} complete. Continue with Step {progress['current_step_sequence']}: "
            f"{progress['current_step_activity']}."
            if progress["current_step_sequence"]
            else "All job steps are complete. Continue with the JHA development team."
        ),
    }
    base._append_audit(doc, call_id, "complete_current_step", args, result)
    doc.save()
    return {
        "ok": True,
        "replayed": False,
        "tool_name": "complete_current_step",
        "result": result,
        "jha": serialize_jha(doc),
    }


def _mark_hold_point_confirmed(doc, args: dict):
    if "hold_or_pause_point" not in args:
        return
    identifier = base._text(args.get("step_identifier"), limit=140)
    sequence = cint(args.get("sequence"))
    row = base._find_step(doc, identifier, sequence)
    if row:
        row.hold_point_confirmed = 1


def _post_process_base_tool(jha_name: str, tool_name: str, arguments, response: dict):
    doc = base._get_jha(jha_name)
    args = base._load_arguments(arguments)

    if tool_name == "record_work_step":
        _mark_hold_point_confirmed(doc, args)
        result = response.get("result") or {}
        if result.get("created") and cint(doc.get("job_steps_confirmed")):
            doc.job_steps_confirmed = 0

    progress = persist_facilitation_fields(doc)
    doc.save()
    if isinstance(response, dict):
        response["jha"] = serialize_jha(doc)
        if isinstance(response.get("result"), dict):
            response["result"]["facilitation"] = progress
    return response


def _execute_completeness(jha_name: str):
    base._require_login()
    doc = base._get_jha(jha_name)
    if doc.jha_status not in base.READABLE_STATUSES:
        frappe.throw(_("PERI tools are not available for this JHA status."), frappe.PermissionError)
    persist_facilitation_fields(doc)
    return {
        "ok": True,
        "replayed": False,
        "tool_name": "run_jha_completeness_check",
        "result": _streamlined_completeness(doc),
        "jha": serialize_jha(doc),
    }


def _execute_mark_ready(jha_name: str, arguments, call_id: str):
    doc, replay_response = _mutation_context(jha_name, call_id, "mark_ready_for_human_review")
    if replay_response:
        return replay_response

    args = base._load_arguments(arguments)
    check = _streamlined_completeness(doc)
    if check["complete"]:
        doc.jha_status = "Ready for Team Review"
        progress = persist_facilitation_fields(doc)
        result = {
            **check,
            "changed": True,
            "status": doc.jha_status,
            "facilitation": progress,
            "message": "Draft marked Ready for Team Review. Human review and sign-on remain required.",
        }
    else:
        result = {
            **check,
            "changed": False,
            "status": doc.jha_status,
            "message": "Draft cannot be marked ready until the listed field-JHA items are resolved.",
        }

    base._append_audit(doc, call_id, "mark_ready_for_human_review", args, result)
    doc.save()
    return {
        "ok": True,
        "replayed": False,
        "tool_name": "mark_ready_for_human_review",
        "result": result,
        "jha": serialize_jha(doc),
    }


@frappe.whitelist(methods=["POST"])
def execute_voice_jha_tool(jha_name: str, tool_name: str, arguments="{}", call_id: str = ""):
    tool_name = base._text(tool_name, limit=100)

    if tool_name == "confirm_job_steps":
        return _execute_confirm_job_steps(jha_name, arguments, call_id)
    if tool_name == "complete_current_step":
        return _execute_complete_current_step(jha_name, arguments, call_id)
    if tool_name == "run_jha_completeness_check":
        return _execute_completeness(jha_name)
    if tool_name == "mark_ready_for_human_review":
        return _execute_mark_ready(jha_name, arguments, call_id)

    response = base.execute_voice_jha_tool(
        jha_name=jha_name,
        tool_name=tool_name,
        arguments=arguments,
        call_id=call_id,
    )

    if tool_name in {"record_work_step", "record_hazard_and_control", "record_participant"}:
        return _post_process_base_tool(jha_name, tool_name, arguments, response)

    if tool_name == "get_current_jha_state" and isinstance(response, dict):
        doc = base._get_jha(jha_name)
        if isinstance(response.get("result"), dict):
            response["result"]["facilitation"] = calculate_facilitation_progress(doc)
        response["jha"] = serialize_jha(doc)
    return response
