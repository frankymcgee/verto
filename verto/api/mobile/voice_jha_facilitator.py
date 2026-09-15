from __future__ import annotations

import copy

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from verto.api.mobile import voice_jha as base
from verto.api.mobile.peri_voice_settings import get_peri_voice_settings
from verto.api.mobile.voice_jha_progress import (
    calculate_facilitation_progress,
    serialize_jha,
    sync_facilitation_fields,
)
from verto.api.mobile.voice_jha_tools import get_realtime_jha_tools


def _streamlined_tools() -> list[dict]:
    tools = copy.deepcopy(get_realtime_jha_tools())
    descriptions = {
        "record_work_step": (
            "Create or update one confirmed job step. Establish and confirm the full ordered job-step list "
            "before starting hazard analysis. Do not set hold_or_pause_point until the crew has explicitly "
            "answered the hold-point question for that step."
        ),
        "record_hazard_and_control": (
            "Create or update one hazard and its controls for the current job step. The core JHA fields are "
            "hazard, controls, critical control and critical-control owner where applicable. Other optional "
            "fields may be recorded when the crew naturally provides them, but do not interrupt the field "
            "discussion merely to populate optional database fields."
        ),
        "run_jha_completeness_check": (
            "Check the field JHA flow after all job steps have been completed and the development team has "
            "been recorded. This is a completeness aid only, not an approval or safety decision."
        ),
        "mark_ready_for_human_review": (
            "Mark the draft Ready for Team Review only after every job step has been completed through the "
            "facilitation workflow and the development team has been recorded."
        ),
    }
    for tool in tools:
        name = tool.get("name")
        if name in descriptions:
            tool["description"] = descriptions[name]

    tools.extend(
        [
            {
                "type": "function",
                "name": "confirm_job_steps",
                "description": (
                    "Persist that the crew has confirmed the complete ordered job-step list. Call this only "
                    "after the team explicitly agrees that the list and sequence are correct. This moves the "
                    "facilitator to the first incomplete job step."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "complete_current_step",
                "description": (
                    "Close the current job step and advance to the next one. Call only after the crew has "
                    "finished identifying hazards and specific controls, has explicitly considered whether "
                    "critical controls apply and supplied their owners where applicable, and has explicitly "
                    "answered the hold-point question yes or no. The server refuses to advance if the step "
                    "is incomplete."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "step_sequence": {"type": "integer", "minimum": 1},
                    },
                    "required": ["step_sequence"],
                    "additionalProperties": False,
                },
            },
        ]
    )
    return tools


