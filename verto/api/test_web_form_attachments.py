"""Public browser Web Form submissions use real Frappe File validation."""

import base64
import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from verto.api import web_form_attachments


class TestWebFormAttachments(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        suffix = frappe.generate_hash(length=8)
        self.form = frappe.get_doc({
            "doctype": "Web Form", "title": f"Test field evidence {suffix}",
            "route": f"test-field-evidence-{suffix}", "doc_type": "Field Interaction",
            "published": 1, "login_required": 0, "allow_incomplete": 1,
            "web_form_fields": [{"fieldname": "supervisor", "fieldtype": "Data", "label": "Supervisor"}],
        }).insert(ignore_permissions=True)
        self.forms = [self.form.name]
        settings = {
            "allow_guests_to_upload_files": 1,
            "allowed_doctypes_for_guest_uploads": "Field Interaction\nNote",
            "allowed_file_extensions": "TXT\nCSV",
        }
        original = frappe.get_system_settings
        self.enterContext(patch.object(frappe, "get_system_settings",
            side_effect=lambda key=None: settings[key] if key in settings else original(key)))
        self.names = []
        frappe.set_user("Guest")

    def tearDown(self):
        frappe.set_user("Administrator")
        for doctype, name in self.names:
            frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
        for name in self.forms:
            frappe.delete_doc("Web Form", name, ignore_permissions=True, force=True)
        super().tearDown()

    def submit(self, attachments, **values):
        data = {"supervisor": "Synthetic test supervisor", **values,
            web_form_attachments.PAYLOAD_KEY: attachments}
        doc = web_form_attachments.accept(self.form.name, json.dumps(data))
        self.names.append((doc.doctype, doc.name))
        return doc

    @staticmethod
    def file(name, content):
        return {"file_name": name, "content": base64.b64encode(content).decode()}

    def test_guest_browser_submission_links_every_file_privately_to_the_new_interaction(self):
        doc = self.submit([self.file("observation.txt", b"Synthetic observation"),
            self.file("measurements.csv", b"Control,Status\nIsolation,Verified")])
        files = frappe.get_all("File", filters={"attached_to_doctype": "Field Interaction",
            "attached_to_name": doc.name}, fields=["name", "is_private", "file_url"])
        self.assertEqual(len(files), 2)
        for file in files:
            self.assertTrue(file.is_private)
            self.assertTrue(file.file_url.startswith("/private/files/"))
            self.assertFalse(frappe.has_permission("File", "read", doc=file.name, user="Guest"))
        self.assertEqual(doc.owner, "Guest")
        self.assertNotIn(web_form_attachments.PAYLOAD_KEY, doc.as_dict())
        frappe.set_user("Administrator")
        for file in files:
            self.assertTrue(frappe.has_permission("File", "read", doc=file.name))

    def test_a_guest_cannot_use_a_known_record_name_to_append_evidence(self):
        doc = self.submit([self.file("first.txt", b"Initial evidence")])
        with self.assertRaises(frappe.PermissionError):
            self.submit([self.file("injected.txt", b"Other visitor")], name=doc.name)
        self.assertEqual(frappe.db.count("File", {"attached_to_doctype": "Field Interaction",
            "attached_to_name": doc.name}), 1)

    def test_invalid_uploads_do_not_insert_a_partial_field_interaction(self):
        before = frappe.db.count("Field Interaction")
        with self.assertRaises(frappe.ValidationError):
            self.submit([self.file("valid.txt", b"Valid first file"),
                self.file("invalid.html", b"<html>Not allowed</html>")])
        self.assertEqual(frappe.db.count("Field Interaction"), before)

    def test_normal_submission_without_files_still_uses_core_accept(self):
        doc = self.submit([])
        self.assertEqual(doc.supervisor, "Synthetic test supervisor")
        self.assertEqual(frappe.db.count("File", {"attached_to_doctype": "Field Interaction",
            "attached_to_name": doc.name}), 0)

    def test_the_same_uploader_supports_a_different_web_form_doctype(self):
        frappe.set_user("Administrator")
        suffix = frappe.generate_hash(length=8)
        self.form = frappe.get_doc({
            "doctype": "Web Form", "title": f"Test note evidence {suffix}",
            "route": f"test-note-evidence-{suffix}", "doc_type": "Note",
            "published": 1, "login_required": 0,
            "web_form_fields": [{"fieldname": "title", "fieldtype": "Data", "label": "Title", "reqd": 1}],
        }).insert(ignore_permissions=True)
        self.forms.append(self.form.name)
        frappe.set_user("Guest")
        doc = self.submit([self.file("note-evidence.txt", b"Synthetic note evidence")], title=f"Test upload {suffix}")
        self.assertEqual(doc.doctype, "Note")
        self.assertEqual(frappe.db.count("File", {"attached_to_doctype": "Note",
            "attached_to_name": doc.name, "is_private": 1}), 1)
