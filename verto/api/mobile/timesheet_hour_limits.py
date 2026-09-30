"""Opt-in email/push alerts for saved Daily Timesheet claims above Project limits."""

from __future__ import annotations

import hashlib
import math
from html import escape
from urllib.parse import quote

import frappe
from frappe.utils import cint, formatdate, get_url, getdate

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


def _queue_email(recipient, doc, claim, claimed_hours, url):
    """Create one normal Email Queue entry per recipient in the save transaction."""
    email = _clean(recipient.get("email"))
    if not email:
        return

    details = (
        ("Person", claim["person"]),
        ("Project", claim["project_name"]),
        ("Project ID", claim["project"]),
        ("Work date", formatdate(claim["date"])),
        ("Shift", claim["shift"]),
        ("Hours claimed", claimed_hours),
        ("Maximum allowed", f"{claim['maximum']:g}"),
        ("Project limit", LIMIT_LABELS[claim["limit_field"]]),
        ("Daily Timesheet", doc.name),
    )
    rows = "".join(
        f"<tr><th align=\"left\">{escape(label)}</th><td>{escape(str(value))}</td></tr>"
        for label, value in details
    )
    frappe.sendmail(
        recipients=[email],
        subject=f"Daily Timesheet exceeds allowed hours: {claim['person']}",
        message=(
            "<p>A saved Daily Timesheet exceeds the Project's allowed hours. Please review the claim.</p>"
            f"<table>{rows}</table>"
            f'<p><a href="{escape(get_url(url), quote=True)}">Open Daily Timesheet in Verto</a></p>'
        ),
        delayed=True,
        is_notification=True,
        reference_doctype="Daily Timesheet",
        reference_name=doc.name,
    )


def _log_delivery_error(doc, channel, recipient):
    frappe.log_error(
        title="Daily Timesheet hour-limit notification failed",
        message=(f"Daily Timesheet: {doc.name}\nChannel: {channel}\n"
                 f"Recipient: {recipient}\n{frappe.get_traceback()}"),
    )


def notify_daily_timesheet_hours_exceeded(doc, method=None):
    """Called by on_update for Desk, mobile and offline-sync saves.

    Push queues after commit; delayed email entries belong to the save transaction.
    Every successful save of an over-limit claim can notify, including re-saves
    with unchanged hours. A failed channel does not stop other deliveries.
    """
    try:
        if cint(doc.get("docstatus")) == 2:
            return
        recipients = _recipient_rows(NOTIFICATION_FLAG)
        if not recipients:
            return
        claim = get_hours_exceeded(doc)
        if not claim:
            return

        # Re-saves replace the same timesheet's old push. The service worker sets
        # renotify for tagged messages, so replacements still alert the recipient.
        tag = hashlib.sha256(doc.name.encode("utf-8")).hexdigest()[:24]
        claimed_hours = f"{claim['hours']:.4f}".rstrip("0").rstrip(".")
        url = f"/app/daily-timesheet/{quote(doc.name, safe='')}"
        for recipient in recipients:
            if recipient.get("receive_email"):
                try:
                    _queue_email(recipient, doc, claim, claimed_hours, url)
                except Exception:
                    _log_delivery_error(doc, "Email", recipient["user"])

        users = [row["user"] for row in recipients if row.get("receive_push")]
        if users:
            try:
                queue_push_to_users(
                    users,
                    {
                        "title": "Daily Timesheet exceeds allowed hours",
                        "body": (
                            f"{claim['person']} · {claim['project_name']} · {formatdate(claim['date'])} "
                            f"({claim['shift']}): {claimed_hours} h claimed; "
                            f"{claim['maximum']:g} h allowed ({LIMIT_LABELS[claim['limit_field']]})."
                        ),
                        "url": url,
                        "tag": f"timesheet-hours-exceeded-{tag}",
                    },
                    notification_type=NOTIFICATION_FLAG,
                )
            except Exception:
                _log_delivery_error(doc, "Push", ", ".join(users))
    except Exception:
        # Notification problems must not lose the employee's timesheet.
        frappe.log_error(
            title="Daily Timesheet hour-limit notification failed",
            message=f"Daily Timesheet: {doc.name}\n{frappe.get_traceback()}",
        )
