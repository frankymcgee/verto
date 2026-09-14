import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from verto.api.mobile.voice_jha_permissions import user_can_access_work_summary


SETTINGS_DOCTYPE = "Verto Mobile Settings"
JHA_DOCTYPE = "Digital Job Hazard Analysis"
DEFAULT_REALTIME_MODEL = "gpt-realtime-2.1"
DEFAULT_TRANSCRIPTION_MODEL = "gpt-realtime-whisper"
MAX_SDP_LENGTH = 250_000
ACTIVE_JHA_STATUSES = (
    "Draft",
    "Voice Discussion in Progress",
    "Incomplete - Actions Required",
    "Ready for Team Review",
)


def _require_login():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def _get_peri_bot():
    try:
        settings = frappe.get_cached_doc(SETTINGS_DOCTYPE)
    except Exception:
        return ""

    for fieldname in ("peri_bot_name", "ai_photo_analysis_bot"):
        if settings.meta.has_field(fieldname):
            value = str(settings.get(fieldname) or "").strip()
            if value and frappe.db.exists("Raven Bot", value):
                return value
    return ""


def _get_peri_bot_doc():
    bot_name = _get_peri_bot()
    if not bot_name:
        frappe.throw(_("Configure a PERI Raven Bot in Verto Mobile Settings."), frappe.ValidationError)

    bot = frappe.get_cached_doc("Raven Bot", bot_name)
    if bot.meta.has_field("is_ai_bot") and not cint(bot.get("is_ai_bot")):
        frappe.throw(_("The configured PERI Raven Bot is not an AI bot."), frappe.ValidationError)

    provider = str(bot.get("model_provider") or "OpenAI").strip()
    if provider and provider.lower() != "openai":
        frappe.throw(
            _("PERI voice currently requires a Raven Bot using the OpenAI provider."),
            frappe.ValidationError,
        )
    return bot


def _get_bot_instructions(bot) -> str:
    stored = str(bot.get("instruction") or "").strip()
    if not cint(bot.get("dynamic_instructions")):
        return stored

    try:
        from raven.ai.handler import get_instructions

        return str(get_instructions(bot) or stored).strip()
    except Exception:
        frappe.log_error(
            title="PERI voice dynamic instructions failed",
            message=frappe.get_traceback(),
        )
        return stored


def _get_realtime_model(bot) -> str:
    configured = str(bot.get("model") or "").strip()
    if configured.startswith("gpt-realtime"):
        return configured
    return DEFAULT_REALTIME_MODEL


def _validate_work_summary(work_summary: str):
    if not work_summary or not frappe.db.exists("Task", work_summary):
        frappe.throw(_("Work Summary was not found."), frappe.DoesNotExistError)

    task = frappe.get_doc("Task", work_summary)
    if task.get("type") != "Work Summary":
        frappe.throw(_("The selected Task is not a Work Summary."), frappe.ValidationError)
    if not task.has_permission("read"):
        frappe.throw(_("You cannot access this Work Summary."), frappe.PermissionError)
    if not user_can_access_work_summary(task.name):
        frappe.throw(_("This Work Summary is not assigned to you."), frappe.PermissionError)

    return task


def _get_active_jha_name(work_summary: str) -> str:
    return (
        frappe.db.get_value(
            JHA_DOCTYPE,
            {
                "work_summary": work_summary,
                "jha_status": ["in", list(ACTIVE_JHA_STATUSES)],
            },
            "name",
            order_by="modified desc",
        )
        or ""
    )


def _row_dict(row, fields):
    return {field: row.get(field) for field in fields}


def _serialize_jha(doc):
    return {
        "name": doc.name,
        "status": doc.jha_status,
        "revision": doc.revision,
        "project": doc.project,
        "work_summary": doc.work_summary,
        "work_summary_title": doc.work_summary_title,
        "work_order_number": doc.work_order_number,
        "work_area": doc.work_area,
        "ai_bot": doc.ai_bot,
        "source_revision": doc.source_revision,
        "modified": doc.modified,
        "voice_session_reference": doc.get("voice_session_reference"),
        "voice_model": doc.get("voice_model"),
        "voice_started_at": doc.get("voice_started_at"),
        "voice_transcription_consent_confirmed": cint(
            doc.get("voice_transcription_consent_confirmed")
        ),
        "voice_transcription_consent_confirmed_by": doc.get(
            "voice_transcription_consent_confirmed_by"
        ),
        "voice_transcription_consent_confirmed_at": doc.get(
            "voice_transcription_consent_confirmed_at"
        ),
        "work_steps": [
            _row_dict(
                row,
                (
                    "name",
                    "idx",
                    "sequence",
                    "activity",
                    "step_origin",
                    "source_step_identifier",
                    "hold_or_pause_point",
                ),
            )
            for row in (doc.work_steps or [])
        ],
        "hazards_and_controls": [
            _row_dict(
                row,
                (
                    "name",
                    "idx",
                    "work_step_sequence",
                    "work_step_reference",
                    "hazard_or_energy_source",
                    "people_exposed",
                    "credible_consequence",
                    "existing_controls",
                    "additional_controls",
                    "hierarchy_level",
                    "control_owner",
                    "verification_method",
                    "verification_status",
                    "critical_risk",
                    "critical_control",
                    "permit_or_ccv_required",
                    "initial_risk",
                    "residual_risk",
                    "information_source",
                ),
            )
            for row in (doc.hazards_and_controls or [])
        ],
        "participants": [
            _row_dict(
                row,
                (
                    "name",
                    "idx",
                    "employee",
                    "participant_name",
                    "role",
                    "present_for_discussion",
                    "transcription_consent",
                    "acknowledged",
                    "acknowledged_at",
                ),
            )
            for row in (doc.participants or [])
        ],
    }


