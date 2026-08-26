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
        "pwa_manifest": False,
        "push_notifications": False,
    }

    if frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        results["settings"] = _ensure_mobile_settings_defaults()
        results["pwa_manifest"] = _ensure_site_pwa_manifest()
        results["push_notifications"] = _ensure_push_notifications()

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


def _ensure_site_pwa_manifest() -> bool:
    """Create/update the site-local PWA manifest without requiring an app logo.

    The manual Generate PWA Manifest action can still create client-specific
    icon sizes later. Fresh installs always receive a valid manifest using the
    packaged Verto fallback icons.
    """
    try:
        from verto.api.mobile.pwa_manifest import (
            _get_existing_or_generated_icon_urls,
            _save_generated_values_to_settings,
            _write_site_manifest,
            build_manifest_from_settings,
        )

        settings = frappe.get_single(SETTINGS_DOCTYPE)
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
