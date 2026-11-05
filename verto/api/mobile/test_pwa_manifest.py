"""Regression checks for site-specific Android/iOS installation metadata."""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from werkzeug.wrappers import Response

from verto.api.mobile import pwa_manifest
from verto.pwa import VertoManifestRenderer


def settings_for(name, short_name, **values):
    values.update(app_name=name, short_name=short_name)
    return SimpleNamespace(
        meta=SimpleNamespace(has_field=lambda field: field in values),
        get=values.get,
    )


class TestPwaManifest(TestCase):
    def setUp(self):
        site = tempfile.TemporaryDirectory()
        self.addCleanup(site.cleanup)
        self.site = Path(site.name)
        site_path = patch.object(
            pwa_manifest.frappe,
            "get_site_path",
            side_effect=lambda *parts: str(self.site.joinpath(*parts)),
        )
        site_path.start()
        self.addCleanup(site_path.stop)

    def render_manifest(self, settings):
        renderer = VertoManifestRenderer(pwa_manifest.DEFAULT_MANIFEST_PUBLIC_URL)
        with (
            patch.object(pwa_manifest.frappe, "get_cached_doc", return_value=settings),
            patch.object(
                renderer,
                "build_response",
                side_effect=lambda data, headers: Response(data, headers=headers),
            ),
        ):
            return renderer.render()

    def test_current_tenant_branding_is_used_on_every_request(self):
        # A shared asset or cached module-level manifest must not leak the last
        # site's branding into another site on the same bench.
        for name, short in [("Mine Site Support", "MSS"), ("Other Site", "Other")]:
            response = self.render_manifest(settings_for(name, short))
            manifest = json.loads(response.get_data(as_text=True))
            self.assertEqual(manifest["name"], name)
            self.assertEqual(manifest["short_name"], short)
            self.assertNotIn("message", manifest)
            self.assertEqual(response.mimetype, "application/manifest+json")
            self.assertIn("no-cache", response.headers["Cache-Control"])

    def test_install_identity_scope_and_required_icons_are_preserved(self):
        manifest = json.loads(
            self.render_manifest(settings_for("Mine Site Support", "MSS")).get_data(as_text=True)
        )
        self.assertEqual(manifest["id"], "/verto-mobile/")
        self.assertTrue(manifest["start_url"].startswith(manifest["scope"]))
        self.assertEqual(manifest["display"], "standalone")
        self.assertFalse(manifest["prefer_related_applications"])
        for purpose in ("any", "maskable"):
            sizes = {icon["sizes"] for icon in manifest["icons"] if icon["purpose"] == purpose}
            self.assertTrue({"192x192", "512x512"}.issubset(sizes))

    def test_old_saved_manifest_urls_cannot_restore_the_build_fallback(self):
        for legacy_url in (
            pwa_manifest.ASSET_MANIFEST_PUBLIC_URL,
            pwa_manifest.SITE_MANIFEST_PUBLIC_URL,
        ):
            settings = settings_for("Mine Site Support", "MSS", pwa_manifest_url=legacy_url)
            with patch.object(pwa_manifest.frappe, "get_cached_doc", return_value=settings):
                metadata = pwa_manifest.get_pwa_metadata()
            self.assertEqual(metadata["manifest_url"], "/verto-mobile.webmanifest")
            self.assertEqual(metadata["short_name"], "MSS")

    def test_missing_generated_icons_use_shipped_public_icons(self):
        with patch.object(pwa_manifest.frappe, "get_cached_doc", side_effect=RuntimeError):
            metadata = pwa_manifest.get_pwa_metadata()
        self.assertEqual(metadata["icon"], "/assets/verto/manifest/mss-pwa-192.png")
        self.assertEqual(metadata["apple_touch_icon"], "/assets/verto/manifest/apple-touch-icon.png")

    def test_manifest_generation_does_not_overwrite_shared_assets(self):
        settings = settings_for("Mine Site Support", "MSS")
        icons = pwa_manifest._get_existing_or_generated_icon_urls(settings)
        with (
            patch.object(pwa_manifest.frappe, "has_permission", return_value=True),
            patch.object(pwa_manifest.frappe, "get_single", return_value=settings),
            patch.object(pwa_manifest.frappe, "clear_cache"),
            patch.object(pwa_manifest, "_generate_pwa_icons_from_app_logo", return_value=icons),
            patch.object(pwa_manifest, "_write_asset_manifest") as write_shared_asset,
        ):
            result = pwa_manifest.generate_manifest_from_settings()
        self.assertEqual(result["manifest_url"], "/verto-mobile.webmanifest")
        write_shared_asset.assert_not_called()
        self.assertTrue(self.site.joinpath("public", "files", pwa_manifest.SITE_MANIFEST_FILENAME).exists())

    def test_renderer_only_handles_the_manifest_route(self):
        self.assertTrue(VertoManifestRenderer("/verto-mobile.webmanifest").can_render())
        for route in ("/verto-mobile", "/verto-mobile-sw.js", "/login"):
            self.assertFalse(VertoManifestRenderer(route).can_render())