def _build_facilitation_instructions(task, jha, bot, config: dict) -> str:
    bot_instructions = base._get_bot_instructions(bot)
    conversation_style = base._build_conversation_style_instructions(config)
    progress = calculate_facilitation_progress(jha)

    steps = [row for row in (jha.work_steps or []) if row.activity]
    existing_steps = "\n".join(
        f"- Step {row.sequence or row.idx}: {row.activity}"
        for row in steps
    ) or "- No job steps are currently recorded."

    progress_lines = []
    for state in progress["steps"]:
        marker = "COMPLETE" if state["discussion_complete"] else "CURRENT" if state["is_current"] else "PENDING"
        progress_lines.append(
            f"- Step {state['sequence']}: {marker}; hazards={state['hazard_count']}; "
            f"controls={'yes' if state['controls_complete'] else 'no'}; "
            f"critical-controls-reviewed={'yes' if state['critical_controls_reviewed'] else 'no'}; "
            f"hold-point-confirmed={'yes' if state['hold_point_complete'] else 'no'}"
        )
    current_progress = "\n".join(progress_lines) or "- No step analysis has been completed yet."

    return f"""
{bot_instructions}

You are PERI, facilitating a live crew discussion to DEVELOP A DRAFT Job Hazard Analysis (JHA) for Mine Site Support. The field JHA must flow in the same order as the workpack: TASK STEP -> HAZARD -> CONTROL -> CRITICAL CONTROL OWNER -> HOLD POINT.

NON-NEGOTIABLE SAFETY RULES:
- Never state or imply that the job, JHA, plant, isolation, controls or work area is safe, approved, authorised or cleared to proceed.
- Never sign, acknowledge, approve, submit or authorise work for any person.
- Never invent hazards, controls, critical controls, owners, permits, site requirements or facts. Ask the crew when information is missing.
- Challenge vague controls such as 'be careful', 'use PPE' or 'follow the procedure' by asking what specific control will actually be in place.
- Human review and sign-on remain mandatory after the discussion.

PERSISTED FACILITATION STATE — THIS IS AUTHORITATIVE:
- Stage: {progress['stage']}
- Job steps confirmed: {'Yes' if progress['job_steps_confirmed'] else 'No'}
- Current step: {progress['current_step_sequence'] or 'None'} {progress['current_step_activity']}
- Completed steps: {progress['completed_step_count']} of {progress['total_step_count']}

RESUME RULES:
- Do not restart a completed phase after a reconnect or page refresh.
- If Stage is Job Steps, establish/confirm the complete ordered step list and then call confirm_job_steps.
- If Stage is Step Analysis, resume at the persisted Current step. Do not re-question completed steps unless the crew asks to correct them.
- If Stage is Development Team, collect the participant names/roles; do not return to step analysis unless a gap is identified.
- If Stage is Completeness Check, run the completeness check and resolve only its listed gaps.

ORDERED FACILITATION FLOW — FOLLOW THIS ORDER STRICTLY:

PHASE 1 — IDENTIFY THE JOB
1. Start with the Work Summary name exactly as supplied below. Keep this very brief.
2. Do not begin by interviewing the crew about participants. Microphone/transcription consent has already been confirmed in the Verto interface. Development-team names are collected near the end.

PHASE 2 — ESTABLISH THE COMPLETE JOB-STEP LIST
3. If job steps are not yet confirmed and CURRENT JOB STEPS already contains planned steps, read the numbered list concisely and ask one question: whether the sequence is correct and whether anything must be added, removed, renamed or reordered.
4. If there are no job steps, ask the team to talk you through the job from start to finish. Build the full ordered step list first using record_work_step.
5. When the team explicitly confirms the complete list, call confirm_job_steps. Do not begin hazard analysis before that tool succeeds.
6. Planned child Tasks are a starting point, not unquestionable truth. Correct them in the JHA when the team confirms the real work method differs.

PHASE 3 — WORK THROUGH ONE STEP AT A TIME
7. Work only on the persisted current step. Do not skip ahead.
8. Ask: "What hazards are there for this step?" Let the crew identify all applicable hazards/energy sources. Use focused prompts only when needed; do not lecture or supply hazards as facts.
9. Record each confirmed hazard with record_hazard_and_control.
10. For each hazard, ask what controls will be in place. Record the specific controls. Challenge vague answers once, concisely.
11. After hazards and controls are covered, explicitly ask whether any of those controls are critical controls. If yes, confirm each critical control and who owns it. If no, accept the crew's explicit no.
12. Ask exactly one close-out question: "Is there a hold point for this step?" Record the explicit yes/no answer by updating the work step with hold_or_pause_point.
13. Once the crew has explicitly covered critical controls/owners and the hold-point decision, call complete_current_step for the current sequence. If the server reports a missing item, ask only for that missing item.
14. When complete_current_step succeeds, move directly to the newly persisted current step. Do not repeat the previous step.
15. Repeat for every job step.

PHASE 4 — FINAL FIELD CHECK AND DEVELOPMENT TEAM
16. After the last step is completed, ask whether any job step, hazard or control has been missed. Only revisit items they identify or that remain incomplete.
17. Then record the JHA development team: ask for the names and roles of the people who participated. Confirm that the previously recorded group transcription consent applies to those people before setting individual transcription_consent true.
18. Run the completeness check. Resolve only the listed field-JHA gaps.
19. When complete, mark the draft Ready for Team Review and clearly state that human review/sign-on is still required and that you have not authorised the work.

DO NOT TURN THIS INTO A DATABASE INTERVIEW:
- The mandatory spoken flow is job steps, hazards, controls, critical controls/owners where applicable, and hold points.
- Credible consequence, people exposed, hierarchy-of-control category, verification method/status, initial risk and residual risk are OPTIONAL conversational fields. Record them if the crew naturally provides them or if a specific safety-critical ambiguity requires clarification, but do not routinely stop the crew to populate them.
- Permits/CCVs may be recorded when identified during the relevant step, but do not run a separate questionnaire unless the crew or hazard requires it.
- Ask one primary question at a time.
- Do not repeat the crew's answer merely to show understanding.
- Successful tool writes should normally be silent.

TOOL RULES:
- Record only information stated or confirmed by the crew.
- Reuse stable identifiers for corrections.
- Use get_current_jha_state if unsure what is already recorded.
- confirm_job_steps requires explicit crew confirmation of the whole ordered list.
- complete_current_step is the only normal way to advance the persisted current step.
- record_participant never acknowledges or signs for a person.
- There is deliberately no tool to approve, sign, authorise work or declare the job safe.

{conversation_style}

CONTROLLED WORK CONTEXT:
JHA: {jha.name} revision {jha.revision or 1}
Project: {task.project or ''}
Work Summary: {task.name} — {task.subject or ''}
Work Area: {task.get('parent_task_name') or ''}
Work Order: {task.get('work_order_number') or ''}
Planned description: {task.get('description') or 'No description supplied.'}

CURRENT JOB STEPS:
{existing_steps}

PERSISTED STEP PROGRESS:
{current_progress}
""".strip()


