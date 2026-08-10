# Copyright (c) 2026, Webwire
# License: Apache-2.0

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import frappe
from frappe import _
from frappe.utils import now_datetime


SETTINGS_DOCTYPE = "Verto Mobile Settings"

SITE_MANIFEST_FILENAME = "verto-mobile-manifest.webmanifest"
SITE_MANIFEST_PUBLIC_URL = f"/files/{SITE_MANIFEST_FILENAME}"

ASSET_MANIFEST_RELATIVE_PATH = ("public", "verto-mobile", "manifest.webmanifest")
ASSET_MANIFEST_PUBLIC_URL = "/assets/verto/verto-mobile/manifest.webmanifest"

DEFAULT_MANIFEST_ID = "/verto-mobile/"
DEFAULT_START_URL = "/verto-mobile"
DEFAULT_SCOPE = "/verto-mobile"
DEFAULT_APP_NAME = "Verto Mobile"
DEFAULT_SHORT_NAME = "Verto"
DEFAULT_THEME_COLOR = "#171717"
DEFAULT_BACKGROUND_COLOR = "#171717"

GENERATED_ICON_FILES = {
    "icon_192": "verto-pwa-icon-192.png",
    "icon_512": "verto-pwa-icon-512.png",
    "maskable_192": "verto-pwa-maskable-192.png",
    "maskable_512": "verto-pwa-maskable-512.png",
    "apple_touch_icon": "verto-pwa-apple-touch-icon.png",
}


def _has_field(doc, fieldname: str) -> bool:
    return bool(doc.meta and doc.meta.has_field(fieldname))


def _get_first(doc, fieldnames: list[str], default=None):
    for fieldname in fieldnames:
        if _has_field(doc, fieldname):
            value = doc.get(fieldname)

            if value not in (None, ""):
                return value

    return default


def _as_bool(value, default=False):
    if value in (None, ""):
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _clean_path_or_url(value: str | None) -> str:
    value = str(value or "").strip()

    if not value:
        return ""

    if value.startswith(("http://", "https://")):
        return value

    if value.startswith("/"):
        return value

    return f"/{value.lstrip('/')}"


def _normalise_pwa_route(value: str | None, fallback: str) -> str:
    value = _clean_path_or_url(value) or fallback

    if value == "/":
        return value

    return value.rstrip("/")


def _normalise_color(value: str | None, fallback: str) -> str:
    value = str(value or "").strip()

    if not value:
        return fallback

    if re.match(r"^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$", value):
        return value

    return fallback


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = _normalise_color(value, DEFAULT_BACKGROUND_COLOR).lstrip("#")

    if len(value) == 3:
        value = "".join(char * 2 for char in value)

    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _normalise_orientation(value: str | None) -> str:
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


def _normalise_display(value: str | None) -> str:
    value = str(value or "").strip()

    allowed = {
        "fullscreen",
        "standalone",
        "minimal-ui",
        "browser",
    }

    return value if value in allowed else "standalone"


def _normalise_manifest_id(value: str | None) -> str:
    value = str(value or "").strip()

    if not value:
        return DEFAULT_MANIFEST_ID

    return value


def _get_app_name(settings) -> str:
    app_name = str(
        _get_first(
            settings,
            [
                "app_name",
                "mobile_app_name",
                "application_name",
                "pwa_name",
                "manifest_name",
            ],
            DEFAULT_APP_NAME,
        )
        or ""
    ).strip()

    return app_name or DEFAULT_APP_NAME


def _get_short_name(settings, app_name: str) -> str:
    # User requested this to come from the Verto Mobile Settings short_name field.
    short_name = str(_get_first(settings, ["short_name"], "") or "").strip()

    if short_name:
        return short_name

    return app_name[:12] if app_name else DEFAULT_SHORT_NAME


def _build_manifest_description(app_name: str) -> str:
    app_name = str(app_name or "").strip() or DEFAULT_APP_NAME
    return f"Mobile companion app for {app_name}"


