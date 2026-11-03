"""Exercise upload boundaries without requiring a running Frappe site."""

import base64
import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class ValidationError(Exception):
    pass


def load_api():
    frappe = ModuleType("frappe")
    frappe._ = lambda message: message
    frappe.whitelist = lambda **kwargs: lambda function: function
    frappe.parse_json = json.loads
    frappe.session = SimpleNamespace(user="Guest")
    frappe.PermissionError = PermissionError
    frappe.ValidationError = ValidationError

    def throw(message, exc=ValidationError):
        raise exc(message)

    frappe.throw = throw
    frappe.get_doc = Mock()
    frappe.get_meta = Mock(return_value=SimpleNamespace(max_attachments=0))
    frappe.get_system_settings = Mock()
    file_api = ModuleType("frappe.core.api.file")
    file_api.get_max_file_size = lambda: 10 * 1024 * 1024
    limiter = ModuleType("frappe.rate_limiter")
    limiter.rate_limit = lambda **kwargs: lambda function: function
    utils = ModuleType("frappe.utils")
    utils.cint = lambda value: int(value or 0)
    modules = {"frappe": frappe, "frappe.core.api.file": file_api,
        "frappe.rate_limiter": limiter, "frappe.utils": utils}
    spec = importlib.util.spec_from_file_location("upload_api_under_test",
        Path(__file__).parents[1] / "verto/api/web_form_attachments.py")
    api = importlib.util.module_from_spec(spec)
    with patch.dict("sys.modules", modules):
        spec.loader.exec_module(api)
    return api, frappe


def attachment(name="evidence.txt", content=b"Observation"):
    return {"file_name": name, "content": base64.b64encode(content).decode()}


