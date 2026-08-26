from __future__ import annotations

import base64
from datetime import datetime

import frappe
from frappe import _


SETTINGS_DOCTYPE = "Verto Mobile Settings"

VAPID_PUBLIC_KEY_CONFIG = "verto_push_vapid_public_key"
VAPID_PRIVATE_KEY_CONFIG = "verto_push_vapid_private_key"
VAPID_SUBJECT_CONFIG = "verto_push_vapid_subject"
DEFAULT_VAPID_SUBJECT = "mailto:support@webwire.com.au"


def _clean(value) -> str:
    return str(value or "").strip()


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _get_settings():
    if not frappe.db or not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        return None

    return frappe.get_single(SETTINGS_DOCTYPE)


def _get_private_key(settings) -> str:
    if not settings or not settings.meta.has_field("vapid_private_key"):
        return ""

    try:
        return _clean(settings.get_password("vapid_private_key", raise_exception=False))
    except Exception:
        return _clean(settings.get("vapid_private_key"))


def _normalise_subject(value: str | None) -> str:
    subject = _clean(value) or DEFAULT_VAPID_SUBJECT

    if subject.startswith(("mailto:", "https://", "http://")):
        return subject

    if "@" in subject:
        return f"mailto:{subject}"

    return DEFAULT_VAPID_SUBJECT


def get_push_settings_config() -> dict:
    settings = _get_settings()

    if not settings:
        return {
            "enabled": False,
            "public_key": "",
            "private_key": "",
            "subject": DEFAULT_VAPID_SUBJECT,
            "configured": False,
        }

    enabled = True
    if settings.meta.has_field("push_notifications_enabled"):
        enabled = bool(settings.get("push_notifications_enabled"))

    public_key = (
        _clean(settings.get("vapid_public_key"))
        if settings.meta.has_field("vapid_public_key")
        else ""
    )
    private_key = _get_private_key(settings)
    subject = _normalise_subject(
        settings.get("vapid_subject")
        if settings.meta.has_field("vapid_subject")
        else DEFAULT_VAPID_SUBJECT
    )

    return {
        "enabled": enabled,
        "public_key": public_key,
        "private_key": private_key,
        "subject": subject,
        "configured": bool(enabled and public_key and private_key),
    }


def apply_runtime_config(**kwargs):
    """Expose Verto settings through frappe.conf for legacy consumers.

    Push notification code historically read VAPID values from site_config.json.
    Keeping these runtime aliases lets existing code continue to work while the
    source of truth moves into Verto Mobile Settings.
    """
    try:
        config = get_push_settings_config()
    except Exception:
        return

    frappe.local.conf[VAPID_PUBLIC_KEY_CONFIG] = config["public_key"] if config["enabled"] else ""
    frappe.local.conf[VAPID_PRIVATE_KEY_CONFIG] = config["private_key"] if config["enabled"] else ""
    frappe.local.conf[VAPID_SUBJECT_CONFIG] = config["subject"]


def _legacy_site_config() -> dict:
    return {
        "public_key": _clean(getattr(frappe.conf, VAPID_PUBLIC_KEY_CONFIG, "")),
        "private_key": _clean(getattr(frappe.conf, VAPID_PRIVATE_KEY_CONFIG, "")),
        "subject": _normalise_subject(getattr(frappe.conf, VAPID_SUBJECT_CONFIG, DEFAULT_VAPID_SUBJECT)),
    }


def _generate_vapid_keypair() -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    private_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )

    return _base64url(public_raw), _base64url(private_der)


def ensure_push_configuration(force: bool = False) -> dict:
    """Ensure a site has a usable VAPID keypair in Verto Mobile Settings.

    Existing site_config values are migrated first. New sites get a generated
    keypair automatically. Repeated calls are safe unless force=True.
    """
    settings = _get_settings()

    if not settings:
        return {"configured": False, "created": False, "migrated": False}

    required_fields = {
        "push_notifications_enabled",
        "vapid_public_key",
        "vapid_private_key",
        "vapid_subject",
    }
    if not all(settings.meta.has_field(fieldname) for fieldname in required_fields):
        return {"configured": False, "created": False, "migrated": False}

    current_public = _clean(settings.get("vapid_public_key"))
    current_private = _get_private_key(settings)
    current_subject = _normalise_subject(settings.get("vapid_subject"))

    if current_public and current_private and not force:
        apply_runtime_config()
        return {"configured": True, "created": False, "migrated": False}

    legacy = _legacy_site_config()
    migrated = False

    if not force and legacy["public_key"] and legacy["private_key"]:
        public_key = legacy["public_key"]
        private_key = legacy["private_key"]
        subject = legacy["subject"]
        migrated = True
    else:
        public_key, private_key = _generate_vapid_keypair()
        subject = current_subject or DEFAULT_VAPID_SUBJECT

    settings.set("push_notifications_enabled", 1)
    settings.set("vapid_public_key", public_key)
    settings.set("vapid_private_key", private_key)
    settings.set("vapid_subject", subject)

    if settings.meta.has_field("vapid_generated_on"):
        settings.set("vapid_generated_on", datetime.now())

    settings.save(ignore_permissions=True)
    frappe.clear_cache(doctype=SETTINGS_DOCTYPE)
    apply_runtime_config()

    return {
        "configured": True,
        "created": not migrated,
        "migrated": migrated,
        "public_key": public_key,
        "subject": subject,
    }


@frappe.whitelist()
def generate_vapid_keys(force: int = 0):
    if not frappe.has_permission(SETTINGS_DOCTYPE, ptype="write"):
        frappe.throw(_("You do not have permission to configure Verto push notifications."), frappe.PermissionError)

    force = bool(int(force or 0))
    return ensure_push_configuration(force=force)
