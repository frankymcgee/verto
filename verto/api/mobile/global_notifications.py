from __future__ import annotations

import hashlib
from html import escape
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import add_days, cint, formatdate, get_url, getdate, now_datetime, nowdate

from verto.api.mobile.push_notifications import queue_push_to_users


SETTINGS_DOCTYPE = "Verto Mobile Settings"
RECIPIENT_DOCTYPE = "Verto Global Notification List"
LOG_DOCTYPE = "Verto Global Notification Log"
SETTINGS_TABLE_FIELD = "global_notification_list"
NOTIFICATION_FLAG = "project_missing_purchase_order"
NOTIFICATION_TYPE = "project_missing_purchase_order"
REMINDER_DAYS = (14, 7, 2)
PROJECT_START_FIELD = "expected_start_date"
PROJECT_PO_FIELD = "purchase_order_number"


def _clean(value) -> str:
    return str(value or "").strip()


def _ensure_system_manager_for_manual_call():
    user = getattr(frappe.session, "user", "") or ""
    if user in ("Administrator", "Guest", ""):
        if user == "Guest":
            frappe.throw(_("Login required"), frappe.PermissionError)
        return

    if "System Manager" not in frappe.get_roles(user):
        frappe.throw(_("System Manager access is required."), frappe.PermissionError)


def _field_exists(doctype: str, fieldname: str) -> bool:
    try:
        return bool(frappe.get_meta(doctype).has_field(fieldname))
    except Exception:
        return False


def ensure_global_notification_settings_field():
    """Install the Global Notification List controls on Verto Mobile Settings."""
    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        return
    if not frappe.db.exists("DocType", RECIPIENT_DOCTYPE):
        return

    from frappe.custom.doctype.custom_field.custom_field import create_custom_field

    fields = [
        {
            "fieldname": "global_notifications_tab",
            "label": "Global Notifications",
            "fieldtype": "Tab Break",
            "insert_after": "timesheet_reminder_exclusions",
        },
        {
            "fieldname": "global_notifications_section",
            "label": "Global Notification Recipients",
            "fieldtype": "Section Break",
            "insert_after": "global_notifications_tab",
            "description": (
                "Choose which users receive each global notification and whether delivery uses email, push, or both."
            ),
        },
        {
            "fieldname": SETTINGS_TABLE_FIELD,
            "label": "Global Notification List",
            "fieldtype": "Table",
            "options": RECIPIENT_DOCTYPE,
            "insert_after": "global_notifications_section",
        },
    ]

    for field in fields:
        if _field_exists(SETTINGS_DOCTYPE, field["fieldname"]):
            continue
        create_custom_field(
            SETTINGS_DOCTYPE,
            field,
            ignore_validate=True,
            is_system_generated=True,
        )

    frappe.clear_cache(doctype=SETTINGS_DOCTYPE)


def after_install():
    ensure_global_notification_settings_field()


def after_migrate():
    ensure_global_notification_settings_field()


def _recipient_rows() -> list[dict]:
    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        return []
    if not _field_exists(SETTINGS_DOCTYPE, SETTINGS_TABLE_FIELD):
        return []

    settings = frappe.get_cached_doc(SETTINGS_DOCTYPE)
    recipients = []
    seen_users = set()

    for row in settings.get(SETTINGS_TABLE_FIELD) or []:
        user = _clean(row.get("user"))
        if not cint(row.get("enabled")):
            continue
        if not cint(row.get(NOTIFICATION_FLAG)):
            continue
        if not user or user in seen_users:
            continue

        user_info = frappe.db.get_value(
            "User",
            user,
            ["enabled", "email", "full_name"],
            as_dict=True,
        ) or {}
        if not cint(user_info.get("enabled")):
            continue

        email = _clean(user_info.get("email")) or (user if "@" in user else "")
        receive_email = bool(cint(row.get("receive_email")) and email)
        receive_push = bool(cint(row.get("receive_push")))
        if not (receive_email or receive_push):
            continue

        seen_users.add(user)
        recipients.append(
            {
                "user": user,
                "full_name": _clean(user_info.get("full_name")) or user,
                "email": email,
                "receive_email": receive_email,
                "receive_push": receive_push,
            }
        )

    return recipients