class TestPublicWebFormAttachments(unittest.TestCase):
    def setUp(self):
        self.api, self.frappe = load_api()
        self.settings = {"allow_guests_to_upload_files": 1,
            "allowed_doctypes_for_guest_uploads": "Field Interaction"}
        self.frappe.get_system_settings.side_effect = self.settings.get
        self.form = SimpleNamespace(doc_type="Field Interaction", login_required=0,
            anonymous=0, max_attachment_size=0, raise_if_unpublished=Mock(),
            get_web_form_request=Mock())
        self.doc = SimpleNamespace(doctype="Field Interaction", name="FI-NEW")
        self.file = SimpleNamespace(insert=Mock())
        self.frappe.get_doc.side_effect = lambda *args: self.file if isinstance(args[0], dict) else self.form
        self.api._accept_web_form = Mock(return_value=self.doc)

    def submit(self, files=None, **values):
        values[self.api.PAYLOAD_KEY] = files if files is not None else [attachment()]
        return self.api.accept("public-field-interaction", json.dumps(values), "request-key")

    def test_files_are_saved_privately_only_after_core_accept_authorizes_the_new_record(self):
        order = []
        self.api._accept_web_form.side_effect = lambda *args: order.append("accept") or self.doc
        self.file.insert.side_effect = lambda **kwargs: order.append("file")
        self.assertIs(self.submit([attachment(), attachment("notes.csv", b"A,B")], supervisor="Test"), self.doc)
        self.assertEqual(order, ["accept", "file", "file"])
        self.assertEqual(json.loads(self.api._accept_web_form.call_args.args[1]), {"supervisor": "Test"})
        self.assertEqual(self.api._accept_web_form.call_args.args[2], "request-key")
        payloads = [call.args[0] for call in self.frappe.get_doc.call_args_list if isinstance(call.args[0], dict)]
        self.assertEqual(len(payloads), 2)
        for payload in payloads:
            self.assertEqual(payload["attached_to_name"], "FI-NEW")
            self.assertEqual(payload["attached_to_doctype"], "Field Interaction")
            self.assertEqual(payload["is_private"], 1)
            self.assertIsInstance(payload["content"], bytes)
            self.assertNotIn("file_url", payload)
        self.file.insert.assert_called_with(ignore_permissions=True)

    def test_other_web_forms_and_existing_records_without_new_files_delegate_unchanged(self):
        self.api.accept("other-form", '{"name":"existing","value":1}')
        self.api._accept_web_form.assert_called_once_with("other-form", '{"name": "existing", "value": 1}', None)
        self.frappe.get_doc.assert_not_called()

    def test_guest_owner_does_not_authorize_appending_to_existing_records(self):
        with self.assertRaises(PermissionError):
            self.submit(name="FI-EXISTING")
        self.api._accept_web_form.assert_not_called()
        self.file.insert.assert_not_called()

    def test_guest_setting_and_doctype_allowlist_are_enforced_for_direct_api_calls(self):
        for settings in ({"allow_guests_to_upload_files": 0},
                         {"allowed_doctypes_for_guest_uploads": "Job Applicant"}):
            with self.subTest(settings=settings), patch.dict(self.settings, settings):
                with self.assertRaises(PermissionError):
                    self.submit()
        self.api._accept_web_form.assert_not_called()

    def test_anonymous_forms_obey_guest_upload_settings_even_for_logged_in_visitors(self):
        self.frappe.session.user = "worker@example.test"
        self.form.anonymous = 1
        self.settings["allow_guests_to_upload_files"] = 0
        with self.assertRaises(PermissionError):
            self.submit()

    def test_publication_login_request_key_and_doctype_gates_cannot_be_skipped(self):
        for changes in ({"doc_type": "User"}, {"login_required": 1}):
            with self.subTest(changes=changes), patch.object(self.api, "_get_form", wraps=self.api._get_form):
                original = {key: getattr(self.form, key) for key in changes}
                self.form.__dict__.update(changes)
                with self.assertRaises(PermissionError):
                    self.submit()
                self.form.__dict__.update(original)
        for method in (self.form.raise_if_unpublished, self.form.get_web_form_request):
            method.side_effect = PermissionError("Not permitted")
            with self.assertRaises(PermissionError):
                self.submit()
            method.side_effect = None
        self.api._accept_web_form.assert_not_called()

    def test_core_validation_failure_never_creates_files_and_file_failure_propagates(self):
        self.api._accept_web_form.side_effect = ValidationError("Mandatory field missing")
        with self.assertRaises(ValidationError):
            self.submit()
        self.file.insert.assert_not_called()
        self.api._accept_web_form.side_effect = None
        self.file.insert.side_effect = ValidationError("File rejected")
        with self.assertRaisesRegex(ValidationError, "File rejected"):
            self.submit()

    def test_invalid_payloads_and_existing_file_urls_never_reach_core_accept(self):
        invalid = [None, {}, "url", [{"file_url": "/private/files/other.txt"}],
            [attachment("../evidence.txt")], [attachment("C:\\evidence.txt")],
            [attachment("bad\x00.txt")], [attachment("payload.html")],
            [attachment(content=b"")], [{"file_name": "evidence.txt", "content": "!!!"}],
            [{"file_name": "evidence.txt", "content": "é"}], [attachment()] * 11]
        for files in invalid:
            with self.subTest(files=str(files)[:100]), self.assertRaises(ValidationError):
                self.api.accept("form", json.dumps({self.api.PAYLOAD_KEY: files}))
        self.api._accept_web_form.assert_not_called()

    def test_file_total_and_count_limits_are_checked_on_decoded_content(self):
        options = {"max_files": 2, "max_file_bytes": 4, "max_total_bytes": 5,
            "allowed_extensions": ["txt"]}
        for files in ([attachment(content=b"12345")],
                      [attachment(content=b"123"), attachment(content=b"456")],
                      [attachment(content=b"1")] * 3):
            with self.subTest(files=files), self.assertRaises(ValidationError):
                self.api._decode_attachments(files, options)
        self.assertEqual(self.api._decode_attachments([attachment(content=b"1234")], options), [("evidence.txt", b"1234")])

    def test_options_use_stricter_site_form_and_doctype_limits(self):
        self.form.max_attachment_size = 2
        self.frappe.get_meta.return_value.max_attachments = 3
        self.settings["allowed_file_extensions"] = "PNG\nPDF\nHTML"
        options = self.api.get_upload_options("form", "request-key")
        self.assertEqual(options["max_file_bytes"], 2 * 1024 * 1024)
        self.assertEqual(options["max_files"], 3)
        self.assertEqual(options["allowed_extensions"], ["pdf", "png"])
        self.form.get_web_form_request.assert_called_with("request-key", allow_used=True)
        with patch.object(self.api, "get_max_file_size", return_value=1024):
            self.assertEqual(self.api._options(self.form)["max_file_bytes"], 1024)


if __name__ == "__main__":
    unittest.main()
