from __future__ import annotations

import json

import frappe
from frappe import _


MAX_TEXT_LENGTH = 8000
MAX_DETAILS_LENGTH = 12000


def _clean(value, limit=MAX_TEXT_LENGTH) -> str:
    return str(value or "").strip()[:limit]


def _as_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


@frappe.whitelist(methods=["POST"])
def log_client_error(message="", source="", stack="", page="", details=None):
    """Create a bounded Error Log entry for a signed-in Verto Mobile client error."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    details = _as_dict(details)
    payload = {
        "message": _clean(message),
        "source": _clean(source, 500),
        "stack": _clean(stack),
        "page": _clean(page, 1000),
        "details": details,
        "user": frappe.session.user,
        "user_agent": _clean(frappe.get_request_header("User-Agent"), 1000),
    }
    serialised = json.dumps(payload, ensure_ascii=False, default=str)
    if len(serialised) > MAX_DETAILS_LENGTH:
        payload["details"] = {"note": "Diagnostic details were truncated."}
        serialised = json.dumps(payload, ensure_ascii=False, default=str)

    title_source = _clean(source, 80) or "Client error"
    log = frappe.log_error(
        title=f"Verto Mobile: {title_source}"[:140],
        message=serialised,
    )
    return {"logged": True, "error_log": getattr(log, "name", None)}
