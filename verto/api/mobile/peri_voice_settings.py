from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint, flt


SETTINGS_DOCTYPE = "Verto Mobile Settings"

REALTIME_MODELS = (
    "gpt-realtime-2.1",
    "gpt-realtime-2.1-mini",
    "gpt-realtime-2",
    "gpt-realtime-1.5",
)

TRANSCRIPTION_MODELS = (
    "gpt-realtime-whisper",
    "gpt-live-transcribe",
    "gpt-transcribe",
    "gpt-4o-transcribe",
    "gpt-4o-mini-transcribe",
    "whisper-1",
)

REALTIME_VOICES = (
    "marin",
    "cedar",
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "sage",
    "shimmer",
    "verse",
)

REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")
TRANSCRIPTION_DELAYS = ("minimal", "low", "medium", "high", "xhigh")
TURN_DETECTION_MODES = ("server_vad", "semantic_vad")
SEMANTIC_VAD_EAGERNESS = ("auto", "low", "medium", "high")
NOISE_REDUCTION_MODES = ("far_field", "near_field", "disabled")
RESPONSE_STYLES = ("Fast / Concise", "Normal", "Detailed")
ACKNOWLEDGEMENT_MODES = ("None", "Minimal (max 2 words)", "Brief sentence")
READBACK_MODES = (
    "Final only",
    "End of each work step + final",
    "Checkpoints + final",
    "Frequent",
)

DEFAULTS = {
    "enabled": True,
    "realtime_model": "gpt-realtime-2.1",
    "custom_realtime_model": "",
    "reasoning_effort": "low",
    "voice": "marin",
    "custom_voice_id": "",
    "speed": 1.0,
    "response_style": "Fast / Concise",
    "acknowledgement_mode": "Minimal (max 2 words)",
    "readback_mode": "End of each work step + final",
    "one_question_at_a_time": True,
    "avoid_paraphrasing": True,
    "silent_tool_success": True,
    "max_spoken_sentences": 2,
    "transcription_model": "gpt-realtime-whisper",
    "custom_transcription_model": "",
    "transcription_language": "en",
    "transcription_delay": "low",
    "noise_reduction": "far_field",
    "turn_detection": "server_vad",
    "semantic_vad_eagerness": "auto",
}

FIELD_DEFAULTS = {
    "peri_voice_enabled": 1,
    "peri_voice_realtime_model": DEFAULTS["realtime_model"],
    "peri_voice_reasoning_effort": DEFAULTS["reasoning_effort"],
    "peri_voice_voice": DEFAULTS["voice"],
    "peri_voice_speed": DEFAULTS["speed"],
    "peri_voice_response_style": DEFAULTS["response_style"],
    "peri_voice_acknowledgement_mode": DEFAULTS["acknowledgement_mode"],
    "peri_voice_readback_mode": DEFAULTS["readback_mode"],
    "peri_voice_one_question_at_a_time": 1,
    "peri_voice_avoid_paraphrasing": 1,
    "peri_voice_silent_tool_success": 1,
    "peri_voice_max_spoken_sentences": DEFAULTS["max_spoken_sentences"],
    "peri_voice_transcription_model": DEFAULTS["transcription_model"],
    "peri_voice_transcription_language": DEFAULTS["transcription_language"],
    "peri_voice_transcription_delay": DEFAULTS["transcription_delay"],
    "peri_voice_noise_reduction": DEFAULTS["noise_reduction"],
    "peri_voice_turn_detection": DEFAULTS["turn_detection"],
    "peri_voice_semantic_vad_eagerness": DEFAULTS["semantic_vad_eagerness"],
}


def _select_options(values) -> str:
    return "\n".join(values)


