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
		if "name" in fields:
			field = fields[1]
			self.assertEqual(filters, {"project": "PROJ-1", field: ["is", "set"]})
			self.assertEqual(kwargs["limit_page_length"], 1)
			return [frappe._dict(name="TASK-BOUNDARY", **{field: (
				"2026-09-01" if field == "exp_start_date" else "2026-09-30"
			)})]
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
		self.assertTrue(details["can_update_project_dates"])

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

	def test_linked_tasks_prevent_excluding_task_start(self):
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

	def test_both_date_endpoints_allow_ranges_covering_tasks(self):
		for endpoint in (planner.update_project_planner_dates, planner.update_project_planner_details):
			for start, end in (("2026-08-25", "2026-10-05"), ("2026-09-01", "2026-10-05"), ("2026-08-25", "2026-09-30")):
				with self.subTest(endpoint=endpoint.__name__, start=start, end=end):
					doc = self.project_fixture()
					endpoint("PROJ-1", project_start_date=start, project_end_date=end)
					doc.set.assert_any_call("expected_start_date", start)
					doc.set.assert_any_call("expected_end_date", end)
					doc.save.assert_called_once()

	def test_both_date_endpoints_explain_conflicting_task_dates(self):
		for endpoint in (planner.update_project_planner_dates, planner.update_project_planner_details):
			for start, end, message in (
				("2026-09-02", "2026-10-05", "Start Date cannot be later than 2026-09-01"),
				("2026-08-25", "2026-09-29", "End Date cannot be earlier than 2026-09-30"),
				("", "2026-10-05", "Start Date is required"),
				("2026-08-25", "", "End Date is required"),
			):
				with self.subTest(endpoint=endpoint.__name__, start=start, end=end):
					doc = self.project_fixture()
					with self.assertRaisesRegex(frappe.ValidationError, message) as error:
						endpoint("PROJ-1", project_start_date=start, project_end_date=end)
					self.assertIn("TASK-BOUNDARY", str(error.exception))
					doc.save.assert_not_called()

	def test_project_can_contract_to_exact_task_bounds(self):
		doc = self.project_fixture()
		doc.get = {"expected_start_date": "2026-08-01", "expected_end_date": "2026-10-31"}.get
		planner.update_project_planner_dates("PROJ-1", "2026-09-01", "2026-09-30")
		doc.save.assert_called_once()

	def test_undated_tasks_do_not_restrict_project_dates(self):
		doc = self.project_fixture()
		self.get_all.side_effect = lambda doctype, **kwargs: []
		planner.update_project_planner_dates("PROJ-1", "2026-09-10", "2026-09-20")
		doc.save.assert_called_once()

	def test_inverted_project_dates_are_rejected(self):
		doc = self.project_fixture()
		with self.assertRaisesRegex(frappe.ValidationError, "Start Date cannot be after"):
			planner.update_project_planner_dates("PROJ-1", "2026-10-01", "2026-09-01")
		doc.save.assert_not_called()


