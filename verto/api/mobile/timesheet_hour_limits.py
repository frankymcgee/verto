"""Opt-in push alerts for saved Daily Timesheet claims above Project limits."""

from __future__ import annotations

import hashlib
import math
from urllib.parse import quote

import frappe
from frappe.utils import cint, formatdate, getdate

from verto.api.mobile.global_notifications import _recipient_rows
from verto.api.mobile.push_notifications import queue_push_to_users


NOTIFICATION_FLAG = "daily_timesheet_hours_exceeded"
LIMIT_LABELS = {
    "max_fly_hrs": "Max Fly Hrs",
    "max_ds_hrs": "Max DS Hrs",
    "max_ns_hrs": "Max NS Hrs",
}


def _clean(value):
    return str(value or "").strip()


def _positive_number(value):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) and number > 0 else 0.0


def _claim_signature(doc):
    """Comments, signatures and modified timestamps do not change the claim."""
    return (
        str(getdate(doc.get("date"))) if doc.get("date") else "",
        _positive_number(doc.get("duration")),
        *(_clean(doc.get(field)) for field in (
            "project_id", "shift", "shift_allocation", "current_user", "owner",
        )),
    )


def _limit_field(shift):
    # Match the prefixed shift codes used by the Planner/mobile app, e.g. FG-DS.
    normalised = _clean(shift).upper().replace("_", "-").replace(" ", "-")
    if normalised.endswith(("FI", "FO")) or normalised in {"FLY-IN", "FLY-OUT"}:
        return "max_fly_hrs"
    if normalised.endswith("DS") or normalised == "DAY-SHIFT":
        return "max_ds_hrs"
    if normalised.endswith("NS") or normalised == "NIGHT-SHIFT":
        return "max_ns_hrs"
    return None


def get_hours_exceeded(doc):
    """Use validated duration (seconds) and the linked allocation's saved data."""
    seconds = _positive_number(doc.get("duration"))
    if cint(doc.get("docstatus")) == 2 or not seconds or not doc.get("date"):
        return None

    allocation = {}
    if doc.get("shift_allocation"):
        allocation = frappe.db.get_value(
            "Shift Assignment", doc.get("shift_allocation"),
            ["custom_project", "shift_type", "employee_name"], as_dict=True,
        ) or {}

    # The fetched display fields can be missing/stale in offline/API payloads.
    project_id = _clean(allocation.get("custom_project")) or _clean(doc.get("project_id"))
    shift = _clean(allocation.get("shift_type")) or _clean(doc.get("shift"))
    field = _limit_field(shift)
    if not project_id or not field or not frappe.get_meta("Project").has_field(field):
        return None

    project = frappe.db.get_value(
        "Project", project_id, ["project_name", field], as_dict=True,
    ) or {}
    maximum = _positive_number(project.get(field))
    # Blank/zero/invalid limits mean unconfigured, never a zero-hour allowance.
    if not maximum or seconds <= maximum * 3600:
        return None

    return {
        "project": project_id,
        "project_name": _clean(project.get("project_name")) or project_id,
        "person": _clean(allocation.get("employee_name"))
        or _clean(doc.get("current_user")) or _clean(doc.get("owner")),
        "date": str(getdate(doc.get("date"))),
        "shift": shift,
        "hours": seconds / 3600,
        "maximum": maximum,
        "limit_field": field,
    }


def notify_daily_timesheet_hours_exceeded(doc, method=None):
    """Called by on_update for Desk, mobile and offline-sync saves.

    Queue after commit via the existing push service, so rolled-back saves do
    not notify. Re-saving an unchanged claim is silent; correcting it and later
    exceeding the limit again is a new event. This is an alert, not a save block.
    """
    try:
        if cint(doc.get("docstatus")) == 2:
            return
        previous = doc.get_doc_before_save()
        if previous and _claim_signature(previous) == _claim_signature(doc):
            return

        users = [row["user"] for row in _recipient_rows(NOTIFICATION_FLAG) if row["receive_push"]]
        if not users:
            return
        claim = get_hours_exceeded(doc)
        if not claim:
            return

        # A distinct timesheet gets its own notification; edits replace its old one.
        tag = hashlib.sha256(doc.name.encode("utf-8")).hexdigest()[:24]
        claimed_hours = f"{claim['hours']:.4f}".rstrip("0").rstrip(".")
        queue_push_to_users(
            users,
            {
                "title": "Daily Timesheet exceeds allowed hours",
                "body": (
                    f"{claim['person']} · {claim['project_name']} · {formatdate(claim['date'])} "
                    f"({claim['shift']}): {claimed_hours} h claimed; "
                    f"{claim['maximum']:g} h allowed ({LIMIT_LABELS[claim['limit_field']]})."
                ),
                "url": f"/app/daily-timesheet/{quote(doc.name, safe='')}",
                "tag": f"timesheet-hours-exceeded-{tag}",
            },
            notification_type=NOTIFICATION_FLAG,
        )
    except Exception:
        # Notification problems must not lose the employee's timesheet.
        frappe.log_error(
            title="Daily Timesheet hour-limit notification failed",
            message=f"Daily Timesheet: {doc.name}\n{frappe.get_traceback()}",
        )