def _get_jha_doc(jha_name: str):
    if not jha_name or not frappe.db.exists(JHA_DOCTYPE, jha_name):
        frappe.throw(_("Digital JHA was not found."), frappe.DoesNotExistError)

    doc = frappe.get_doc(JHA_DOCTYPE, jha_name)
    if not doc.has_permission("read"):
        frappe.throw(_("You cannot access this Digital JHA."), frappe.PermissionError)

    return doc


def _build_voice_instructions(task, jha, bot) -> str:
    bot_instructions = _get_bot_instructions(bot)
    existing_steps = "\n".join(
        f"- Step {row.sequence or row.idx}: {row.activity}"
        for row in (jha.work_steps or [])
        if row.activity
    ) or "- No structured work steps have been recorded yet."

    existing_hazards = "\n".join(
        f"- Step {row.work_step_sequence or '?'}: {row.hazard_or_energy_source}"
        for row in (jha.hazards_and_controls or [])
        if row.hazard_or_energy_source
    ) or "- No structured hazards have been recorded yet."

    return f"""
{bot_instructions}

You are PERI, facilitating a live crew discussion to DEVELOP A DRAFT Job Hazard Analysis (JHA) for Mine Site Support. This is a safety-critical conversation. You are an assistant and facilitator, not the accountable approver.

NON-NEGOTIABLE SAFETY RULES:
- Never state or imply that the job, JHA, controls, plant, isolation or work area is safe, approved, authorised or cleared to proceed.
- Never sign, acknowledge, approve, submit or authorise work for any person.
- Never invent site rules, permits, procedures, legislation, hazards, controls or facts. Ask for clarification when information is missing.
- Treat vague controls such as 'be careful', 'use PPE' or 'follow the procedure' as incomplete. Ask what specific control will be implemented, who owns it and how it will be verified.
- Where a credible high-consequence hazard may exist, explicitly ask the crew about critical controls, isolation, permits/CCVs, hold points and verification.
- Human review and individual acknowledgement remain mandatory before work proceeds.
- This voice milestone is discussion-only. You do not currently have tools that write JHA rows. Do not claim that spoken information has been saved into the structured JHA unless the application explicitly confirms it.

FACILITATION METHOD:
1. Briefly greet the crew and identify the Work Summary below.
2. Ask the crew to describe the job in their own words before relying on the planned description.
3. Work through the job one step at a time.
4. For each step discuss: people exposed; hazards/energy sources; credible consequences; existing controls; additional controls; hierarchy of control; control owner; verification method; residual risk; critical controls; permits/CCVs/SWMS; hold/pause points; stop-work triggers; and emergency/recovery considerations where relevant.
5. Ask concise follow-up questions rather than delivering long lectures.
6. Periodically read back what you understood and ask the crew to correct anything inaccurate.
7. At the end, summarise unresolved items and remind the team that the structured JHA must be reviewed and completed in Verto before sign-on.

CONTROLLED WORK CONTEXT:
JHA: {jha.name} revision {jha.revision or 1}
Project: {task.project or ''}
Work Summary: {task.name} — {task.subject or ''}
Work Area: {task.get('parent_task_name') or ''}
Work Order: {task.get('work_order_number') or ''}
Planned description: {task.get('description') or 'No description supplied.'}

CURRENT STRUCTURED STEPS:
{existing_steps}

CURRENT STRUCTURED HAZARDS:
{existing_hazards}
""".strip()