def _project_rows_for_date(target_date) -> list[dict]:
    if not frappe.db.exists("DocType", "Project"):
        return []
    if not _field_exists("Project", PROJECT_START_FIELD):
        return []
    if not _field_exists("Project", PROJECT_PO_FIELD):
        return []

    fields = ["name", "project_name", "status", PROJECT_START_FIELD, PROJECT_PO_FIELD]
    rows = frappe.get_all(
        "Project",
        filters={PROJECT_START_FIELD: target_date},
        fields=fields,
        order_by=f"{PROJECT_START_FIELD} asc, name asc",
        limit_page_length=1000,
        ignore_permissions=True,
    )

    result = []
    for row in rows:
        status = _clean(row.get("status")).casefold()
        if status in {"completed", "cancelled", "canceled"}:
            continue
        if _clean(row.get(PROJECT_PO_FIELD)):
            continue
        result.append(dict(row))

    return result


def _delivery_key(*, project: str, user: str, channel: str, reminder_days: int, start_date) -> str:
    raw = "|".join(
        [
            NOTIFICATION_TYPE,
            _clean(project),
            _clean(user),
            _clean(channel).lower(),
            str(int(reminder_days)),
            str(getdate(start_date)),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _delivery_already_logged(delivery_key: str) -> bool:
    if not frappe.db.exists("DocType", LOG_DOCTYPE):
        return False
    return bool(frappe.db.exists(LOG_DOCTYPE, {"delivery_key": delivery_key}))


def _record_delivery(*, delivery_key: str, project: str, user: str, channel: str, reminder_days: int, start_date):
    if not frappe.db.exists("DocType", LOG_DOCTYPE):
        return
    if _delivery_already_logged(delivery_key):
        return

    frappe.get_doc(
        {
            "doctype": LOG_DOCTYPE,
            "delivery_key": delivery_key,
            "notification_type": NOTIFICATION_TYPE,
            "project": project,
            "recipient_user": user,
            "channel": channel,
            "reminder_days": int(reminder_days),
            "scheduled_start_date": getdate(start_date),
            "queued_at": now_datetime(),
        }
    ).insert(ignore_permissions=True)


def _project_url(project_name: str) -> str:
    return get_url(f"/app/project/{quote(_clean(project_name), safe='')}")


def _email_subject(project_label: str, reminder_days: int) -> str:
    return f"Project Purchase Order required: {project_label} starts in {reminder_days} days"


def _email_message(project: dict, reminder_days: int) -> str:
    project_id = _clean(project.get("name"))
    project_label = _clean(project.get("project_name")) or project_id
    start_date = getdate(project.get(PROJECT_START_FIELD))
    project_url = _project_url(project_id)

    return f"""
<p>Hello,</p>
<p><strong>{escape(project_label)}</strong> is scheduled to start in <strong>{reminder_days} days</strong> on <strong>{formatdate(start_date)}</strong>, but no Purchase Order number has been entered in Verto.</p>
<p>Please update the Project before the scheduled start date.</p>
<p><a href="{project_url}">Open Project in Verto</a></p>
<p><strong>Project ID:</strong> {escape(project_id)}<br>
<strong>Scheduled Start:</strong> {formatdate(start_date)}<br>
<strong>Purchase Order:</strong> Missing</p>
""".strip()


def _queue_email(recipient: dict, project: dict, reminder_days: int) -> bool:
    project_id = _clean(project.get("name"))
    project_label = _clean(project.get("project_name")) or project_id
    email = _clean(recipient.get("email"))
    if not email:
        return False

    frappe.sendmail(
        recipients=[email],
        subject=_email_subject(project_label, reminder_days),
        message=_email_message(project, reminder_days),
        delayed=True,
        reference_doctype="Project",
        reference_name=project_id,
    )
    return True


def _queue_push(recipient: dict, project: dict, reminder_days: int):
    project_id = _clean(project.get("name"))
    project_label = _clean(project.get("project_name")) or project_id
    start_date = getdate(project.get(PROJECT_START_FIELD))

    return queue_push_to_users(
        [recipient["user"]],
        {
            "title": "Project Purchase Order required",
            "body": f"{project_label} starts in {reminder_days} days and has no Purchase Order number entered.",
            "url": f"/app/project/{quote(project_id, safe='')}",
            "tag": f"project-po-missing-{project_id}-{reminder_days}-{start_date}",
        },
        notification_type=NOTIFICATION_TYPE,
    )


def _dispatch_channel(*, recipient: dict, project: dict, reminder_days: int, channel: str, dry_run: bool) -> dict:
    project_id = _clean(project.get("name"))
    start_date = getdate(project.get(PROJECT_START_FIELD))
    user = recipient["user"]
    key = _delivery_key(
        project=project_id,
        user=user,
        channel=channel,
        reminder_days=reminder_days,
        start_date=start_date,
    )

    if _delivery_already_logged(key):
        return {"status": "already_queued", "channel": channel, "project": project_id, "user": user}

    if dry_run:
        return {"status": "would_queue", "channel": channel, "project": project_id, "user": user}

    queued = False
    if channel == "Email":
        queued = _queue_email(recipient, project, reminder_days)
    elif channel == "Push":
        queued = bool(_queue_push(recipient, project, reminder_days))

    if not queued:
        return {"status": "not_queued", "channel": channel, "project": project_id, "user": user}

    _record_delivery(
        delivery_key=key,
        project=project_id,
        user=user,
        channel=channel,
        reminder_days=reminder_days,
        start_date=start_date,
    )
    return {"status": "queued", "channel": channel, "project": project_id, "user": user}


def send_project_missing_purchase_order_reminders(reference_date=None, dry_run=False):
    """Send 14/7/2-day reminders for Projects without Purchase Orders.

    Scheduler calls this once per day. ``reference_date`` and ``dry_run`` are
    intentionally supported for bench-console testing.
    """
    if reference_date is not None or cint(dry_run):
        _ensure_system_manager_for_manual_call()

    reference = getdate(reference_date or nowdate())
    dry_run = bool(cint(dry_run))
    recipients = _recipient_rows()

    summary = {
        "reference_date": str(reference),
        "recipient_count": len(recipients),
        "project_count": 0,
        "queued": 0,
        "already_queued": 0,
        "not_queued": 0,
        "would_queue": 0,
        "deliveries": [],
    }

    if not recipients:
        return summary

    seen_projects = set()

    for reminder_days in REMINDER_DAYS:
        target_date = getdate(add_days(reference, reminder_days))
        projects = _project_rows_for_date(target_date)

        for project in projects:
            project_id = _clean(project.get("name"))
            seen_projects.add(project_id)

            for recipient in recipients:
                if recipient.get("receive_email"):
                    result = _dispatch_channel(
                        recipient=recipient,
                        project=project,
                        reminder_days=reminder_days,
                        channel="Email",
                        dry_run=dry_run,
                    )
                    summary["deliveries"].append(result)
                    summary[result["status"]] = summary.get(result["status"], 0) + 1

                if recipient.get("receive_push"):
                    result = _dispatch_channel(
                        recipient=recipient,
                        project=project,
                        reminder_days=reminder_days,
                        channel="Push",
                        dry_run=dry_run,
                    )
                    summary["deliveries"].append(result)
                    summary[result["status"]] = summary.get(result["status"], 0) + 1

    summary["project_count"] = len(seen_projects)
    return summary


@frappe.whitelist(methods=["POST"])
def preview_project_missing_purchase_order_reminders(reference_date=None):
    _ensure_system_manager_for_manual_call()
    return send_project_missing_purchase_order_reminders(reference_date=reference_date, dry_run=True)
