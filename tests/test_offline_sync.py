"""Exercise mobile retry and duplicate guards without a running Frappe site."""
import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class ValidationError(Exception):
    pass


class DuplicateEntryError(Exception):
    pass


class UniqueValidationError(Exception):
    pass


def load_apis():
    frappe = ModuleType("frappe")
    frappe.whitelist = lambda **kwargs: lambda function: function
    frappe.session = SimpleNamespace(user="worker@example.test")
    frappe.PermissionError = PermissionError
    frappe.ValidationError = ValidationError
    frappe.DuplicateEntryError = DuplicateEntryError
    frappe.UniqueValidationError = UniqueValidationError
    frappe.DoesNotExistError = LookupError

    def throw(message, exc=ValidationError):
        raise exc(message)

    frappe.throw = throw
    frappe.db = SimpleNamespace(exists=Mock(return_value=False), set_value=Mock(),
        get_value=Mock(return_value=None), commit=Mock(), rollback=Mock())
    frappe.logger = Mock()
    frappe.get_doc = Mock()
    frappe.new_doc = Mock()
    frappe.get_meta = Mock(return_value=SimpleNamespace(fields=[]))
    frappe.has_permission = Mock(return_value=True)
    frappe.request = SimpleNamespace(files={})
    utils = ModuleType("frappe.utils")
    for name in ("cint", "getdate", "get_datetime", "now_datetime", "today", "add_days", "add_to_date"):
        setattr(utils, name, Mock(return_value="2026-11-05"))
    document = ModuleType("frappe.model.document")
    document.Document = object
    jobs = ModuleType("frappe.utils.background_jobs")
    jobs.enqueue = Mock()
    files = ModuleType("frappe.utils.file_manager")
    files.save_file = Mock()
    mobile = ModuleType("verto.api.mobile")
    api = ModuleType("verto.api")
    api.fetch_records = Mock()
    modules = {"frappe": frappe, "frappe.utils": utils, "frappe.utils.file_manager": files,
        "verto.api.mobile": mobile, "verto.api": api,
        "frappe.model.document": document, "frappe.utils.background_jobs": jobs}

    def load(name, path=None):
        spec = importlib.util.spec_from_file_location(f"{name}_under_test",
            Path(__file__).parents[1] / (path or f"verto/api/mobile/{name}.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    with patch.dict("sys.modules", modules):
        documents = load("documents")
        mobile.documents = documents
        mobile.shifts = Mock()
        offline = load("offline")
        documents.daily_timesheet = load("daily_timesheet", "verto/verto/doctype/daily_timesheet/daily_timesheet.py")
    return offline, documents, frappe, files


class TestOfflineSync(unittest.TestCase):
    def setUp(self):
        self.offline, self.documents, self.frappe, self.files = load_apis()
        self.result = {"doctype": "Daily Timesheet", "name": "TS-1", "route": "/shifts"}
        self.receipt = SimpleNamespace(name="operation-1", user=self.frappe.session.user,
            receipt_type="document_create", target_doctype="Daily Timesheet", target_name="TS-1",
            result_json=json.dumps(self.result), insert=Mock())
        self.frappe.get_doc.return_value = self.receipt
        self.documents.apply_fetch_from = Mock(return_value={"values": {}})
        self.documents.create_mobile_doc = Mock(return_value=self.result)
        self.documents.update_mobile_doc = Mock(return_value=self.result)

    def sync(self, **overrides):
        options = dict(operation_id="operation-1", action_type="create", mobile_doctype="daily-timesheet",
            values={"date": "2026-11-05", "__verto_offline_user": self.frappe.session.user})
        options.update(overrides)
        return self.offline.sync_action(**options)

    def test_reserves_receipt_before_fetching_or_creating_and_commits_result_together(self):
        order = []
        self.receipt.insert.side_effect = lambda **kw: order.append("reserve")
        self.documents.apply_fetch_from.side_effect = lambda **kw: order.append("fetch") or {}
        self.documents.create_mobile_doc.side_effect = lambda **kw: order.append("create") or self.result
        self.frappe.db.set_value.side_effect = lambda *args: order.append("result")
        self.frappe.db.commit.side_effect = lambda: order.append("commit")
        self.assertEqual(self.sync()["result"], self.result)
        self.assertEqual(order, ["reserve", "fetch", "create", "result", "commit"])

    def test_committed_retry_does_not_run_document_hooks_again(self):
        self.frappe.db.exists.return_value = True
        self.assertTrue(self.sync()["duplicate"])
        self.documents.create_mobile_doc.assert_not_called()
        self.documents.apply_fetch_from.assert_not_called()
        self.receipt.insert.assert_not_called()

    def test_concurrent_receipt_winner_is_returned_before_a_second_document_write(self):
        for error in (DuplicateEntryError, UniqueValidationError):
            with self.subTest(error=error):
                self.frappe.db.exists.side_effect = [False, True]
                self.receipt.insert.side_effect = error("Other request won")
                self.assertEqual(self.sync(), {"ok": True, "duplicate": True, "result": self.result})
                self.documents.create_mobile_doc.assert_not_called()
        self.assertEqual(self.frappe.db.rollback.call_count, 2)

    def test_failed_write_rolls_back_the_reservation_and_never_commits(self):
        self.documents.create_mobile_doc.side_effect = ValidationError("Invalid shift")
        with self.assertRaisesRegex(ValidationError, "Invalid shift"):
            self.sync()
        self.frappe.db.rollback.assert_called_once()
        self.frappe.db.commit.assert_not_called()

    def test_failed_result_write_also_rolls_back_the_document(self):
        self.frappe.db.set_value.side_effect = RuntimeError("Database unavailable")
        with self.assertRaises(RuntimeError):
            self.sync()
        self.frappe.db.rollback.assert_called_once()
        self.frappe.db.commit.assert_not_called()

    def test_blank_or_oversized_operation_ids_never_create_a_document(self):
        for operation_id in ("", " ", "x" * 141):
            with self.subTest(operation_id=operation_id), self.assertRaises(ValidationError):
                self.sync(operation_id=operation_id)
        self.documents.create_mobile_doc.assert_not_called()

    def test_changed_actor_and_foreign_receipts_cannot_replay_work(self):
        with self.assertRaises(PermissionError):
            self.sync(values={"__verto_offline_user": "another"})
        self.frappe.db.exists.return_value = True
        self.receipt.user = "another"
        with self.assertRaises(PermissionError):
            self.sync()
        self.documents.create_mobile_doc.assert_not_called()

    def test_update_uses_the_same_receipt_guard(self):
        self.sync(action_type="update", docname="TS-1")
        self.documents.create_mobile_doc.assert_not_called()
        self.documents.update_mobile_doc.assert_called_once()

    def test_attachment_race_reserves_its_receipt_before_writing_a_file(self):
        parent = {"target_doctype": "Daily Timesheet", "target_name": "TS-1", "result": self.result}
        uploaded = SimpleNamespace(filename="photo.jpg", stream=Mock())
        self.frappe.request.files["file"] = uploaded
        self.frappe.db.exists.return_value = True
        self.documents.has_desk_write_permission = Mock(return_value=True)
        execute = Mock(return_value={"doctype": "Daily Timesheet", "docname": "TS-1", "name": "FILE-1"})
        order = []
        self.receipt.insert.side_effect = lambda **kw: order.append("reserve")
        execute.side_effect = lambda *args: order.append("file") or {"doctype": "Daily Timesheet", "docname": "TS-1", "name": "FILE-1"}
        with patch.object(self.offline, "_get_receipt", side_effect=[parent, None, None]), \
             patch.object(self.offline, "_save_uploaded_attachment", execute):
            self.offline.upload_attachment("operation-1", "photo-1", "Daily Timesheet", "TS-1")
        self.assertEqual(order, ["reserve", "file"])
        self.assertEqual(self.frappe.db.set_value.call_args.args[2]["target_name"], "TS-1")
        execute.assert_called_once()


class TestDailyTimesheetDuplicates(unittest.TestCase):
    def setUp(self):
        _, self.documents, self.frappe, _ = load_apis()
        self.values = {"current_user": "Worker", "date": "2026-11-05", "shift_allocation": "SHIFT-1"}
        self.doc = Mock(shift_allocation="SHIFT-1")
        self.doc.get.side_effect = self.values.get

    def test_duplicate_check_locks_the_allocation_then_reads_the_latest_timesheet(self):
        self.documents.daily_timesheet.prevent_duplicate_daily_timesheet(self.doc)
        calls = self.frappe.db.get_value.call_args_list
        self.assertEqual(calls[0].args, ("Shift Assignment", "SHIFT-1", "name"))
        self.assertTrue(calls[0].kwargs["for_update"])
        self.assertEqual(calls[1].args[1], {**self.values, "docstatus": ["!=", 2]})
        self.assertTrue(calls[1].kwargs["for_update"])

    def test_existing_hours_cannot_be_overwritten_by_a_new_submission_id(self):
        self.frappe.db.get_value.side_effect = ["SHIFT-1", "TS-EXISTING"]
        with self.assertRaisesRegex(ValidationError, "Open the existing timesheet"):
            self.documents.daily_timesheet.prevent_duplicate_daily_timesheet(self.doc)

    def test_unallocated_timesheets_lock_the_user_and_match_only_unallocated_records(self):
        self.values["shift_allocation"] = ""
        self.documents.daily_timesheet.prevent_duplicate_daily_timesheet(self.doc)
        calls = self.frappe.db.get_value.call_args_list
        self.assertEqual(calls[0].args[:2], ("User", self.frappe.session.user))
        self.assertEqual(calls[1].args[1]["shift_allocation"], ["is", "not set"])


class TestWeeklyTimesheetReplay(unittest.TestCase):
    def test_competing_jobs_lock_the_employee_before_looking_for_a_weekly_sheet(self):
        _, documents, frappe, _ = load_apis()
        frappe.db.get_value.side_effect = ["EMP-1", "WEEK-1"]
        doc = {"current_user": "Worker", "date": "2026-11-05", "project_id": "PROJ-1"}
        result = documents.daily_timesheet.get_weekly_timesheet_for_update("EMP-1", doc)
        self.assertEqual(result, "WEEK-1")
        calls = frappe.db.get_value.call_args_list
        self.assertEqual(calls[0].args, ("Employee", "EMP-1", "name"))
        self.assertEqual(calls[1].args[0], "Timesheet")
        self.assertEqual(calls[1].args[1]["parent_project"], "PROJ-1")
        self.assertEqual(calls[1].args[1]["docstatus"], ("!=", 2))
        self.assertTrue(all(call.kwargs["for_update"] for call in calls))

    def test_existing_user_fallback_is_also_serialised(self):
        _, documents, frappe, _ = load_apis()
        documents.daily_timesheet.get_weekly_timesheet_for_update(None, {"owner": "worker@example.test"})
        self.assertEqual(frappe.db.get_value.call_args_list[0].args[:2], ("User", "worker@example.test"))


if __name__ == "__main__":
    unittest.main()
