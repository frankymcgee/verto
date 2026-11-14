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
    frappe._ = lambda message: message
    frappe.get_list = Mock(return_value=[])
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
        work_order_task = load("work_order_task", "verto/safety/work_order_task.py")
        modules["verto.safety.work_order_task"] = work_order_task
        with patch.dict("sys.modules", modules):
            documents = load("documents")
            documents.field_interaction = load(
                "field_interaction", "verto/safety/doctype/field_interaction/field_interaction.py",
            )
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


class TestWorkOrderTask(unittest.TestCase):
    def setUp(self):
        self.offline, self.documents, self.frappe, _ = load_apis()
        self.fields = {
            name: SimpleNamespace(fieldname=name, fieldtype=fieldtype, get={"fetch_from": fetch_from}.get)
            for name, fieldtype, fetch_from in (
                ("scope_or_wo", "Select", None),
                ("link_task", "Link", None),
                ("link_project", "Link", "link_task.project"),
                ("work_order_number", "Data", "link_task.work_order_number"),
                ("work_scope", "Data", "link_task.subject"),
                ("work_area", "Data", "link_task.parent_task_name"),
            )
        }
        self.meta = SimpleNamespace(
            has_field=self.fields.__contains__,
            get_field=self.fields.get,
            fields=list(self.fields.values()),
        )
        self.tasks = [
            {"name": "WRONG", "project": "OTHER-PROJECT", "work_order_number": "WO-1"},
            {"name": "FIRST", "project": "PROJ-1", "work_order_number": "WO-1",
             "subject": "Inspect conveyor", "parent_task_name": "Conveyor Area"},
            {"name": "SELECTED", "project": "PROJ-1", "work_order_number": "WO-1",
             "subject": "Inspect pump", "parent_task_name": "Pump Room"},
            {"name": "REPLACEMENT", "project": "PROJ-1", "work_order_number": "WO-2",
             "subject": "Inspect chute", "parent_task_name": "Chute Area"},
        ]
        self.frappe.get_list.side_effect = lambda doctype, filters, fields, limit: [
            {key: row.get(key) for key in fields}
            for row in self.tasks if all(row.get(key) == value for key, value in filters.items())
        ][:limit]

    def form(self, task=None, work_order="WO-1", project="PROJ-1"):
        form = self.documents.field_interaction.FieldInteraction()
        values = {
            "scope_or_wo": "Work Order Number", "work_order_number": work_order,
            "link_task": task, "link_project": project,
            "work_scope": "Inspect pump", "work_area": "Pump Room",
        }
        form.get = values.get
        form.set = values.__setitem__
        form.update = values.update
        form.meta = self.meta
        form.doctype = "Field Interaction"
        form.name = "FI-1"
        form.set_compliance_percentage = Mock()
        return form

    def test_validate_preserves_the_exact_task_with_duplicate_work_orders(self):
        form = self.form(task="SELECTED")
        form.validate()
        self.assertEqual(form.get("link_task"), "SELECTED")
        self.assertEqual(form.get("link_project"), "PROJ-1")
        self.frappe.get_list.assert_called_once_with(
            "Task", filters={"project": "PROJ-1", "work_order_number": "WO-1", "name": "SELECTED"},
            fields=["name", "subject", "parent_task_name"], limit=1,
        )

    def test_ambiguous_work_order_warns_while_editing_and_blocks_save(self):
        form = self.form()
        change = form.mobile_field_change("work_order_number")
        self.assertIn("multiple tasks", change["warnings"][0])
        self.assertIsNone(form.get("link_task"))
        with self.assertRaisesRegex(ValidationError, "multiple tasks"):
            form.validate()
        self.assertIsNone(form.get("link_task"))

    def test_work_order_from_another_project_cannot_relink_the_form(self):
        form = self.form(task="WRONG", project="PROJ-3")
        change = form.mobile_field_change("link_project")
        self.assertIn("selected project", change["warnings"][0])
        self.assertEqual(change["values"], {"link_task": "", "work_scope": "", "work_area": ""})
        form.validate()
        self.assertEqual(form.get("link_project"), "PROJ-3")
        self.assertEqual(form.get("link_task"), "")

    def test_editing_the_work_order_can_resolve_a_unique_task_in_the_same_project(self):
        form = self.form(task="SELECTED", work_order="WO-2")
        change = form.mobile_field_change("work_order_number")
        self.assertEqual(change["values"], {
            "link_task": "REPLACEMENT", "work_scope": "Inspect chute", "work_area": "Chute Area",
        })
        form.validate()
        self.assertEqual(form.get("link_task"), "REPLACEMENT")

    def test_mobile_work_scope_rejects_a_task_from_another_project(self):
        form = self.form(task="WRONG")
        form.set("scope_or_wo", "Work Scope")
        with self.assertRaisesRegex(ValidationError, "does not belong"):
            self.documents.prepare_mobile_task_link(form)

    def test_mobile_replay_saves_the_exact_task_before_any_photos_are_uploaded(self):
        form = self.form()
        form.insert = Mock(side_effect=form.validate)
        self.documents.get_allowed_doctype = Mock(return_value=form.doctype)
        self.documents.apply_fetch_from = Mock(return_value={"values": {}})
        self.frappe.get_meta.return_value = self.meta
        self.frappe.new_doc.return_value = form

        result = self.offline._execute_document_action("create", "field-interaction", {
            "link_task": "SELECTED", "link_project": "PROJ-1", "work_order_number": "WO-1",
            "scope_or_wo": "Work Order Number",
        }, None)

        self.assertEqual(result["name"], "FI-1")
        self.assertEqual(form.get("link_task"), "SELECTED")
        form.insert.assert_called_once()
