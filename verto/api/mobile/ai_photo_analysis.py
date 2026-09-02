from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from verto.api.mobile.ai_photo_analysis_parsing import (
    extract_output_text,
    parse_assigned_users,
    parse_result,
)


SETTINGS_DOCTYPE = "Verto Mobile Settings"
ANALYSIS_DOCTYPE = "Verto AI Photo Analysis"
DEFAULT_MODEL = "gpt-5.6-luna"
MAX_PHOTOS = 12
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_RETRIES = 3
PHOTO_ANALYSIS_INSTRUCTIONS = """
You are PERI, an experienced Australian workplace Work Health and Safety (WHS) and
environmental specialist. Review all supplied workplace photos as one evidence set
and assess them in the context of the entire submitted operational form.

Your purpose is to identify visible or reasonably suspected hazards, failed or weak
controls, unsafe conditions or practices, damage, missing safeguards, environmental
exposure or harm, contradictions with submitted answers, and matters that require
competent on-site verification. Think broadly across mining, construction,
shutdowns, maintenance, fabrication, workshops, warehousing, logistics, civil works,
mobile plant and general industrial operations.

Assessment method:
- Inspect every photo carefully, including foreground, background, ground/floor,
  overhead areas, edges, access routes and small critical controls.
- Consider all photos collectively. One photo may provide context or evidence for
  another.
- Use every answered form question, its description and answer as operational
  context. Check whether the visible evidence is consistent with those answers.
- Ignore whether a field is configured as mandatory and ignore unanswered, blank or
  absent form fields. Form-completion validation is outside this review.
- Do not expect every form answer to be visually provable. Text, dates, names,
  signatures, administrative details and matters inherently outside the camera view
  must not fail merely because they cannot be seen.
- Do not invent people, actions, substances, equipment conditions, measurements,
  permits, certifications or events that are not supported by the evidence.
- Distinguish clearly between what is visible, what is reasonably suspected, and
  what cannot be confirmed from photos alone.

Apply a broad WHS and environmental lens, prioritising high-consequence matters:
- critical risks such as work at height, dropped objects, lifting and suspended
  loads, mobile plant interaction, electricity, stored energy, confined spaces, hot
  work, fire/explosion, hazardous substances, structural failure and line of fire;
- housekeeping, access/egress, barricading, signage, exclusion zones, guarding,
  grating, handrails, kickrails/toe boards, covers, gates, latches, clips, bolts and
  other small but important controls;
- PPE and work practices only where they are actually visible;
- ground conditions, lighting, visibility, weather, dust, fumes, vapours, smoke,
  ventilation, heat, noise and other occupational exposures;
- spills, leaks, staining, waste, chemical storage, bunding, drains, runoff,
  sediment, erosion, waterways, contamination pathways and response equipment;
- whether visible controls appear suitable, complete, continuous, correctly used,
  maintained and fit for purpose.

Outcome rules:
- fail: the photos show a credible WHS/environmental issue, failed or missing
  control, unsafe condition/practice, material contradiction with an answered form
  question, or photo quality/relevance so poor that the intended photographic
  evidence cannot reasonably be assessed.
- uncertain: there is a credible possible issue or inconsistency, but the photos or
  context are insufficient to determine whether it is actually present. State the
  precise on-site check needed. Do not use uncertain for every limitation inherent
  in a photograph.
- pass: the photos are relevant and usable, no material inconsistency is visible,
  and no significant WHS/environmental issue is visible or reasonably suspected.
  Pass means no issue was identified in this evidence; it is not a certification
  that the task or workplace is safe or compliant.

Photo quality is part of the assessment: consider focus, lighting, obstruction,
framing, distance, coverage and whether the subject relevant to the form can be
identified. Minor cosmetic quality issues must not affect the outcome when the
evidence remains assessable.

Write a concise, specific summary suitable for a project notification and analysis
record. Lead with the highest-risk finding. Identify the visible evidence, why it
matters, practical immediate action where warranted, and any targeted site
verification. Avoid generic checklist commentary and unsupported legal conclusions.

Return JSON only in the supplied schema. `findings_requiring_attention` must contain
short, actionable findings or verification items that explain a fail or uncertain
outcome; return an empty array for pass.
""".strip()
PROJECT_FIELD_CANDIDATES = (
    "project",
    "link_project",
    "custom_project",
    "project_id",
    "parent_project",
    "project_name",
    "custom_project_name",
)
EXCLUDED_FIELD_TYPES = {
    "Section Break",
    "Tab Break",
    "Column Break",
    "HTML",
    "Button",
    "Image",
    "Signature",
    "Password",
}


