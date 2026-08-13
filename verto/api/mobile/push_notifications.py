from __future__ import annotations

import json
from urllib.parse import quote, urlparse

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, now_datetime, nowdate


SUBSCRIPTION_DOCTYPE = "Verto Push Subscription"
SETTINGS_DOCTYPE = "Verto Mobile Settings"

VAPID_PUBLIC_KEY_CONFIG = "verto_push_vapid_public_key"
VAPID_PRIVATE_KEY_CONFIG = "verto_push_vapid_private_key"
VAPID_SUBJECT_CONFIG = "verto_push_vapid_subject"

DEFAULT_VAPID_SUBJECT = "mailto:support@webwire.com.au"
DEFAULT_NOTIFICATION_URL = "/verto-mobile"
MISSING_HOURS_NOTIFICATION_URL = "/verto-mobile/shifts"
TIMESHEET_EXCLUSIONS_FIELD = "timesheet_reminder_exclusions"

SHIFT_PROJECT_FIELD_CANDIDATES = (
    "custom_project",
    "project",
    "custom_project_name",
    "project_name",
)
DAILY_TIMESHEET_PROJECT_FIELD_CANDIDATES = (
    "project_id",
    "project",
    "parent_project",
    "link_project",
    "project_name",
    "custom_project_name",
)


def _require_login():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def _as_dict(value):
    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            decoded = json.loads(value or "{}")
        except (TypeError, ValueError):
            decoded = {}

        return decoded if isinstance(decoded, dict) else {}

    return {}


def _clean(value) -> str:
    return str(value or "").strip()


def _as_bool(value, default=False) -> bool:
    if value in (None, ""):
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    return _clean(value).lower() in {"1", "true", "yes", "y", "on"}


def _site_config_value(key: str, default=""):
    return getattr(frappe.conf, key, None) or default


def _get_vapid_config() -> dict:
    public_key = _clean(_site_config_value(VAPID_PUBLIC_KEY_CONFIG))
    private_key = _clean(_site_config_value(VAPID_PRIVATE_KEY_CONFIG))
    subject = _clean(_site_config_value(VAPID_SUBJECT_CONFIG, DEFAULT_VAPID_SUBJECT))

    if not subject.startswith(("mailto:", "https://", "http://")):
        subject = f"mailto:{subject}" if "@" in subject else DEFAULT_VAPID_SUBJECT

    # site_config.json may contain an escaped PEM value. A filesystem path can also
    # be supplied and is passed through unchanged for pywebpush to load.
    if "\\n" in private_key and "-----BEGIN" in private_key:
        private_key = private_key.replace("\\n", "\n")

    return {
        "public_key": public_key,
        "private_key": private_key,
        "subject": subject,
        "configured": bool(public_key and private_key),
    }


def _validate_subscription(subscription: dict) -> dict:
    endpoint = _clean(subscription.get("endpoint"))
    keys = _as_dict(subscription.get("keys"))
    p256dh = _clean(keys.get("p256dh"))
    auth = _clean(keys.get("auth"))

    parsed_endpoint = urlparse(endpoint)

    if parsed_endpoint.scheme != "https" or not parsed_endpoint.netloc:
        frappe.throw(_("The push subscription endpoint is invalid."), frappe.ValidationError)

    if not p256dh or not auth:
        frappe.throw(_("The push subscription encryption keys are missing."), frappe.ValidationError)

    return {
        "endpoint": endpoint,
        "p256dh": p256dh,
        "auth": auth,
        "expiration_time": _clean(subscription.get("expirationTime")),
    }


def _subscription_doctype_exists() -> bool:
    return bool(frappe.db.exists("DocType", SUBSCRIPTION_DOCTYPE))


@frappe.whitelist()
def get_push_config():
    _require_login()

    vapid = _get_vapid_config()
    subscription_count = 0

    if _subscription_doctype_exists():
        subscription_count = frappe.db.count(
            SUBSCRIPTION_DOCTYPE,
            filters={
                "user": frappe.session.user,
                "enabled": 1,
            },
        )

    return {
        "configured": vapid["configured"],
        "public_key": vapid["public_key"] if vapid["configured"] else "",
        "subscription_count": subscription_count,
    }