def _resolve_local_file_path(file_url: str | None) -> Path | None:
    file_url = str(file_url or "").strip()

    if not file_url:
        return None

    parsed = urlparse(file_url)
    path = unquote(parsed.path if parsed.scheme else file_url)

    if path.startswith("/files/"):
        return Path(frappe.get_site_path("public", "files", path.replace("/files/", "", 1)))

    if path.startswith("/private/files/"):
        return Path(frappe.get_site_path("private", "files", path.replace("/private/files/", "", 1)))

    if path.startswith("files/"):
        return Path(frappe.get_site_path("public", "files", path.replace("files/", "", 1)))

    if path.startswith("private/files/"):
        return Path(frappe.get_site_path("private", "files", path.replace("private/files/", "", 1)))

    possible_path = Path(path)

    if possible_path.exists():
        return possible_path

    return None


def _generated_icon_path(key: str) -> Path:
    return Path(frappe.get_site_path("public", "files", GENERATED_ICON_FILES[key]))


def _generated_icon_url(key: str, cache_bust: bool = True) -> str:
    filename = GENERATED_ICON_FILES[key]
    path = _generated_icon_path(key)
    url = f"/files/{filename}"

    if cache_bust and path.exists():
        return f"{url}?v={int(path.stat().st_mtime)}"

    return url


def _contain_image(image, size: int, padding_ratio: float, background_color: str):
    from PIL import Image

    background_rgb = _hex_to_rgb(background_color)
    canvas = Image.new("RGBA", (size, size), (*background_rgb, 255))

    working = image.convert("RGBA")

    max_size = max(1, int(size * (1 - padding_ratio * 2)))
    working.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    x = (size - working.width) // 2
    y = (size - working.height) // 2

    canvas.alpha_composite(working, (x, y))

    return canvas


def _generate_pwa_icons_from_app_logo(settings) -> dict[str, str]:
    # User requested PWA icons to be generated from Verto Mobile Settings.app_logo.
    app_logo = _get_first(settings, ["app_logo"], "")

    if not app_logo:
        frappe.throw(_("Please add an App Logo before generating the PWA manifest."))

    source_path = _resolve_local_file_path(app_logo)

    if not source_path or not source_path.exists():
        frappe.throw(
            _("Could not find the App Logo file for PWA icon generation: {0}").format(app_logo)
        )

    try:
        from PIL import Image
    except Exception:
        frappe.throw(
            _(
                "Pillow is required to generate PWA icons. Run: "
                "./env/bin/pip install pillow"
            )
        )

    background_color = _normalise_color(
        _get_first(settings, ["pwa_background_color", "background_color"], DEFAULT_BACKGROUND_COLOR),
        DEFAULT_BACKGROUND_COLOR,
    )

    with Image.open(source_path) as image:
        generated_images = {
            "icon_192": _contain_image(image, 192, 0.08, background_color),
            "icon_512": _contain_image(image, 512, 0.08, background_color),
            "maskable_192": _contain_image(image, 192, 0.20, background_color),
            "maskable_512": _contain_image(image, 512, 0.20, background_color),
            "apple_touch_icon": _contain_image(image, 180, 0.08, background_color),
        }

        for key, generated_image in generated_images.items():
            output_path = _generated_icon_path(key)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            generated_image.save(output_path, "PNG", optimize=True)

    return {
        key: _generated_icon_url(key)
        for key in GENERATED_ICON_FILES
    }


