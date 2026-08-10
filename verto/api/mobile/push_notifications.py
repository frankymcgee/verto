from __future__ import annotations

import json
from urllib.parse import quote, urlparse

import frappe
from frappe import _
from frappe.utils import now_datetime


SUBSCRIPTION_DOCTYPE = "Verto Push Subscription"

VAPID_PUBLIC_KEY_CONFIG = "verto_push_vapid_public_key"
VAPID_PRIVATE_KEY_CONFIG = "verto_push_vapid_private_key"
VAPID_SUBJECT_CONFIG = "verto_push_vapid_subject"

DEFAULT_VAPID_SUBJECT = "mailto:support@webwire.com.au"
DEFAULT_NOTIFICATION_URL = "/verto-mobile/"


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


def notify_project_chat_message(doc, method=None):
    channel_id = _clean(getattr(doc, "channel_id", None))
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