@frappe.whitelist()
def save_push_subscription(subscription=None, device_label="", user_agent=""):
    _require_login()

    if not _subscription_doctype_exists():
        frappe.throw(
            _("Verto Push Subscription is not installed. Run bench migrate first."),
            frappe.ValidationError,
        )

    vapid = _get_vapid_config()

    if not vapid["configured"]:
        frappe.throw(_("Web Push has not been configured for this site."), frappe.ValidationError)

    values = _validate_subscription(_as_dict(subscription))
    existing_name = frappe.db.get_value(
        SUBSCRIPTION_DOCTYPE,
        {"endpoint": values["endpoint"]},
        "name",
    )

    if existing_name:
        doc = frappe.get_doc(SUBSCRIPTION_DOCTYPE, existing_name)
    else:
        doc = frappe.new_doc(SUBSCRIPTION_DOCTYPE)

    doc.update(
        {
            "user": frappe.session.user,
            "endpoint": values["endpoint"],
            "p256dh": values["p256dh"],
            "auth": values["auth"],
            "expiration_time": values["expiration_time"],
            "device_label": _clean(device_label)[:140],
            "user_agent": _clean(user_agent),
            "enabled": 1,
            "disabled_on": None,
            "last_error": "",
            "last_error_at": None,
        }
    )

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    return {
        "name": doc.name,
        "enabled": bool(doc.enabled),
    }


@frappe.whitelist()
def disable_push_subscription(endpoint=""):
    _require_login()

    endpoint = _clean(endpoint)

    if not endpoint or not _subscription_doctype_exists():
        return {"disabled": False}

    subscription_name = frappe.db.get_value(
        SUBSCRIPTION_DOCTYPE,
        {
            "endpoint": endpoint,
            "user": frappe.session.user,
        },
        "name",
    )

    if not subscription_name:
        return {"disabled": False}

    frappe.db.set_value(
        SUBSCRIPTION_DOCTYPE,
        subscription_name,
        {
            "enabled": 0,
            "disabled_on": now_datetime(),
        },
        update_modified=True,
    )

    return {"disabled": True}


def _normalise_users(users) -> list[str]:
    if isinstance(users, str):
        try:
            decoded = json.loads(users)
            users = decoded if isinstance(decoded, list) else [users]
        except (TypeError, ValueError):
            users = [users]

    unique_users = []
    seen = set()

    for user in users or []:
        user = _clean(user)

        if not user or user == "Guest" or user in seen:
            continue

        seen.add(user)
        unique_users.append(user)

    return unique_users


def queue_push_to_users(users, payload: dict, notification_type="general"):
    users = _normalise_users(users)

    if not users or not _get_vapid_config()["configured"]:
        return None

    return frappe.enqueue(
        "verto.api.mobile.push_notifications.send_push_to_users",
        queue="short",
        timeout=300,
        enqueue_after_commit=True,
        users=users,
        payload=payload,
        notification_type=notification_type,
    )


def _record_delivery_success(subscription_name: str):
    frappe.db.set_value(
        SUBSCRIPTION_DOCTYPE,
        subscription_name,
        {
            "last_successful_delivery": now_datetime(),
            "last_error": "",
            "last_error_at": None,
        },
        update_modified=False,
    )


def _record_delivery_failure(subscription_name: str, error, status_code=None):
    if status_code in (404, 410):
        frappe.delete_doc(
            SUBSCRIPTION_DOCTYPE,
            subscription_name,
            ignore_permissions=True,
            force=True,
        )
        return

    updates = {
        "last_error": _clean(error)[:500],
        "last_error_at": now_datetime(),
    }

    frappe.db.set_value(
        SUBSCRIPTION_DOCTYPE,
        subscription_name,
        updates,
        update_modified=False,
    )


