"""Verify native Gantt scope and pagination without a running Frappe site."""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch


class TestMobileGantt(TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe._ = lambda message: message
        self.frappe.whitelist = lambda **kwargs: lambda function: function
        self.frappe.PermissionError = PermissionError
        self.frappe.ValidationError = ValueError
        self.frappe.local = SimpleNamespace(response_headers={})
        self.frappe.has_permission = Mock(return_value=True)
        self.frappe.get_list = Mock()
        self.frappe.get_meta = Mock(return_value=SimpleNamespace(has_field=lambda field: field == "exp_start_time"))

        def throw(message, exc):
            raise exc(message)

        self.frappe.throw = throw
        self.require_login = Mock()
        self.form_buttons = Mock(return_value={
            "generic_forms": [{"mobile_doctype": "take-5"}],
            "task_forms": [{"mobile_doctype": "field-interaction"}],
            "ccv_forms": [{"mobile_doctype": "ccv-lifting-operations"}],
        })
        modules = {
            "frappe": self.frappe,
            "frappe.utils": SimpleNamespace(cint=lambda value: int(value or 0)),
            "verto.api.mobile.home": SimpleNamespace(
                require_login=self.require_login, get_mobile_form_buttons=self.form_buttons,
            ),
        }
        spec = importlib.util.spec_from_file_location(
            "mobile_gantt_under_test", Path(__file__).parents[1] / "verto/api/mobile/gantt.py",
        )
        self.gantt = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", modules):
            spec.loader.exec_module(self.gantt)
        self.project = {"name": "PROJ-1", "project_name": "Shutdown"}

    def test_guest_and_select_only_task_access_cannot_fetch_a_schedule(self):
        self.require_login.side_effect = PermissionError("Login required")
        with self.assertRaises(PermissionError):
            self.gantt.get_schedule("PROJ-1")
        self.frappe.has_permission.assert_not_called()

        self.require_login.side_effect = None
        self.frappe.has_permission.return_value = False
        with self.assertRaises(PermissionError):
            self.gantt.get_schedule("PROJ-1")
        self.frappe.has_permission.assert_called_once_with("Task", "read")
        self.frappe.get_list.assert_not_called()
        self.form_buttons.assert_not_called()

    def test_inaccessible_project_or_area_stops_before_querying_schedule_rows(self):
        self.frappe.get_list.side_effect = [[]]
        with self.assertRaises(PermissionError):
            self.gantt.get_schedule("PROJ-1")
        self.frappe.get_list.assert_called_once()

        self.frappe.get_list.reset_mock()
        self.frappe.get_list.side_effect = [[self.project], []]
        with self.assertRaises(PermissionError):
            self.gantt.get_schedule("PROJ-1", "AREA-FROM-ANOTHER-PROJECT")
        self.assertEqual(self.frappe.get_list.call_count, 2)
        self.assertEqual(self.frappe.get_list.call_args.kwargs["filters"], {
            "name": "AREA-FROM-ANOTHER-PROJECT", "project": "PROJ-1",
        })

    def test_area_queries_are_inclusive_and_page_through_current_project_tasks(self):
        area = {"name": "AREA-1", "subject": "Plant room", "lft": 10, "rgt": 30}
        rows = [{"name": f"TASK-{i}"} for i in range(self.gantt.PAGE_SIZE + 1)]
        self.frappe.get_list.side_effect = [[self.project], [area], rows]

        result = self.gantt.get_schedule("PROJ-1", "AREA-1", start=50)

        self.assertEqual(result["project_name"], "Shutdown")
        self.assertEqual(result["area_name"], "Plant room")
        self.assertEqual(result["tasks"], rows[:-1])
        self.assertEqual(result["next_start"], 100)
        self.assertNotIn("task_forms", result)
        self.assertNotIn("ccv_forms", result)
        self.form_buttons.assert_not_called()
        self.assertEqual(self.frappe.local.response_headers["Cache-Control"], "no-store")
        query = self.frappe.get_list.call_args.kwargs
        self.assertEqual(query["filters"], {
            "project": "PROJ-1", "status": ["not in", ["Completed", "Cancelled"]],
            "type": ["not in", ["Task Step", "Outline"]], "lft": [">=", 10], "rgt": ["<=", 30],
        })
        self.assertEqual(query["order_by"], "lft asc, name asc")
        self.assertIn("lft", query["fields"])
        self.assertIn("rgt", query["fields"])
        self.assertEqual(query["offset"], 50)
        self.assertEqual(query["limit"], 51)
        self.assertIn("exp_start_time", query["fields"])
        self.assertNotIn("exp_end_time", query["fields"])
        self.assertNotIn("ignore_permissions", query)

    def test_area_without_tree_bounds_remains_scoped_to_the_selected_task(self):
        self.frappe.get_list.side_effect = [[self.project], [{"name": "AREA-1"}], []]
        result = self.gantt.get_schedule("PROJ-1", "AREA-1")
        self.assertIsNone(result["next_start"])
        self.assertEqual(result["area_name"], "AREA-1")
        self.assertEqual(self.frappe.get_list.call_args.kwargs["filters"]["name"], "AREA-1")

    def test_first_schedule_page_includes_the_allowed_task_form_and_ccv_options(self):
        self.frappe.get_list.side_effect = [[self.project], [{"name": "TASK-1"}]]

        result = self.gantt.get_schedule("PROJ-1")

        self.form_buttons.assert_called_once_with()
        self.assertEqual(result["task_forms"], [{"mobile_doctype": "field-interaction"}])
        self.assertEqual(result["ccv_forms"], [{"mobile_doctype": "ccv-lifting-operations"}])
        self.assertNotIn("generic_forms", result)
