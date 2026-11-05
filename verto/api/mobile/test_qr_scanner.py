from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from verto.api.mobile import qr_scanner as qr


class TestQrDocumentResolver(TestCase):
    def setUp(self):
        self.enterContext(patch.object(frappe, "session", SimpleNamespace(user="reader@example.test")))
        self.enterContext(patch.object(frappe.local, "response_headers", {}, create=True))
        self.enterContext(patch.object(frappe, "get_all", return_value=["Take 5", "Task", "Digital Job Hazard Analysis"]))
        self.doc = Mock(name="document")
        self.doc.name = "DOC/001"
        self.doc.get.return_value = 3
        self.enterContext(patch.object(frappe, "get_doc", return_value=self.doc))
        self.enterContext(patch.object(qr, "_mobile_forms", return_value={"take-5": "Take 5"}))

    def test_mobile_forms_use_the_enabled_mapping_and_normal_read_permissions(self):
        result = qr.resolve_document("take-5", "DOC/001")
        self.assertEqual(result, {"kind": "mobile", "url": "/verto-mobile/edit/take-5/DOC%2F001"})
        self.doc.check_permission.assert_called_once_with("read")

    def test_other_readable_documents_open_in_the_desk_drawer(self):
        self.assertEqual(qr.resolve_document("Task", "DOC/001"), {"kind": "desk", "url": "/app/task/DOC%2F001"})

    def test_jha_links_keep_the_printed_revision_and_use_the_live_workpack_screen(self):
        self.assertEqual(qr.resolve_document("digital-job-hazard-analysis", "DOC/001", "2")["url"], "/verto-mobile/jha/DOC%2F001?revision=2")
        self.assertEqual(qr.resolve_document("Digital Job Hazard Analysis", "DOC/001")["url"], "/verto-mobile/jha/DOC%2F001?revision=3")

    def test_read_denial_is_not_bypassed_by_qr_scanning(self):
        self.doc.check_permission.side_effect = frappe.PermissionError
        with self.assertRaises(frappe.PermissionError): qr.resolve_document("task", "DOC/001")

    def test_guest_and_unknown_document_types_are_rejected(self):
        with self.assertRaises(frappe.DoesNotExistError): qr.resolve_document("unknown", "DOC/001")
        frappe.session.user = "Guest"
        with self.assertRaises(frappe.PermissionError): qr.resolve_document("task", "DOC/001")

    def test_invalid_revision_and_names_are_rejected(self):
        for version in ["-1", "0", "two"]:
            with self.subTest(version=version), self.assertRaises(frappe.ValidationError):
                qr.resolve_document("digital-job-hazard-analysis", "DOC/001", version)
        with self.assertRaises(frappe.ValidationError): qr.resolve_document("task", "")


class TestQrProjectTool(TestCase):
    def tools(self, rows):
        from verto.api.mobile import home
        with patch.object(home, "get_settings_child_rows", return_value=rows):
            return home.get_project_tools_from_settings(None)

    def test_scanner_is_in_default_and_existing_customised_menus(self):
        self.assertIn("scan qr", [item["key"] for item in self.tools([])])
        tools = self.tools([{"tool_key": "Map", "enabled": 1, "label": "Our map"}])
        self.assertEqual([item["key"] for item in tools], ["map", "scan qr"])
        self.assertEqual(tools[0]["label"], "Our map")

    def test_administrators_can_disable_or_rename_the_scanner(self):
        self.assertEqual(self.tools([{"tool_key": "Scan QR", "enabled": 0}]), [])
        self.assertEqual(self.tools([{"tool_key": "Scan QR", "enabled": 1, "label": "Scan document"}])[0]["label"], "Scan document")