PERI_VOICE_FIELDS = [
    {
        "fieldname": "peri_voice_jha_tab",
        "label": "PERI Voice JHA",
        "fieldtype": "Tab Break",
        "insert_after": "project_tools",
        "description": "Configure the OpenAI Realtime behaviour used by Develop JHA with PERI. OpenAI credentials remain managed by Raven Settings.",
    },
    {
        "fieldname": "peri_voice_enabled",
        "label": "Enable PERI Voice JHA",
        "fieldtype": "Check",
        "insert_after": "peri_voice_jha_tab",
        "default": "1",
    },
    {
        "fieldname": "peri_voice_model_section",
        "label": "Realtime Model & Voice",
        "fieldtype": "Section Break",
        "insert_after": "peri_voice_enabled",
        "depends_on": "eval:doc.peri_voice_enabled",
    },
    {
        "fieldname": "peri_voice_realtime_model",
        "label": "Realtime Model",
        "fieldtype": "Select",
        "insert_after": "peri_voice_model_section",
        "options": _select_options(REALTIME_MODELS),
        "default": DEFAULTS["realtime_model"],
        "description": "OpenAI Realtime model used for the live PERI conversation.",
    },
    {
        "fieldname": "peri_voice_custom_realtime_model",
        "label": "Custom Realtime Model Override",
        "fieldtype": "Data",
        "insert_after": "peri_voice_realtime_model",
        "description": "Optional. When set, this model ID overrides the Realtime Model selection. Use only an OpenAI model supported by the Realtime calls endpoint.",
    },
    {
        "fieldname": "peri_voice_reasoning_effort",
        "label": "Reasoning Effort",
        "fieldtype": "Select",
        "insert_after": "peri_voice_custom_realtime_model",
        "options": _select_options(REASONING_EFFORTS),
        "default": DEFAULTS["reasoning_effort"],
        "description": "Used by reasoning-capable Realtime 2.x models. Lower values reduce latency; higher values can improve complex reasoning.",
    },
    {
        "fieldname": "peri_voice_output_column",
        "fieldtype": "Column Break",
        "insert_after": "peri_voice_reasoning_effort",
    },
    {
        "fieldname": "peri_voice_voice",
        "label": "Voice",
        "fieldtype": "Select",
        "insert_after": "peri_voice_output_column",
        "options": _select_options(REALTIME_VOICES),
        "default": DEFAULTS["voice"],
        "description": "Built-in Realtime voice. Marin and Cedar are recommended for best quality.",
    },
    {
        "fieldname": "peri_voice_custom_voice_id",
        "label": "Custom Voice ID Override",
        "fieldtype": "Data",
        "insert_after": "peri_voice_voice",
        "description": "Optional OpenAI custom voice ID, for example voice_1234. When set, it overrides the built-in Voice selection.",
    },
    {
        "fieldname": "peri_voice_speed",
        "label": "Voice Speed",
        "fieldtype": "Float",
        "insert_after": "peri_voice_custom_voice_id",
        "default": "1.0",
        "description": "Realtime output speech speed. Supported range is 0.25 to 1.5; 1.0 is normal speed.",
        "precision": "2",
    },
    {
        "fieldname": "peri_voice_conversation_section",
        "label": "Conversation Behaviour",
        "fieldtype": "Section Break",
        "insert_after": "peri_voice_speed",
        "depends_on": "eval:doc.peri_voice_enabled",
    },
    {
        "fieldname": "peri_voice_response_style",
        "label": "Response Style",
        "fieldtype": "Select",
        "insert_after": "peri_voice_conversation_section",
        "options": _select_options(RESPONSE_STYLES),
        "default": DEFAULTS["response_style"],
        "description": "Fast / Concise minimizes spoken time. Normal allows modest explanation. Detailed is for training or complex discussion.",
    },
    {
        "fieldname": "peri_voice_acknowledgement_mode",
        "label": "Acknowledgement Style",
        "fieldtype": "Select",
        "insert_after": "peri_voice_response_style",
        "options": _select_options(ACKNOWLEDGEMENT_MODES),
        "default": DEFAULTS["acknowledgement_mode"],
        "description": "Controls whether PERI says things like Recorded or Got it after crew answers and successful draft writes.",
    },
    {
        "fieldname": "peri_voice_max_spoken_sentences",
        "label": "Maximum Spoken Sentences Per Turn",
        "fieldtype": "Int",
        "insert_after": "peri_voice_acknowledgement_mode",
        "default": str(DEFAULTS["max_spoken_sentences"]),
        "description": "Soft cap for normal spoken turns. Safety-critical clarification and final review may exceed this when necessary. Recommended: 1-2 for field use.",
    },
    {
        "fieldname": "peri_voice_behaviour_column",
        "fieldtype": "Column Break",
        "insert_after": "peri_voice_max_spoken_sentences",
    },
    {
        "fieldname": "peri_voice_readback_mode",
        "label": "Read-back Frequency",
        "fieldtype": "Select",
        "insert_after": "peri_voice_behaviour_column",
        "options": _select_options(READBACK_MODES),
        "default": DEFAULTS["readback_mode"],
        "description": "Controls when PERI verbally summarizes recorded JHA information instead of immediately moving to the next question.",
    },
    {
        "fieldname": "peri_voice_one_question_at_a_time",
        "label": "Ask One Question at a Time",
        "fieldtype": "Check",
        "insert_after": "peri_voice_readback_mode",
        "default": "1",
        "description": "Prevents PERI from stacking several questions into a long spoken turn.",
    },
    {
        "fieldname": "peri_voice_avoid_paraphrasing",
        "label": "Avoid Repeating / Paraphrasing Crew Answers",
        "fieldtype": "Check",
        "insert_after": "peri_voice_one_question_at_a_time",
        "default": "1",
        "description": "When enabled, PERI should not repeat the crew's answer merely to confirm it unless clarification or a configured read-back is required.",
    },
    {
        "fieldname": "peri_voice_silent_tool_success",
        "label": "Keep Successful Draft Writes Silent",
        "fieldtype": "Check",
        "insert_after": "peri_voice_avoid_paraphrasing",
        "default": "1",
        "description": "When enabled, successful JHA tool writes are not narrated back to the crew; PERI immediately continues to the next missing question.",
    },
    {
        "fieldname": "peri_voice_input_section",
        "label": "Microphone & Transcription",
        "fieldtype": "Section Break",
        "insert_after": "peri_voice_silent_tool_success",
        "depends_on": "eval:doc.peri_voice_enabled",
    },
    {
        "fieldname": "peri_voice_transcription_model",
        "label": "Transcription Model",
        "fieldtype": "Select",
        "insert_after": "peri_voice_input_section",
        "options": _select_options(TRANSCRIPTION_MODELS),
        "default": DEFAULTS["transcription_model"],
        "description": "Speech-to-text model used for the live crew transcript preview.",
    },
    {
        "fieldname": "peri_voice_custom_transcription_model",
        "label": "Custom Transcription Model Override",
        "fieldtype": "Data",
        "insert_after": "peri_voice_transcription_model",
        "description": "Optional. When set, this model ID overrides the Transcription Model selection.",
    },
    {
        "fieldname": "peri_voice_transcription_language",
        "label": "Transcription Language",
        "fieldtype": "Data",
        "insert_after": "peri_voice_custom_transcription_model",
        "default": DEFAULTS["transcription_language"],
        "description": "ISO-639-1 language code sent to transcription, for example en.",
    },
    {
        "fieldname": "peri_voice_transcription_delay",
        "label": "Realtime Whisper Delay",
        "fieldtype": "Select",
        "insert_after": "peri_voice_transcription_language",
        "options": _select_options(TRANSCRIPTION_DELAYS),
        "default": DEFAULTS["transcription_delay"],
        "depends_on": "eval:doc.peri_voice_transcription_model=='gpt-realtime-whisper'",
        "description": "Accuracy/latency trade-off for gpt-realtime-whisper. Higher values wait longer before emitting transcript text.",
    },
    {
        "fieldname": "peri_voice_input_column",
        "fieldtype": "Column Break",
        "insert_after": "peri_voice_transcription_delay",
    },
    {
        "fieldname": "peri_voice_noise_reduction",
        "label": "Noise Reduction",
        "fieldtype": "Select",
        "insert_after": "peri_voice_input_column",
        "options": _select_options(NOISE_REDUCTION_MODES),
        "default": DEFAULTS["noise_reduction"],
        "description": "far_field is suited to shared phones/tablets or room microphones; near_field is suited to close-talking headsets.",
    },
    {
        "fieldname": "peri_voice_turn_detection",
        "label": "Turn Detection",
        "fieldtype": "Select",
        "insert_after": "peri_voice_noise_reduction",
        "options": _select_options(TURN_DETECTION_MODES),
        "default": DEFAULTS["turn_detection"],
        "description": "server_vad responds after detected silence; semantic_vad also considers whether the speaker appears finished.",
    },
    {
        "fieldname": "peri_voice_semantic_vad_eagerness",
        "label": "Semantic VAD Eagerness",
        "fieldtype": "Select",
        "insert_after": "peri_voice_turn_detection",
        "options": _select_options(SEMANTIC_VAD_EAGERNESS),
        "default": DEFAULTS["semantic_vad_eagerness"],
        "depends_on": "eval:doc.peri_voice_turn_detection=='semantic_vad'",
        "description": "Controls how quickly Semantic VAD decides the crew member has finished speaking.",
    },
]