def _create_realtime_call(*, sdp: str, task, jha, bot):
    from raven.ai.openai_client import get_open_ai_client

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

    model = _get_realtime_model(bot)
    response = calls.create(
        sdp=sdp,
        session={
            "type": "realtime",
            "model": model,
            "instructions": _build_voice_instructions(task, jha, bot),
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "noise_reduction": {"type": "far_field"},
                    "transcription": {
                        "model": DEFAULT_TRANSCRIPTION_MODEL,
                        "language": "en",
                        "delay": "low",
                    },
                }
            },
        },
    )

    # Keep the SDP answer byte-for-byte equivalent to OpenAI's response. In
    # particular, do not trim the final CRLF: strict SDP parsers may reject a
    # description whose final line terminator has been removed.
    answer_sdp = str(getattr(response, "text", "") or "")
    if not answer_sdp:
        frappe.throw(_("OpenAI did not return a WebRTC SDP answer."), frappe.ValidationError)

    http_response = getattr(response, "response", None)
    request_id = ""
    if http_response is not None:
        request_id = str(http_response.headers.get("x-request-id") or "").strip()

    return {
        "sdp": answer_sdp,
        "model": model,
        "session_reference": request_id,
    }


@frappe.whitelist(methods=["GET"])
def get_voice_jha_bootstrap(work_summary: str):
    """Return trusted Work Summary context and any active JHA draft.

    This endpoint deliberately does not submit, approve, sign or authorise work.
    """
    _require_login()
    task = _validate_work_summary(work_summary)

    existing_name = _get_active_jha_name(task.name)
    existing_jha = None
    if existing_name:
        existing_jha = _serialize_jha(_get_jha_doc(existing_name))

    peri_bot = _get_peri_bot()
    return {
        "work_summary": task.name,
        "title": task.subject,
        "project": task.project,
        "work_area": task.get("parent_task_name") or "",
        "work_order_number": task.get("work_order_number") or "",
        "description": task.get("description") or "",
        "peri_bot": peri_bot,
        "existing_jha": existing_jha,
        "realtime_enabled": bool(peri_bot),
        "prototype_stage": "live-voice-pilot",
        "notice": "PERI can prepare a draft JHA only. Human review and sign-on remain mandatory before work proceeds.",
    }


@frappe.whitelist(methods=["GET"])
def get_voice_jha_snapshot(jha_name: str):
    _require_login()
    return _serialize_jha(_get_jha_doc(jha_name))


@frappe.whitelist(methods=["POST"])
def create_voice_jha_draft(work_summary: str):
    _require_login()
    task = _validate_work_summary(work_summary)

    existing = _get_active_jha_name(task.name)
    if existing:
        result = _serialize_jha(_get_jha_doc(existing))
        result["created"] = False
        return result

    doc = frappe.get_doc(
        {
            "doctype": JHA_DOCTYPE,
            "project": task.project,
            "work_summary": task.name,
            "work_summary_title": task.subject,
            "work_order_number": task.get("work_order_number") or "",
            "work_area": task.get("parent_task_name") or "",
            "jha_status": "Draft",
            "ai_bot": _get_peri_bot() or None,
        }
    )

    if not doc.has_permission("create"):
        frappe.throw(_("You cannot create a Digital JHA for this Work Summary."), frappe.PermissionError)

    doc.insert()

    result = _serialize_jha(doc)
    result["created"] = True
    return result


@frappe.whitelist(methods=["POST"])
def start_voice_jha_call(jha_name: str, sdp: str, consent_confirmed=0):
    """Negotiate the live PERI WebRTC session without exposing OpenAI credentials.

    The endpoint records facilitator confirmation that everyone present consented to
    microphone use/transcription. It does not create structured JHA rows, submit,
    approve, sign or authorise the JHA.
    """
    _require_login()

    if not cint(consent_confirmed):
        frappe.throw(
            _("Confirm that everyone present has agreed to microphone use and transcription."),
            frappe.ValidationError,
        )

    # SDP is a line-oriented wire format. Do not call strip()/rstrip() here:
    # browser offers normally end in CRLF, and removing that terminator can make
    # OpenAI's strict SDP parser fail with `failed to unmarshal SDP: EOF`.
    offer_sdp = str(sdp or "")
    if not offer_sdp or not offer_sdp.startswith("v=0"):
        frappe.throw(_("A valid WebRTC SDP offer is required."), frappe.ValidationError)
    if len(offer_sdp) > MAX_SDP_LENGTH:
        frappe.throw(_("The WebRTC SDP offer is unexpectedly large."), frappe.ValidationError)

    jha = _get_jha_doc(jha_name)
    if not jha.has_permission("write"):
        frappe.throw(_("You cannot start voice for this Digital JHA."), frappe.PermissionError)
    if jha.jha_status not in ACTIVE_JHA_STATUSES:
        frappe.throw(
            _("Voice discussion is only available while the Digital JHA is active."),
            frappe.ValidationError,
        )

    task = _validate_work_summary(jha.work_summary)
    bot = _get_peri_bot_doc()

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
    jha.save()

    return {
        "sdp": call["sdp"],
        "model": call["model"],
        "session_reference": call.get("session_reference") or "",
        "consent_confirmed_at": started_at,
        "jha": _serialize_jha(jha),
    }
