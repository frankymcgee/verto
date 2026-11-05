"""Cancelled projects remain visible within the normal annual planner scope."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from verto.api import planner


class TestPlannerCancelledProjects(TestCase):
	def setUp(self):
		self.projects = [
			{"name": name, "project_name": name, "status": status,
			 "expected_start_date": start, "expected_end_date": end, "is_active": "No"}
			for name, status, start, end in [
				("CANCELLED", "Cancelled", "2026-09-01", "2026-09-30"),
				("OPEN", "Open", "2026-09-01", "2026-09-30"),
				("COMPLETED", "Completed", "2026-09-01", "2026-09-30"),
				("OUTSIDE", "Cancelled", "2025-09-01", "2025-09-30"),
				("UNDATED", "Cancelled", None, None),
			]
		]
		self.enterContext(patch.object(frappe, "get_meta", return_value=SimpleNamespace(
			has_field=lambda field: field in {"expected_start_date", "expected_end_date", "is_active"},
		)))
		self.enterContext(patch.object(frappe, "get_all", side_effect=self.query_projects))
		self.enterContext(patch.object(planner, "get_project_requirements", return_value={}))
		self.enterContext(patch.object(planner, "get_project_task_counts", return_value={}))

	def query_projects(self, doctype, *, filters, **kwargs):
		self.assertEqual(doctype, "Project")
		rows = self.projects
		for field, (operator, value) in filters.items():
			if operator == "!=":
				rows = [row for row in rows if row.get(field) != value]
			elif operator == "in":
				rows = [row for row in rows if row.get(field) in value]
			else:
				self.fail(f"Unexpected project filter: {operator}")
		return [frappe._dict(row) for row in rows]

	def test_cancelled_projects_without_allocations_keep_the_year_scope(self):
		projects = planner.get_project_meta([], "2026-01-01", "2026-12-31")
		self.assertEqual(set(projects), {"CANCELLED", "OPEN", "COMPLETED"})
		self.assertEqual(projects["CANCELLED"].status, "Cancelled")
		self.assertFalse(projects["CANCELLED"].is_active)

	def test_referenced_undated_cancelled_projects_and_name_lookups_are_retained(self):
		projects = planner.get_project_meta(["UNDATED"], "2026-01-01", "2026-12-31")
		self.assertIn("UNDATED", projects)
		self.assertNotIn("OUTSIDE", projects)
		self.assertEqual(set(planner.get_project_meta(["CANCELLED"])), {"CANCELLED"})

	def test_both_annual_payloads_include_cancelled_projects_without_shifts(self):
		for sparse in (False, True):
			with self.subTest(sparse_assignments=sparse):
				rows = planner.get_year_project_rows([], "2026-01-01", "2026-12-31", sparse_assignments=sparse)
				by_name = {row["project"]: row for row in rows}
				self.assertEqual(set(by_name), {"CANCELLED", "OPEN", "COMPLETED"})
				self.assertEqual(by_name["CANCELLED"]["status"], "Cancelled")
				self.assertEqual(by_name["CANCELLED"]["start_date"], "2026-09-01")
				self.assertEqual(by_name["CANCELLED"]["end_date"], "2026-09-30")