def _clean(value) -> str:
    return str(value or "").strip()


def _get_settings() -> dict:
    try:
        settings = frappe.get_single(SETTINGS_DOCTYPE)
    except frappe.DoesNotExistError:
        return {"enabled": False, "api_key": "", "model": DEFAULT_MODEL}

    enabled = bool(
        settings.meta.has_field("ai_photo_analysis_enabled")
        and cint(settings.get("ai_photo_analysis_enabled"))
    )
    model = (
        _clean(settings.get("ai_photo_analysis_model"))
        if settings.meta.has_field("ai_photo_analysis_model")
        else ""
    ) or DEFAULT_MODEL

    api_key = ""
    if settings.meta.has_field("ai_photo_analysis_api_key"):
        try:
            api_key = _clean(
                settings.get_password("ai_photo_analysis_api_key", raise_exception=False)
            )
        except Exception:
            api_key = ""

    return {"enabled": enabled, "api_key": api_key, "model": model}


def _canonical_project(value: str) -> str:
    value = _clean(value)
    if not value or not frappe.db.exists("DocType", "Project"):
        return ""
    if frappe.db.exists("Project", value):
        return value

    meta = frappe.get_meta("Project")
    for fieldname in ("project_name", "title"):
        if meta.has_field(fieldname):
            name = frappe.db.get_value("Project", {fieldname: value}, "name")
            if name:
                return name
    return ""


def _resolve_project(doc) -> str:
    meta = frappe.get_meta(doc.doctype)
    for fieldname in PROJECT_FIELD_CANDIDATES:
        if not meta.has_field(fieldname):
            continue
        project = _canonical_project(doc.get(fieldname))
        if project:
            return project

    for task_field in ("link_task", "task", "task_name"):
        if not meta.has_field(task_field) or not doc.get(task_field):
            continue
        task = doc.get(task_field)
        if frappe.db.exists("Task", task):
            return _canonical_project(frappe.db.get_value("Task", task, "project"))
    return ""


def _normalise_answer(value):
    if value in (None, ""):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _question_context(doc) -> list[dict]:
    questions = []
    meta = frappe.get_meta(doc.doctype)

    for df in meta.fields:
        if not df.fieldname or df.fieldtype in EXCLUDED_FIELD_TYPES or getattr(df, "hidden", 0):
            continue

        value = doc.get(df.fieldname)
        question = {
            "fieldname": df.fieldname,
            "question": df.label or df.fieldname,
            "description": _clean(df.description),
            "fieldtype": df.fieldtype,
        }

        if df.fieldtype == "Table":
            child_meta = frappe.get_meta(df.options)
            rows = []
            for row in value or []:
                row_values = {}
                for child_df in child_meta.fields:
                    if (
                        not child_df.fieldname
                        or child_df.fieldtype in EXCLUDED_FIELD_TYPES
                        or getattr(child_df, "hidden", 0)
                    ):
                        continue
                    row_values[child_df.label or child_df.fieldname] = _normalise_answer(
                        row.get(child_df.fieldname)
                    )
                rows.append(row_values)
            question["answer"] = rows
        elif df.fieldtype in ("Attach", "Attach Image"):
            question["answer"] = "Attachment supplied" if value else None
        else:
            question["answer"] = _normalise_answer(value)

        questions.append(question)

    return questions


def _get_image_files(doctype: str, docname: str) -> list:
    rows = frappe.get_all(
        "File",
        filters={"attached_to_doctype": doctype, "attached_to_name": docname},
        fields=["name", "file_name", "file_url", "file_size", "is_private", "modified"],
        order_by="creation asc",
        limit_page_length=100,
    )
    images = []
    for row in rows:
        mime_type = mimetypes.guess_type(row.file_name or row.file_url or "")[0] or ""
        if not mime_type.startswith("image/"):
            continue
        if cint(row.file_size) > MAX_IMAGE_BYTES:
            continue
        row["mime_type"] = mime_type
        images.append(row)
    return images[:MAX_PHOTOS]


