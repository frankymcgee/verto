import json
import frappe
from frappe import _


DEFAULT_WORKSPACE = "Mine Site Support"
DEFAULT_GENERAL_CHANNEL = "general"
PERI_CHANNEL_SUFFIX = " _ P.E.R.I."


def _doctype_exists(doctype):
    return bool(frappe.db.exists("DocType", doctype))


def _field_exists(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _safe_json(value, fallback=None):
    if fallback is None:
        fallback = {}

    if not value:
        return fallback

    if isinstance(value, (dict, list)):
        return value

    try:
        return json.loads(value)
    except Exception:
        return fallback


def _get_current_user_full_name(user):
    if not user:
        return ""

    return frappe.db.get_value("User", user, "full_name") or user


def _get_user_image(user):
    if not user:
        return ""

    return frappe.db.get_value("User", user, "user_image") or ""


def _get_peri_channel_name(user=None):
    user = user or frappe.session.user
    return f"{user}{PERI_CHANNEL_SUFFIX}"


def _get_channel_fields():
    fields = ["name"]

    for fieldname in [
        "channel_name",
        "channel_id",
        "workspace",
        "type",
        "channel_description",
        "description",
        "is_archived",
        "is_direct_message",
        "is_self_message",
        "is_thread",
        "is_ai_thread",
        "is_dm_thread",
        "last_message_timestamp",
        "last_message_details",
        "creation",
        "modified",
        "owner",
    ]:
        if _field_exists("Raven Channel", fieldname):
            fields.append(fieldname)

    return fields


def _normalise_channel(channel):
    channel_name = (
        channel.get("channel_name")
        or channel.get("channel_id")
        or channel.get("name")
    )

    return {
        "name": channel.get("name"),
        "channel_name": channel_name,
        "channel_id": channel.get("name"),
        "workspace": channel.get("workspace") or DEFAULT_WORKSPACE,
        "type": channel.get("type") or "",
        "description": channel.get("channel_description")
        or channel.get("description")
        or "",
        "is_archived": bool(channel.get("is_archived") or 0),
        "is_direct_message": bool(channel.get("is_direct_message") or 0),
        "is_self_message": bool(channel.get("is_self_message") or 0),
        "is_thread": bool(channel.get("is_thread") or 0),
        "is_ai_thread": bool(channel.get("is_ai_thread") or 0),
        "is_dm_thread": bool(channel.get("is_dm_thread") or 0),
        "last_message_timestamp": str(channel.get("last_message_timestamp") or ""),
        "last_message_details": channel.get("last_message_details"),
        "peer_user_id": channel.get("peer_user_id"),
        "full_name": channel.get("full_name"),
    }


def _resolve_channel_name(channel_value):
    if not _doctype_exists("Raven Channel"):
        frappe.throw("Raven Channel DocType was not found. Please confirm Raven is installed.")

    if isinstance(channel_value, dict):
        channel_value = (
            channel_value.get("name")
            or channel_value.get("channel")
            or channel_value.get("channel_id")
            or channel_value.get("channel_name")
        )

    channel_value = str(channel_value or "").strip()

    if not channel_value:
        frappe.throw("Channel is required.")

    lookup_filters = [{"name": channel_value}]

    if _field_exists("Raven Channel", "channel_name"):
        lookup_filters.append({"channel_name": channel_value})

    if _field_exists("Raven Channel", "channel_id"):
        lookup_filters.append({"channel_id": channel_value})

    for filters in lookup_filters:
        existing = frappe.db.get_value("Raven Channel", filters, "name")

        if existing:
            return existing

    wanted = channel_value.lower()

    for row in frappe.get_all(
        "Raven Channel",
        fields=_get_channel_fields(),
        limit_page_length=500,
    ):
        possible_values = [
            row.get("name"),
            row.get("channel_name"),
            row.get("channel_id"),
        ]

        if any(str(value or "").lower() == wanted for value in possible_values):
            return row.name

    return channel_value


def _resolve_workspace_name(workspace=None):
    workspace = workspace or DEFAULT_WORKSPACE

    if _doctype_exists("Raven Workspace") and frappe.db.exists("Raven Workspace", workspace):
        return workspace

    return workspace


def _get_or_create_named_channel(
    channel_label,
    workspace=DEFAULT_WORKSPACE,
    channel_type="Open",
    is_direct_message=0,
    use_workspace=True,
):
    if not _doctype_exists("Raven Channel"):
        frappe.throw("Raven Channel DocType was not found. Please confirm Raven is installed.")

    channel_label = str(channel_label or "").strip()

    if not channel_label:
        frappe.throw("Channel name is required.")

    filters_to_try = []

    if _field_exists("Raven Channel", "channel_name"):
        filters = {"channel_name": channel_label}

        if use_workspace and workspace and _field_exists("Raven Channel", "workspace"):
            filters["workspace"] = workspace

        filters_to_try.append(filters)

    filters_to_try.append({"name": channel_label})

    for filters in filters_to_try:
        existing = frappe.db.get_value("Raven Channel", filters, "name")

        if existing:
            return frappe.get_doc("Raven Channel", existing)

    doc_data = {
        "doctype": "Raven Channel",
    }

    if _field_exists("Raven Channel", "channel_name"):
        doc_data["channel_name"] = channel_label

    if use_workspace and workspace and _field_exists("Raven Channel", "workspace"):
        doc_data["workspace"] = workspace

    if _field_exists("Raven Channel", "type"):
        doc_data["type"] = channel_type

    if _field_exists("Raven Channel", "is_direct_message"):
        doc_data["is_direct_message"] = is_direct_message

    channel = frappe.get_doc(doc_data)
    channel.insert(ignore_permissions=True)

    return channel


def _get_or_create_general_channel():
    return _get_or_create_named_channel(
        channel_label=DEFAULT_GENERAL_CHANNEL,
        workspace=DEFAULT_WORKSPACE,
        channel_type="Open",
        is_direct_message=0,
        use_workspace=True,
    )


def _get_or_create_peri_channel(user=None):
    user = user or frappe.session.user

    return _get_or_create_named_channel(
        channel_label=_get_peri_channel_name(user),
        workspace=None,
        channel_type="Private",
        is_direct_message=1,
        use_workspace=False,
    )


def _get_message_file_attachments(message):
    attachments = []

    file_url = message.get("file")

    if file_url:
        file_name = file_url.split("/")[-1] if "/" in file_url else file_url
        extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

        attachments.append({
            "name": message.get("name"),
            "file_name": file_name,
            "file_url": file_url,
            "is_private": file_url.startswith("/private/"),
            "file_size": 0,
            "extension": extension,
            "is_image": message.get("message_type") == "Image"
            or extension in ["jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"],
            "is_pdf": extension == "pdf",
            "is_document": extension in [
                "doc",
                "docx",
                "xls",
                "xlsx",
                "ppt",
                "pptx",
                "csv",
                "txt",
                "pdf",
            ],
            "thumbnail_width": message.get("thumbnail_width"),
            "thumbnail_height": message.get("thumbnail_height"),
            "file_thumbnail": message.get("file_thumbnail"),
            "blurhash": message.get("blurhash"),
        })

    return attachments


def _get_linked_document_preview(link_doctype, link_document):
    if not link_doctype or not link_document:
        return None

    try:
        from raven.api.document_link import get_preview_data

        preview = get_preview_data(link_doctype, link_document)

        if not preview:
            return None

        preview_fields = []

        for key, value in preview.items():
            if key in ["preview_image", "preview_title", "id", "raven_document_link"]:
                continue

            preview_fields.append({
                "label": key,
                "value": value,
            })

        return {
            "doctype": link_doctype,
            "docname": link_document,
            "title": preview.get("preview_title") or link_document,
            "subtitle": link_doctype,
            "route": preview.get("raven_document_link"),
            "preview_image": preview.get("preview_image"),
            "id": preview.get("id") or link_document,
            "fields": preview_fields,
            "raw": preview,
        }
    except Exception:
        return {
            "doctype": link_doctype,
            "docname": link_document,
            "title": link_document,
            "subtitle": link_doctype,
            "route": f"/app/{frappe.desk.utils.slug(link_doctype)}/{link_document}",
            "preview_image": None,
            "id": link_document,
            "fields": [],
            "raw": {},
        }



def _get_raven_bot_image_fields():
    if not _doctype_exists("Raven Bot"):
        return []

    meta = frappe.get_meta("Raven Bot")

    image_fields = []

    for df in meta.fields:
        fieldname = df.fieldname or ""
        label = df.label or ""
        fieldtype = df.fieldtype or ""

        if fieldtype in ["Attach", "Attach Image", "Image"]:
            image_fields.append(fieldname)
            continue

        lowered = f"{fieldname} {label}".lower()

        if any(keyword in lowered for keyword in ["image", "avatar", "photo", "picture", "icon"]):
            image_fields.append(fieldname)

    return list(dict.fromkeys(image_fields))


def _get_raven_bot_image(bot):
    bot = str(bot or "").strip()

    if not bot or not _doctype_exists("Raven Bot"):
        return ""

    if not hasattr(frappe.local, "verto_raven_bot_image_cache"):
        frappe.local.verto_raven_bot_image_cache = {}

    cache = frappe.local.verto_raven_bot_image_cache

    if bot in cache:
        return cache[bot]

    image_fields = _get_raven_bot_image_fields()

    if not image_fields:
        cache[bot] = ""
        return ""

    bot_name = None

    if frappe.db.exists("Raven Bot", bot):
        bot_name = bot
    else:
        # Try common display-name fields if message.bot is a label, not the docname.
        filters_to_try = []

        for fieldname in ["bot_name", "title", "full_name", "name"]:
            if fieldname == "name" or _field_exists("Raven Bot", fieldname):
                filters_to_try.append({fieldname: bot})

        for filters in filters_to_try:
            found = frappe.db.get_value("Raven Bot", filters, "name")
            if found:
                bot_name = found
                break

    if not bot_name:
        cache[bot] = ""
        return ""

    fields = ["name"] + image_fields
    bot_doc = frappe.db.get_value("Raven Bot", bot_name, fields, as_dict=True)

    image_value = ""

    for fieldname in image_fields:
        if bot_doc and bot_doc.get(fieldname):
            image_value = bot_doc.get(fieldname)
            break

    cache[bot] = image_value or ""
    return cache[bot]

def _normalise_message(message):
    if not isinstance(message, dict):
        message = message.as_dict()

    owner = message.get("owner") or ""
    sender = message.get("sender") or owner
    content = message.get("content")
    text = content if content is not None else message.get("text") or ""

    link_doctype = message.get("link_doctype")
    link_document = message.get("link_document")

    document_links = []

    if link_doctype and link_document:
        document_links.append({
            "doctype": link_doctype,
            "docname": link_document,
        })

    document_preview = _get_linked_document_preview(link_doctype, link_document)

    return {
        "name": message.get("name"),
        "owner": owner,
        "sender": sender,
        "sender_full_name": _get_current_user_full_name(sender or owner),
        "user_image": _get_user_image(sender or owner),
        "creation": str(message.get("creation") or ""),
        "modified": str(message.get("modified") or ""),
        "text": text,
        "message": text,
        "content": content or text,
        "channel_id": message.get("channel_id"),
        "channel": message.get("channel_id"),
        "message_type": message.get("message_type"),
        "message_reactions": _safe_json(message.get("message_reactions"), []),
        "is_reply": bool(message.get("is_reply") or 0),
        "linked_message": message.get("linked_message"),
        "replied_message_details": _safe_json(message.get("replied_message_details"), {}),
        "is_thread": bool(message.get("is_thread") or 0),
        "is_edited": bool(message.get("is_edited") or 0),
        "is_forwarded": bool(message.get("is_forwarded") or 0),
        "is_bot_message": bool(message.get("is_bot_message") or 0),
        "bot": message.get("bot"),
        "bot_image": _get_raven_bot_image(message.get("bot")),
        "hide_link_preview": bool(message.get("hide_link_preview") or 0),
        "poll_id": message.get("poll_id"),
        "file": message.get("file"),
        "file_thumbnail": message.get("file_thumbnail"),
        "thumbnail_width": message.get("thumbnail_width"),
        "thumbnail_height": message.get("thumbnail_height"),
        "blurhash": message.get("blurhash"),
        "attachments": _get_message_file_attachments(message),
        "link_doctype": link_doctype,
        "link_document": link_document,
        "document_links": document_links,
        "document_preview": document_preview,
        "linked_doctype": link_doctype,
        "linked_docname": link_document,
        "reference_doctype": link_doctype,
        "reference_docname": link_document,
        "document_type": link_doctype,
        "document_name": link_document,
        "thread_count": get_number_of_replies_safe(message.get("name")) if message.get("is_thread") else 0,
    }


def _normalise_messages(messages):
    return [_normalise_message(message) for message in messages or []]


def get_number_of_replies_safe(message_id):
    if not message_id:
        return 0

    try:
        from raven.api.threads import get_number_of_replies

        return int(get_number_of_replies(message_id) or 0)
    except Exception:
        return 0


def _get_channel_members_safe(channel_id):
    try:
        from raven.api.chat import get_channel_members

        return get_channel_members(channel_id)
    except Exception:
        return {}


def _get_all_channels_safe():
    try:
        from raven.api.raven_channel import get_all_channels

        result = get_all_channels()

        channels = result.get("channels", []) if isinstance(result, dict) else []
        dm_channels = result.get("dm_channels", []) if isinstance(result, dict) else []

        return channels + dm_channels
    except Exception:
        channels = frappe.get_all(
            "Raven Channel",
            fields=_get_channel_fields(),
            order_by="modified desc",
            limit_page_length=100,
        )

        return [dict(channel) for channel in channels]


def _get_channel_messages_via_raven(channel_id, limit=20, base_message=None):
    from raven.api.chat_stream import get_messages

    result = get_messages(
        channel_id=channel_id,
        limit=int(limit or 20),
        base_message=base_message,
    )

    return {
        **result,
        "messages": _normalise_messages(result.get("messages", [])),
    }


def _get_older_messages_via_raven(channel_id, from_message, limit=20):
    from raven.api.chat_stream import get_older_messages

    result = get_older_messages(
        channel_id=channel_id,
        from_message=from_message,
        limit=int(limit or 20),
    )

    return {
        **result,
        "messages": _normalise_messages(result.get("messages", [])),
    }


def _get_newer_messages_via_raven(channel_id, from_message, limit=20):
    from raven.api.chat_stream import get_newer_messages

    result = get_newer_messages(
        channel_id=channel_id,
        from_message=from_message,
        limit=int(limit or 20),
    )

    return {
        **result,
        "messages": _normalise_messages(result.get("messages", [])),
    }


def _create_thread_via_raven(message_id):
    from raven.api.threads import create_thread

    return create_thread(message_id=message_id)


def _get_or_create_thread_for_message(message_id):
    if not frappe.db.exists("Raven Message", message_id):
        frappe.throw(_("Message not found."))

    message = frappe.get_doc("Raven Message", message_id)

    if getattr(message, "is_thread", 0):
        if frappe.db.exists("Raven Channel", message_id):
            return {
                "channel_id": getattr(message, "channel_id", None),
                "thread_id": message_id,
            }

        existing_thread = frappe.db.get_value(
            "Raven Channel",
            {"channel_name": message_id, "is_thread": 1},
            "name",
        )

        if existing_thread:
            return {
                "channel_id": getattr(message, "channel_id", None),
                "thread_id": existing_thread,
            }

    return _create_thread_via_raven(message_id)


def _ensure_channel_member(channel_id, user_id):
    if not user_id:
        return

    if frappe.db.exists(
        "Raven Channel Member",
        {
            "channel_id": channel_id,
            "user_id": user_id,
        },
    ):
        return

    frappe.get_doc({
        "doctype": "Raven Channel Member",
        "channel_id": channel_id,
        "user_id": user_id,
    }).insert(ignore_permissions=True)


def _insert_text_message(channel_id, text, is_reply=0, linked_message=None):
    text = (text or "").strip()

    if not text:
        frappe.throw(_("Message cannot be empty."))

    if not frappe.has_permission("Raven Channel", doc=channel_id, ptype="read"):
        frappe.throw(_("You do not have permission to access this channel."), frappe.PermissionError)

    doc = frappe.get_doc({
        "doctype": "Raven Message",
        "channel_id": channel_id,
        "message_type": "Text",
        "text": text,
        "content": text,
        "is_reply": is_reply,
        "linked_message": linked_message,
    })

    doc.insert(ignore_permissions=False)

    return _normalise_message(doc.as_dict())


@frappe.whitelist()
def get_mobile_chat_bootstrap():
    user = frappe.session.user

    general_channel = _get_or_create_general_channel()
    peri_channel = _get_or_create_peri_channel(user)

    raw_channels = _get_all_channels_safe()

    required_channels = [
        general_channel.as_dict(),
        peri_channel.as_dict(),
    ]

    for required_channel in required_channels:
        if not any(channel.get("name") == required_channel.get("name") for channel in raw_channels):
            raw_channels.insert(0, required_channel)

    channels = [_normalise_channel(channel) for channel in raw_channels]

    active_channel = next(
        (
            channel
            for channel in channels
            if channel.get("name") == general_channel.name
        ),
        channels[0] if channels else None,
    )

    messages = []

    if active_channel:
        try:
            messages = get_channel_messages(active_channel["name"], limit=20).get("messages", [])
        except Exception:
            messages = []

    return {
        "current_user": user,
        "current_user_full_name": _get_current_user_full_name(user),
        "channels": channels,
        "active_channel": active_channel,
        "messages": messages,
    }


@frappe.whitelist()
def get_channels():
    raw_channels = _get_all_channels_safe()

    return {
        "channels": [_normalise_channel(channel) for channel in raw_channels],
    }


@frappe.whitelist()
def get_channel_members(channel):
    channel_id = _resolve_channel_name(channel)

    return {
        "members": _get_channel_members_safe(channel_id),
    }


@frappe.whitelist()
def get_channel_messages(channel, limit=20, base_message=None):
    channel_id = _resolve_channel_name(channel)

    return _get_channel_messages_via_raven(
        channel_id=channel_id,
        limit=limit,
        base_message=base_message,
    )


@frappe.whitelist()
def get_older_messages(channel, from_message, limit=20):
    channel_id = _resolve_channel_name(channel)

    return _get_older_messages_via_raven(
        channel_id=channel_id,
        from_message=from_message,
        limit=limit,
    )


@frappe.whitelist()
def get_newer_messages(channel, from_message, limit=20):
    channel_id = _resolve_channel_name(channel)

    return _get_newer_messages_via_raven(
        channel_id=channel_id,
        from_message=from_message,
        limit=limit,
    )


@frappe.whitelist()
def send_channel_message(channel, text):
    channel_id = _resolve_channel_name(channel)

    message = _insert_text_message(
        channel_id=channel_id,
        text=text,
        is_reply=0,
    )

    try:
        frappe.publish_realtime(
            event="verto_mobile_raven_message",
            message={
                "channel": channel_id,
                "message": message,
            },
            user=frappe.session.user,
            after_commit=True,
        )
    except Exception:
        pass

    return {
        "message": message,
    }


@frappe.whitelist()
def get_or_create_peri_channel():
    user = frappe.session.user
    channel = _get_or_create_peri_channel(user)

    try:
        _ensure_channel_member(channel.name, user)
    except Exception:
        pass

    normalised_channel = _normalise_channel(channel.as_dict())

    return {
        "channel": normalised_channel.get("name"),
        "name": normalised_channel.get("name"),
        "channel_id": normalised_channel.get("name"),
        "channel_name": normalised_channel.get("channel_name"),
        "workspace": normalised_channel.get("workspace") or DEFAULT_WORKSPACE,
        "type": normalised_channel.get("type"),
        "is_direct_message": normalised_channel.get("is_direct_message"),
        "url": f"/verto-mobile/chat?channel={normalised_channel.get('name')}&mode=ai",
    }


@frappe.whitelist()
def get_or_create_general_channel():
    channel = _get_or_create_general_channel()

    normalised_channel = _normalise_channel(channel.as_dict())

    return {
        "channel": normalised_channel.get("name"),
        "name": normalised_channel.get("name"),
        "channel_id": normalised_channel.get("name"),
        "channel_name": normalised_channel.get("channel_name"),
        "workspace": normalised_channel.get("workspace"),
        "type": normalised_channel.get("type"),
        "url": f"/verto-mobile/chat?channel={normalised_channel.get('name')}",
    }


@frappe.whitelist()
def create_direct_message_channel(user_id):
    from raven.api.raven_channel import create_direct_message_channel

    channel_id = create_direct_message_channel(user_id=user_id)

    channel = frappe.get_doc("Raven Channel", channel_id)

    return {
        "channel": _normalise_channel(channel.as_dict()),
    }


@frappe.whitelist()
def get_document_preview_data(doctype, docname):
    from raven.api.document_link import get_preview_data

    preview = get_preview_data(doctype=doctype, docname=docname)

    if not preview:
        return {
            "doctype": doctype,
            "docname": docname,
            "title": docname,
            "subtitle": doctype,
            "route": f"/app/{frappe.desk.utils.slug(doctype)}/{docname}",
            "fields": [],
            "raw": {},
        }

    fields = []

    for key, value in preview.items():
        if key in ["preview_image", "preview_title", "id", "raven_document_link"]:
            continue

        fields.append({
            "label": key,
            "value": value,
        })

    return {
        "doctype": doctype,
        "docname": docname,
        "title": preview.get("preview_title") or docname,
        "subtitle": doctype,
        "route": preview.get("raven_document_link"),
        "preview_image": preview.get("preview_image"),
        "id": preview.get("id") or docname,
        "fields": fields,
        "raw": preview,
    }


@frappe.whitelist()
def get_document_link(doctype, docname, with_site_url=True):
    from raven.api.document_link import get

    return {
        "link": get(
            doctype=doctype,
            docname=docname,
            with_site_url=with_site_url,
        ),
    }


@frappe.whitelist()
def get_number_of_replies(message):
    return {
        "count": get_number_of_replies_safe(message),
    }


@frappe.whitelist()
def create_thread(message):
    thread = _get_or_create_thread_for_message(message)

    thread_id = thread.get("thread_id")

    return {
        **thread,
        "thread_id": thread_id,
        "messages": get_channel_messages(thread_id, limit=20).get("messages", []) if thread_id else [],
    }


@frappe.whitelist()
def get_message_thread(message, limit=20):
    thread = _get_or_create_thread_for_message(message)

    thread_id = thread.get("thread_id")
    parent = frappe.get_doc("Raven Message", message)

    thread_messages = []

    if thread_id:
        try:
            thread_messages = get_channel_messages(thread_id, limit=limit).get("messages", [])
        except Exception:
            thread_messages = []

    return {
        "parent": _normalise_message(parent.as_dict()),
        "replies": thread_messages,
        "thread_id": thread_id,
        "channel_id": thread.get("channel_id"),
        "thread_supported": True,
    }


@frappe.whitelist()
def get_thread_messages(thread_id, limit=20, base_message=None):
    return get_channel_messages(
        channel=thread_id,
        limit=limit,
        base_message=base_message,
    )


@frappe.whitelist()
def send_thread_reply(parent_message, text):
    thread = _get_or_create_thread_for_message(parent_message)
    thread_id = thread.get("thread_id")

    if not thread_id:
        frappe.throw(_("Could not resolve thread channel."))

    message = _insert_text_message(
        channel_id=thread_id,
        text=text,
        is_reply=0,
    )

    try:
        frappe.publish_realtime(
            event="verto_mobile_raven_thread_reply",
            message={
                "channel": thread_id,
                "channel_id": thread_id,
                "parent_message": parent_message,
                "reply": message,
            },
            after_commit=True,
        )
    except Exception:
        pass

    return {
        "reply": message,
        "thread_id": thread_id,
    }


@frappe.whitelist()
def get_all_threads(
    workspace=None,
    content=None,
    channel_id=None,
    is_ai_thread=0,
    start_after=0,
    limit=10,
    only_show_unread=False,
):
    from raven.api.threads import get_all_threads

    threads = get_all_threads(
        workspace=workspace,
        content=content,
        channel_id=channel_id,
        is_ai_thread=is_ai_thread,
        start_after=start_after,
        limit=limit,
        only_show_unread=only_show_unread,
    )

    return {
        "threads": threads,
    }


@frappe.whitelist()
def get_other_threads(
    workspace=None,
    content=None,
    channel_id=None,
    is_ai_thread=0,
    start_after=0,
    limit=10,
):
    from raven.api.threads import get_other_threads

    threads = get_other_threads(
        workspace=workspace,
        content=content,
        channel_id=channel_id,
        is_ai_thread=is_ai_thread,
        start_after=start_after,
        limit=limit,
    )

    return {
        "threads": threads,
    }


@frappe.whitelist()
def get_unread_threads(workspace=None, thread_id=None):
    from raven.api.threads import get_unread_threads

    return {
        "threads": get_unread_threads(
            workspace=workspace,
            thread_id=thread_id,
        ),
    }


@frappe.whitelist()
def mark_all_messages_as_read(channel_ids):
    from raven.api.raven_channel import mark_all_messages_as_read

    if isinstance(channel_ids, str):
        channel_ids = json.loads(channel_ids)

    return {
        "message": mark_all_messages_as_read(channel_ids=channel_ids),
    }

@frappe.whitelist()
def debug_raven_bot_image(bot):
    bot = str(bot or "").strip()

    fields = _get_raven_bot_image_fields()

    result = {
        "bot_input": bot,
        "image_fields_found": fields,
        "bot_exists_by_name": bool(frappe.db.exists("Raven Bot", bot)) if bot else False,
        "resolved_image": _get_raven_bot_image(bot),
        "matches": [],
    }

    if not _doctype_exists("Raven Bot"):
        result["error"] = "Raven Bot DocType does not exist"
        return result

    for row in frappe.get_all(
        "Raven Bot",
        fields=["name"] + fields,
        limit_page_length=50,
    ):
        result["matches"].append(row)

    return result