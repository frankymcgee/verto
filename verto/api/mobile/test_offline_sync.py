"""Database integration checks for competing offline request receipts."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock, patch
import uuid

import frappe
from frappe.tests import IntegrationTestCase

from verto.api.mobile import offline


class TestOfflineReceiptTransactions(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        self.operation_id = f"test-offline-{uuid.uuid4().hex}"
        self.result = {"doctype": "Daily Timesheet", "name": "TS-OFFLINE-TEST", "route": "/shifts"}

    def tearDown(self):
        frappe.db.rollback()
        frappe.db.delete(offline.RECEIPT_DOCTYPE, {"name": self.operation_id})
        frappe.db.commit()
        super().tearDown()

    def test_failed_document_leaves_no_receipt_and_can_be_retried(self):
        with self.assertRaises(frappe.ValidationError):
            offline._run_receipted_operation(self.operation_id, "document_create",
                lambda: frappe.throw("Invalid form", frappe.ValidationError))
        self.assertFalse(frappe.db.exists(offline.RECEIPT_DOCTYPE, self.operation_id))
        executed = Mock(return_value=self.result)
        first = offline._run_receipted_operation(self.operation_id, "document_create", executed)
        second = offline._run_receipted_operation(self.operation_id, "document_create", executed)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["result"], self.result)
        executed.assert_called_once()

    def test_two_database_connections_execute_the_document_write_only_once(self):
        site = frappe.local.site
        sites_path = frappe.local.sites_path
        first_writing, second_reserving = Event(), Event()
        reserve = offline._save_receipt

        def save_receipt(*args, **kwargs):
            if first_writing.is_set():
                second_reserving.set()
            return reserve(*args, **kwargs)

        def create_document():
            first_writing.set()
            if not second_reserving.wait(15):
                raise RuntimeError("Second request did not reach its reservation")
            return self.result

        executed = Mock(side_effect=create_document)

        def request():
            frappe.init(site=site, sites_path=sites_path)
            frappe.connect()
            try:
                frappe.set_user("Administrator")
                return offline._run_receipted_operation(self.operation_id, "document_create", executed)
            finally:
                frappe.db.rollback()
                frappe.destroy()

        with patch.object(offline, "_save_receipt", side_effect=save_receipt), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(request)
            self.assertTrue(first_writing.wait(15))
            second = pool.submit(request)
            results = [first.result(timeout=30), second.result(timeout=30)]
        self.assertEqual(sorted(item["duplicate"] for item in results), [False, True])
        self.assertTrue(all(item["result"] == self.result for item in results))
        executed.assert_called_once()
