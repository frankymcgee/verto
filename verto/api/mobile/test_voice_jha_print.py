"""Runtime print branding, safe rendering and settings persistence."""

import base64
from io import BytesIO
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from bs4 import BeautifulSoup
from frappe.tests import IntegrationTestCase
from PIL import Image

from verto.api.mobile import voice_jha_print as printing


class TestJhaPrintBranding(TestCase):
    def setUp(self):
        self.settings = frappe._dict()
        self.enterContext(patch.object(frappe, "get_cached_doc", return_value=self.settings))

    def render(self, steps=3, resources=True, hazards=None):
        doc = frappe._dict(
            name="JHA-PRINT-TEST", revision=1, jha_status="Signed", creation=None,
            participants=[], hazards_and_controls=hazards or [],
            work_steps=[frappe._dict(sequence=i + 1, activity="Service pump") for i in range(steps)],
        )
        supporting_records = [frappe._dict(
            work_step=1, step_activity="Service pump", kind="Permit", reference="PERMIT-1",
            effective_status="Confirmed", details="Pump access", annotations=[],
            recorder_name="Supervisor", recorded_at="2026-10-21 08:00:00",
        )] if resources else []
        return frappe.render_template(printing.PRINT_HTML, {
            "doc": doc,
            "jha_workpack_qr": lambda doc: {"url": "/verto-mobile/jha/JHA-PRINT-TEST?revision=1", "image": "data:image/png;base64,AA=="},
            "jha_print_field_checks": lambda doc: [],
            "jha_print_resources": lambda doc: supporting_records,
        })

    def test_blank_settings_preserve_the_existing_branding(self):
        branding = printing.jha_print_branding()
        self.assertEqual(branding["company_name"], "Mine Site Support")
        self.assertEqual(branding["header_text"], "MINE SITE SUPPORT")
        self.assertEqual(branding["font_family"], "Arial, Helvetica, sans-serif")
        self.assertEqual(branding["primary_colour"], "#f47a20")
        self.assertEqual(branding["critical_risk_colour"], "#ffd34d")
        self.assertEqual(branding["logo"], "")

    def test_custom_branding_renders_on_every_page_and_keeps_the_revision_qr(self):
        self.settings.update(jha_print_company_name="Webwire Pty Ltd", jha_print_font="Georgia",
                             jha_print_primary_colour="#0055aa", jha_print_heading_text_colour="#eeeeee",
                             jha_print_text_colour="#123456", jha_print_border_colour="#654321",
                             jha_print_critical_risk_colour="#aa3300", jha_print_critical_risk_text_colour="#fedcba",
                             jha_print_critical_risk_border_colour="#abcdef")
        html = self.render()
        self.assertIn("<td>Webwire Pty Ltd</td>", html)
        self.assertEqual(html.count('<div class="brand">WEBWIRE PTY LTD</div>'), 7)
        self.assertNotIn("MINE SITE SUPPORT", html)
        self.assertIn("font-family: Georgia, 'Times New Roman', serif;", html)
        for colour in ("#0055aa", "#eeeeee", "#123456", "#654321", "#aa3300", "#fedcba", "#abcdef"):
            self.assertIn(colour, html)
        self.assertIn("/verto-mobile/jha/JHA-PRINT-TEST?revision=1", html)
        self.assertIn("JHA-PRINT-TEST &nbsp; | &nbsp; Rev 1", html)

    def test_custom_header_text_is_escaped_on_the_empty_matrix_page_too(self):
        self.settings.update(jha_print_company_name='ACME <script>alert(1)</script>',
                             jha_print_header_text='A & B <img src=x onerror="alert(1)">')
        html = self.render(steps=0, resources=False)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("ACME &lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertEqual(html.count("A &amp; B &lt;img"), 5)

    def test_settings_secrets_are_not_exposed_to_print_users(self):
        self.settings.update(vapid_private_key="secret-private-key", ai_photo_analysis_api_key="secret-api-key")
        branding = printing.jha_print_branding()
        self.assertNotIn("secret", str(branding))
        self.assertNotIn("vapid_private_key", branding)

    def test_invalid_css_values_are_rejected_and_old_invalid_values_fall_back(self):
        for key, value in (("jha_print_primary_colour", "red; } body { display: none"),
                           ("jha_print_text_colour", "</style><script>alert(1)</script>"),
                           ("jha_print_critical_risk_colour", "url(https://example.test)"),
                           ("jha_print_font", "Arial; background: url(https://example.test)")):
            with self.subTest(key=key):
                self.settings.clear()
                self.settings[key] = value
                with self.assertRaises(frappe.ValidationError):
                    printing.validate_jha_print_settings(self.settings)
                branding = printing.jha_print_branding()
                self.assertNotIn(value, str(branding))
        self.settings.clear()
        self.settings.jha_print_primary_colour = " #ABC "
        printing.validate_jha_print_settings(self.settings)
        self.assertEqual(printing.jha_print_branding()["primary_colour"], "#ABC")

    def test_all_available_fonts_render_as_css_without_html_entities(self):
        for font, family in printing.PRINT_FONTS.items():
            with self.subTest(font=font):
                self.settings.jha_print_font = font
                printing.validate_jha_print_settings(self.settings)
                self.assertIn("font-family: " + family + ";", self.render(steps=0, resources=False))

    def test_private_logo_is_embedded_as_image_data_on_every_page(self):
        content = BytesIO()
        Image.new("RGBA", (40, 20), (0, 80, 160, 128)).save(content, format="PNG")
        file = Mock()
        file.get_content.return_value = content.getvalue()
        self.settings.jha_print_logo = "/private/files/company-logo.png"
        with patch.object(frappe.db, "get_value", return_value="LOGO-FILE") as lookup, \
             patch.object(frappe, "get_doc", return_value=file):
            html = self.render()
            logo = printing.jha_print_branding()["logo"]
        self.assertEqual(html.count('class="brand-logo"'), 7)
        self.assertNotIn('class="brand"', html)
        for header in BeautifulSoup(html, "html.parser").select(".page-title"):
            column = header.select_one(".header-branding")
            self.assertTrue(column.select_one(".brand-logo"))
            self.assertTrue(column.select_one(".brand-logo").find_next_sibling("a", class_="workpack-qr"))
        self.assertNotIn("/private/files/", html)
        with Image.open(BytesIO(base64.b64decode(logo.split(",", 1)[1]))) as decoded:
            self.assertEqual(decoded.size, (40, 20))
            self.assertEqual(decoded.mode, "RGBA")
        lookup.assert_called_with("File", {"file_url": self.settings.jha_print_logo}, "name")

    def test_text_fallback_and_revision_qr_share_the_right_column_on_every_page(self):
        self.settings.jha_print_header_text = "MSS"
        for header in BeautifulSoup(self.render(), "html.parser").select(".page-title"):
            column = header.select_one(".header-branding")
            self.assertTrue(header.select_one(".header-title"))
            self.assertEqual(column.select_one(".brand").text, "MSS")
            self.assertTrue(column.select_one(".brand").find_next_sibling("a", class_="workpack-qr"))
            self.assertIsNone(column.select_one(".brand-logo"))

    def test_all_critical_risks_and_controls_are_complete_including_more_than_eight(self):
        risks = [frappe._dict(critical_risk=1, work_step_sequence=1,
            hazard_or_energy_source=f"Risk {i}: unexpected brake movement and stored energy while removing guarding for inspection.",
            critical_control=f"Control {i}: isolate the winch and brake, lock onto the isolation permit and verify zero energy before removing guarding.") for i in range(10)]
        soup = BeautifulSoup(self.render(hazards=risks), "html.parser")
        summaries = soup.select(".risk-chip")
        self.assertEqual(len(summaries), len(risks))
        for summary, risk in zip(summaries, risks):
            self.assertIn(risk.hazard_or_energy_source, summary.text)
            self.assertIn(risk.critical_control, summary.text)
            self.assertNotIn("...", summary.text)
        pages = soup.select(".pack-page")
        self.assertEqual(len(pages), 9)
        for i, page in enumerate(pages):
            self.assertIn(f"Page {i + 1} of 9", page.select_one(".page-footer").text)

    def test_missing_or_invalid_logo_keeps_the_print_readable(self):
        self.settings.jha_print_logo = "/files/missing.png"
        with patch.object(frappe.db, "get_value", return_value=None):
            self.assertEqual(printing.jha_print_branding()["logo"], "")
            self.assertIn("MINE SITE SUPPORT", self.render())
        file = Mock()
        file.get_content.return_value = b"not an image"
        with patch.object(frappe.db, "get_value", return_value="LOGO-FILE"), \
             patch.object(frappe, "get_doc", return_value=file):
            self.assertEqual(printing.jha_print_branding()["logo"], "")
        with patch.object(frappe.db, "get_value", return_value="LOGO-FILE"), \
             patch.object(frappe, "get_doc", side_effect=frappe.DoesNotExistError):
            self.assertEqual(printing.jha_print_branding()["logo"], "")

    def test_logo_setting_cannot_make_printing_fetch_external_images(self):
        for logo in ("https://example.test/logo.png", "//example.test/logo.png", "data:image/svg+xml,test", "/files/logo.svg"):
            with self.subTest(logo=logo):
                self.settings.jha_print_logo = logo
                with self.assertRaises(frappe.ValidationError):
                    printing.validate_jha_print_settings(self.settings)
                with patch.object(frappe.db, "get_value") as lookup:
                    self.assertEqual(printing.jha_print_branding()["logo"], "")
                    lookup.assert_not_called()


class IntegrationTestJhaPrintSettings(IntegrationTestCase):
    def test_saved_branding_refreshes_immediately_and_survives_format_setup(self):
        self.addCleanup(frappe.clear_document_cache, "Verto Mobile Settings", "Verto Mobile Settings")
        settings = frappe.get_doc("Verto Mobile Settings")
        with patch("verto.install.refresh_mobile_settings_configuration"):
            settings.jha_print_company_name = "First Print Company"
            settings.jha_print_header_text = ""
            settings.jha_print_font = "Verdana"
            settings.jha_print_primary_colour = "#224466"
            settings.save(ignore_permissions=True)
            self.assertEqual(printing.jha_print_branding()["header_text"], "FIRST PRINT COMPANY")
            printing.ensure_jha_print_format()
            settings.reload()
            self.assertEqual(settings.jha_print_primary_colour, "#224466")
            settings.jha_print_company_name = "Updated Print Company"
            settings.save(ignore_permissions=True)
            self.assertEqual(printing.jha_print_branding()["company_name"], "Updated Print Company")
            settings.jha_print_text_colour = "red; display:none"
            with self.assertRaises(frappe.ValidationError):
                settings.save(ignore_permissions=True)