def _fingerprint(doc, files: list) -> str:
    payload = {
        "doctype": doc.doctype,
        "name": doc.name,
        "modified": str(doc.modified),
        "files": [
            {"name": row.name, "modified": str(row.modified), "size": cint(row.file_size)}
            for row in files
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _create_analysis(doc, project: str, files: list, fingerprint: str, model: str):
    return frappe.get_doc(
        {
            "doctype": ANALYSIS_DOCTYPE,
            "source_doctype": doc.doctype,
            "source_name": doc.name,
            "project": project,
            "submitted_by": doc.owner,
            "status": "Queued",
            "request_fingerprint": fingerprint,
            "model": model,
            "photo_files": "\n".join(row.file_url or row.file_name for row in files),
        }
    ).insert(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def queue_submitted_form_review(doctype: str, docname: str):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)
    if not doctype or not docname or not frappe.db.exists(doctype, docname):
        frappe.throw(_("Submitted form was not found."), frappe.DoesNotExistError)

    from verto.api.mobile.documents import get_allowed_mobile_doctypes

    if doctype not in set(get_allowed_mobile_doctypes().values()):
        frappe.throw(_("This DocType is not an enabled Verto Mobile form."), frappe.PermissionError)

    doc = frappe.get_doc(doctype, docname)
    if not doc.has_permission("read"):
        frappe.throw(_("You cannot review this submitted form."), frappe.PermissionError)

    settings = _get_settings()
    if not settings["enabled"]:
        return {"queued": False, "reason": "disabled"}
    if not settings["api_key"]:
        frappe.log_error(
            title="Verto AI photo analysis is not configured",
            message="Enable AI Photo Analysis and add an OpenAI API key in Verto Mobile Settings.",
        )
        return {"queued": False, "reason": "missing_api_key"}

    files = _get_image_files(doctype, docname)
    if not files:
        return {"queued": False, "reason": "no_photos"}

    fingerprint = _fingerprint(doc, files)
    existing = frappe.db.get_value(
        ANALYSIS_DOCTYPE, {"request_fingerprint": fingerprint}, ["name", "status"], as_dict=True
    )
    if existing:
        return {"queued": False, "duplicate": True, **existing}

    project = _resolve_project(doc)
    try:
        analysis = _create_analysis(doc, project, files, fingerprint, settings["model"])
    except frappe.DuplicateEntryError:
        existing = frappe.db.get_value(
            ANALYSIS_DOCTYPE,
            {"request_fingerprint": fingerprint},
            ["name", "status"],
            as_dict=True,
        )
        return {"queued": False, "duplicate": True, **(existing or {})}
    frappe.enqueue(
        "verto.api.mobile.ai_photo_analysis.run_submitted_form_review",
        queue="long",
        timeout=900,
        enqueue_after_commit=True,
        analysis_name=analysis.name,
    )
    return {"queued": True, "analysis": analysis.name, "photo_count": len(files)}


def _image_content(file_row) -> dict:
    file_doc = frappe.get_doc("File", file_row.name)
    content = file_doc.get_content()
    if isinstance(content, str):
        content = content.encode("utf-8")
    encoded = base64.b64encode(content).decode("ascii")
    return {
        "type": "input_image",
        "image_url": f"data:{file_row.mime_type};base64,{encoded}",
        "detail": "high",
    }


def _call_openai(settings: dict, doc, files: list) -> tuple[dict, dict]:
    import requests

    questions = _question_context(doc)
    content = [
        {
            "type": "input_text",
            "text": json.dumps(
                {
                    "form_doctype": doc.doctype,
                    "form_name": doc.name,
                    "questions": questions,
                    "photo_count": len(files),
                },
                ensure_ascii=False,
                default=str,
            ),
        }
    ]
    content.extend(_image_content(row) for row in files)
    payload = {
        "model": settings["model"],
        "instructions": PHOTO_ANALYSIS_INSTRUCTIONS,
        "input": [{"role": "user", "content": content}],
        "max_output_tokens": 1200,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "verto_photo_evidence_review",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "outcome": {"type": "string", "enum": ["pass", "fail", "uncertain"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                        "summary": {"type": "string"},
                        "findings_requiring_attention": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "outcome",
                        "confidence",
                        "summary",
                        "findings_requiring_attention",
                    ],
                    "additionalProperties": False,
                },
            }
        },
    }
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {settings['api_key']}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=180,
    )
    response.raise_for_status()
    raw = response.json()
    return parse_result(extract_output_text(raw)), raw


