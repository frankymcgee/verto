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

DEFAULTS = {
    "enabled": True,
    "realtime_model": "gpt-realtime-2.1",
    "custom_realtime_model": "",
    "reasoning_effort": "low",
    "voice": "marin",
    "custom_voice_id": "",
    "speed": 1.0,
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
        "fieldname": "peri_voice_input_section",
        "label": "Microphone & Transcription",
        "fieldtype": "Section Break",
        "insert_after": "peri_voice_speed",
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

    reasoning_effort = str(
        _get_value(settings, "peri_voice_reasoning_effort", DEFAULTS["reasoning_effort"])
    ).strip()
    if reasoning_effort not in REASONING_EFFORTS:
        reasoning_effort = DEFAULTS["reasoning_effort"]

    voice = str(_get_value(settings, "peri_voice_voice", DEFAULTS["voice"])).strip()
    if voice not in REALTIME_VOICES:
        voice = DEFAULTS["voice"]

    noise_reduction = str(
        _get_value(settings, "peri_voice_noise_reduction", DEFAULTS["noise_reduction"])
    ).strip()
    if noise_reduction not in NOISE_REDUCTION_MODES:
        noise_reduction = DEFAULTS["noise_reduction"]

    turn_detection = str(
        _get_value(settings, "peri_voice_turn_detection", DEFAULTS["turn_detection"])
    ).strip()
    if turn_detection not in TURN_DETECTION_MODES:
        turn_detection = DEFAULTS["turn_detection"]

    semantic_eagerness = str(
        _get_value(
            settings,
            "peri_voice_semantic_vad_eagerness",
            DEFAULTS["semantic_vad_eagerness"],
        )
    ).strip()
    if semantic_eagerness not in SEMANTIC_VAD_EAGERNESS:
        semantic_eagerness = DEFAULTS["semantic_vad_eagerness"]

    transcription_delay = str(
        _get_value(settings, "peri_voice_transcription_delay", DEFAULTS["transcription_delay"])
    ).strip()
    if transcription_delay not in TRANSCRIPTION_DELAYS:
        transcription_delay = DEFAULTS["transcription_delay"]

    return {
        "enabled": bool(cint(_get_value(settings, "peri_voice_enabled", 1))),
        "realtime_model": realtime_model or DEFAULTS["realtime_model"],
        "reasoning_effort": reasoning_effort,
        "voice": voice,
        "custom_voice_id": str(_get_value(settings, "peri_voice_custom_voice_id", "") or "").strip(),
        "speed": speed,
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