def _get_existing_or_generated_icon_urls(settings) -> dict[str, str]:
    generated_files_exist = all(
        _generated_icon_path(key).exists()
        for key in GENERATED_ICON_FILES
    )

    if generated_files_exist:
        return {
            key: _generated_icon_url(key)
            for key in GENERATED_ICON_FILES
        }

    app_logo = _clean_path_or_url(_get_first(settings, ["app_logo"], ""))

    if app_logo:
        return {
            "icon_192": app_logo,
            "icon_512": app_logo,
            "maskable_192": app_logo,
            "maskable_512": app_logo,
            "apple_touch_icon": app_logo,
        }

    return {
        "icon_192": "/assets/verto/manifest/mss-pwa-192.png",
        "icon_512": "/assets/verto/manifest/mss-pwa-512.png",
        "maskable_192": "/assets/verto/manifest/mss-pwa-maskable-192.png",
        "maskable_512": "/assets/verto/manifest/mss-pwa-maskable-512.png",
        "apple_touch_icon": "/assets/verto/manifest/apple-touch-icon.png",
    }


def _build_icons(generated_icon_urls: dict[str, str]) -> list[dict]:
    return [
        {
            "src": generated_icon_urls["icon_192"],
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any",
        },
        {
            "src": generated_icon_urls["icon_512"],
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any",
        },
        {
            "src": generated_icon_urls["maskable_192"],
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "maskable",
        },
        {
            "src": generated_icon_urls["maskable_512"],
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "maskable",
        },
        {
            "src": generated_icon_urls["apple_touch_icon"],
            "sizes": "180x180",
            "type": "image/png",
            "purpose": "any",
        },
    ]


def _get_child_rows(settings, fieldnames: list[str]):
    for fieldname in fieldnames:
        if _has_field(settings, fieldname):
            rows = settings.get(fieldname) or []

            if rows:
                return rows

    return []


def _build_screenshots(settings) -> list[dict]:
    rows = _get_child_rows(
        settings,
        [
            "pwa_screenshots",
            "manifest_screenshots",
            "app_screenshots",
            "screenshots",
        ],
    )

    screenshots = []

    for row in rows:
        src = _clean_path_or_url(
            row.get("src")
            or row.get("image")
            or row.get("screenshot")
            or row.get("file")
            or row.get("file_url")
        )

        if not src:
            continue

        screenshots.append(
            {
                "src": src,
                "sizes": row.get("sizes") or row.get("size") or "1242x2688",
                "type": row.get("type") or row.get("mime_type") or "image/png",
                "description": row.get("description") or row.get("label") or "Verto Mobile screenshot",
            }
        )

    return screenshots


def _build_shortcuts(settings) -> list[dict]:
    rows = _get_child_rows(
        settings,
        [
            "pwa_shortcuts",
            "manifest_shortcuts",
            "app_shortcuts",
            "shortcuts",
        ],
    )

    shortcuts = []

    for row in rows:
        name = str(row.get("name") or row.get("label") or row.get("title") or "").strip()
        url = _clean_path_or_url(row.get("url") or row.get("route") or "")

        if not name or not url:
            continue

        shortcuts.append(
            {
                "name": name,
                "short_name": row.get("short_name") or name[:12],
                "url": url,
                "description": row.get("description") or name,
            }
        )

    if shortcuts:
        return shortcuts

    return [
        {
            "name": "Home",
            "short_name": "Home",
            "url": "/verto-mobile",
            "description": "Open the Verto Mobile home page",
        },
        {
            "name": "Shifts",
            "short_name": "Shifts",
            "url": "/verto-mobile/shifts",
            "description": "View allocated shifts",
        },
        {
            "name": "Forms",
            "short_name": "Forms",
            "url": "/verto-mobile/forms",
            "description": "Open completed forms",
        },
        {
            "name": "Ask PERI",
            "short_name": "PERI",
            "url": "/verto-mobile/chat/peri?mode=ai",
            "description": "Open Ask PERI",
        },
    ]