def send_push_to_users(users, payload=None, notification_type="general"):
    users = _normalise_users(users)
    payload = _as_dict(payload)
    vapid = _get_vapid_config()

    if not users or not payload or not vapid["configured"] or not _subscription_doctype_exists():
        return {"sent": 0, "failed": 0}

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        frappe.log_error(
            title="Verto Web Push dependency missing",
            message="Install verto/requirements.txt so pywebpush is available.",
        )
        return {"sent": 0, "failed": 0}

    subscriptions = frappe.get_all(
        SUBSCRIPTION_DOCTYPE,
        filters={
            "user": ["in", users],
            "enabled": 1,
        },
        fields=["name", "endpoint", "p256dh", "auth"],
        ignore_permissions=True,
        limit_page_length=1000,
    )

    sent = 0
    failed = 0

    for subscription in subscriptions:
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh,
                "auth": subscription.auth,
            },
        }

        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
                vapid_private_key=vapid["private_key"],
                vapid_claims={"sub": vapid["subject"]},
                ttl=3600,
                headers={"Urgency": "normal"},
            )
            _record_delivery_success(subscription.name)
            sent += 1
        except WebPushException as error:
            status_code = getattr(getattr(error, "response", None), "status_code", None)
            _record_delivery_failure(subscription.name, error, status_code)
            failed += 1
        except Exception as error:
            _record_delivery_failure(subscription.name, error)
            failed += 1

    return {
        "sent": sent,
        "failed": failed,
        "notification_type": notification_type,
    }


@frappe.whitelist()
def send_test_push_notification():
    _require_login()

    queue_push_to_users(
        [frappe.session.user],
        {
            "title": "Verto notifications enabled",
            "body": "Push notifications are working on this device.",
            "url": DEFAULT_NOTIFICATION_URL,
            "tag": "verto-push-test",
        },
        notification_type="test",
    )

    return {"queued": True}


def _enabled_user(user: str) -> bool:
    if not user or user == "Guest":
        return False

    return bool(frappe.db.get_value("User", user, "enabled"))


def _queue_shift_notification(doc, changed=False):
    if getattr(doc, "docstatus", 0) != 1 or not getattr(doc, "employee", None):
        return

    user = frappe.db.get_value("Employee", doc.employee, "user_id")

    if not _enabled_user(user):
        return

    queue_push_to_users(
        [user],
        {
            "title": "Shift updated" if changed else "Shift assigned",
            "body": (
                "Your shift allocation has been updated."
                if changed
                else "A new shift has been assigned to you."
            ),
            "url": "/verto-mobile/shifts",
            "tag": f"shift-{doc.name}",
        },
        notification_type="shift_changed" if changed else "shift_assigned",
    )


def notify_shift_assigned(doc, method=None):
    _queue_shift_notification(doc, changed=False)


def notify_shift_changed(doc, method=None):
    _queue_shift_notification(doc, changed=True)


def _normalise_identity(value) -> str:
    return _clean(value).casefold()


def _log_missing_hours_configuration_error(message: str):
    frappe.log_error(
        title="Verto missing-hours reminder configuration",
        message=message,
    )


def _row_project(row, fieldnames) -> str:
    for fieldname in fieldnames:
        value = _clean(row.get(fieldname))
        if value:
            return value

    return ""


def _canonical_project_id(value, cache=None) -> str:
    """Return the Project document ID for either an ID or display name."""
    value = _clean(value)
    if not value:
        return ""

    cache = cache if cache is not None else {}
    cache_key = _normalise_identity(value)
    if cache_key in cache:
        return cache[cache_key]

    project_id = ""
    if frappe.db.exists("DocType", "Project"):
        if frappe.db.exists("Project", value):
            project_id = value
        else:
            project_meta = frappe.get_meta("Project")
            for title_field in ("project_name", "title"):
                if not project_meta.has_field(title_field):
                    continue

                project_id = _clean(
                    frappe.db.get_value(
                        "Project",
                        {title_field: value},
                        "name",
                    )
                )
                if project_id:
                    break

    project_id = project_id or value
    cache[cache_key] = project_id
    cache[_normalise_identity(project_id)] = project_id
    return project_id


def _get_timesheet_reminder_exclusions(target_date) -> set[tuple[str, str]]:
    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        return set()

    settings_meta = frappe.get_meta(SETTINGS_DOCTYPE)
    if not settings_meta.has_field(TIMESHEET_EXCLUSIONS_FIELD):
        return set()

    settings = frappe.get_single(SETTINGS_DOCTYPE)
    exclusions = set()
    project_cache = {}

    for row in settings.get(TIMESHEET_EXCLUSIONS_FIELD) or []:
        if not _as_bool(row.get("enabled"), default=True):
            continue

        user = _normalise_identity(row.get("user"))
        project = _normalise_identity(
            _canonical_project_id(row.get("project"), project_cache)
        )
        if not user or not project:
            continue

        from_date = getdate(row.get("from_date")) if row.get("from_date") else None
        to_date = getdate(row.get("to_date")) if row.get("to_date") else None

        if from_date and target_date < from_date:
            continue

        if to_date and target_date > to_date:
            continue

        exclusions.add((user, project))

    return exclusions


