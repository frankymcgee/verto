from __future__ import annotations

import hashlib
import html
import json


def parse_assigned_users(value) -> list[str]:
    """Return the unique users stored in Frappe's JSON `_assign` field."""
    if isinstance(value, str):
        try:
            value = json.loads(value or "[]")
        except (TypeError, ValueError):
            return []

    if not isinstance(value, (list, tuple)):
        return []

    users = []
    seen = set()
    for item in value:
        user = str(item or "").strip()
        if not user or user == "Guest" or user in seen:
            continue
        seen.add(user)
        users.append(user)
    return users


def extract_output_text(response: dict) -> str:
    if response.get("output_text"):
        return str(response["output_text"] or "").strip()

    parts = []
    for item in response.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content["text"])

    if parts:
        return "\n".join(parts).strip()

    # Compatibility with Raven/OpenAI versions that only expose Chat
    # Completions instead of the Responses API.
    for choice in response.get("choices") or []:
        content = (choice.get("message") or {}).get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            parts.extend(
                item.get("text")
                for item in content
                if isinstance(item, dict) and item.get("text")
            )
    return "\n".join(parts).strip()


def _decode_json_object(value: str) -> dict:
    try:
        result = json.loads(value)
    except json.JSONDecodeError as original_error:
        # Some models still add a short preface despite the JSON-only
        # instruction. Decode the first complete object without accepting a
        # truncated or otherwise malformed payload.
        decoder = json.JSONDecoder()
        for index, character in enumerate(value):
            if character != "{":
                continue
            try:
                result, _ = decoder.raw_decode(value[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(result, dict):
                break
        else:
            raise original_error

    if not isinstance(result, dict):
        raise ValueError("AI response must contain a JSON object.")
    return result


def parse_result(text: str) -> dict:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1]
        value = value.rsplit("```", 1)[0].strip()
    result = _decode_json_object(value)
    outcome = str(result.get("outcome") or "").strip().lower()
    if outcome not in {"pass", "fail", "uncertain"}:
        raise ValueError("AI response contained an invalid outcome.")
    confidence = max(0, min(100, float(result.get("confidence") or 0)))
    # Accept the original key so already-queued responses remain parseable during
    # a rolling deployment, but expose only the broader findings terminology.
    details = result.get("findings_requiring_attention")
    if details is None:
        details = result.get("required_details_not_verified") or []
    if not isinstance(details, list):
        details = [str(details)]
    return {
        "outcome": outcome,
        "confidence": confidence,
        "summary": str(result.get("summary") or "").strip()[:1000],
        "findings_requiring_attention": [
            str(item).strip() for item in details if str(item).strip()
        ],
    }


def build_dm_notification_name(analysis_name: str, user: str) -> str:
    """Return a stable, short Raven notification key for DM deduplication."""
    recipient_hash = hashlib.sha256(str(user or "").encode("utf-8")).hexdigest()[:16]
    return f"vap:{str(analysis_name or '').strip()}:{recipient_hash}"[:140]


def deliver_direct_messages(
    users,
    *,
    analysis_name: str,
    can_receive,
    was_sent,
    send_message,
    on_error=None,
) -> dict:
    """Deliver independently and return an audit-friendly result.

    The callbacks keep this orchestration independent of Frappe/Raven and make
    partial delivery and retry deduplication directly testable.
    """
    delivery = {"sent": [], "already_sent": [], "skipped": [], "failed": []}
    for user in users:
        if not can_receive(user):
            delivery["skipped"].append(user)
            continue

        notification_name = build_dm_notification_name(analysis_name, user)
        if was_sent(notification_name):
            delivery["already_sent"].append(user)
            continue

        try:
            message_name = send_message(user, notification_name)
            delivery["sent"].append({"user": user, "message": message_name})
        except Exception as error:
            delivery["failed"].append(user)
            if on_error:
                on_error(user, error)
    return delivery


def build_review_dm_html(
    result: dict,
    *,
    source_doctype: str,
    source_name: str,
    project_label: str,
) -> str:
    """Build escaped HTML for the bot-authored project-assignee DM."""

    def escaped(value) -> str:
        return html.escape(str(value or ""), quote=True)

    outcome = str(result.get("outcome") or "").strip().lower()
    title = (
        "Photo review identified an issue"
        if outcome == "fail"
        else "Photo evidence needs review"
    )
    confidence = max(0, min(100, float(result.get("confidence") or 0)))
    findings = [
        str(item).strip()
        for item in result.get("findings_requiring_attention") or []
        if str(item).strip()
    ]
    findings_html = ""
    if findings:
        findings_html = (
            "<p><strong>Findings requiring attention</strong></p><ul>"
            + "".join(f"<li>{escaped(item)}</li>" for item in findings)
            + "</ul>"
        )

    return (
        f"<p><strong>{escaped(title)}</strong></p>"
        f"<p><strong>Project:</strong> {escaped(project_label)}<br>"
        f"<strong>Form:</strong> {escaped(source_doctype)} {escaped(source_name)}<br>"
        f"<strong>Outcome:</strong> {escaped(outcome.title())}<br>"
        f"<strong>Confidence:</strong> {confidence:g}%</p>"
        f"<p>{escaped(result.get('summary'))}</p>"
        f"{findings_html}"
        "<p>Please review the linked form and confirm or correct the issue on site.</p>"
    )