def build_manifest_from_settings(settings=None, generated_icon_urls: dict[str, str] | None = None) -> dict:
    settings = settings or frappe.get_single(SETTINGS_DOCTYPE)

    app_name = _get_app_name(settings)
    short_name = _get_short_name(settings, app_name)

    if not generated_icon_urls:
        generated_icon_urls = _get_existing_or_generated_icon_urls(settings)

    start_url = _normalise_pwa_route(
        _get_first(settings, ["pwa_start_url", "start_url"], DEFAULT_START_URL),
        DEFAULT_START_URL,
    )

    scope = _normalise_pwa_route(
        _get_first(settings, ["pwa_scope", "scope"], DEFAULT_SCOPE),
        DEFAULT_SCOPE,
    )

    manifest = {
        "name": app_name,
        "short_name": short_name,
        "id": _normalise_manifest_id(
            _get_first(
                settings,
                ["pwa_manifest_id", "manifest_id", "app_id"],
                DEFAULT_MANIFEST_ID,
            )
        ),
        "start_url": start_url,
        "scope": scope,
        "display": _normalise_display(
            _get_first(settings, ["pwa_display", "display"], "standalone")
        ),
        "description": _build_manifest_description(app_name),
        "lang": str(_get_first(settings, ["pwa_lang", "manifest_lang", "lang"], "en-AU")),
        "dir": str(_get_first(settings, ["pwa_dir", "manifest_dir", "dir"], "auto")),
        "theme_color": _normalise_color(
            _get_first(settings, ["pwa_theme_color", "theme_color"], DEFAULT_THEME_COLOR),
            DEFAULT_THEME_COLOR,
        ),
        "background_color": _normalise_color(
            _get_first(
                settings,
                ["pwa_background_color", "background_color"],
                DEFAULT_BACKGROUND_COLOR,
            ),
            DEFAULT_BACKGROUND_COLOR,
        ),
        "orientation": _normalise_orientation(
            _get_first(settings, ["pwa_orientation", "orientation"], "portrait-primary")
        ),
        "prefer_related_applications": _as_bool(
            _get_first(
                settings,
                ["prefer_related_applications", "pwa_prefer_related_applications"],
                False,
            ),
            False,
        ),
        "icons": _build_icons(generated_icon_urls),
        "screenshots": _build_screenshots(settings),
        "categories": [
            category.strip()
            for category in str(
                _get_first(
                    settings,
                    ["pwa_categories", "manifest_categories", "categories"],
                    "business,productivity",
                )
            ).split(",")
            if category.strip()
        ],
        "shortcuts": _build_shortcuts(settings),
    }

    edge_width = _get_first(settings, ["edge_side_panel_width", "pwa_edge_side_panel_width"], 420)

    try:
        edge_width = int(edge_width)
    except (TypeError, ValueError):
        edge_width = 420

    if edge_width:
        manifest["edge_side_panel"] = {
            "preferred_width": edge_width,
        }

    return manifest


def _write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_site_manifest(manifest_json: str) -> str:
    path = Path(frappe.get_site_path("public", "files", SITE_MANIFEST_FILENAME))
    _write_text(path, manifest_json)

    return SITE_MANIFEST_PUBLIC_URL


def _write_asset_manifest(manifest_json: str) -> str:
    try:
        app_path = Path(frappe.get_app_path("verto"))
        path = app_path.joinpath(*ASSET_MANIFEST_RELATIVE_PATH)
        _write_text(path, manifest_json)

        return ASSET_MANIFEST_PUBLIC_URL
    except Exception:
        frappe.log_error(
            title="Verto PWA asset manifest write failed",
            message=frappe.get_traceback(),
        )

        return ""