def _get_allocated_users_for_date(target_date) -> tuple[dict[str, dict], list[dict]]:
    if not frappe.db.exists("DocType", "Shift Assignment"):
        _log_missing_hours_configuration_error(
            "Shift Assignment is not available; missing-hours reminders were skipped."
        )
        return {}, []

    shift_meta = frappe.get_meta("Shift Assignment")
    required_shift_fields = {"employee", "start_date", "end_date"}
    missing_shift_fields = [
        fieldname
        for fieldname in required_shift_fields
        if not shift_meta.has_field(fieldname)
    ]

    if missing_shift_fields:
        _log_missing_hours_configuration_error(
            "Shift Assignment is missing required fields: "
            + ", ".join(sorted(missing_shift_fields))
        )
        return {}, []

    shift_fields = ["name", "employee"]
    if shift_meta.has_field("employee_name"):
        shift_fields.append("employee_name")

    for fieldname in SHIFT_PROJECT_FIELD_CANDIDATES:
        if shift_meta.has_field(fieldname) and fieldname not in shift_fields:
            shift_fields.append(fieldname)

    shift_filters = {
        "docstatus": 1,
        "start_date": ["<=", target_date],
        "end_date": [">=", target_date],
    }
    if shift_meta.has_field("status"):
        shift_filters["status"] = "Active"

    shift_rows = frappe.get_all(
        "Shift Assignment",
        filters=shift_filters,
        fields=shift_fields,
        limit_page_length=10000,
    )
    employee_ids = sorted({_clean(row.get("employee")) for row in shift_rows if row.get("employee")})

    if not employee_ids:
        return {}, []

    employee_meta = frappe.get_meta("Employee")
    employee_fields = ["name", "employee_name", "user_id"]
    employee_filters = {
        "name": ["in", employee_ids],
        "user_id": ["is", "set"],
    }
    if employee_meta.has_field("status"):
        employee_filters["status"] = "Active"

    employees = frappe.get_all(
        "Employee",
        filters=employee_filters,
        fields=employee_fields,
        limit_page_length=10000,
    )
    employee_by_id = {row.name: row for row in employees if row.get("user_id")}
    user_ids = sorted({_clean(row.user_id) for row in employees if row.get("user_id")})

    if not user_ids:
        return {}, []

    enabled_users = {
        row.name: row
        for row in frappe.get_all(
            "User",
            filters={
                "name": ["in", user_ids],
                "enabled": 1,
            },
            fields=["name", "full_name"],
            limit_page_length=10000,
        )
    }

    exclusions = _get_timesheet_reminder_exclusions(target_date)
    allocated_users = {}
    excluded_allocations = []
    project_cache = {}

    for shift in shift_rows:
        employee = employee_by_id.get(_clean(shift.get("employee")))
        if not employee:
            continue

        user = _clean(employee.user_id)
        if user not in enabled_users:
            continue

        project = _canonical_project_id(
            _row_project(shift, SHIFT_PROJECT_FIELD_CANDIDATES),
            project_cache,
        )
        if (
            project
            and (_normalise_identity(user), _normalise_identity(project)) in exclusions
        ):
            excluded_allocations.append(
                {
                    "user": user,
                    "project": project,
                    "shift_assignment": _clean(shift.name),
                }
            )
            continue

        allocation = allocated_users.setdefault(
            user,
            {
                "user": user,
                "user_full_name": _clean(enabled_users[user].get("full_name")),
                "employee_ids": set(),
                "employee_names": set(),
                "shift_assignments": set(),
                "allocations": [],
            },
        )
        allocation["employee_ids"].add(_clean(employee.name))
        allocation["employee_names"].add(_clean(employee.get("employee_name")))
        allocation["employee_names"].add(_clean(shift.get("employee_name")))
        allocation["employee_names"].discard("")
        allocation["shift_assignments"].add(_clean(shift.name))
        allocation["allocations"].append(
            {
                "shift_assignment": _clean(shift.name),
                "project": project,
            }
        )

    return allocated_users, excluded_allocations


