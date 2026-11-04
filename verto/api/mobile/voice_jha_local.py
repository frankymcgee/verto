"""Private SDP exchange with the optional tenant-local speech service.

The browser receives only SDP and ICE connection credentials. Raven's key is
passed directly to the trusted tenant service, never through frontend code.
The service delegates every JHA read/write to the existing authenticated tools.
"""
from __future__ import annotations

import copy
import json
from urllib.parse import urlsplit

import frappe
import requests

from verto.api.mobile.peri_voice_settings import SETTINGS_DOCTYPE


def local_ice_servers() -> list[dict]:
    settings = frappe.get_cached_doc(SETTINGS_DOCTYPE)
    raw = settings.get("peri_voice_local_ice_servers") or "[]"
    try:
        servers = json.loads(raw)
    except (TypeError, ValueError):
        frappe.throw("Local Speech ICE Servers must be a JSON array.", frappe.ValidationError)
    if not isinstance(servers, list) or len(servers) > 8:
        frappe.throw("Local Speech ICE Servers must be an array of up to eight servers.", frappe.ValidationError)
    result = []
    for server in servers:
        if not isinstance(server, dict) or set(server) - {"urls", "username", "credential"}:
            frappe.throw("Invalid Local Speech ICE server settings.", frappe.ValidationError)
        urls = server.get("urls")
        values = [urls] if isinstance(urls, str) else urls
        if not isinstance(values, list) or not values or not all(
            isinstance(url, str) and url.startswith(("stun:", "stuns:", "turn:", "turns:")) for url in values
        ):
            frappe.throw("Local Speech ICE server URLs must use STUN or TURN.", frappe.ValidationError)
        result.append({key: value for key, value in server.items() if key in {"urls", "username", "credential"}})
    return result


def create_local_call(*, client, sdp: str, config: dict, instructions: str, tools: list[dict]) -> dict:
    url = str(config.get("local_service_url") or "").strip().rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        frappe.throw("Configure a valid Local Speech Service URL in Verto Mobile Settings.", frappe.ValidationError)
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        frappe.throw("Use HTTPS for a speech service on another host, or HTTP on loopback.", frappe.ValidationError)

    settings = frappe.get_single(SETTINGS_DOCTYPE)
    token = settings.get_password("peri_voice_local_service_token", raise_exception=False)
    if not token:
        frappe.throw("Set the Local Speech Service Token in Verto Mobile Settings.", frappe.ValidationError)
    api_key = getattr(client, "api_key", None)
    if not isinstance(api_key, str) or not api_key:
        frappe.throw("Configure Raven's OpenAI API key before using local speech.", frappe.ValidationError)

    response_tools = copy.deepcopy(tools)
    for tool in response_tools:
        tool["strict"] = False
    payload = {
        "sdp": sdp,
        "tenant": frappe.local.site,
        "instructions": instructions,
        "tools": response_tools,
        "model": config["local_backend_model"],
        "reasoning_effort": config["local_reasoning_effort"],
        "openai_api_key": api_key,
        "openai_base_url": str(getattr(client, "base_url", "https://api.openai.com/v1")),
        "openai_project": getattr(client, "project", None),
        "openai_organization": getattr(client, "organization", None),
        "ice_servers": local_ice_servers(),
    }
    try:
        # Do not follow redirects with a request carrying either credential.
        # A service failure must never silently start a billable cloud voice call.
        response = requests.post(url + "/offer", json=payload, headers={"Authorization": f"Bearer {token}"},
                                 timeout=(3, 25), allow_redirects=False)
        if response.status_code != 200:
            frappe.throw("The local speech service is unavailable or not ready. Check its health and configuration.", frappe.ValidationError)
        answer = response.json()
    except (requests.RequestException, ValueError):
        # Never log an HTTP request/response that can contain an API key.
        frappe.throw("Could not reach the local speech service. Check its URL, token and service logs.", frappe.ValidationError)
    if not isinstance(answer, dict) or not str(answer.get("sdp") or "").startswith("v=0") or not answer.get("session_reference"):
        frappe.throw("The local speech service did not return a valid WebRTC answer.", frappe.ValidationError)
    return {"sdp": answer["sdp"], "model": config["local_backend_model"],
            "session_reference": str(answer["session_reference"])}