class TestPlannerTaskAssignmentChanges(TestCase):
	def setUp(self):
		self.current_users = ["alex@example.com", "blake@example.com"]
		self.valid_users = {"alex@example.com", "blake@example.com", "casey@example.com"}
		self.task = SimpleNamespace(
			name="TASK-1", project="PROJ-1", subject="Execution Works",
			get=lambda field: {"type": "Work Summary", "_assign": self.current_users}.get(field),
			check_permission=Mock(),
		)
		self.get_doc = self.enterContext(patch.object(planner.frappe, "get_doc", return_value=self.task))
		self.get_all = self.enterContext(patch.object(
			planner.frappe, "get_all", side_effect=self.valid_user_query,
		))
		self.details = self.enterContext(patch.object(planner, "get_project_planner_details", return_value={
			"project": "PROJ-1", "execution_tasks": [],
		}))
		self.add = self.enterContext(patch("frappe.desk.form.assign_to.add"))
		self.remove = self.enterContext(patch("frappe.desk.form.assign_to.remove"))

	def valid_user_query(self, doctype, *, filters, **kwargs):
		self.assertEqual(doctype, "User")
		self.assertEqual(filters["enabled"], 1)
		self.assertEqual(filters["user_type"], "System User")
		return [user for user in filters["name"][1] if user in self.valid_users]

	def update(self, additions, removals):
		return planner.update_project_execution_task_assignments("PROJ-1", "TASK-1", additions, removals)

	def assert_no_mutations(self):
		self.add.assert_not_called()
		self.remove.assert_not_called()

	def test_adds_person_without_removing_current_assignees(self):
		result = self.update(["casey@example.com"], [])
		self.assertEqual(result["assigned_users"], ["casey@example.com"])
		self.assertEqual(result["removed_users"], [])
		self.add.assert_called_once_with({
			"assign_to": ["casey@example.com"], "doctype": "Task", "name": "TASK-1",
			"description": "Execution Works",
		})
		self.remove.assert_not_called()
		self.get_doc.assert_called_once_with("Task", "TASK-1", for_update=True)
		self.task.check_permission.assert_called_once_with("write")

	def test_removes_person_using_standard_assignment_flow(self):
		result = self.update([], ["alex@example.com"])
		self.assertEqual(result["removed_users"], ["alex@example.com"])
		self.remove.assert_called_once_with("Task", "TASK-1", "alex@example.com")
		self.add.assert_not_called()
		self.get_all.assert_not_called()

	def test_replaces_person_and_preserves_unrelated_concurrent_addition(self):
		self.current_users.append("drew@example.com")  # added since the picker was opened
		result = self.update(["casey@example.com"], ["alex@example.com"])
		self.assertEqual(result["assigned_users"], ["casey@example.com"])
		self.assertEqual(result["removed_users"], ["alex@example.com"])
		self.remove.assert_called_once_with("Task", "TASK-1", "alex@example.com")
		self.assertEqual(result["project_details"]["project"], "PROJ-1")

	def test_can_remove_all_assignees_even_above_addition_limit(self):
		self.current_users = [f"user-{i}@example.com" for i in range(60)]
		result = self.update([], self.current_users)
		self.assertEqual(len(result["removed_users"]), 60)
		self.assertEqual(self.remove.call_count, 60)
		self.add.assert_not_called()

	def test_disabled_assignees_can_be_removed(self):
		self.valid_users.remove("alex@example.com")
		self.update([], ["alex@example.com"])
		self.remove.assert_called_once_with("Task", "TASK-1", "alex@example.com")
		self.get_all.assert_not_called()

	def test_invalid_addition_prevents_removals(self):
		for user in ("disabled@example.com", "Guest"):
			with self.subTest(user=user), self.assertRaises(frappe.ValidationError):
				self.update([user], ["alex@example.com"])
		self.assert_no_mutations()

	def test_failed_standard_addition_does_not_start_removals(self):
		self.add.side_effect = frappe.PermissionError("Cannot share task")
		with self.assertRaises(frappe.PermissionError):
			self.update(["casey@example.com"], ["alex@example.com"])
		self.remove.assert_not_called()

	def test_conflicting_add_and_remove_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.update(["alex@example.com"], ["ALEX@example.com"])
		self.assert_no_mutations()

	def test_malformed_lists_are_rejected(self):
		for additions, removals in (({}, []), ([], None), (None, [])):
			with self.subTest(additions=additions, removals=removals), self.assertRaises(frappe.ValidationError):
				self.update(additions, removals)
		self.assert_no_mutations()

	def test_duplicate_users_are_only_changed_once(self):
		self.update('["casey@example.com", "casey@example.com"]', '["alex@example.com", "alex@example.com"]')
		self.assertEqual(self.add.call_args.args[0]["assign_to"], ["casey@example.com"])
		self.remove.assert_called_once()

	def test_repeated_update_is_a_noop(self):
		self.update(["alex@example.com"], ["removed@example.com"])
		self.assert_no_mutations()

	def test_task_from_another_project_is_rejected(self):
		self.task.project = "OTHER-PROJECT"
		with self.assertRaises(frappe.ValidationError):
			self.update([], ["alex@example.com"])
		self.assert_no_mutations()

	def test_read_only_task_is_rejected(self):
		self.task.check_permission.side_effect = frappe.PermissionError("Read only")
		with self.assertRaises(frappe.PermissionError):
			self.update([], ["alex@example.com"])
		self.assert_no_mutations()

	def test_non_execution_task_is_rejected(self):
		self.task.get = lambda field: "Outline" if field == "type" else self.current_users
		with self.assertRaises(frappe.ValidationError):
			self.update([], ["alex@example.com"])
		self.assert_no_mutations()

	def test_picker_includes_current_disabled_and_missing_accounts(self):
		self.current_users = ["disabled@example.com", "missing@example.com"]
		self.get_all.side_effect = [
			[frappe._dict(name="casey@example.com", full_name="Casey", user_image=None)],
			[frappe._dict(name="disabled@example.com", full_name="Former user", user_image=None)],
		]
		result = planner.get_task_assignment_users("PROJ-1", "TASK-1")
		self.assertEqual(result["assigned_users"], self.current_users)
		self.assertEqual({user["user"] for user in result["users"]},
			{"casey@example.com", "disabled@example.com", "missing@example.com"})
		self.assertEqual(result["task"], "TASK-1")

	def test_legacy_add_endpoint_remains_additive(self):
		result = planner.assign_project_execution_task("PROJ-1", "TASK-1", ["casey@example.com"])
		self.assertEqual(result["assigned_users"], ["casey@example.com"])
		self.add.assert_called_once()
		self.remove.assert_not_called()