def _get_daily_timesheets_with_hours(target_date):
    if not frappe.db.exists("DocType", "Daily Timesheet"):
        _log_missing_hours_configuration_error(
            "Daily Timesheet is not available; missing-hours reminders were skipped."
        )
        return None

    timesheet_meta = frappe.get_meta("Daily Timesheet")
    required_timesheet_fields = {"date", "duration"}
    missing_timesheet_fields = [
        fieldname
        for fieldname in required_timesheet_fields
        if not timesheet_meta.has_field(fieldname)
    ]

    if missing_timesheet_fields:
        _log_missing_hours_configuration_error(
            "Daily Timesheet is missing required fields: "
            + ", ".join(sorted(missing_timesheet_fields))
        )
        return None

    fields = ["name", "owner", "duration"]
    for fieldname in ("employee", "employee_name", "current_user"):
        if timesheet_meta.has_field(fieldname):
            fields.append(fieldname)

    for fieldname in DAILY_TIMESHEET_PROJECT_FIELD_CANDIDATES:
        if timesheet_meta.has_field(fieldname) and fieldname not in fields:
            fields.append(fieldname)

    timesheets = frappe.get_all(
        "Daily Timesheet",
        filters={
            "date": target_date,
            "docstatus": ["!=", 2],
            "duration": [">", 0],
        },
        fields=fields,
        limit_page_length=10000,
    )

    project_cache = {}
    for timesheet in timesheets:
        timesheet["_verto_project_id"] = _canonical_project_id(
            _row_project(timesheet, DAILY_TIMESHEET_PROJECT_FIELD_CANDIDATES),
            project_cache,
        )

    return timesheets


def _timesheet_matches_user(timesheet, allocation: dict) -> bool:
    user_id = _normalise_identity(allocation.get("user"))
    user_full_name = _normalise_identity(allocation.get("user_full_name"))
    employee_ids = {
        _normalise_identity(value)
        for value in allocation.get("employee_ids", set())
        if value
    }
    employee_names = {
        _normalise_identity(value)
        for value in allocation.get("employee_names", set())
        if value
    }

    if _normalise_identity(timesheet.get("owner")) == user_id:
        return True

    if _normalise_identity(timesheet.get("employee")) in employee_ids:
        return True

    if _normalise_identity(timesheet.get("employee_name")) in employee_names:
        return True

    current_user = _normalise_identity(timesheet.get("current_user"))
    return bool(
        current_user
        and current_user
        in ({user_id, user_full_name} | employee_names)
    )


def _timesheet_matches_allocation(timesheet, allocation: dict, shift_allocation: dict) -> bool:
    if not _timesheet_matches_user(timesheet, allocation):
        return False

    shift_project = _normalise_identity(shift_allocation.get("project"))
    timesheet_project = _normalise_identity(
        timesheet.get("_verto_project_id")
        or _row_project(timesheet, DAILY_TIMESHEET_PROJECT_FIELD_CANDIDATES)
    )

    # Preserve the existing user-and-date matching on sites where either side
    # does not expose a usable project field. When both values exist, require an
    # exact project match so hours on another project do not satisfy this shift.
    return not shift_project or not timesheet_project or shift_project == timesheet_project


def get_missing_hours_users(target_date=None) -> dict:
    target_date = getdate(target_date or add_days(nowdate(), -1))
    allocated_users, excluded_allocations = _get_allocated_users_for_date(target_date)

    if not allocated_users:
        return {
            "date": target_date,
            "allocated_users": {},
            "completed_users": [],
            "missing_users": [],
            "excluded_allocations": excluded_allocations,
        }

    timesheets = _get_daily_timesheets_with_hours(target_date)
    if timesheets is None:
        return {
            "date": target_date,
            "allocated_users": allocated_users,
            "completed_users": [],
            "missing_users": [],
            "excluded_allocations": excluded_allocations,
            "skipped": True,
        }

    completed_users = {
        user
        for user, allocation in allocated_users.items()
        if allocation["allocations"]
        and all(
            any(
                _timesheet_matches_allocation(
                    timesheet,
                    allocation,
                    shift_allocation,
                )
                for timesheet in timesheets
            )
            for shift_allocation in allocation["allocations"]
        )
    }
    missing_users = sorted(set(allocated_users) - completed_users)

    return {
        "date": target_date,
        "allocated_users": allocated_users,
        "completed_users": sorted(completed_users),
        "missing_users": missing_users,
        "excluded_allocations": excluded_allocations,
    }


