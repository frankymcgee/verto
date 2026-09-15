"""Planner bootstrap and bounded read batches, using the normal permission checks."""
import json

import frappe

from verto.api import planner
from verto.api.planner_realtime import can_subscribe

MAX_BATCH_SIZE = 20
LIST_DOCTYPES = {"Employee", "Project"}
SETTINGS_FIELDS = ("planner_app_name", "planner_icon", "desk_icon", "planner_view_default")
BOOTSTRAP_SECTIONS = {"shell", "settings", "references", "projects"}
REFERENCES = {
    "company": ("Company", ["name"], 1000),
    "department": ("Department", ["name", "company"], 10000),
    "branch": ("Branch", ["name"], 1000),
    "designation": ("Designation", ["name"], 1000),
    "shift_type": ("Shift Type", ["name"], 1000),
    "shift_location": ("Shift Location", ["name"], 1000),
}


def _check_access():
    if not can_subscribe():
        frappe.throw("You do not have permission to access the planner.", frappe.PermissionError)


def _list(**params):
    from frappe.client import get_list

    # Same handler as the original HTTP calls: validates fields and applies
    # document, field-level and user permissions. Never use get_all here.
    return frappe.call(get_list, **params)


def _read_result(callback):
    # Keep one failed dataset from contaminating the batch's server messages.
    previous_messages = frappe.local.message_log
    frappe.local.message_log = []
    try:
        return {"data": callback()}
    except (frappe.PermissionError, frappe.ValidationError) as exc:
        return {"error": {"exc_type": type(exc).__name__, "message": str(exc)}}
    except Exception:
        frappe.log_error(title="Planner data read failed")
        return {"error": {"exc_type": "ServerError", "message": "Unable to load planner data. Please retry."}}
    finally:
        frappe.local.message_log = previous_messages


@frappe.whitelist(methods=["POST"])
def get_bootstrap(sections=None):
    """One per-user response for the shell and shared dropdowns; no shared cache."""
    _check_access()
    if isinstance(sections, str):
        try:
            sections = json.loads(sections)
        except ValueError:
            frappe.throw("Invalid planner bootstrap sections.")
    if sections is None:
        sections = sorted(BOOTSTRAP_SECTIONS)
    if not isinstance(sections, list) or not sections or any(
        not isinstance(section, str) or section not in BOOTSTRAP_SECTIONS for section in sections
    ):
        frappe.throw("Invalid planner bootstrap sections.")
    result = {"sections": sections, "errors": {}}

    def include(key, callback, fallback, destination=None, error_key=None):
        read = _read_result(callback)
        (destination if destination is not None else result)[key] = read.get("data", fallback)
        if "error" in read:
            result["errors"][error_key or key] = read["error"]

    def settings():
        doc = frappe.get_doc("Verto Mobile Settings", "Verto Mobile Settings")
        doc.check_permission("read")
        doc.apply_fieldlevel_read_permissions()
        # Do not send the entire settings document (including unrelated secrets).
        return {field: doc.get(field) for field in SETTINGS_FIELDS}

    if "shell" in sections:
        from verto.default_apps import get_apps

        result["user"] = planner.get_current_user_info()
        result["default_company"] = planner.get_default_company()
        include("apps", get_apps, [], error_key="shell.apps")
    if "settings" in sections:
        include("settings", settings, {})
    if "references" in sections:
        result["references"] = {}
        for key, (doctype, fields, limit) in REFERENCES.items():
            include(key, lambda d=doctype, f=fields, n=limit: _list(
                doctype=d, fields=f, order_by="name asc", limit_page_length=n,
            ), [], result["references"], error_key=f"references.{key}")
    if "projects" in sections:
        include("projects", lambda: _list(
            doctype="Project", fields=["name", "project_name"],
            filters=[["status", "=", "Open"]], order_by="project_name asc", limit_page_length=200,
        ), [])
    return result


def _prepare_read(request):
    if not isinstance(request, dict) or not isinstance(request.get("params", {}), dict):
        frappe.throw("Invalid planner read.")
    method, params = request.get("method"), dict(request.get("params", {}))
    if not isinstance(method, str):
        frappe.throw("Invalid planner read method.")
    handlers = {
        "verto.api.planner.get_events": planner.get_events,
        "verto.api.planner.get_year_events": planner.get_year_events,
        "verto.api.planner.get_available_employees": planner.get_available_employees,
    }
    if method == "frappe.client.get_list":
        if not isinstance(params.get("doctype"), str) or params["doctype"] not in LIST_DOCTYPES:
            frappe.throw("This document type cannot be read in a planner batch.")
        # Frappe UI sends both aliases. Preserve normal get_list pagination,
        # but prohibit an unbounded read. Existing workforce limit is 99,999.
        try:
            limit = int(params.get("limit_page_length", 20))
            start = int(params.get("limit_start", 0))
        except (ValueError, TypeError, OverflowError):
            frappe.throw("Invalid planner pagination.")
        if not 1 <= limit <= 100000 or start < 0:
            frappe.throw("Invalid planner pagination.")
        params["limit_page_length"], params["limit_start"] = limit, start
        # Extra UI aliases are ignored by the original HTTP dispatcher too.
        allowed = {"doctype", "fields", "filters", "or_filters", "order_by", "group_by",
                   "parent", "limit_start", "limit_page_length"}
        params = {key: value for key, value in params.items() if key in allowed}
        return lambda: _list(**params)
    if method not in handlers:
        frappe.throw("This method cannot be called in a planner read batch.")
    return lambda: frappe.call(handlers[method], **params)


@frappe.whitelist(methods=["POST"])
def get_planner_data(requests):
    """Run independent reads sequentially in one authenticated HTTP request."""
    _check_access()
    if isinstance(requests, str):
        try:
            requests = json.loads(requests)
        except (ValueError, TypeError):
            frappe.throw("Invalid planner batch.")
    if not isinstance(requests, list) or not 1 <= len(requests) <= MAX_BATCH_SIZE:
        frappe.throw("A planner batch must contain between 1 and 20 reads.")
    # Validate the entire envelope first. No arbitrary method lookup,
    # write handler, permission bypass or client-supplied execution context.
    callbacks = [_prepare_read(request) for request in requests]
    return {"results": [_read_result(callback) for callback in callbacks]}
