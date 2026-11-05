from __future__ import annotations

import base64
import hashlib
import json
import mimetypes

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from verto.api.mobile.ai_photo_analysis_parsing import (
    build_review_dm_html,
    deliver_direct_messages,
    extract_output_text,
    parse_assigned_users,
    parse_result,
)


SETTINGS_DOCTYPE = "Verto Mobile Settings"
ANALYSIS_DOCTYPE = "Verto AI Photo Analysis"
MAX_PHOTOS = 12
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_RETRIES = 3
PHOTO_ANALYSIS_INSTRUCTIONS = """
Act as an experienced Australian workplace Work Health and Safety (WHS) and
environmental specialist for this task. Review all supplied workplace photos as one
evidence set and assess them in the context of the entire submitted operational
form. Retain the identity and high-level behaviour of the nominated Raven AI bot.

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

Return JSON only with exactly these keys: `outcome` (`pass`, `fail` or `uncertain`),
`confidence` (a number from 0 to 100), `summary` (a string), and
`findings_requiring_attention` (an array of strings). The findings array must contain
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
        return {"enabled": False, "bot": ""}

    enabled = bool(
        settings.meta.has_field("ai_photo_analysis_enabled")
        and cint(settings.get("ai_photo_analysis_enabled"))
    )
    bot_name = (
        _clean(settings.get("ai_photo_analysis_bot"))
        if settings.meta.has_field("ai_photo_analysis_bot")
        else ""
    )

    # The legacy Verto model and API-key fields are deliberately ignored. The
    # selected Raven Bot and Raven Settings are now authoritative.
    return {"enabled": enabled, "bot": bot_name}


def _get_analysis_bot(bot_name: str, *, for_inference: bool = True):
    bot_name = _clean(bot_name)
    if not bot_name:
        raise ValueError("Select an AI Photo Analysis Bot in Verto Mobile Settings.")
    if not frappe.db.exists("DocType", "Raven Bot"):
        raise ValueError("Raven Bot is not installed on this site.")
    if not frappe.db.exists("Raven Bot", bot_name):
        raise ValueError(f"The selected Raven Bot {bot_name!r} no longer exists.")

    bot = frappe.get_cached_doc("Raven Bot", bot_name)
    if not cint(getattr(bot, "is_ai_bot", 0)):
        raise ValueError(f"The selected Raven Bot {bot_name!r} is not an AI bot.")
    if not _clean(getattr(bot, "raven_user", None)):
        raise ValueError(f"The selected Raven Bot {bot_name!r} has no Raven User.")
    if for_inference:
        if not _clean(getattr(bot, "model", None)):
            raise ValueError(f"The selected Raven Bot {bot_name!r} has no model configured.")

        provider = _clean(getattr(bot, "model_provider", None)) or "OpenAI"
        if provider != "OpenAI":
            raise ValueError(
                "AI photo analysis currently requires a Raven Bot using the OpenAI "
                "provider and a vision-capable model."
            )
    return bot


def _get_raven_ai_client():
    """Use Raven's credential authority without enabling conversational tools.

    Photo review is a deterministic background classification task. Calling the
    general Raven agent runner here would allow unrelated bot write tools and
    would not consistently preserve multimodal input across Raven providers.
    """
    from raven.ai.openai_client import get_open_ai_client

    return get_open_ai_client()


def _get_bot_instructions(bot, instruction_user: str = "") -> str:
    stored_instruction = _clean(getattr(bot, "instruction", None))
    if not cint(getattr(bot, "dynamic_instructions", 0)):
        return stored_instruction

    try:
        from raven.ai.handler import get_instructions
    except ImportError:
        return stored_instruction

    # Scheduled retries can run as Administrator. Render Raven's dynamic bot
    # prompt as the original form submitter so the same bot context is used on
    # the initial review and every retry.
    original_user = frappe.session.user
    should_switch_user = bool(instruction_user and instruction_user != original_user)
    if should_switch_user:
        frappe.set_user(instruction_user)
    try:
        return _clean(get_instructions(bot) or stored_instruction)
    finally:
        if should_switch_user:
            frappe.set_user(original_user)


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


def _create_analysis(doc, project: str, files: list, fingerprint: str, bot):
    values = {
        "doctype": ANALYSIS_DOCTYPE,
        "source_doctype": doc.doctype,
        "source_name": doc.name,
        "project": project,
        "submitted_by": doc.owner,
        "status": "Queued",
        "request_fingerprint": fingerprint,
        "model": _clean(getattr(bot, "model", None)),
        "photo_files": "\n".join(row.file_url or row.file_name for row in files),
    }
    if frappe.get_meta(ANALYSIS_DOCTYPE).has_field("ai_bot"):
        values["ai_bot"] = bot.name
    return frappe.get_doc(values).insert(ignore_permissions=True)


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

    try:
        bot = _get_analysis_bot(settings["bot"])
        # This validates Raven Settings and constructs the configured client;
        # it does not make a network request in the form-save path.
        _get_raven_ai_client()
    except Exception as error:
        frappe.log_error(
            title="Verto AI photo analysis bot is not configured",
            message=_clean(error),
        )
        return {
            "queued": False,
            "reason": "missing_ai_bot" if not settings["bot"] else "invalid_ai_bot",
            "message": _clean(error),
        }

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
        analysis = _create_analysis(doc, project, files, fingerprint, bot)
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


def _analysis_schema() -> dict:
    return {
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
    }


def _serialise_ai_response(response) -> dict:
    if isinstance(response, dict):
        return response
    if hasattr(response, "model_dump"):
        try:
            return response.model_dump(mode="json")
        except TypeError:
            return response.model_dump()
    if hasattr(response, "to_dict"):
        return response.to_dict()
    raise ValueError("Raven's AI client returned an unsupported response object.")


def _validate_ai_response(response_data: dict, api: str):
    if response_data.get("error"):
        raise ValueError(f"Raven AI response error: {response_data['error']}")

    if api == "responses" and response_data.get("status") == "incomplete":
        details = response_data.get("incomplete_details") or "output was incomplete"
        raise ValueError(f"Raven AI response incomplete: {details}")

    if api == "chat_completions":
        choice = (response_data.get("choices") or [{}])[0]
        finish_reason = choice.get("finish_reason")
        if finish_reason in {"length", "content_filter"}:
            raise ValueError(f"Raven AI response stopped because of {finish_reason}.")
        refusal = (choice.get("message") or {}).get("refusal")
        if refusal:
            raise ValueError(f"Raven AI refused the photo review: {refusal}")


def _call_raven_bot(
    bot,
    client,
    doc,
    files: list,
    *,
    instruction_user: str = "",
) -> tuple[dict, dict]:
    questions = _question_context(doc)
    context_text = json.dumps(
        {
            "form_doctype": doc.doctype,
            "form_name": doc.name,
            "questions": questions,
            "photo_count": len(files),
        },
        ensure_ascii=False,
        default=str,
    )
    responses_content = [
        {
            "type": "input_text",
            "text": context_text,
        }
    ]
    responses_content.extend(_image_content(row) for row in files)
    instructions = "\n\n".join(
        part
        for part in (
            _get_bot_instructions(bot, instruction_user),
            PHOTO_ANALYSIS_INSTRUCTIONS,
        )
        if part
    )
    request_client = (
        client.with_options(timeout=180)
        if hasattr(client, "with_options")
        else client
    )

    if hasattr(request_client, "responses"):
        response = request_client.responses.create(
            model=bot.model,
            instructions=instructions,
            input=[{"role": "user", "content": responses_content}],
            max_output_tokens=3000,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "verto_photo_evidence_review",
                    "strict": True,
                    "schema": _analysis_schema(),
                }
            },
        )
        api = "responses"
    else:
        # Raven 2 installations using an older OpenAI SDK may not expose the
        # Responses API. Preserve bot-owned credentials/model/instructions and
        # use its multimodal Chat Completions client without sampling options.
        chat_content = [{"type": "text", "text": context_text}]
        for item in responses_content[1:]:
            chat_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": item["image_url"], "detail": "high"},
                }
            )
        chat_parameters = {
            "model": bot.model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": chat_content},
            ],
            "response_format": {"type": "json_object"},
        }
        if _clean(bot.model).lower().startswith(("gpt-5", "o1", "o3", "o4")):
            chat_parameters["max_completion_tokens"] = 3000
        else:
            chat_parameters["max_tokens"] = 3000
        response = request_client.chat.completions.create(**chat_parameters)
        api = "chat_completions"

    response_data = _serialise_ai_response(response)
    _validate_ai_response(response_data, api)
    output_text = extract_output_text(response_data)
    if not output_text:
        raise ValueError("The nominated Raven AI bot returned no analysis text.")
    result = parse_result(output_text)
    raw = {
        "raven_bot": bot.name,
        "provider": _clean(getattr(bot, "model_provider", None)) or "OpenAI",
        "model": bot.model,
        "api": api,
        "response": response_data,
    }
    return result, raw


def _stored_analysis_result(analysis):
    """Reuse a successful inference when only Raven DM delivery needs retrying."""
    try:
        raw = json.loads(analysis.analysis_json or "{}")
    except (TypeError, ValueError):
        return None

    result = raw.get("normalised_result") if isinstance(raw, dict) else None
    if not isinstance(result, dict):
        return None
    try:
        return parse_result(json.dumps(result)), raw
    except (TypeError, ValueError):
        return None


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


def _has_enabled_raven_user(user: str) -> bool:
    if not frappe.db.exists("DocType", "Raven User"):
        return False
    meta = frappe.get_meta("Raven User")
    if not meta.has_field("user"):
        return False

    fields = ["name"]
    if meta.has_field("enabled"):
        fields.append("enabled")
    raven_user = frappe.db.get_value(
        "Raven User",
        {"user": user},
        fields,
        as_dict=True,
    )
    return bool(
        raven_user
        and (not meta.has_field("enabled") or cint(raven_user.get("enabled")))
    )


def _dm_was_sent(bot, notification_name: str) -> bool:
    if not frappe.db.exists("DocType", "Raven Message"):
        return False
    meta = frappe.get_meta("Raven Message")
    if not meta.has_field("notification"):
        return False

    filters = {"notification": notification_name}
    if meta.has_field("bot"):
        filters["bot"] = bot.raven_user
    return bool(frappe.db.exists("Raven Message", filters))


def _message_project_assignees(analysis, doc, result: dict, bot) -> dict:
    users = _project_assignees(analysis.project)
    if not users:
        return {"sent": [], "already_sent": [], "skipped": [], "failed": []}

    project_label = (
        frappe.db.get_value("Project", analysis.project, "project_name") or analysis.project
    )
    message = build_review_dm_html(
        result,
        source_doctype=doc.doctype,
        source_name=doc.name,
        project_label=project_label,
    )

    def send_message(user, notification_name):
        return bot.send_direct_message(
            user_id=user,
            text=message,
            link_doctype=doc.doctype,
            link_document=doc.name,
            markdown=False,
            notification_name=notification_name,
        )

    def log_delivery_error(user, error):
        frappe.log_error(
            title=f"Verto AI photo DM failed: {analysis.name}",
            message=f"Recipient: {user}\nError: {_clean(error)}\n\n{frappe.get_traceback()}",
        )

    delivery = deliver_direct_messages(
        users,
        analysis_name=analysis.name,
        can_receive=_has_enabled_raven_user,
        was_sent=lambda notification_name: _dm_was_sent(bot, notification_name),
        send_message=send_message,
        on_error=log_delivery_error,
    )

    if delivery["skipped"]:
        frappe.log_error(
            title=f"Verto AI photo DM recipients unavailable: {analysis.name}",
            message=(
                "These assigned Project users do not have an enabled Raven User: "
                + ", ".join(delivery["skipped"])
            ),
        )
    return delivery


def run_submitted_form_review(analysis_name: str):
    if not frappe.db.exists(ANALYSIS_DOCTYPE, analysis_name):
        return {"ok": False, "reason": "analysis_missing"}

    analysis = frappe.get_doc(ANALYSIS_DOCTYPE, analysis_name)
    if analysis.status == "Completed":
        return {"ok": True, "duplicate": True}

    try:
        analysis.db_set("status", "Processing", update_modified=False)
        settings = _get_settings()
        if not settings["enabled"]:
            analysis.db_set(
                {
                    "status": "Skipped",
                    "error_message": "AI photo analysis is disabled in Verto Mobile Settings.",
                },
                update_modified=False,
            )
            return {"ok": False, "reason": "disabled"}

        stored_analysis = _stored_analysis_result(analysis)
        bot_name = _clean(getattr(analysis, "ai_bot", None)) or settings["bot"]
        try:
            bot = _get_analysis_bot(bot_name, for_inference=not bool(stored_analysis))
        except Exception as error:
            analysis.db_set(
                {
                    "status": "Skipped",
                    "error_message": _clean(error)[:4000],
                    "analysed_on": now_datetime(),
                },
                update_modified=False,
            )
            frappe.log_error(
                title=f"Verto AI photo analysis bot is not configured: {analysis.name}",
                message=_clean(error),
            )
            return {"ok": False, "reason": "not_configured", "error": _clean(error)}

        if not frappe.db.exists(analysis.source_doctype, analysis.source_name):
            raise frappe.DoesNotExistError("The submitted form no longer exists.")
        doc = frappe.get_doc(analysis.source_doctype, analysis.source_name)

        if stored_analysis:
            result, raw = stored_analysis
        else:
            client = _get_raven_ai_client()
            files = _get_image_files(doc.doctype, doc.name)
            if not files:
                analysis.db_set(
                    {
                        "status": "Skipped",
                        "error_message": "No supported photos remain attached.",
                    },
                    update_modified=False,
                )
                return {"ok": False, "reason": "no_photos"}
            result, raw = _call_raven_bot(
                bot,
                client,
                doc,
                files,
                instruction_user=analysis.submitted_by,
            )
        raw["normalised_result"] = result
        delivery = {"sent": [], "already_sent": [], "skipped": [], "failed": []}
        if result["outcome"] in {"fail", "uncertain"}:
            delivery = _message_project_assignees(analysis, doc, result, bot)
        raw["dm_delivery"] = delivery
        model_name = (
            _clean(getattr(bot, "model", None))
            or _clean(raw.get("model"))
            or _clean(analysis.model)
        )

        result_values = {
            "outcome": result["outcome"].title(),
            "confidence": result["confidence"],
            "summary": result["summary"],
            "required_details": "\n".join(result["findings_requiring_attention"]),
            "model": model_name,
            "analysis_json": json.dumps(raw, ensure_ascii=False, default=str)[:1000000],
            "analysed_on": now_datetime(),
            "error_message": "",
        }
        if analysis.meta.has_field("ai_bot"):
            result_values["ai_bot"] = bot.name

        if delivery["failed"]:
            result_values.update(
                {
                    "status": "Failed",
                    "retry_count": cint(analysis.retry_count) + 1,
                    "error_message": (
                        "Photo analysis completed, but Raven direct-message delivery "
                        "failed for: " + ", ".join(delivery["failed"])
                    )[:4000],
                }
            )
            analysis.db_set(result_values, update_modified=False)
            return {
                "ok": False,
                "reason": "dm_delivery_failed",
                "outcome": result["outcome"],
                "dm_delivery": delivery,
            }

        result_values["status"] = "Completed"
        analysis.db_set(result_values, update_modified=False)
        return {
            "ok": True,
            "outcome": result["outcome"],
            "dm_delivery": delivery,
        }
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