def after_install():
    ensure_peri_voice_settings()


def after_migrate():
    ensure_peri_voice_settings()


def ensure_peri_voice_settings() -> bool:
    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        return False

    create_custom_fields({SETTINGS_DOCTYPE: PERI_VOICE_FIELDS}, update=True)
    frappe.clear_cache(doctype=SETTINGS_DOCTYPE)

    settings = frappe.get_single(SETTINGS_DOCTYPE)
    changed = False
    for fieldname, value in FIELD_DEFAULTS.items():
        if settings.meta.has_field(fieldname) and settings.get(fieldname) in (None, ""):
            settings.set(fieldname, value)
            changed = True

    if changed:
        settings.save(ignore_permissions=True)

    frappe.clear_cache(doctype=SETTINGS_DOCTYPE)
    return True


def _get_value(settings, fieldname: str, default=None):
    if settings.meta.has_field(fieldname):
        value = settings.get(fieldname)
        if value not in (None, ""):
            return value
    return default


def _validated_choice(settings, fieldname: str, default: str, allowed) -> str:
    value = str(_get_value(settings, fieldname, default) or "").strip()
    return value if value in allowed else default


def get_peri_voice_settings() -> dict:
    try:
        settings = frappe.get_cached_doc(SETTINGS_DOCTYPE)
    except Exception:
        return dict(DEFAULTS)

    realtime_model = str(
        _get_value(settings, "peri_voice_custom_realtime_model", "")
        or _get_value(settings, "peri_voice_realtime_model", DEFAULTS["realtime_model"])
    ).strip()
    transcription_model = str(
        _get_value(settings, "peri_voice_custom_transcription_model", "")
        or _get_value(settings, "peri_voice_transcription_model", DEFAULTS["transcription_model"])
    ).strip()

    speed = flt(_get_value(settings, "peri_voice_speed", DEFAULTS["speed"]))
    speed = max(0.25, min(1.5, speed or DEFAULTS["speed"]))

    max_sentences = cint(
        _get_value(
            settings,
            "peri_voice_max_spoken_sentences",
            DEFAULTS["max_spoken_sentences"],
        )
    )
    max_sentences = max(1, min(6, max_sentences or DEFAULTS["max_spoken_sentences"]))

    reasoning_effort = _validated_choice(
        settings,
        "peri_voice_reasoning_effort",
        DEFAULTS["reasoning_effort"],
        REASONING_EFFORTS,
    )
    voice = _validated_choice(
        settings,
        "peri_voice_voice",
        DEFAULTS["voice"],
        REALTIME_VOICES,
    )
    response_style = _validated_choice(
        settings,
        "peri_voice_response_style",
        DEFAULTS["response_style"],
        RESPONSE_STYLES,
    )
    acknowledgement_mode = _validated_choice(
        settings,
        "peri_voice_acknowledgement_mode",
        DEFAULTS["acknowledgement_mode"],
        ACKNOWLEDGEMENT_MODES,
    )
    readback_mode = _validated_choice(
        settings,
        "peri_voice_readback_mode",
        DEFAULTS["readback_mode"],
        READBACK_MODES,
    )
    noise_reduction = _validated_choice(
        settings,
        "peri_voice_noise_reduction",
        DEFAULTS["noise_reduction"],
        NOISE_REDUCTION_MODES,
    )
    turn_detection = _validated_choice(
        settings,
        "peri_voice_turn_detection",
        DEFAULTS["turn_detection"],
        TURN_DETECTION_MODES,
    )
    semantic_eagerness = _validated_choice(
        settings,
        "peri_voice_semantic_vad_eagerness",
        DEFAULTS["semantic_vad_eagerness"],
        SEMANTIC_VAD_EAGERNESS,
    )
    transcription_delay = _validated_choice(
        settings,
        "peri_voice_transcription_delay",
        DEFAULTS["transcription_delay"],
        TRANSCRIPTION_DELAYS,
    )

    return {
        "enabled": bool(cint(_get_value(settings, "peri_voice_enabled", 1))),
        "realtime_model": realtime_model or DEFAULTS["realtime_model"],
        "reasoning_effort": reasoning_effort,
        "voice": voice,
        "custom_voice_id": str(_get_value(settings, "peri_voice_custom_voice_id", "") or "").strip(),
        "speed": speed,
        "response_style": response_style,
        "acknowledgement_mode": acknowledgement_mode,
        "readback_mode": readback_mode,
        "one_question_at_a_time": bool(
            cint(_get_value(settings, "peri_voice_one_question_at_a_time", 1))
        ),
        "avoid_paraphrasing": bool(
            cint(_get_value(settings, "peri_voice_avoid_paraphrasing", 1))
        ),
        "silent_tool_success": bool(
            cint(_get_value(settings, "peri_voice_silent_tool_success", 1))
        ),
        "max_spoken_sentences": max_sentences,
        "transcription_model": transcription_model or DEFAULTS["transcription_model"],
        "transcription_language": str(
            _get_value(
                settings,
                "peri_voice_transcription_language",
                DEFAULTS["transcription_language"],
            )
            or ""
        ).strip(),
        "transcription_delay": transcription_delay,
        "noise_reduction": noise_reduction,
        "turn_detection": turn_detection,
        "semantic_vad_eagerness": semantic_eagerness,
    }