def send_previous_day_missing_hours_reminders(target_date=None, dry_run=False):
    """Notify enabled users who had a shift but recorded no hours for the date.

    The scheduler calls this without arguments, which checks yesterday in the
    site's configured timezone. ``target_date`` and ``dry_run`` are provided so
    administrators can safely verify historical data with ``bench execute``.
    """
    result = get_missing_hours_users(target_date)
    target_date = result["date"]
    missing_users = result["missing_users"]
    dry_run = bool(cint(dry_run))

    if missing_users and not dry_run and not result.get("skipped"):
        formatted_date = target_date.strftime("%A, %-d %B")
        queue_push_to_users(
            missing_users,
            {
                "title": "Timesheet Reminder",
                "body": (
                    f"No hours are recorded for your shift on {formatted_date}. "
                    "Tap to enter them."
                ),
                "url": MISSING_HOURS_NOTIFICATION_URL,
                "tag": f"missing-hours-{target_date.isoformat()}",
            },
            notification_type="missing_hours",
        )

    return {
        "date": target_date.isoformat(),
        "allocated_user_count": len(result["allocated_users"]),
        "completed_user_count": len(result["completed_users"]),
        "missing_user_count": len(missing_users),
        "missing_users": missing_users,
        "excluded_allocation_count": len(result["excluded_allocations"]),
        "excluded_allocations": result["excluded_allocations"],
        "dry_run": dry_run,
        "queued": bool(missing_users and not dry_run and not result.get("skipped")),
        "skipped": bool(result.get("skipped")),
    }


def notify_document_assignment(doc, method=None):
    if getattr(doc, "status", "Open") != "Open":
        return

    allocated_to = _clean(getattr(doc, "allocated_to", None))
    reference_type = _clean(getattr(doc, "reference_type", None))
    reference_name = _clean(getattr(doc, "reference_name", None))

    if not allocated_to or not reference_type or not reference_name:
        return

    if allocated_to == getattr(doc, "owner", None) or not _enabled_user(allocated_to):
        return

    from verto.api.mobile.documents import ALLOWED_MOBILE_DOCTYPES, get_mobile_slug_for_doctype

    allowed_mobile_doctypes = set(ALLOWED_MOBILE_DOCTYPES.values())

    if reference_type == "Task":
        title = "Task assigned"
        body = "A project task has been assigned to you."
        url = DEFAULT_NOTIFICATION_URL
    elif reference_type in allowed_mobile_doctypes:
        mobile_slug = get_mobile_slug_for_doctype(reference_type)
        title = "Form assigned"
        body = "A form has been assigned to you."
        url = (
            f"/verto-mobile/edit/{quote(mobile_slug, safe='')}"
            f"/{quote(reference_name, safe='')}"
        )
    else:
        return

    queue_push_to_users(
        [allocated_to],
        {
            "title": title,
            "body": body,
            "url": url,
            "tag": f"assignment-{doc.name}",
        },
        notification_type="assignment",
    )


def get_project_notification_users(project_name: str) -> list[str]:
    if not project_name:
        return []

    rows = frappe.db.sql(
        """
        SELECT DISTINCT todo.allocated_to AS user
        FROM `tabToDo` todo
        INNER JOIN `tabTask` task
            ON task.name = todo.reference_name
        INNER JOIN `tabUser` enabled_user
            ON enabled_user.name = todo.allocated_to
        WHERE todo.reference_type = 'Task'
          AND todo.status = 'Open'
          AND task.project = %(project_name)s
          AND COALESCE(task.status, '') NOT IN ('Cancelled', 'Template')
          AND enabled_user.enabled = 1
          AND COALESCE(todo.allocated_to, '') != ''
        """,
        {"project_name": project_name},
        as_dict=True,
    )

    return [row.user for row in rows if row.user]


def _get_project_for_raven_channel(channel_id: str):
    if not channel_id or not frappe.get_meta("Project").has_field("raven_channel"):
        return None

    return frappe.db.get_value(
        "Project",
        {"raven_channel": channel_id},
        ["name", "project_name"],
        as_dict=True,
    )


