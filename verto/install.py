from __future__ import annotations

import frappe


SETTINGS_DOCTYPE = "Verto Mobile Settings"
DEFAULT_SETTINGS = {
    "app_name": "Verto Mobile",
    "short_name": "Verto",
    "fallback_home_route": "/",
    "planner_app_name": "Planner",
    "planner_view_default": "Month",
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
    }

    if frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        results["settings"] = _ensure_mobile_settings_defaults()
        results["pwa_manifest"] = _ensure_site_pwa_manifest()

    frappe.clear_cache()
    return results


def _ensure_mobile_settings_defaults() -> bool:
    settings = frappe.get_single(SETTINGS_DOCTYPE)
    changed = False

    for fieldname, default_value in DEFAULT_SETTINGS.items():
        if settings.meta.has_field(fieldname) and not settings.get(fieldname):
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
        from verto.api.mobile.pwa_manifest import ensure_site_manifest

        ensure_site_manifest()
        return True
    except Exception:
        frappe.log_error(
            title="Verto automatic PWA manifest setup failed",
            message=frappe.get_traceback(),
        )
        return False
