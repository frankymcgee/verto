from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from verto.api.mobile import voice_jha as voice
from verto.api.mobile import voice_jha_tools as base


def _step_hazards(step, hazards):
    return [
        row
        for row in hazards
        if (
            (step.source_step_identifier and row.work_step_reference == step.source_step_identifier)
            or cint(row.work_step_sequence) == cint(step.sequence)
        )
    ]


def _streamlined_completeness(doc) -> dict:
    issues: list[str] = []
    steps = list(doc.work_steps or [])
    hazards = list(doc.hazards_and_controls or [])
    participants = list(doc.participants or [])

    if not steps:
        issues.append("No job steps have been recorded.")

    for step in steps:
        step_label = f"Step {step.sequence or step.idx}"
        step_rows = _step_hazards(step, hazards)
        if not step_rows:
            issues.append(f"{step_label}: no hazard/control row has been recorded.")
        if step.meta.has_field("hold_point_confirmed") and not cint(step.get("hold_point_confirmed")):
            issues.append(f"{step_label}: hold point has not been explicitly confirmed yes or no.")

    for row in hazards:
        label = f"Step {row.work_step_sequence or '?'} hazard '{base._text(row.hazard_or_energy_source, limit=80) or 'unnamed'}'"
        if not base._text(row.hazard_or_energy_source):
            issues.append(f"{label}: hazard is missing.")
        if not (base._text(row.existing_controls) or base._text(row.additional_controls)):
            issues.append(f"{label}: no specific controls are recorded.")

        critical = cint(row.critical_risk) or bool(base._text(row.critical_control))
        if critical:
            if not base._text(row.critical_control):
                issues.append(f"{label}: critical risk is identified but the critical control is missing.")
            if not base._text(row.control_owner):
                issues.append(f"{label}: critical control owner is missing.")

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
        "work_step_count": len(steps),
        "hazard_count": len(hazards),
        "participant_count": len(participants),
        "message": (
            "Field JHA completeness checks passed; human review is still required."
            if not issues
            else f"Field JHA has {len(issues)} outstanding completeness item(s)."
        ),
    }


def _mark_hold_point_confirmed(jha_name: str, args: dict):
    if "hold_or_pause_point" not in args:
        return
    if not frappe.get_meta("Digital JHA Work Step").has_field("hold_point_confirmed"):
        return

    doc = frappe.get_doc(base.JHA_DOCTYPE, jha_name)
    identifier = base._text(args.get("step_identifier"), limit=140)
    sequence = cint(args.get("sequence"))
    row = base._find_step(doc, identifier, sequence)
    if row and not cint(row.get("hold_point_confirmed")):
        row.db_set("hold_point_confirmed", 1, update_modified=False)


def _execute_completeness(jha_name: str):
    base._require_login()
    doc = base._get_jha(jha_name)
    if doc.jha_status not in base.READABLE_STATUSES:
        frappe.throw(_("PERI tools are not available for this JHA status."), frappe.PermissionError)
    return {
        "ok": True,
        "replayed": False,
        "tool_name": "run_jha_completeness_check",
        "result": _streamlined_completeness(doc),
        "jha": voice._serialize_jha(doc),
    }


def _execute_mark_ready(jha_name: str, arguments, call_id: str):
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

    args = base._load_arguments(arguments)
    replay = base._find_audit_result(doc, call_id)
    if replay is not None:
        return {
            "ok": True,
            "replayed": True,
            "tool_name": "mark_ready_for_human_review",
            "result": replay,
            "jha": voice._serialize_jha(doc),
        }

    check = _streamlined_completeness(doc)
    if check["complete"]:
        doc.jha_status = "Ready for Team Review"
        result = {
            **check,
            "changed": True,
            "status": doc.jha_status,
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
        "jha": voice._serialize_jha(doc),
    }


@frappe.whitelist(methods=["POST"])
def execute_voice_jha_tool(jha_name: str, tool_name: str, arguments="{}", call_id: str = ""):
    tool_name = base._text(tool_name, limit=100)

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

    if tool_name == "record_work_step":
        args = base._load_arguments(arguments)
        _mark_hold_point_confirmed(jha_name, args)
        if isinstance(response, dict) and isinstance(response.get("result"), dict):
            response["result"]["hold_point_confirmed"] = 1 if "hold_or_pause_point" in args else 0

    return response
