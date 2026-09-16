from __future__ import annotations

import frappe
from frappe.utils import cint, now_datetime


STAGE_JOB_STEPS = "Job Steps"
STAGE_STEP_ANALYSIS = "Step Analysis"
STAGE_DEVELOPMENT_TEAM = "Development Team"
STAGE_COMPLETENESS = "Completeness Check"
STAGE_READY = "Ready for Team Review"
STAGE_SIGNED = "Signed"
STAGE_REVIEW_REQUIRED = "Review Required - Work Changed"


def _text(value) -> str:
    return str(value or "").strip()


def _sorted_steps(doc):
    return sorted(
        list(doc.work_steps or []),
        key=lambda row: (cint(row.sequence or row.idx or 0), cint(row.idx or 0)),
    )


def _hazards_for_step(step, hazards):
    sequence = cint(step.sequence or step.idx or 0)
    identifier = _text(step.get("source_step_identifier"))
    return [
        row
        for row in hazards
        if (
            (identifier and _text(row.get("work_step_reference")) == identifier)
            or cint(row.get("work_step_sequence")) == sequence
        )
    ]


def _has_controls(row) -> bool:
    return bool(_text(row.get("existing_controls")) or _text(row.get("additional_controls")))


def _is_critical(row) -> bool:
    return bool(cint(row.get("critical_risk")) or _text(row.get("critical_control")))


def get_step_progress(step, hazards) -> dict:
    rows = _hazards_for_step(step, hazards)
    critical_rows = [row for row in rows if _is_critical(row)]

    hazards_complete = bool(rows)
    controls_complete = hazards_complete and all(_has_controls(row) for row in rows)
    critical_owner_complete = all(
        bool(_text(row.get("critical_control")) and _text(row.get("control_owner")))
        for row in critical_rows
    ) if critical_rows else False
    hold_point_complete = bool(cint(step.get("hold_point_confirmed")))
    discussion_flag = bool(cint(step.get("step_discussion_complete")))
    critical_controls_reviewed = bool(cint(step.get("critical_controls_reviewed")))

    requirements_complete = (
        hazards_complete
        and controls_complete
        and critical_controls_reviewed
        and (not critical_rows or critical_owner_complete)
        and hold_point_complete
    )
    discussion_complete = bool(discussion_flag and requirements_complete)

    return {
        "name": step.name,
        "sequence": cint(step.sequence or step.idx or 0),
        "activity": step.activity or "",
        "hazard_count": len(rows),
        "hazards_complete": hazards_complete,
        "controls_complete": controls_complete,
        "critical_control_required": bool(critical_rows),
        "critical_controls_reviewed": critical_controls_reviewed,
        "critical_owner_complete": critical_owner_complete if critical_rows else critical_controls_reviewed,
        "hold_point_complete": hold_point_complete,
        "hold_point": bool(cint(step.get("hold_or_pause_point"))) if hold_point_complete else None,
        "discussion_complete": discussion_complete,
    }


def calculate_facilitation_progress(doc) -> dict:
    steps = _sorted_steps(doc)
    hazards = list(doc.hazards_and_controls or [])
    step_states = [get_step_progress(step, hazards) for step in steps]
    job_steps_confirmed = bool(cint(doc.get("job_steps_confirmed")))

    status = _text(doc.jha_status)
    if status == "Signed":
        stage = STAGE_SIGNED
        current_sequence = 0
    elif status == "Review Required - Work Changed":
        stage = STAGE_REVIEW_REQUIRED
        current_sequence = 0
    elif status == "Ready for Team Review":
        stage = STAGE_READY
        current_sequence = 0
    elif not steps or not job_steps_confirmed:
        stage = STAGE_JOB_STEPS
        current_sequence = 0
    else:
        incomplete = [state for state in step_states if not state["discussion_complete"]]
        if incomplete:
            stage = STAGE_STEP_ANALYSIS
            stored = cint(doc.get("current_step_sequence"))
            matching = next((state for state in incomplete if state["sequence"] == stored), None)
            current_sequence = (matching or incomplete[0])["sequence"]
        else:
            current_sequence = 0
            participants = [
                row for row in (doc.participants or []) if cint(row.get("present_for_discussion"))
            ]
            stage = STAGE_COMPLETENESS if participants else STAGE_DEVELOPMENT_TEAM

    for state in step_states:
        state["is_current"] = bool(
            stage == STAGE_STEP_ANALYSIS and state["sequence"] == current_sequence
        )

    current_step = next(
        (state for state in step_states if state["sequence"] == current_sequence),
        None,
    )

    return {
        "stage": stage,
        "job_steps_confirmed": job_steps_confirmed,
        "current_step_sequence": current_sequence,
        "current_step_activity": current_step["activity"] if current_step else "",
        "completed_step_count": sum(1 for state in step_states if state["discussion_complete"]),
        "total_step_count": len(step_states),
        "steps": step_states,
    }


def sync_facilitation_fields(doc, *, update_timestamp: bool = True) -> dict:
    progress = calculate_facilitation_progress(doc)
    changed = False

    values = {
        "facilitation_stage": progress["stage"],
        "current_step_sequence": progress["current_step_sequence"],
    }
    for fieldname, value in values.items():
        if doc.meta.has_field(fieldname) and doc.get(fieldname) != value:
            doc.set(fieldname, value)
            changed = True

    if changed and update_timestamp and doc.meta.has_field("facilitation_updated_at"):
        doc.facilitation_updated_at = now_datetime()

    return progress


def persist_facilitation_fields(doc) -> dict:
    progress = sync_facilitation_fields(doc)
    values = {}
    for fieldname in ("facilitation_stage", "current_step_sequence", "facilitation_updated_at"):
        if doc.meta.has_field(fieldname):
            values[fieldname] = doc.get(fieldname)
    if values and doc.name:
        frappe.db.set_value(doc.doctype, doc.name, values, update_modified=False)
    return progress


def serialize_jha(doc) -> dict:
    from verto.api.mobile import voice_jha

    snapshot = voice_jha._serialize_jha(doc)
    progress = sync_facilitation_fields(doc, update_timestamp=False)
    snapshot["facilitation"] = progress
    snapshot["facilitation_stage"] = progress["stage"]
    snapshot["job_steps_confirmed"] = cint(doc.get("job_steps_confirmed"))
    snapshot["current_step_sequence"] = progress["current_step_sequence"]
    snapshot["facilitation_updated_at"] = doc.get("facilitation_updated_at")

    states_by_name = {state["name"]: state for state in progress["steps"] if state.get("name")}
    for row in snapshot.get("work_steps") or []:
        state = states_by_name.get(row.get("name"))
        if state:
            row.update(
                {
                    "hold_point_confirmed": cint(state["hold_point_complete"]),
                    "critical_controls_reviewed": cint(state["critical_controls_reviewed"]),
                    "step_discussion_complete": cint(state["discussion_complete"]),
                }
            )
    return snapshot