def _save_generated_values_to_settings(settings, manifest_url: str, generated_icon_urls: dict[str, str]):
    updates = {}

    if _has_field(settings, "pwa_manifest_url"):
        updates["pwa_manifest_url"] = manifest_url

    if _has_field(settings, "manifest_url"):
        updates["manifest_url"] = manifest_url

    if _has_field(settings, "pwa_manifest_last_generated"):
        updates["pwa_manifest_last_generated"] = now_datetime()

    if _has_field(settings, "manifest_last_generated"):
        updates["manifest_last_generated"] = now_datetime()

    field_map = {
        "pwa_icon_192": "icon_192",
        "manifest_icon_192": "icon_192",
        "pwa_icon_512": "icon_512",
        "manifest_icon_512": "icon_512",
        "pwa_maskable_icon_192": "maskable_192",
        "manifest_maskable_icon_192": "maskable_192",
        "pwa_maskable_icon_512": "maskable_512",
        "manifest_maskable_icon_512": "maskable_512",
        "apple_touch_icon": "apple_touch_icon",
        "pwa_apple_touch_icon": "apple_touch_icon",
    }

    for fieldname, key in field_map.items():
        if _has_field(settings, fieldname) and generated_icon_urls.get(key):
            updates[fieldname] = generated_icon_urls[key]

    if updates:
        settings.db_set(updates, update_modified=True)


@frappe.whitelist()
def generate_manifest_from_settings():
    if not frappe.has_permission(SETTINGS_DOCTYPE, ptype="write"):
        frappe.throw(
            _("You do not have permission to update the Verto Mobile manifest."),
            frappe.PermissionError,
        )

    settings = frappe.get_single(SETTINGS_DOCTYPE)

    generated_icon_urls = _generate_pwa_icons_from_app_logo(settings)
    manifest = build_manifest_from_settings(settings, generated_icon_urls)
    manifest_json = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"

    site_manifest_url = _write_site_manifest(manifest_json)
    asset_manifest_url = _write_asset_manifest(manifest_json)

    _save_generated_values_to_settings(settings, site_manifest_url, generated_icon_urls)

    frappe.clear_cache(doctype=SETTINGS_DOCTYPE)

    return {
        "manifest": manifest,
        "manifest_url": site_manifest_url,
        "asset_manifest_url": asset_manifest_url,
        "generated_icons": generated_icon_urls,
        "written_files": [
            site_manifest_url,
            asset_manifest_url,
            *generated_icon_urls.values(),
        ],
    }


@frappe.whitelist(allow_guest=True)
def get_pwa_metadata():
    try:
        settings = frappe.get_cached_doc(SETTINGS_DOCTYPE)
    except Exception:
        settings = None

    if not settings:
        return {
            "app_name": DEFAULT_APP_NAME,
            "short_name": DEFAULT_SHORT_NAME,
            "description": _build_manifest_description(DEFAULT_APP_NAME),
            "manifest_url": SITE_MANIFEST_PUBLIC_URL,
            "apple_touch_icon": _generated_icon_url("apple_touch_icon", cache_bust=False),
            "icon": _generated_icon_url("icon_192", cache_bust=False),
            "theme_color": DEFAULT_THEME_COLOR,
            "background_color": DEFAULT_BACKGROUND_COLOR,
        }

    app_name = _get_app_name(settings)
    short_name = _get_short_name(settings, app_name)
    icon_urls = _get_existing_or_generated_icon_urls(settings)

    manifest_url = _get_first(
        settings,
        ["pwa_manifest_url", "manifest_url"],
        SITE_MANIFEST_PUBLIC_URL,
    )

    return {
        "app_name": app_name,
        "short_name": short_name,
        "description": _build_manifest_description(app_name),
        "manifest_url": _clean_path_or_url(manifest_url) or SITE_MANIFEST_PUBLIC_URL,
        "apple_touch_icon": icon_urls["apple_touch_icon"],
        "icon": icon_urls["icon_192"],
        "theme_color": _normalise_color(
            _get_first(settings, ["pwa_theme_color", "theme_color"], DEFAULT_THEME_COLOR),
            DEFAULT_THEME_COLOR,
        ),
        "background_color": _normalise_color(
            _get_first(settings, ["pwa_background_color", "background_color"], DEFAULT_BACKGROUND_COLOR),
            DEFAULT_BACKGROUND_COLOR,
        ),
    }