def _build_realtime_session(task, jha, bot, config: dict) -> dict:
    session = base._build_realtime_session(task, jha, bot, config)
    session["instructions"] = _build_facilitation_instructions(task, jha, bot, config)
    session["tools"] = _streamlined_tools()
    return session


def _create_realtime_call(*, sdp: str, task, jha, bot):
    from raven.ai.openai_client import get_open_ai_client

    config = get_peri_voice_settings()
    if not config.get("enabled"):
        frappe.throw(_("PERI Voice JHA is disabled in Verto Mobile Settings."), frappe.ValidationError)

    client = get_open_ai_client()
    realtime = getattr(client, "realtime", None)
    calls = getattr(realtime, "calls", None) if realtime else None
    if calls is None or not hasattr(calls, "create"):
        frappe.throw(
            _(
                "The installed OpenAI Python SDK does not support Realtime WebRTC calls. "
                "Update Raven/OpenAI dependencies before enabling PERI voice."
            ),
            frappe.ValidationError,
        )

    response = calls.create(
        sdp=sdp,
        session=_build_realtime_session(task, jha, bot, config),
    )
    answer_sdp = str(getattr(response, "text", "") or "")
    if not answer_sdp:
        frappe.throw(_("OpenAI did not return a WebRTC SDP answer."), frappe.ValidationError)

    request_id = ""
    http_response = getattr(response, "response", None)
    if http_response is not None:
        request_id = str(http_response.headers.get("x-request-id") or "").strip()

    return {
        "sdp": answer_sdp,
        "model": config["realtime_model"],
        "configuration": base._public_voice_configuration(config),
        "session_reference": request_id,
    }


@frappe.whitelist(methods=["POST"])
def start_voice_jha_call(jha_name: str, sdp: str, consent_confirmed=0):
    base._require_login()

    if not cint(consent_confirmed):
        frappe.throw(
            _("Confirm that everyone present has agreed to microphone use and transcription."),
            frappe.ValidationError,
        )

    offer_sdp = str(sdp or "")
    if not offer_sdp or not offer_sdp.startswith("v=0"):
        frappe.throw(_("A valid WebRTC SDP offer is required."), frappe.ValidationError)
    if len(offer_sdp) > base.MAX_SDP_LENGTH:
        frappe.throw(_("The WebRTC SDP offer is unexpectedly large."), frappe.ValidationError)

    jha = base._get_jha_doc(jha_name)
    if not jha.has_permission("write"):
        frappe.throw(_("You cannot start voice for this Digital JHA."), frappe.PermissionError)
    if jha.jha_status not in base.ACTIVE_JHA_STATUSES:
        frappe.throw(
            _("Voice discussion is only available while the Digital JHA is active."),
            frappe.ValidationError,
        )

    sync_facilitation_fields(jha, update_timestamp=False)
    task = base._validate_work_summary(jha.work_summary)
    bot = base._get_peri_bot_doc()

    try:
        call = _create_realtime_call(sdp=offer_sdp, task=task, jha=jha, bot=bot)
    except (frappe.ValidationError, frappe.PermissionError):
        raise
    except Exception:
        frappe.log_error(
            title=f"PERI voice connection failed for {jha.name}",
            message=frappe.get_traceback(),
        )
        frappe.throw(
            _("Could not start the PERI voice session. Check the Raven/OpenAI Realtime configuration."),
            frappe.ValidationError,
        )

    started_at = now_datetime()
    jha.jha_status = "Voice Discussion in Progress"
    jha.voice_transcription_consent_confirmed = 1
    jha.voice_transcription_consent_confirmed_by = frappe.session.user
    jha.voice_transcription_consent_confirmed_at = started_at
    jha.voice_model = call["model"]
    jha.voice_started_at = started_at
    jha.voice_session_reference = call.get("session_reference") or ""
    sync_facilitation_fields(jha)
    jha.save()

    return {
        "sdp": call["sdp"],
        "model": call["model"],
        "configuration": call.get("configuration") or {},
        "session_reference": call.get("session_reference") or "",
        "consent_confirmed_at": started_at,
        "jha": serialize_jha(jha),
    }
