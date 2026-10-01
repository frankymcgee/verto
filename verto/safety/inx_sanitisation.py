"""Redact incident text without rewriting safety facts or inventing controls."""

import hashlib
import json
import re


SOURCE_FIELDS = {
    "site_name": "location",
    "incident_summary": "detailed_observation",
    "immediate_actions": "immediate_actions",
}
TEXT_FIELDS = (*SOURCE_FIELDS, "title", "investigation_findings", "investigation_actions", "recommended_controls")
PLACEHOLDERS = {
    "person": "[person]",
    "contact": "[contact detail removed]",
    "identifier": "[personal identifier removed]",
    "address": "[personal address removed]",
    "private_detail": "[private detail removed]",
}
PATTERNS = (
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.UNICODE), "contact"),
    (re.compile(r"(?<!\w)(?:\+61\s*\(?[23478]\)?|\(?0[23478]\)?)(?:[\s.-]*\d){8}(?!\w)"), "contact"),
    (re.compile(r"\b(?:DOB|date of birth)\s*[:=-]?\s*(?:\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\b", re.I), "private_detail"),
    (re.compile(r"\b(?:employee|personnel|payroll|patient|claim)\s*(?:ID|no\.?|number|#)\s*[:=-]?\s*(?=[A-Z0-9/-]*\d)[A-Z0-9][A-Z0-9/-]{2,}\b", re.I), "identifier"),
)
NON_NAMES = {"administrator", "admin", "system", "user", "unknown", "manager", "supervisor", "site", "assigned", "none", "not", "and",
             "person", "personal", "contact", "detail", "removed", "identifier", "address", "private"}


def text_hash(value):
    return hashlib.sha256(str(value or "").encode()).hexdigest()


def draft_inputs(source, lesson):
    """Refresh source-managed values; retain a curator's wording before redaction."""
    try:
        hashes = json.loads(lesson.get("sanitisation_field_hashes") or "{}")
    except (TypeError, ValueError):
        hashes = {}
    if not isinstance(hashes, dict):
        hashes = {}
    fields, managed = {}, []
    for field in TEXT_FIELDS:
        current = str(lesson.get(field) or "")
        if field in SOURCE_FIELDS and (not current.strip() or hashes.get(field) == text_hash(current)):
            fields[field] = str(source.get(SOURCE_FIELDS[field]) or "")
            managed.append(field)
        else:
            fields[field] = current
    return fields, managed


def mask_known_identifiers(fields, personnel=()):
    """Known personnel names stay in process memory and are masked before inference."""
    names = set()
    for value in personnel:
        value = str(value or "").strip()
        if len(value) >= 3 and value.casefold() not in NON_NAMES:
            names.add(value)
        names.update(word for word in re.findall(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", value)
                     if len(word) >= 3 and word.casefold() not in NON_NAMES)
    result = {}
    for field, text in fields.items():
        value = str(text or "")
        # Mask contacts first: replacing a person's email username would otherwise
        # make the remaining address invisible to the full-address pattern.
        for pattern, kind in PATTERNS:
            value = pattern.sub(PLACEHOLDERS[kind], value)
        # A workplace can share a surname with personnel; let context identify
        # personal addresses in this field rather than masking site-name tokens.
        if names and field != "site_name":
            pattern = r"(?<!\w)(?:" + "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True)) + r")(?!\w)"
            value = re.sub(pattern, PLACEHOLDERS["person"], value, flags=re.I)
        result[field] = value
    return result


def apply_redactions(fields, payload):
    """Only exact source spans can be replaced; model-authored prose is rejected."""
    if not isinstance(payload, dict) or set(payload) != {"redactions"}:
        raise ValueError("Invalid redaction response.")
    redactions = payload["redactions"]
    if not isinstance(redactions, list) or len(redactions) > 200:
        raise ValueError("Invalid redaction list.")
    spans = {}
    for item in redactions:
        if not isinstance(item, dict) or set(item) != {"field", "text", "kind"}:
            raise ValueError("Invalid redaction item.")
        field, text, kind = item["field"], item["text"], item["kind"]
        if (not isinstance(field, str) or field not in fields or not isinstance(text, str)
                or not text.strip() or not isinstance(kind, str) or kind not in PLACEHOLDERS
                or text not in fields[field] or text in PLACEHOLDERS.values()):
            raise ValueError("Redactions must identify original text.")
        spans.setdefault(field, {})[text] = PLACEHOLDERS[kind]
    result = {}
    for field, value in fields.items():
        matches = spans.get(field, {})
        if matches:
            # One pass handles nested/overlapping spans without changing newly inserted markers.
            pattern = re.compile("|".join(re.escape(text) for text in sorted(matches, key=len, reverse=True)))
            value = pattern.sub(lambda match: matches[match.group()], value)
        limit = 140 if field in {"site_name", "title"} else 32767
        if len(value) > limit:
            raise ValueError("Redacted text exceeds its destination limit.")
        result[field] = value
    return result


def redaction_schema():
    return {
        "type": "object", "additionalProperties": False, "required": ["redactions"],
        "properties": {"redactions": {
            "type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["field", "text", "kind"],
                "properties": {
                    "field": {"type": "string", "enum": list(TEXT_FIELDS)},
                    "text": {"type": "string"},
                    "kind": {"type": "string", "enum": list(PLACEHOLDERS)},
                },
            },
        }},
    }
