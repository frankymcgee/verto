from __future__ import annotations

import json

import frappe


SETTINGS_DOCTYPE = "Verto Mobile Settings"
DEFAULT_SETTINGS = {
    "app_name": "Verto Mobile",
    "short_name": "Verto",
    "fallback_home_route": "/",
    "planner_app_name": "Planner",
    "planner_view_default": "Month",
    "push_notifications_enabled": 1,
    "vapid_subject": "mailto:support@webwire.com.au",
}


def after_install():
    """Bring a newly-installed Verto site to a known usable baseline."""
    ensure_verto_setup()


def after_migrate():
    """Repair/re-apply safe Verto defaults after every migration.

    This function must remain idempotent because Frappe calls it repeatedly over
    the lifetime of a site.
    """
    ensure_verto_setup()


def ensure_verto_setup():
    results = {
        "settings": False,
        "integration_defaults": False,
        "pwa_manifest": False,
        "push_notifications": False,
        "optional_integrations": {},
    }

    if frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        results["settings"] = _ensure_mobile_settings_defaults()
        results["integration_defaults"] = _ensure_integration_defaults()
        results["pwa_manifest"] = _ensure_site_pwa_manifest()
        results["push_notifications"] = _ensure_push_notifications()

    results["optional_integrations"] = _ensure_optional_integrations()
    frappe.clear_cache()
    return results


def _ensure_mobile_settings_defaults() -> bool:
    settings = frappe.get_single(SETTINGS_DOCTYPE)
    changed = False

    for fieldname, default_value in DEFAULT_SETTINGS.items():
        if settings.meta.has_field(fieldname) and settings.get(fieldname) in (None, ""):
            settings.set(fieldname, default_value)
            changed = True

    if changed:
        settings.save(ignore_permissions=True)

    return changed


def _ensure_integration_defaults() -> bool:
    """Adopt safe defaults created by required apps instead of manual setup."""
    settings = frappe.get_single(SETTINGS_DOCTYPE)
    changed = False

    if (
        settings.meta.has_field("default_workspace")
        and not settings.get("default_workspace")
        and frappe.db.exists("DocType", "Raven Workspace")
    ):
        workspace = (
            frappe.db.get_value("Raven Workspace", {"workspace_name": "Raven"}, "name")
            or frappe.db.get_value("Raven Workspace", {}, "name")
        )
        if workspace:
            settings.set("default_workspace", workspace)
            changed = True

    if (
        settings.meta.has_field("default_chat_channel")
        and not settings.get("default_chat_channel")
        and frappe.db.exists("DocType", "Raven Channel")
    ):
        channel = (
            frappe.db.get_value("Raven Channel", {"name": "general"}, "name")
            or frappe.db.get_value(
                "Raven Channel",
                {"channel_name": "General", "is_direct_message": 0},
                "name",
            )
        )
        if channel:
            settings.set("default_chat_channel", channel)
            changed = True

    if changed:
        settings.save(ignore_permissions=True)

    return changed


def _ensure_site_pwa_manifest() -> bool:
    """Create/update the site-local PWA manifest and generated icons."""
    try:
        from verto.api.mobile.pwa_manifest import (
            _generate_pwa_icons_from_app_logo,
            _get_existing_or_generated_icon_urls,
            _save_generated_values_to_settings,
            _write_site_manifest,
            build_manifest_from_settings,
        )

        settings = frappe.get_single(SETTINGS_DOCTYPE)

        if settings.meta.has_field("app_logo") and settings.get("app_logo"):
            try:
                icon_urls = _generate_pwa_icons_from_app_logo(settings)
            except Exception:
                frappe.log_error(
                    title="Verto automatic PWA icon generation failed",
                    message=frappe.get_traceback(),
                )
                icon_urls = _get_existing_or_generated_icon_urls(settings)
        else:
            icon_urls = _get_existing_or_generated_icon_urls(settings)

        manifest = build_manifest_from_settings(settings, icon_urls)
        manifest_json = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        manifest_url = _write_site_manifest(manifest_json)
        _save_generated_values_to_settings(settings, manifest_url, icon_urls)
        return True
    except Exception:
        frappe.log_error(
            title="Verto automatic PWA manifest setup failed",
            message=frappe.get_traceback(),
        )
        return False


def _ensure_push_notifications() -> bool:
    """Migrate legacy VAPID config or generate keys for a new v16 site."""
    try:
        from verto.runtime_config import ensure_push_configuration

        result = ensure_push_configuration(force=False)
        return bool(result.get("configured"))
    except Exception:
        frappe.log_error(
            title="Verto automatic push notification setup failed",
            message=frappe.get_traceback(),
        )
        return False


def _ensure_optional_integrations() -> dict:
    try:
        from verto.optional_integrations import sync_optional_customizations

        return sync_optional_customizations()
    except Exception:
        frappe.log_error(
            title="Verto optional integration setup failed",
            message=frappe.get_traceback(),
        )
        return {}


def refresh_mobile_settings_configuration(doc=None, method=None):
    """Keep runtime/PWA configuration aligned whenever settings are saved."""
    _ensure_site_pwa_manifest()

    try:
        from verto.runtime_config import apply_runtime_config

        apply_runtime_config()
    except Exception:
        frappe.log_error(
            title="Verto runtime configuration refresh failed",
            message=frappe.get_traceback(),
        )
