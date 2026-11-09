"""Project radios: LiveKit audio, server-controlled publishing and Redis floor leases."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlsplit

import frappe
from frappe import _


CHANNEL = "Verto Walkie Talkie"
SETTINGS = "Verto Walkie Talkie Settings"
HEARTBEAT_SECONDS = 3
LEASE_SECONDS = 10
SESSION_SECONDS = 60


def _login():
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)
    frappe.local.response_headers["Cache-Control"] = "no-store"


def _manager(user):
    return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def _project_access(project, user):
    if frappe.db.exists("Project User", {"parent": project, "parenttype": "Project", "user": user}):
        return True
    return bool(frappe.db.sql("""
        SELECT name FROM `tabTask` WHERE project = %s AND status != 'Cancelled'
        AND JSON_CONTAINS(COALESCE(NULLIF(_assign, ''), '[]'), %s) LIMIT 1
    """, (project, json.dumps(user))))


def has_permission(doc, user=None, ptype=None, permission_type=None, **kwargs):
    user = user or frappe.session.user
    if not user or user == "Guest":
        return False
    if _manager(user):
        return True
    if (ptype or permission_type or "read") != "read" or not doc:
        return False
    if not _project_access(doc.get("project"), user):
        return False
    raven = doc.get("raven_channel")
    return not raven or bool(frappe.db.exists("Raven Channel Member", {"channel_id": raven, "user_id": user}))


def get_permission_query_conditions(user=None):
    user = user or frappe.session.user
    if not user or user == "Guest":
        return "1=0"
    if _manager(user):
        return ""
    escaped = frappe.db.escape(user)
    assigned = frappe.db.escape(json.dumps(user))
    return f"""(
        EXISTS (SELECT 1 FROM `tabProject User` pu WHERE pu.parent = `tab{CHANNEL}`.project
            AND pu.parenttype = 'Project' AND pu.user = {escaped})
        OR EXISTS (SELECT 1 FROM `tabTask` t WHERE t.project = `tab{CHANNEL}`.project
            AND t.status != 'Cancelled'
            AND JSON_CONTAINS(COALESCE(NULLIF(t._assign, ''), '[]'), {assigned}))
    ) AND (COALESCE(`tab{CHANNEL}`.raven_channel, '') = '' OR EXISTS (
        SELECT 1 FROM `tabRaven Channel Member` m
        WHERE m.channel_id = `tab{CHANNEL}`.raven_channel AND m.user_id = {escaped}
    ))"""


def _config(require_enabled=True):
    settings = frappe.get_single(SETTINGS)
    if require_enabled and not settings.enabled:
        frappe.throw(_("Walkie talkie is not enabled. Contact your administrator."))
    url = str(settings.livekit_url or "").strip().rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme != "wss" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        frappe.throw(_("Set a valid secure LiveKit URL in Verto Walkie Talkie Settings."))
    secret = settings.get_password("livekit_api_secret", raise_exception=False)
    if not settings.livekit_api_key or not secret:
        frappe.throw(_("Configure the LiveKit API key and secret in Verto Walkie Talkie Settings."))
    return {"url": url, "key": settings.livekit_api_key, "secret": secret,
            "max_seconds": max(5, min(120, int(settings.max_transmission_seconds or 60)))}


def _token(config, room, *, identity="", name="", admin=False):
    # LiveKit uses standard HS256 JWTs. No media or server SDK is needed in Frappe.
    now = int(time.time())
    grant = {"room": room, "roomAdmin": True} if admin else {
        "room": room, "roomJoin": True, "canSubscribe": True, "canPublish": False,
        "canPublishData": False, "canPublishSources": ["microphone"], "canUpdateOwnMetadata": False,
    }
    claims = {"iss": config["key"], "sub": identity, "name": name,
              "nbf": now - 5, "exp": now + (60 if admin else 300), "video": grant}

    def encode(value):
        return base64.urlsafe_b64encode(value).rstrip(b"=")

    unsigned = b".".join(encode(json.dumps(value, separators=(",", ":")).encode())
                         for value in ({"alg": "HS256", "typ": "JWT"}, claims))
    signature = hmac.new(config["secret"].encode(), unsigned, hashlib.sha256).digest()
    return (unsigned + b"." + encode(signature)).decode()


def _service(config, room, method, data):
    import requests

    try:
        response = requests.post(
            "https://" + config["url"][6:] + "/twirp/livekit.RoomService/" + method,
            headers={"Authorization": "Bearer " + _token(config, room, admin=True)},
            json={"room": room, **data}, timeout=5, allow_redirects=False,
        )
        if response.status_code == 404 and response.json().get("code") == "not_found":
            return False
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Unexpected LiveKit response")
        return True
    except (requests.RequestException, ValueError):
        # Do not log responses, tokens, or credentials.
        frappe.throw(_("Could not reach the walkie talkie audio service. Try joining again."))


def _publish(config, session, allowed):
    return _service(config, session["room"], "UpdateParticipant", {
        "identity": session["identity"], "permission": {
            "canSubscribe": True, "canPublish": allowed, "canPublishData": False,
            "canPublishSources": ["MICROPHONE"], "canUpdateMetadata": False,
        },
    })


def _get(key):
    value = frappe.cache.get(frappe.cache.make_key("verto:radio:" + key))
    return json.loads(value) if value else None


def _put(key, value, seconds=SESSION_SECONDS):
    # Raw Redis commands fail closed if Redis is unavailable (set_value suppresses errors).
    frappe.cache.set(frappe.cache.make_key("verto:radio:" + key), json.dumps(value), ex=seconds)


def _delete(key):
    frappe.cache.delete(frappe.cache.make_key("verto:radio:" + key))


def _lock(room):
    return frappe.cache.lock(frappe.cache.make_key("verto:radio:lock:" + room), timeout=30, blocking_timeout=3)


def _floor(config, room):
    floor = _get("floor:" + room)
    if floor and time.time() >= floor["expires_at"]:
        _publish(config, floor, False)
        _delete("floor:" + room)
        floor = None
    return floor


def _public_floor(floor):
    return {key: floor[key] for key in ("identity", "display_name")} if floor else None


def _session(session_id):
    _login()
    if not isinstance(session_id, str) or not 20 <= len(session_id) <= 100:
        frappe.throw(_("Invalid walkie talkie session."), frappe.PermissionError)
    session = _get("session:" + session_id)
    if not session or session["user"] != frappe.session.user:
        frappe.throw(_("Walkie talkie session expired. Join the channel again."), frappe.PermissionError)
    return session


def _channel_access(name):
    doc = frappe.get_doc(CHANNEL, name)
    if not doc.enabled or not has_permission(doc):
        frappe.throw(_("You do not have access to this walkie talkie channel."), frappe.PermissionError)
    return doc


@frappe.whitelist(methods=["GET"])
def get_channels(project: str):
    _login()
    if not _manager(frappe.session.user) and not _project_access(project, frappe.session.user):
        frappe.throw(_("You do not have access to this project radio."), frappe.PermissionError)
    channels = frappe.get_list(CHANNEL, filters={"project": project, "enabled": 1},
                               fields=["name", "channel_name", "project"], order_by="channel_name asc")
    return {"channels": channels}


@frappe.whitelist(methods=["POST"])
def join_channel(channel: str):
    _login()
    doc = _channel_access(channel)
    config = _config()
    session_id = secrets.token_urlsafe(24)
    room = "verto-radio-" + hashlib.sha256((frappe.local.site + ":" + doc.name).encode()).hexdigest()[:32]
    session = {"user": frappe.session.user, "channel": doc.name, "room": room,
               "identity": secrets.token_hex(16),
               "display_name": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user}
    _put("session:" + session_id, session)
    return {"session_id": session_id, "url": config["url"], "identity": session["identity"],
            "token": _token(config, room, identity=session["identity"], name=session["display_name"]),
            "heartbeat_seconds": HEARTBEAT_SECONDS, "lease_seconds": LEASE_SECONDS,
            "max_transmission_seconds": config["max_seconds"]}


@frappe.whitelist(methods=["POST"])
def floor_action(session_id: str, action: str):
    session = _session(session_id)
    if action not in {"claim", "heartbeat", "release"}:
        frappe.throw(_("Invalid walkie talkie action."))
    config = _config(require_enabled=action != "release")
    if action != "release":
        try:
            _channel_access(session["channel"])
        except frappe.PermissionError:
            _service(config, session["room"], "RemoveParticipant", {"identity": session["identity"]})
            raise
    with _lock(session["room"]):
        floor = _floor(config, session["room"])
        owns_floor = bool(floor and floor["session_id"] == session_id)
        if action == "release" and owns_floor:
            _publish(config, session, False)
            _delete("floor:" + session["room"])
            floor = None
        elif action == "claim" and not floor:
            now = time.time()
            floor = {**session, "session_id": session_id, "started_at": now,
                     "expires_at": now + LEASE_SECONDS, "deadline": now + config["max_seconds"]}
            # Persist the owner before granting publish, so failed responses remain recoverable.
            _put("floor:" + session["room"], floor, 86400)
            if not _publish(config, session, True):
                _delete("floor:" + session["room"])
                frappe.throw(_("The audio connection has closed. Join the channel again."))
        elif action == "heartbeat" and owns_floor:
            if time.time() >= floor["deadline"]:
                _publish(config, session, False)
                _delete("floor:" + session["room"])
                floor = None
            else:
                floor["expires_at"] = min(time.time() + LEASE_SECONDS, floor["deadline"])
                _put("floor:" + session["room"], floor, 86400)
        _put("session:" + session_id, session)
        return {"granted": bool(floor and floor["session_id"] == session_id), "floor": _public_floor(floor)}


@frappe.whitelist(methods=["POST"])
def leave_channel(session_id: str):
    session = _session(session_id)
    config = _config(require_enabled=False)
    with _lock(session["room"]):
        _service(config, session["room"], "RemoveParticipant", {"identity": session["identity"]})
        floor = _get("floor:" + session["room"])
        if floor and floor["session_id"] == session_id:
            _delete("floor:" + session["room"])
        _delete("session:" + session_id)
    return {"left": True}
