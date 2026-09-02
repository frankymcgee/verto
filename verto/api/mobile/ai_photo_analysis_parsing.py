from __future__ import annotations

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
    return "\n".join(parts).strip()


def parse_result(text: str) -> dict:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1]
        value = value.rsplit("```", 1)[0].strip()
    result = json.loads(value)
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
