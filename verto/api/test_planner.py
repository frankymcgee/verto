"""Regression coverage for v16 project task counts and Planner visibility."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe.database.query import _validate_select_field

from verto.api import planner


class TestPlannerProjectTasks(TestCase):
	def setUp(self):
		self.task_counts = {"PROJ-1": 3, "PROJ-2": 1}
		self.get_all = self.enterContext(
			patch.object(planner.frappe, "get_all", side_effect=self.query_task_counts)
		)
		self.get_meta = self.enterContext(patch.object(
			planner.frappe, "get_meta",
			return_value=SimpleNamespace(has_field=lambda field: field == "project"),
		))

	def query_task_counts(self, doctype, *, fields, filters, **kwargs):
		# Use Frappe v16's actual SELECT validator so the old raw COUNT string
		# fails here just as it does on the migrated site. Database rows are mocked.
		for field in fields:
			if isinstance(field, str):
				_validate_select_field(field)
		rows = [
			frappe._dict(project=project, task_count=count)
			for project, count in sorted(self.task_counts.items())
			if project in filters["project"][1]
		]
		limit = kwargs.get("limit", kwargs.get("limit_page_length"))
		return rows[:limit] if limit else rows

	def project_fixture(self):
		values = {
			"status": "Open",
			"expected_start_date": "2026-09-01",
			"expected_end_date": "2026-09-30",
		}
		doc = SimpleNamespace(
			name="PROJ-1", project_name="Test project", status="Open",
			get=values.get, meta=SimpleNamespace(has_field=lambda field: field in values),
			set=Mock(), save=Mock(),
		)
		self.enterContext(patch.object(planner.frappe, "get_doc", return_value=doc))
		self.enterContext(patch.object(planner.frappe, "has_permission", return_value=True))
		self.enterContext(patch.object(planner, "_project_planner_edit_fields", return_value={
			"start_date_field": "expected_start_date",
			"end_date_field": "expected_end_date",
		}))
		self.execution_tasks = [{
			"name": "TASK-3", "subject": "Execution Works", "parent_task": "TASK-2",
			"location_subject": "General", "assignees": [], "can_assign": True,
		}]
		self.enterContext(patch.object(
			planner, "_get_project_execution_tasks", return_value=self.execution_tasks,
		))
		return doc

	def test_counts_are_available_with_v16_field_validation(self):
		counts = planner.get_project_task_counts(["PROJ-1", "PROJ-2", "EMPTY", "PROJ-1", ""])
		self.assertEqual(counts, {"PROJ-1": 3, "PROJ-2": 1})
		self.get_all.assert_called_once()
		self.assertEqual(self.get_all.call_args.kwargs["filters"]["project"][1],
			["EMPTY", "PROJ-1", "PROJ-2"])

	def test_empty_project_list_does_not_query(self):
		self.assertEqual(planner.get_project_task_counts([]), {})
		self.get_meta.assert_not_called()
		self.get_all.assert_not_called()

	def test_counts_are_not_truncated_at_annual_roster_limit(self):
		self.task_counts = {f"PROJ-{i:04}": 1 for i in range(1001)}
		self.assertEqual(planner.get_project_task_counts(self.task_counts), self.task_counts)

	def test_query_failure_is_not_reported_as_no_tasks(self):
		self.get_all.side_effect = RuntimeError("Task query failed")
		with self.assertRaisesRegex(RuntimeError, "Task query failed"):
			planner.get_project_task_counts(["PROJ-1"])

	def test_metadata_failure_is_not_reported_as_no_tasks(self):
		self.get_meta.side_effect = RuntimeError("Task metadata failed")
		with self.assertRaisesRegex(RuntimeError, "Task metadata failed"):
			planner.get_project_task_counts(["PROJ-1"])

	def test_project_details_show_tasks_and_allocation_controls(self):
		self.project_fixture()
		details = planner.get_project_planner_details("PROJ-1")
		self.assertEqual(details["task_count"], 3)
		self.assertTrue(details["has_tasks"])
		self.assertEqual(details["execution_tasks"], self.execution_tasks)
		self.assertTrue(details["execution_tasks"][0]["can_assign"])
		self.assertFalse(details["can_create_generic_tasks"])
		self.assertFalse(details["can_update_project_dates"])

	def test_project_without_tasks_keeps_creation_and_date_controls(self):
		self.project_fixture()
		self.task_counts.clear()
		self.execution_tasks.clear()
		details = planner.get_project_planner_details("PROJ-1")
		self.assertEqual(details["task_count"], 0)
		self.assertFalse(details["has_tasks"])
		self.assertEqual(details["execution_tasks"], [])
		self.assertTrue(details["can_create_generic_tasks"])
		self.assertTrue(details["can_update_project_dates"])

	def test_annual_project_row_retains_linked_task_indicator(self):
		with patch.object(planner, "get_project_meta", return_value={"PROJ-1": frappe._dict(
			project_name="Test project", expected_start_date="2026-09-01",
			expected_end_date="2026-09-30", _start_field="expected_start_date",
			_end_field="expected_end_date",
		)}):
			rows = planner.get_year_project_rows([], "2026-01-01", "2026-12-31", sparse_assignments=True)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["task_count"], 3)
		self.assertTrue(rows[0]["has_tasks"])

	def test_linked_tasks_prevent_project_date_changes(self):
		doc = self.project_fixture()
		with self.assertRaises(frappe.ValidationError):
			planner.update_project_planner_dates("PROJ-1", "2026-09-02", "2026-09-30")
		doc.set.assert_not_called()
		doc.save.assert_not_called()

	def test_query_failure_prevents_project_date_changes(self):
		doc = self.project_fixture()
		self.get_all.side_effect = RuntimeError("Task query failed")
		with self.assertRaisesRegex(RuntimeError, "Task query failed"):
			planner.update_project_planner_dates("PROJ-1", "2026-09-02", "2026-09-30")
		doc.set.assert_not_called()
		doc.save.assert_not_called()
