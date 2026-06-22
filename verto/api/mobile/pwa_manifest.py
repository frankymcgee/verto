# Copyright (c) 2026, Webwire
# License: Apache-2.0

import json
import re
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import now_datetime

SETTINGS_DOCTYPE = "Verto Mobile Settings"

SITE_MANIFEST_FILENAME = "verto-mobile-manifest.webmanifest"
SITE_MANIFEST_PUBLIC_URL = f"/files/{SITE_MANIFEST_FILENAME}"

ASSET_MANIFEST_PUBLIC_URL = "/assets/verto/verto-mobile/manifest.webmanifest"
ASSET_MANIFEST_RELATIVE_PATH = ("public", "verto-mobile", "manifest.webmanifest")

DEFAULT_START_URL = "/verto-mobile/"
DEFAULT_SCOPE = "/verto-mobile/"
DEFAULT_APP_NAME = "MSS Dashboard"
DEFAULT_SHORT_NAME = "MSS"
DEFAULT_DESCRIPTION = "PWA Companion app for Mine Site Support"
DEFAULT_THEME_COLOR = "#171717"
DEFAULT_BACKGROUND_COLOR = "#171717"
DEFAULT_ICON_192 = "/assets/verto/manifest/mss-pwa-192.png"
DEFAULT_ICON_512 = "/assets/verto/manifest/mss-pwa-512.png"
DEFAULT_ICON_MASKABLE_192 = "/assets/verto/manifest/mss-pwa-maskable-192.png"
DEFAULT_ICON_MASKABLE_512 = "/assets/verto/manifest/mss-pwa-maskable-512.png"
DEFAULT_APPLE_TOUCH_ICON = "/assets/verto/manifest/apple-touch-icon.png"


def has_field(doc, fieldname: str) -> bool:
    return bool(doc.meta and doc.meta.has_field(fieldname))


def get_first(doc, fieldnames: list[str], default=None):
    for fieldname in fieldnames:
        if has_field(doc, fieldname):
            value = doc.get(fieldname)
            if value not in (None, ""):
                return value
    return default


def clean_url(value: str | None) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "/")):
        return value
    return f"/{value.lstrip('/')}"


def as_bool(value, default=False):
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def normalise_color(value: str | None, fallback: str) -> str:
    value = str(value or "").strip()
    if re.match(r"^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$", value):
        return value
    return fallback


def normalise_orientation(value: str | None) -> str:
    value = str(value or "").strip()
    allowed = {
        "any",
        "natural",
        "landscape",
        "landscape-primary",
        "landscape-secondary",
        "portrait",
        "portrait-primary",
        "portrait-secondary",
    }
    return value if value in allowed else "portrait-primary"


def normalise_display(value: str | None) -> str:
    value = str(value or "").strip()
    allowed = {"fullscreen", "standalone", "minimal-ui", "browser"}
    return value if value in allowed else "standalone"


def icon_from_settings(settings, fieldnames: list[str], fallback: str) -> str:
    return clean_url(get_first(settings, fieldnames, fallback))


