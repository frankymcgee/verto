from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from verto.api.mobile.voice_jha_permissions import user_can_access_work_summary


JHA_DOCTYPE = "Digital Job Hazard Analysis"
WRITEABLE_STATUSES = {
    "Draft",
    "Voice Discussion in Progress",
    "Incomplete - Actions Required",
}
READABLE_STATUSES = WRITEABLE_STATUSES | {"Ready for Team Review"}
MUTATING_TOOLS = {
    "record_work_step",
    "record_hazard_and_control",
    "record_participant",
    "mark_ready_for_human_review",
}
MAX_ARGUMENT_LENGTH = 32_000
MAX_AUDIT_ENTRIES = 200

HIERARCHY_LEVELS = {
    "Elimination",
    "Substitution",
    "Isolation",
    "Engineering",
    "Administrative",
    "PPE",
}
VERIFICATION_STATUSES = {
    "Not Verified",
    "Reported by Team",
    "Verified On Site",
}


def get_realtime_jha_tools() -> list[dict]:
    """Allowlisted Realtime function tools for a draft Digital JHA.

    These tools deliberately omit submission, approval, acknowledgement/signature
    and work-authorisation operations.
    """
    return [
        {
            "type": "function",
            "name": "get_current_jha_state",
            "description": (
                "Read the current structured draft JHA. Use this before correcting or "
                "updating existing entries, and whenever you are unsure what has already been recorded."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "record_work_step",
            "description": (
                "Create or update one confirmed work step in the draft JHA. Call only after the crew "
                "has confirmed the step. Reuse the same step_identifier when adding corrections. "
                "This never approves or authorises work."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "step_identifier": {
                        "type": "string",
                        "description": "Stable short identifier you reuse for this step, e.g. voice-step-1.",
                    },
                    "sequence": {"type": "integer", "minimum": 1},
                    "activity": {"type": "string"},
                    "hold_or_pause_point": {"type": "boolean"},
                },
                "required": ["step_identifier", "sequence"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "record_hazard_and_control",
            "description": (
                "Create or update one hazard/control row for a confirmed work step. Record only what the "
                "crew has actually discussed or confirmed. Reuse hazard_identifier for corrections. "
                "Never invent controls, verification, risk ratings, permits or critical controls."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hazard_identifier": {
                        "type": "string",
                        "description": "Stable short identifier you reuse for this hazard, e.g. voice-hazard-1-1.",
                    },
                    "work_step_identifier": {"type": "string"},
                    "work_step_sequence": {"type": "integer", "minimum": 1},
                    "hazard_or_energy_source": {"type": "string"},
                    "people_exposed": {"type": "string"},
                    "credible_consequence": {"type": "string"},
                    "existing_controls": {"type": "string"},
                    "additional_controls": {"type": "string"},
                    "hierarchy_level": {
                        "type": "string",
                        "enum": [
                            "Elimination",
                            "Substitution",
                            "Isolation",
                            "Engineering",
                            "Administrative",
                            "PPE",
                        ],
                    },
                    "control_owner": {"type": "string"},
                    "verification_method": {"type": "string"},
                    "verification_status": {
                        "type": "string",
                        "enum": ["Not Verified", "Reported by Team", "Verified On Site"],
                    },
                    "critical_risk": {"type": "boolean"},
                    "critical_control": {"type": "string"},
                    "permit_or_ccv_required": {"type": "string"},
                    "initial_risk": {"type": "string"},
                    "residual_risk": {"type": "string"},
                },
                "required": [
                    "hazard_identifier",
                    "work_step_identifier",
                    "work_step_sequence",
                ],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "record_participant",
            "description": (
                "Create or update a person present for the JHA discussion. Transcription consent may only "
                "be recorded true when that person's consent has been explicitly confirmed. This tool can "
                "never acknowledge or sign the JHA for the participant."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "participant_identifier": {
                        "type": "string",
                        "description": "Stable identifier you reuse for this participant.",
                    },
                    "participant_name": {"type": "string"},
                    "employee": {"type": "string"},
                    "role": {"type": "string"},
                    "present_for_discussion": {"type": "boolean"},
                    "transcription_consent": {"type": "boolean"},
                },
                "required": ["participant_identifier"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "run_jha_completeness_check",
            "description": (
                "Check the structured draft for missing steps, hazards, consequences, controls, owners, "
                "verification, residual risk, critical controls and participant consent. This is a draft "
                "completeness check only and is not an approval or statement that work is safe."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "mark_ready_for_human_review",
            "description": (
                "Mark the draft Ready for Team Review only after the crew says the discussion is complete "
                "and the completeness check has no outstanding items. This does not approve, submit, sign "
                "or authorise the JHA or the work."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    ]


def _require_login():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def _get_jha(jha_name: str):
    if not jha_name or not frappe.db.exists(JHA_DOCTYPE, jha_name):
        frappe.throw(_("Digital JHA was not found."), frappe.DoesNotExistError)

    doc = frappe.get_doc(JHA_DOCTYPE, jha_name)
    if not doc.has_permission("read"):
        frappe.throw(_("You cannot access this Digital JHA."), frappe.PermissionError)
    if not user_can_access_work_summary(doc.work_summary):
        frappe.throw(_("This Digital JHA is not linked to work assigned to you."), frappe.PermissionError)
    return doc


def _load_arguments(arguments) -> dict:
    if isinstance(arguments, dict):
        return arguments

    raw = str(arguments or "{}")
    if len(raw) > MAX_ARGUMENT_LENGTH:
        frappe.throw(_("PERI tool arguments are unexpectedly large."), frappe.ValidationError)

    try:
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        frappe.throw(_("PERI returned invalid tool arguments."), frappe.ValidationError)

    if not isinstance(value, dict):
        frappe.throw(_("PERI tool arguments must be an object."), frappe.ValidationError)
    return value


def _text(value, *, limit=2000) -> str:
    text = str(value or "").strip()
    if len(text) > limit:
        text = text[:limit]
    return text


def _identifier(value, label: str) -> str:
    value = _text(value, limit=140)
    if not value:
        frappe.throw(_(f"{label} is required."), frappe.ValidationError)
    return value


def _positive_int(value, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        frappe.throw(_(f"{label} must be a whole number."), frappe.ValidationError)
    if result < 1:
        frappe.throw(_(f"{label} must be at least 1."), frappe.ValidationError)
    return result


def _bool(value) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if value else 0
    return 1 if str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"} else 0


def _find_step(doc, identifier: str, sequence: int | None = None):
    for row in doc.work_steps or []:
        if _text(row.source_step_identifier, limit=140) == identifier:
            return row
    if sequence:
        for row in doc.work_steps or []:
            if cint(row.sequence) == sequence:
                existing_id = _text(row.source_step_identifier, limit=140)
                if not existing_id or existing_id == identifier:
                    return row
    return None


def _find_hazard(doc, identifier: str):
    for row in doc.hazards_and_controls or []:
        if _text(row.get("source_hazard_identifier"), limit=140) == identifier:
            return row
    return None


def _find_participant(doc, identifier: str):
    for row in doc.participants or []:
        if _text(row.get("source_participant_identifier"), limit=140) == identifier:
            return row
    return None


def _record_work_step(doc, args: dict) -> dict:
    identifier = _identifier(args.get("step_identifier"), "Step identifier")
    sequence = _positive_int(args.get("sequence"), "Step sequence")
    row = _find_step(doc, identifier, sequence)
    created = row is None

    if created:
        activity = _text(args.get("activity"))
        if not activity:
            frappe.throw(_("Activity is required when creating a new work step."), frappe.ValidationError)
        row = doc.append(
            "work_steps",
            {
                "sequence": sequence,
                "activity": activity,
                "step_origin": "Voice-derived",
                "source_step_identifier": identifier,
                "hold_or_pause_point": _bool(args.get("hold_or_pause_point")),
            },
        )
    else:
        row.sequence = sequence
        activity = _text(args.get("activity"))
        if activity:
            row.activity = activity
        if "hold_or_pause_point" in args:
            row.hold_or_pause_point = _bool(args.get("hold_or_pause_point"))
        if not row.source_step_identifier:
            row.source_step_identifier = identifier

    return {
        "created": created,
        "step_identifier": identifier,
        "sequence": row.sequence,
        "activity": row.activity,
        "hold_or_pause_point": cint(row.hold_or_pause_point),
        "message": "Draft work step recorded." if created else "Draft work step updated.",
    }


def _record_hazard_and_control(doc, args: dict) -> dict:
    identifier = _identifier(args.get("hazard_identifier"), "Hazard identifier")
    step_identifier = _identifier(args.get("work_step_identifier"), "Work step identifier")
    step_sequence = _positive_int(args.get("work_step_sequence"), "Work step sequence")
    step = _find_step(doc, step_identifier, step_sequence)
    if not step:
        frappe.throw(
            _("Record the referenced work step before recording its hazard."),
            frappe.ValidationError,
        )

    row = _find_hazard(doc, identifier)
    created = row is None
    hazard = _text(args.get("hazard_or_energy_source"))

    if created:
        if not hazard:
            frappe.throw(
                _("Hazard / energy source is required when creating a new hazard row."),
                frappe.ValidationError,
            )
        row = doc.append(
            "hazards_and_controls",
            {
                "source_hazard_identifier": identifier,
                "work_step_sequence": step_sequence,
                "work_step_reference": step_identifier,
                "hazard_or_energy_source": hazard,
                "information_source": "Team discussion",
                "verification_status": "Not Verified",
            },
        )
    else:
        row.work_step_sequence = step_sequence
        row.work_step_reference = step_identifier
        if hazard:
            row.hazard_or_energy_source = hazard

    text_fields = (
        "people_exposed",
        "credible_consequence",
        "existing_controls",
        "additional_controls",
        "control_owner",
        "verification_method",
        "critical_control",
        "permit_or_ccv_required",
        "initial_risk",
        "residual_risk",
    )
    for fieldname in text_fields:
        if fieldname not in args:
            continue
        value = _text(args.get(fieldname))
        if value:
            row.set(fieldname, value)

    if "hierarchy_level" in args:
        hierarchy = _text(args.get("hierarchy_level"), limit=50)
        if hierarchy and hierarchy not in HIERARCHY_LEVELS:
            frappe.throw(_("Invalid hierarchy of control value."), frappe.ValidationError)
        if hierarchy:
            row.hierarchy_level = hierarchy

    if "verification_status" in args:
        status = _text(args.get("verification_status"), limit=50)
        if status and status not in VERIFICATION_STATUSES:
            frappe.throw(_("Invalid verification status."), frappe.ValidationError)
        if status:
            row.verification_status = status

    if "critical_risk" in args:
        row.critical_risk = _bool(args.get("critical_risk"))

    row.information_source = "Team discussion"

    return {
        "created": created,
        "hazard_identifier": identifier,
        "work_step_identifier": step_identifier,
        "work_step_sequence": step_sequence,
        "hazard_or_energy_source": row.hazard_or_energy_source,
        "message": "Draft hazard/control recorded." if created else "Draft hazard/control updated.",
    }


def _record_participant(doc, args: dict) -> dict:
    identifier = _identifier(args.get("participant_identifier"), "Participant identifier")
    row = _find_participant(doc, identifier)
    created = row is None
    participant_name = _text(args.get("participant_name"), limit=140)

    if created:
        if not participant_name:
            frappe.throw(
                _("Participant name is required when creating a participant."),
                frappe.ValidationError,
            )
        row = doc.append(
            "participants",
            {
                "source_participant_identifier": identifier,
                "participant_name": participant_name,
                "present_for_discussion": 1,
                "transcription_consent": 0,
                "acknowledged": 0,
            },
        )
    elif participant_name:
        row.participant_name = participant_name

    employee = _text(args.get("employee"), limit=140)
    if employee:
        if not frappe.db.exists("Employee", employee):
            frappe.throw(_("The supplied Employee record does not exist."), frappe.ValidationError)
        row.employee = employee

    role = _text(args.get("role"), limit=140)
    if role:
        row.role = role

    if "present_for_discussion" in args:
        row.present_for_discussion = _bool(args.get("present_for_discussion"))
    if "transcription_consent" in args:
        row.transcription_consent = _bool(args.get("transcription_consent"))

    # Deliberately never set acknowledged/acknowledged_at here.
    return {
        "created": created,
        "participant_identifier": identifier,
        "participant_name": row.participant_name,
        "present_for_discussion": cint(row.present_for_discussion),
        "transcription_consent": cint(row.transcription_consent),
        "message": "Participant recorded." if created else "Participant updated.",
    }


def _state(doc) -> dict:
    return {
        "jha": doc.name,
        "status": doc.jha_status,
        "revision": doc.revision,
        "work_steps": [
            {
                "step_identifier": row.source_step_identifier,
                "sequence": row.sequence,
                "activity": row.activity,
                "hold_or_pause_point": cint(row.hold_or_pause_point),
            }
            for row in (doc.work_steps or [])
        ],
        "hazards_and_controls": [
            {
                "hazard_identifier": row.get("source_hazard_identifier"),
                "work_step_identifier": row.work_step_reference,
                "work_step_sequence": row.work_step_sequence,
                "hazard_or_energy_source": row.hazard_or_energy_source,
                "credible_consequence": row.credible_consequence,
                "existing_controls": row.existing_controls,
                "additional_controls": row.additional_controls,
                "control_owner": row.control_owner,
                "verification_method": row.verification_method,
                "verification_status": row.verification_status,
                "critical_risk": cint(row.critical_risk),
                "critical_control": row.critical_control,
                "permit_or_ccv_required": row.permit_or_ccv_required,
                "residual_risk": row.residual_risk,
            }
            for row in (doc.hazards_and_controls or [])
        ],
        "participants": [
            {
                "participant_identifier": row.get("source_participant_identifier"),
                "participant_name": row.participant_name,
                "role": row.role,
                "present_for_discussion": cint(row.present_for_discussion),
                "transcription_consent": cint(row.transcription_consent),
                "acknowledged": cint(row.acknowledged),
            }
            for row in (doc.participants or [])
        ],
    }


def _completeness(doc) -> dict:
    issues: list[str] = []
    steps = list(doc.work_steps or [])
    hazards = list(doc.hazards_and_controls or [])
    participants = list(doc.participants or [])

    if not steps:
        issues.append("No work steps have been recorded.")

    for step in steps:
        step_hazards = [
            row
            for row in hazards
            if (
                (step.source_step_identifier and row.work_step_reference == step.source_step_identifier)
                or cint(row.work_step_sequence) == cint(step.sequence)
            )
        ]
        if not step_hazards:
            issues.append(f"Step {step.sequence}: no hazard/control row has been recorded.")

    for row in hazards:
        label = f"Step {row.work_step_sequence or '?'} hazard '{_text(row.hazard_or_energy_source, limit=80) or 'unnamed'}'"
        if not _text(row.credible_consequence):
            issues.append(f"{label}: credible consequence is missing.")
        if not (_text(row.existing_controls) or _text(row.additional_controls)):
            issues.append(f"{label}: no specific controls are recorded.")
        if not _text(row.control_owner):
            issues.append(f"{label}: control owner is missing.")
        if not _text(row.verification_method):
            issues.append(f"{label}: verification method is missing.")
        if not _text(row.residual_risk):
            issues.append(f"{label}: residual risk is missing.")
        if cint(row.critical_risk) and not _text(row.critical_control):
            issues.append(f"{label}: critical risk is flagged but the critical control is missing.")

    if not participants:
        issues.append("No JHA participants have been recorded.")
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
            "Draft completeness checks passed; human review is still required."
            if not issues
            else f"Draft has {len(issues)} outstanding completeness item(s)."
        ),
    }


def _mark_ready(doc, args: dict) -> dict:
    check = _completeness(doc)
    if not check["complete"]:
        return {
            **check,
            "changed": False,
            "status": doc.jha_status,
            "message": "Draft cannot be marked ready until the listed completeness items are resolved.",
        }

    doc.jha_status = "Ready for Team Review"
    return {
        **check,
        "changed": True,
        "status": doc.jha_status,
        "message": "Draft marked Ready for Team Review. Human review, acknowledgement and sign-on remain required.",
    }


def _audit_entries(doc) -> list[dict]:
    raw = _text(doc.get("voice_tool_audit_log"), limit=500_000)
    if not raw:
        return []
    try:
        entries = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return entries if isinstance(entries, list) else []


def _find_audit_result(doc, call_id: str):
    if not call_id:
        return None
    for entry in reversed(_audit_entries(doc)):
        if entry.get("call_id") == call_id:
            return entry.get("result")
    return None


def _append_audit(doc, call_id: str, tool_name: str, args: dict, result: dict):
    if not doc.meta.has_field("voice_tool_audit_log"):
        return
    entries = _audit_entries(doc)
    entries.append(
        {
            "call_id": call_id,
            "tool_name": tool_name,
            "arguments": args,
            "result": result,
            "executed_by": frappe.session.user,
            "executed_at": str(now_datetime()),
        }
    )
    doc.voice_tool_audit_log = json.dumps(entries[-MAX_AUDIT_ENTRIES:], ensure_ascii=False)


TOOL_HANDLERS = {
    "get_current_jha_state": lambda doc, args: _state(doc),
    "record_work_step": _record_work_step,
    "record_hazard_and_control": _record_hazard_and_control,
    "record_participant": _record_participant,
    "run_jha_completeness_check": lambda doc, args: _completeness(doc),
    "mark_ready_for_human_review": _mark_ready,
}


@frappe.whitelist(methods=["POST"])
def execute_voice_jha_tool(jha_name: str, tool_name: str, arguments="{}", call_id: str = ""):
    """Execute one allowlisted PERI voice tool against the current user's JHA.

    The model never supplies DocType or field names. All mutations are explicit,
    assignment-scoped, draft-only and audited. There is intentionally no submit,
    approve, sign, acknowledge-for-user or work-authorisation tool.
    """
    _require_login()
    tool_name = _text(tool_name, limit=100)
    if tool_name not in TOOL_HANDLERS:
        frappe.throw(_("PERI requested a tool that is not allowed."), frappe.PermissionError)

    doc = _get_jha(jha_name)
    if doc.jha_status not in READABLE_STATUSES:
        frappe.throw(_("PERI tools are not available for this JHA status."), frappe.PermissionError)

    args = _load_arguments(arguments)
    mutating = tool_name in MUTATING_TOOLS

    if mutating:
        if not call_id:
            frappe.throw(_("A Realtime tool call ID is required for draft writes."), frappe.ValidationError)
        if doc.jha_status not in WRITEABLE_STATUSES:
            frappe.throw(
                _("PERI cannot modify this JHA after it has been marked ready for human review."),
                frappe.PermissionError,
            )
        if not doc.has_permission("write"):
            frappe.throw(_("You cannot modify this Digital JHA."), frappe.PermissionError)

        replay = _find_audit_result(doc, call_id)
        if replay is not None:
            from verto.api.mobile.voice_jha import _serialize_jha

            return {
                "ok": True,
                "replayed": True,
                "tool_name": tool_name,
                "result": replay,
                "jha": _serialize_jha(doc),
            }

    result = TOOL_HANDLERS[tool_name](doc, args)

    if mutating:
        _append_audit(doc, call_id, tool_name, args, result)
        doc.save()

    from verto.api.mobile.voice_jha import _serialize_jha

    return {
        "ok": True,
        "replayed": False,
        "tool_name": tool_name,
        "result": result,
        "jha": _serialize_jha(doc),
    }
