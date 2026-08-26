# Copyright (c) 2026, Webwire and Contributors
# See license.txt

import base64
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from verto.api.mobile.push_notifications import _get_vapid_config
from verto.runtime_config import (
    VAPID_PRIVATE_KEY_CONFIG,
    VAPID_PUBLIC_KEY_CONFIG,
    apply_runtime_config,
    ensure_push_configuration,
    get_push_settings_config,
)


def _decode_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


class TestVertoMobileSettings(FrappeTestCase):
    def test_vapid_keys_are_generated_and_available_at_runtime(self):
        result = ensure_push_configuration(force=True)

        self.assertTrue(result["configured"])
        self.assertTrue(result["created"])

        config = get_push_settings_config()
        self.assertTrue(config["configured"])
        self.assertTrue(config["public_key"])
        self.assertTrue(config["private_key"])

        public_raw = _decode_base64url(config["public_key"])
        self.assertEqual(len(public_raw), 65)
        self.assertEqual(public_raw[0], 4)

        apply_runtime_config()
        self.assertEqual(frappe.conf.get(VAPID_PUBLIC_KEY_CONFIG), config["public_key"])
        self.assertEqual(frappe.conf.get(VAPID_PRIVATE_KEY_CONFIG), config["private_key"])

    def test_push_config_prefers_mobile_settings_over_legacy_values(self):
        settings_config = {
            "enabled": True,
            "public_key": "settings-public",
            "private_key": "settings-private",
            "subject": "mailto:settings@example.com",
            "configured": True,
        }

        with (
            patch(
                "verto.runtime_config.get_push_settings_config",
                return_value=settings_config,
            ),
            patch(
                "verto.api.mobile.push_notifications._site_config_value",
                return_value="legacy-value",
            ) as legacy_value,
        ):
            config = _get_vapid_config()

        self.assertTrue(config["configured"])
        self.assertEqual(config["public_key"], "settings-public")
        self.assertEqual(config["private_key"], "settings-private")
        self.assertEqual(config["subject"], "mailto:settings@example.com")
        legacy_value.assert_not_called()

    def test_disabled_mobile_setting_does_not_fall_back_to_legacy_values(self):
        settings_config = {
            "enabled": False,
            "public_key": "settings-public",
            "private_key": "settings-private",
            "subject": "mailto:settings@example.com",
            "configured": False,
        }

        with (
            patch(
                "verto.runtime_config.get_push_settings_config",
                return_value=settings_config,
            ),
            patch(
                "verto.api.mobile.push_notifications._site_config_value",
                return_value="legacy-value",
            ) as legacy_value,
        ):
            config = _get_vapid_config()

        self.assertFalse(config["configured"])
        self.assertEqual(config["public_key"], "")
        self.assertEqual(config["private_key"], "")
        self.assertEqual(config["subject"], "mailto:settings@example.com")
        legacy_value.assert_not_called()

    def test_empty_settings_can_use_legacy_values_until_migrated(self):
        settings_config = {
            "enabled": True,
            "public_key": "",
            "private_key": "",
            "subject": "mailto:settings@example.com",
            "configured": False,
        }
        legacy = {
            VAPID_PUBLIC_KEY_CONFIG: "legacy-public",
            VAPID_PRIVATE_KEY_CONFIG: "legacy-private",
        }

        def legacy_value(key, default=""):
            return legacy.get(key, default)

        with (
            patch(
                "verto.runtime_config.get_push_settings_config",
                return_value=settings_config,
            ),
            patch(
                "verto.api.mobile.push_notifications._site_config_value",
                side_effect=legacy_value,
            ),
        ):
            config = _get_vapid_config()

        self.assertTrue(config["configured"])
        self.assertEqual(config["public_key"], "legacy-public")
        self.assertEqual(config["private_key"], "legacy-private")

    def test_setup_is_idempotent(self):
        from verto.install import ensure_verto_setup

        first = ensure_verto_setup()
        second = ensure_verto_setup()

        self.assertIn("push_notifications", first)
        self.assertIn("pwa_manifest", first)
        self.assertIn("optional_integrations", first)
        self.assertTrue(second["push_notifications"])