def build_icons(settings) -> list[dict]:
    icon_192 = icon_from_settings(
        settings,
        ["pwa_icon_192", "manifest_icon_192", "android_icon_192", "icon_192"],
        DEFAULT_ICON_192,
    )
    icon_512 = icon_from_settings(
        settings,
        ["pwa_icon_512", "manifest_icon_512", "android_icon_512", "icon_512", "app_icon_url", "app_icon", "logo"],
        DEFAULT_ICON_512,
    )
    maskable_192 = icon_from_settings(
        settings,
        ["pwa_maskable_icon_192", "maskable_icon_192", "manifest_maskable_icon_192"],
        DEFAULT_ICON_MASKABLE_192,
    )
    maskable_512 = icon_from_settings(
        settings,
        ["pwa_maskable_icon_512", "maskable_icon_512", "manifest_maskable_icon_512"],
        DEFAULT_ICON_MASKABLE_512,
    )
    apple_touch_icon = icon_from_settings(
        settings,
        ["apple_touch_icon", "ios_icon", "pwa_apple_touch_icon"],
        DEFAULT_APPLE_TOUCH_ICON,
    )

    return [
        {"src": icon_192, "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": icon_512, "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": maskable_192, "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
        {"src": maskable_512, "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        {"src": apple_touch_icon, "sizes": "180x180", "type": "image/png", "purpose": "any"},
    ]


def child_rows(settings, fieldnames: list[str]):
    for fieldname in fieldnames:
        if has_field(settings, fieldname):
            rows = settings.get(fieldname) or []
            if rows:
                return rows
    return []


def build_screenshots(settings) -> list[dict]:
    rows = child_rows(settings, ["pwa_screenshots", "manifest_screenshots", "app_screenshots", "screenshots"])
    screenshots = []

    for row in rows:
        src = clean_url(row.get("src") or row.get("image") or row.get("screenshot") or row.get("file") or row.get("file_url"))
        if not src:
            continue
        screenshots.append({
            "src": src,
            "sizes": row.get("sizes") or row.get("size") or "1242x2688",
            "type": row.get("type") or row.get("mime_type") or "image/png",
            "description": row.get("description") or row.get("label") or "Verto Mobile screenshot",
        })

    if screenshots:
        return screenshots

    fallback = []
    for index, description in [
        (1, "Companion app for Mine Site Support"),
        (2, "Complete Site Forms online"),
        (3, "Chat with teams on any jobsite"),
        (4, "Direct message other team members"),
    ]:
        src = clean_url(get_first(settings, [f"pwa_screenshot_{index}", f"screenshot_{index}"], ""))
        if src:
            fallback.append({"src": src, "sizes": "1242x2688", "type": "image/png", "description": description})
    return fallback


def build_shortcuts(settings) -> list[dict]:
    rows = child_rows(settings, ["pwa_shortcuts", "manifest_shortcuts", "app_shortcuts", "shortcuts"])
    shortcuts = []

    for row in rows:
        name = str(row.get("name") or row.get("label") or row.get("title") or "").strip()
        url = clean_url(row.get("url") or row.get("route") or "")
        if not name or not url:
            continue
        shortcuts.append({"name": name, "short_name": row.get("short_name") or name[:12], "url": url, "description": row.get("description") or name})

    if shortcuts:
        return shortcuts

    return [
        {"name": "Home", "short_name": "Home", "url": "/verto-mobile/", "description": "Open the Verto Mobile home page"},
        {"name": "Shifts", "short_name": "Shifts", "url": "/verto-mobile/shifts", "description": "View allocated shifts"},
        {"name": "Forms", "short_name": "Forms", "url": "/verto-mobile/forms", "description": "Open completed forms"},
        {"name": "Ask PERI", "short_name": "PERI", "url": "/verto-mobile/chat/peri?mode=ai", "description": "Open Ask PERI"},
    ]


def build_manifest_from_settings(settings=None) -> dict:
    settings = settings or frappe.get_single(SETTINGS_DOCTYPE)

    app_name = str(get_first(settings, ["pwa_name", "manifest_name", "app_name", "mobile_app_name", "application_name"], DEFAULT_APP_NAME)).strip() or DEFAULT_APP_NAME
    short_name = str(get_first(settings, ["pwa_short_name", "manifest_short_name", "short_name", "app_short_name"], DEFAULT_SHORT_NAME)).strip() or DEFAULT_SHORT_NAME
    description = str(get_first(settings, ["pwa_description", "manifest_description", "app_description", "description"], DEFAULT_DESCRIPTION)).strip() or DEFAULT_DESCRIPTION
    start_url = clean_url(get_first(settings, ["pwa_start_url", "start_url"], DEFAULT_START_URL)) or DEFAULT_START_URL
    scope = clean_url(get_first(settings, ["pwa_scope", "scope"], DEFAULT_SCOPE)) or DEFAULT_SCOPE

    manifest = {
        "name": app_name,
        "short_name": short_name,
        "id": str(get_first(settings, ["pwa_manifest_id", "manifest_id", "app_id"], scope)).strip() or scope,
        "start_url": start_url,
        "scope": scope,
        "display": normalise_display(get_first(settings, ["pwa_display", "display"], "standalone")),
        "description": description,
        "lang": str(get_first(settings, ["pwa_lang", "manifest_lang", "lang"], "en-AU")),
        "dir": str(get_first(settings, ["pwa_dir", "manifest_dir", "dir"], "auto")),
        "theme_color": normalise_color(get_first(settings, ["pwa_theme_color", "theme_color"], DEFAULT_THEME_COLOR), DEFAULT_THEME_COLOR),
        "background_color": normalise_color(get_first(settings, ["pwa_background_color", "background_color"], DEFAULT_BACKGROUND_COLOR), DEFAULT_BACKGROUND_COLOR),
        "orientation": normalise_orientation(get_first(settings, ["pwa_orientation", "orientation"], "portrait-primary")),
        "prefer_related_applications": as_bool(get_first(settings, ["prefer_related_applications", "pwa_prefer_related_applications"], False), False),
        "icons": build_icons(settings),
        "screenshots": build_screenshots(settings),
        "categories": [value.strip() for value in str(get_first(settings, ["pwa_categories", "manifest_categories", "categories"], "business,productivity")).split(",") if value.strip()],
        "shortcuts": build_shortcuts(settings),
    }

    edge_width = get_first(settings, ["edge_side_panel_width", "pwa_edge_side_panel_width"], 420)
    try:
        edge_width = int(edge_width)
    except (TypeError, ValueError):
        edge_width = 420
    if edge_width:
        manifest["edge_side_panel"] = {"preferred_width": edge_width}

    return manifest


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_site_manifest(manifest_json: str) -> str:
    path = Path(frappe.get_site_path("public", "files", SITE_MANIFEST_FILENAME))
    write_text(path, manifest_json)
    return SITE_MANIFEST_PUBLIC_URL


def write_asset_manifest(manifest_json: str) -> str:
    try:
        app_path = Path(frappe.get_app_path("verto"))
        path = app_path.joinpath(*ASSET_MANIFEST_RELATIVE_PATH)
        write_text(path, manifest_json)
        return ASSET_MANIFEST_PUBLIC_URL
    except Exception:
        frappe.log_error(title="Verto PWA asset manifest write failed", message=frappe.get_traceback())
        return ""


def save_manifest_url_to_settings(settings, manifest_url: str):
    updates = {}
    if has_field(settings, "pwa_manifest_url"):
        updates["pwa_manifest_url"] = manifest_url
    if has_field(settings, "manifest_url"):
        updates["manifest_url"] = manifest_url
    if has_field(settings, "pwa_manifest_last_generated"):
        updates["pwa_manifest_last_generated"] = now_datetime()
    if has_field(settings, "manifest_last_generated"):
        updates["manifest_last_generated"] = now_datetime()
    if updates:
        settings.db_set(updates, update_modified=True)


@frappe.whitelist()
def generate_manifest_from_settings():
    if not frappe.has_permission(SETTINGS_DOCTYPE, ptype="write"):
        frappe.throw(_("You do not have permission to update the Verto Mobile manifest."), frappe.PermissionError)

    settings = frappe.get_single(SETTINGS_DOCTYPE)
    manifest = build_manifest_from_settings(settings)
    manifest_json = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"

    site_manifest_url = write_site_manifest(manifest_json)
    asset_manifest_url = write_asset_manifest(manifest_json)
    save_manifest_url_to_settings(settings, site_manifest_url)
    frappe.clear_cache(doctype=SETTINGS_DOCTYPE)

    return {"manifest": manifest, "manifest_url": site_manifest_url, "asset_manifest_url": asset_manifest_url}


@frappe.whitelist(allow_guest=True)
def get_pwa_metadata():
    try:
        settings = frappe.get_cached_doc(SETTINGS_DOCTYPE)
    except Exception:
        settings = None

    if not settings:
        return {"app_name": DEFAULT_APP_NAME, "short_name": DEFAULT_SHORT_NAME, "description": DEFAULT_DESCRIPTION, "manifest_url": SITE_MANIFEST_PUBLIC_URL, "apple_touch_icon": DEFAULT_APPLE_TOUCH_ICON, "icon": DEFAULT_ICON_192, "theme_color": DEFAULT_THEME_COLOR, "background_color": DEFAULT_BACKGROUND_COLOR}

    app_name = get_first(settings, ["pwa_name", "manifest_name", "app_name", "mobile_app_name", "application_name"], DEFAULT_APP_NAME)
    short_name = get_first(settings, ["pwa_short_name", "manifest_short_name", "short_name", "app_short_name"], DEFAULT_SHORT_NAME)
    description = get_first(settings, ["pwa_description", "manifest_description", "app_description", "description"], DEFAULT_DESCRIPTION)
    manifest_url = get_first(settings, ["pwa_manifest_url", "manifest_url"], SITE_MANIFEST_PUBLIC_URL)
    apple_touch_icon = icon_from_settings(settings, ["apple_touch_icon", "ios_icon", "pwa_apple_touch_icon"], DEFAULT_APPLE_TOUCH_ICON)
    icon = icon_from_settings(settings, ["pwa_icon_192", "manifest_icon_192", "app_icon_url", "app_icon", "logo"], DEFAULT_ICON_192)

    return {
        "app_name": app_name or DEFAULT_APP_NAME,
        "short_name": short_name or DEFAULT_SHORT_NAME,
        "description": description or DEFAULT_DESCRIPTION,
        "manifest_url": clean_url(manifest_url) or SITE_MANIFEST_PUBLIC_URL,
        "apple_touch_icon": apple_touch_icon,
        "icon": icon,
        "theme_color": normalise_color(get_first(settings, ["pwa_theme_color", "theme_color"], DEFAULT_THEME_COLOR), DEFAULT_THEME_COLOR),
        "background_color": normalise_color(get_first(settings, ["pwa_background_color", "background_color"], DEFAULT_BACKGROUND_COLOR), DEFAULT_BACKGROUND_COLOR),
    }
