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
    "ai_photo_analysis_enabled": 0,
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
    from verto.access import ensure_access_roles_and_profiles

    results = {
        "access_profiles": ensure_access_roles_and_profiles(),
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
    settings_changed = False
    project_default_changed = _ensure_project_raven_channel_default()

    analysis_bot = _resolve_existing_photo_analysis_bot(settings)
    if analysis_bot:
        settings.set("ai_photo_analysis_bot", analysis_bot)
        settings_changed = True

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
            settings_changed = True

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
            settings_changed = True

    if settings_changed:
        settings.save(ignore_permissions=True)

    return settings_changed or project_default_changed


def _resolve_existing_photo_analysis_bot(settings) -> str:
    """Adopt the configured PERI AI bot during the settings migration.

    An explicit photo-analysis selection is never overwritten. This helper is
    intentionally best-effort so sites without a PERI bot can migrate and then
    select their nominated Raven bot in Verto Mobile Settings.
    """
    if (
        not settings.meta.has_field("ai_photo_analysis_bot")
        or settings.get("ai_photo_analysis_bot")
        or not frappe.db.exists("DocType", "Raven Bot")
    ):
        return ""

    candidates = []
    if (
        settings.meta.has_field("peri_bot_user")
        and settings.get("peri_bot_user")
        and frappe.db.exists("DocType", "Raven User")
        and frappe.get_meta("Raven User").has_field("bot")
    ):
        candidates.append(
            frappe.db.get_value("Raven User", settings.get("peri_bot_user"), "bot")
        )

    if settings.meta.has_field("peri_bot_name") and settings.get("peri_bot_name"):
        peri_bot_name = settings.get("peri_bot_name")
        candidates.append(peri_bot_name)
        if frappe.get_meta("Raven Bot").has_field("bot_name"):
            candidates.append(
                frappe.db.get_value("Raven Bot", {"bot_name": peri_bot_name}, "name")
            )

    bot_meta = frappe.get_meta("Raven Bot")
    for candidate in dict.fromkeys(candidate for candidate in candidates if candidate):
        if not frappe.db.exists("Raven Bot", candidate):
            continue
        if bot_meta.has_field("is_ai_bot") and not frappe.db.get_value(
            "Raven Bot", candidate, "is_ai_bot"
        ):
            continue
        if bot_meta.has_field("model_provider") and frappe.db.get_value(
            "Raven Bot", candidate, "model_provider"
        ) != "OpenAI":
            continue
        if bot_meta.has_field("model") and not frappe.db.get_value(
            "Raven Bot", candidate, "model"
        ):
            continue
        return candidate
    return ""


def _ensure_project_raven_channel_default() -> bool:
    """Clear legacy Project Raven defaults without touching Project data.

    The Raven channel on Project is optional. App chat defaults belong in Verto
    Mobile Settings; using one as a Project field default prevents ordinary
    Project creation when that channel does not exist yet. Clear only the legacy
    metadata values and preserve explicitly stored channels on Project records.
    """
    custom_field = "Project-custom_raven_channel"
    if not frappe.db.exists("Custom Field", custom_field):
        return False

    current_default = frappe.db.get_value("Custom Field", custom_field, "default")
    if current_default not in {"mss-general", "general"}:
        return False

    frappe.db.set_value(
        "Custom Field",
        custom_field,
        "default",
        None,
        update_modified=False,
    )
    frappe.clear_cache(doctype="Project")
    return True


def _ensure_site_pwa_manifest() -> bool:
    """Create/update the site-local PWA manifest and generated icons."""
    try:
        from verto.api.mobile.pwa_manifest import (
            _generate_pwa_icons_from_app_logo,
            _get_existing_or_generated_icon_urls,
            _save_generated_values_to_settings,
            _write_asset_manifest,
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
        site_manifest_url = _write_site_manifest(manifest_json)
        manifest_url = _write_asset_manifest(manifest_json) or site_manifest_url
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