def _get_raven_channel(channel_id: str):
    if not channel_id or not frappe.db.exists("DocType", "Raven Channel"):
        return None

    meta = frappe.get_meta("Raven Channel")
    fields = ["name"]

    for fieldname in (
        "is_direct_message",
        "is_self_message",
        "dm_user_1",
        "dm_user_2",
    ):
        if meta.has_field(fieldname):
            fields.append(fieldname)

    return frappe.db.get_value(
        "Raven Channel",
        channel_id,
        fields,
        as_dict=True,
    )


def _get_direct_message_users(channel_id: str, channel) -> list[str]:
    users = []

    for fieldname in ("dm_user_1", "dm_user_2"):
        user = _clean(channel.get(fieldname))
        if user:
            users.append(user)

    # Raven versions before dm_user_1/dm_user_2 stored the participants only
    # in Raven Channel Member. Also use the member rows as a defensive fallback
    # if either canonical DM field is empty.
    if len(set(users)) < 2 and frappe.db.exists("DocType", "Raven Channel Member"):
        members = frappe.get_all(
            "Raven Channel Member",
            filters={"channel_id": channel_id},
            fields=["user_id"],
            limit_page_length=20,
        )
        users.extend(_clean(member.user_id) for member in members)

    return _normalise_users(users)


def _get_raven_sender_name(doc) -> str:
    is_bot_message = cint(getattr(doc, "is_bot_message", 0))
    raven_user = _clean(
        getattr(doc, "bot", None)
        if is_bot_message
        else getattr(doc, "owner", None)
    )

    if raven_user and frappe.db.exists("DocType", "Raven User"):
        full_name = _clean(frappe.db.get_value("Raven User", raven_user, "full_name"))
        if full_name:
            return full_name

    owner = _clean(getattr(doc, "owner", None))
    if owner:
        return _clean(frappe.db.get_value("User", owner, "full_name"))

    return ""


def _notify_direct_message(doc, channel_id: str, channel) -> bool:
    if not cint(channel.get("is_direct_message")):
        return False

    # A Raven self-message is a private note to the same user, not an incoming
    # DM, so it must never generate a push notification.
    if cint(channel.get("is_self_message")):
        return True

    owner = _clean(getattr(doc, "owner", None))
    is_bot_message = cint(getattr(doc, "is_bot_message", 0))
    bot = _clean(getattr(doc, "bot", None))

    recipients = []
    for user in _get_direct_message_users(channel_id, channel):
        # For ordinary messages the owner is the sender. Raven bot messages can
        # retain the requesting user as owner, so exclude the bot identity and
        # keep the human participant eligible for the bot response.
        if (not is_bot_message and user == owner) or (is_bot_message and user == bot):
            continue

        if _enabled_user(user):
            recipients.append(user)

    if not recipients:
        return True

    sender_name = _get_raven_sender_name(doc)
    title = f"New message from {sender_name}" if sender_name else "New direct message"

    queue_push_to_users(
        recipients,
        {
            "title": title,
            "body": "You have a new direct message in Raven.",
            "url": f"/verto-mobile/chat?channel={quote(channel_id, safe='')}",
            "tag": f"direct-message-{channel_id}",
        },
        notification_type="direct_message",
    )

    return True


def notify_project_chat_message(doc, method=None):
    channel_id = _clean(getattr(doc, "channel_id", None))

    if not channel_id:
        return

    if (
        _clean(getattr(doc, "message_type", None)) == "System"
        or getattr(getattr(doc, "flags", None), "send_silently", False)
        or getattr(frappe.flags, "in_install", False)
        or getattr(frappe.flags, "in_patch", False)
        or getattr(frappe.flags, "in_import", False)
    ):
        return

    channel = _get_raven_channel(channel_id)

    if channel and _notify_direct_message(doc, channel_id, channel):
        return

    project = _get_project_for_raven_channel(channel_id)

    if not project:
        return

    author = _clean(getattr(doc, "owner", None))
    recipients = [
        user
        for user in get_project_notification_users(project.name)
        if user != author
    ]

    if not recipients:
        return

    queue_push_to_users(
        recipients,
        {
            "title": "New project message",
            "body": "A new message was posted in your project chat.",
            "url": f"/verto-mobile/chat?channel={quote(channel_id, safe='')}",
            "tag": f"project-chat-{channel_id}",
        },
        notification_type="project_chat",
    )
