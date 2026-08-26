# Copyright (c) 2026, Webwire and Contributors
# See license.txt

import base64

import frappe
from frappe.tests.utils import FrappeTestCase

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

    def test_setup_is_idempotent(self):
        from verto.install import ensure_verto_setup

        first = ensure_verto_setup()
        second = ensure_verto_setup()

        self.assertIn("push_notifications", first)
        self.assertIn("pwa_manifest", first)
        self.assertIn("optional_integrations", first)
        self.assertTrue(second["push_notifications"])
