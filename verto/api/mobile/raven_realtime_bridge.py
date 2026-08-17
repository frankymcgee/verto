# VERTO_RAVEN_BACKEND_REALTIME_BRIDGE_2026_06_10
"""
Small Verto realtime bridge for Raven messages.

Why this exists:
- Raven publishes its native realtime events to Raven/Frappe rooms.
- In the Verto mobile route, the socket can be connected while not receiving those Raven room events.
- This bridge does not replace Raven APIs or Raven message handling.
- It simply republishes Raven Message changes to the actual Raven Channel members using a
  Verto-specific realtime event that the native Verto frontend can listen for.

Add the hook entries from hooks_raven_realtime_additions.py to verto/hooks.py.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time
from typing import Any

import frappe

BRIDGE_EVENT = "verto:raven_message_event"
RAVEN_GLOBAL_ROOM = "doctype:Raven User"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return str(value)

    if isinstance(value, list):
        return [_json_safe(item) for item in value]

    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}

    return value


def _get_raven_user_details(user_id: str | None) -> dict[str, Any]:
    if not user_id:
        return {}

    try:
        raven_user = frappe.db.get_value(
            "Raven User",
            user_id,
            ["full_name", "user_image", "type", "bot"],
            as_dict=True,
        )
    except Exception:
        raven_user = None

    if not raven_user:
        return {}

    return {
        "sender_full_name": raven_user.get("full_name"),
        "user_image": raven_user.get("user_image"),
        "raven_user_type": raven_user.get("type"),
        "raven_user_bot": raven_user.get("bot"),
    }


def _message_payload(doc) -> dict[str, Any]:
    payload = {
        "name": doc.name,
        "owner": doc.owner,
        "sender": getattr(doc, "owner", None),
        "creation": getattr(doc, "creation", None),
        "modified": getattr(doc, "modified", None),
        "modified_by": getattr(doc, "modified_by", None),
        "channel_id": getattr(doc, "channel_id", None),
        "channel": getattr(doc, "channel_id", None),
        "text": getattr(doc, "text", None),
        "message": getattr(doc, "text", None),
        "content": getattr(doc, "content", None),
        "file": getattr(doc, "file", None),
        "message_type": getattr(doc, "message_type", None),
        "message_reactions": getattr(doc, "message_reactions", None),
        "_liked_by": getattr(doc, "_liked_by", None),
        "is_reply": getattr(doc, "is_reply", None),
        "linked_message": getattr(doc, "linked_message", None),
        "replied_message_details": getattr(doc, "replied_message_details", None),
        "link_doctype": getattr(doc, "link_doctype", None),
        "link_document": getattr(doc, "link_document", None),
        "is_thread": getattr(doc, "is_thread", None),
        "is_forwarded": getattr(doc, "is_forwarded", None),
        "is_edited": getattr(doc, "is_edited", None),
        "is_bot_message": getattr(doc, "is_bot_message", None),
        "bot": getattr(doc, "bot", None),
        "hide_link_preview": getattr(doc, "hide_link_preview", None),
        "file_thumbnail": getattr(doc, "file_thumbnail", None),
        "thumbnail_width": getattr(doc, "thumbnail_width", None),
        "thumbnail_height": getattr(doc, "thumbnail_height", None),
        "image_width": getattr(doc, "image_width", None),
        "image_height": getattr(doc, "image_height", None),
        "blurhash": getattr(doc, "blurhash", None),
        "json": getattr(doc, "json", None),
    }

    payload.update(_get_raven_user_details(getattr(doc, "owner", None)))

    if getattr(doc, "is_bot_message", 0) and getattr(doc, "bot", None):
        try:
            bot_details = frappe.db.get_value(
                "Raven Bot",
                doc.bot,
                ["bot_name", "image"],
                as_dict=True,
            )
        except Exception:
            bot_details = None

        if bot_details:
            payload["bot_image"] = bot_details.get("image")
            payload["sender_full_name"] = bot_details.get("bot_name") or payload.get("sender_full_name")

    return _json_safe(payload)


def _get_channel_recipients(channel_id: str | None) -> list[str]:
    if not channel_id:
        return []

    try:
        users = frappe.db.get_all(
            "Raven Channel Member",
            filters={"channel_id": channel_id},
            pluck="user_id",
        )
    except Exception:
        users = []

    recipients: set[str] = set()

    for user in users or []:
        if user and user != "Guest":
            recipients.add(user)

    # Always include the sender/session user where possible. This makes testing across
    # two tabs/devices as the same user work reliably.
    try:
        if frappe.session.user and frappe.session.user != "Guest":
            recipients.add(frappe.session.user)
    except Exception:
        pass

    return sorted(recipients)


def _publish_to_recipients(payload: dict[str, Any], channel_id: str | None):
    recipients = _get_channel_recipients(channel_id)

    for user in recipients:
        frappe.publish_realtime(
            BRIDGE_EVENT,
            payload,
            user=user,
            after_commit=True,
        )

    # Also publish to Raven's global frontend room as a best-effort fallback for
    # public/open channels where membership rows may be incomplete.
    frappe.publish_realtime(
        BRIDGE_EVENT,
        payload,
        room=RAVEN_GLOBAL_ROOM,
        after_commit=True,
    )


def publish_raven_message_upsert(doc, method: str | None = None):
    """Hook for Raven Message on_update.

    This is intentionally an upsert event. Raven Message on_update can be fired for
    newly-created messages, image/file metadata completion, edits, thread metadata updates,
    and reaction-like changes. The frontend can safely merge by message.name.
    """
    channel_id = getattr(doc, "channel_id", None)

    if not channel_id:
        return

    payload = {
        "action": "upsert",
        "doctype": "Raven Message",
        "name": doc.name,
        "message_id": doc.name,
        "channel_id": channel_id,
        "is_thread": getattr(doc, "is_thread", None),
        "is_reply": getattr(doc, "is_reply", None),
        "linked_message": getattr(doc, "linked_message", None),
        "message": _message_payload(doc),
    }

    _publish_to_recipients(_json_safe(payload), channel_id)


def publish_raven_message_delete(doc, method: str | None = None):
    """Hook for Raven Message after_delete."""
    channel_id = getattr(doc, "channel_id", None)

    if not channel_id:
        return

    payload = {
        "action": "delete",
        "doctype": "Raven Message",
        "name": doc.name,
        "message_id": doc.name,
        "channel_id": channel_id,
        "is_thread": getattr(doc, "is_thread", None),
        "is_reply": getattr(doc, "is_reply", None),
        "linked_message": getattr(doc, "linked_message", None),
    }

    _publish_to_recipients(_json_safe(payload), channel_id)