def _project_assignees(project: str) -> list[str]:
    if not project or not frappe.db.exists("Project", project):
        return []
    assigned_users = parse_assigned_users(
        frappe.db.get_value("Project", project, "_assign")
    )
    return [
        user
        for user in assigned_users
        if frappe.db.get_value("User", user, "enabled")
    ]


def _notify_project_assignees(analysis, doc, result: dict):
    users = _project_assignees(analysis.project)
    if not users:
        return
    from verto.api.mobile.documents import get_mobile_slug_for_doctype
    from verto.api.mobile.push_notifications import queue_push_to_users

    outcome = result["outcome"]
    title = (
        "Photo review identified an issue"
        if outcome == "fail"
        else "Photo evidence needs review"
    )
    project_label = (
        frappe.db.get_value("Project", analysis.project, "project_name") or analysis.project
    )
    body = f"{doc.doctype} {doc.name} for {project_label}: {result['summary']}"
    slug = get_mobile_slug_for_doctype(doc.doctype)
    url = f"/verto-mobile/edit/{quote(slug)}/{quote(doc.name)}"
    queue_push_to_users(
        users,
        {
            "title": title,
            "body": body[:240],
            "url": url,
            "tag": f"ai-photo-{analysis.name}",
        },
        notification_type=f"ai_photo_{outcome}",
    )


def run_submitted_form_review(analysis_name: str):
    if not frappe.db.exists(ANALYSIS_DOCTYPE, analysis_name):
        return {"ok": False, "reason": "analysis_missing"}

    analysis = frappe.get_doc(ANALYSIS_DOCTYPE, analysis_name)
    if analysis.status == "Completed":
        return {"ok": True, "duplicate": True}

    try:
        analysis.db_set("status", "Processing", update_modified=False)
        settings = _get_settings()
        if not settings["enabled"] or not settings["api_key"]:
            analysis.db_set(
                {
                    "status": "Skipped",
                    "error_message": "AI photo analysis is disabled or not configured.",
                },
                update_modified=False,
            )
            return {"ok": False, "reason": "not_configured"}

        if not frappe.db.exists(analysis.source_doctype, analysis.source_name):
            raise frappe.DoesNotExistError("The submitted form no longer exists.")
        doc = frappe.get_doc(analysis.source_doctype, analysis.source_name)
        files = _get_image_files(doc.doctype, doc.name)
        if not files:
            analysis.db_set(
                {"status": "Skipped", "error_message": "No supported photos remain attached."},
                update_modified=False,
            )
            return {"ok": False, "reason": "no_photos"}

        result, raw = _call_openai(settings, doc, files)
        analysis.db_set(
            {
                "status": "Completed",
                "outcome": result["outcome"].title(),
                "confidence": result["confidence"],
                "summary": result["summary"],
                "required_details": "\n".join(result["findings_requiring_attention"]),
                "analysis_json": json.dumps(raw, ensure_ascii=False, default=str)[:1000000],
                "analysed_on": now_datetime(),
                "error_message": "",
            },
            update_modified=False,
        )
        if result["outcome"] in {"fail", "uncertain"}:
            _notify_project_assignees(analysis, doc, result)
        return {"ok": True, "outcome": result["outcome"]}
    except Exception as error:
        analysis.db_set(
            {
                "status": "Failed",
                "retry_count": cint(analysis.retry_count) + 1,
                "error_message": _clean(error)[:4000],
                "analysed_on": now_datetime(),
            },
            update_modified=False,
        )
        frappe.log_error(
            title=f"Verto AI photo analysis failed: {analysis.name}",
            message=frappe.get_traceback(),
        )
        return {"ok": False, "error": _clean(error)}


def retry_failed_reviews():
    """Retry transient or malformed AI responses without duplicating reviews."""
    if not frappe.db.exists("DocType", ANALYSIS_DOCTYPE):
        return {"queued": 0}

    names = frappe.get_all(
        ANALYSIS_DOCTYPE,
        filters={"status": "Failed", "retry_count": ["<", MAX_RETRIES]},
        pluck="name",
        order_by="modified asc",
        limit_page_length=25,
    )
    for name in names:
        frappe.enqueue(
            "verto.api.mobile.ai_photo_analysis.run_submitted_form_review",
            queue="long",
            timeout=900,
            analysis_name=name,
        )
    return {"queued": len(names)}
