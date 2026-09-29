"""Leave visibility and scheduling regressions for the annual roster."""

import re
import sqlite3
from unittest import TestCase
from unittest.mock import patch

import frappe

from verto.api import planner


class TestPlannerLeaveStatuses(TestCase):
	def setUp(self):
		# Execute the real query against isolated rows without creating HR records.
		self.db = sqlite3.connect(":memory:")
		self.addCleanup(self.db.close)
		self.db.row_factory = sqlite3.Row
		self.db.executescript('''
			CREATE TABLE `tabEmployee` (name TEXT, company TEXT);
			INSERT INTO `tabEmployee` VALUES ('EMP-1', 'MSS'), ('EMP-2', 'Other');
			CREATE TABLE `tabLeave Application` (
				name TEXT, employee TEXT, leave_type TEXT, from_date TEXT, to_date TEXT,
				description TEXT, status TEXT, docstatus INTEGER, modified TEXT,
				total_leave_days REAL, half_day INTEGER, half_day_date TEXT
			);
		''')
		for name, status, docstatus, day, employee, modified in [
			("APPROVED", "Approved", 1, "2026-09-10", "EMP-1", "2026-09-02"),
			("OPEN", "Open", 0, "2026-09-11", "EMP-1", "2026-09-03"),
			("OLDER-OPEN", "Open", 0, "2026-09-11", "EMP-1", "2026-09-01"),
			("REJECTED", "Rejected", 1, "2026-09-12", "EMP-1", "2026-09-02"),
			("CANCELLED", "Approved", 2, "2026-09-13", "EMP-1", "2026-09-02"),
			("OLD-CANCELLED", "Approved", 2, "2026-09-10", "EMP-1", "2026-09-04"),
			("OUTSIDE-RANGE", "Open", 0, "2026-10-01", "EMP-1", "2026-09-02"),
			("OTHER-COMPANY", "Open", 0, "2026-09-14", "EMP-2", "2026-09-02"),
		]:
			self.db.execute(
				"INSERT INTO `tabLeave Application` VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
				(name, employee, "Annual Leave", day, day, "Reason", status, docstatus, modified, 1, 0, None),
			)
		self.enterContext(patch.object(frappe.db, "sql", side_effect=self.execute_query))

	def execute_query(self, query, values=None, **kwargs):
		# Frappe's named parameters use the database driver's placeholder syntax.
		query = re.sub(r"%\((\w+)\)s", r":\1", str(query))
		return [frappe._dict(dict(row)) for row in self.db.execute(query, values or {})]

	def leaves(self, **kwargs):
		return planner.get_leaves("2026-09-01", "2026-09-30", {"company": "MSS"}, **kwargs)

	def test_all_statuses_respect_dates_and_employee_filters_and_normalise_cancellation(self):
		rows = self.leaves(include_all_statuses=True)
		self.assertEqual(set(rows), {"EMP-1"})
		by_name = {row["leave"]: row for row in rows["EMP-1"]}
		self.assertEqual(set(by_name), {"APPROVED", "OPEN", "OLDER-OPEN", "REJECTED", "CANCELLED", "OLD-CANCELLED"})
		self.assertEqual({row["status"] for row in by_name.values()}, {"Open", "Approved", "Rejected", "Cancelled"})
		self.assertEqual(by_name["CANCELLED"]["status"], "Cancelled")
		self.assertEqual(by_name["CANCELLED"]["docstatus"], 2)

	def test_month_query_keeps_approved_submitted_leave_only(self):
		self.assertEqual([row["leave"] for row in self.leaves()["EMP-1"]], ["APPROVED"])

	def test_annual_index_preserves_shifts_with_non_approved_leave(self):
		leaves = self.leaves(include_all_statuses=True)
		shift = {"name": "SHIFT-1", "employee": "EMP-1", "start_date": "2026-09-10", "end_date": "2026-09-13"}
		days, applications, shifts = planner.get_year_employee_event_index(leaves, [shift], "2026-01-01", "2026-12-31")
		self.assertEqual(days["EMP-1"]["2026-09-10"], {"leave": "APPROVED"})
		for day, name in [(11, "OPEN"), (12, "REJECTED"), (13, "CANCELLED")]:
			self.assertEqual(days["EMP-1"][f"2026-09-{day}"], {"leave": name, "shifts": ["SHIFT-1"]})
		self.assertIn("SHIFT-1", shifts)
		self.assertEqual(applications["CANCELLED"]["status"], "Cancelled")

	def test_index_prefers_active_leave_even_if_historical_rows_arrive_first(self):
		leaves = {"EMP-1": [
			{"leave": name, "status": status, "docstatus": docstatus, "from_date": "2026-09-10", "to_date": "2026-09-10"}
			for name, status, docstatus in [("OLD", "Approved", 2), ("DENIED", "Rejected", 1), ("NEW", "Open", 0)]
		]}
		days, _, _ = planner.get_year_employee_event_index(leaves, [], "2026-01-01", "2026-12-31")
		self.assertEqual(days["EMP-1"]["2026-09-10"]["leave"], "NEW")

	def test_both_annual_contracts_request_all_leave_statuses(self):
		for name, result in [
			("get_holidays", {}), ("get_shift_rows", []), ("get_year_day_markers", {}),
			("get_year_timesheet_days", {}), ("get_year_project_rows", []),
			("get_employee_planner_tooltip_details", {}),
		]:
			self.enterContext(patch.object(planner, name, return_value=result))
		for version in (1, 2):
			with self.subTest(contract_version=version):
				data = planner.get_year_events(2026, {"company": "MSS"}, {}, contract_version=version)
				rows = data["events"]["EMP-1"] if version == 1 else data["leave_applications"].values()
				self.assertEqual({row["status"] for row in rows}, {"Open", "Approved", "Rejected", "Cancelled"})
