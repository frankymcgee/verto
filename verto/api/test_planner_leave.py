"""Leave visibility, scheduling and in-planner editing regressions."""

import re
import sqlite3
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe

from verto.api import planner, planner_leave


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


class TestPlannerLeaveDialog(TestCase):
	def setUp(self):
		self.permissions = {"read", "write", "submit", "cancel"}
		self.levels = {"read": [0, 1], "write": [0, 1]}
		self.fields = [frappe._dict(field) for field in [
			{"fieldname": "employee", "fieldtype": "Link", "options": "Employee"},
			{"fieldname": "from_date", "fieldtype": "Date"},
			{"fieldname": "to_date", "fieldtype": "Date"},
			{"fieldname": "description", "fieldtype": "Small Text"},
			{"fieldname": "status", "fieldtype": "Select", "permlevel": 1},
			{"fieldname": "follow_via_email", "fieldtype": "Check", "allow_on_submit": 1},
			{"fieldname": "total_leave_days", "fieldtype": "Float", "read_only": 1},
			{"fieldname": "private_note", "fieldtype": "Data", "permlevel": 2},
			{"fieldname": "password", "fieldtype": "Password"},
			{"fieldname": "workflow_state", "fieldtype": "Data"},
		]]
		self.doc = Mock(doctype="Leave Application", name="LEAVE-1", modified="2026-09-29 12:00:00", docstatus=0)
		# Mock's name constructor parameter is diagnostic, not a document field.
		self.doc.name = "LEAVE-1"
		for df in self.fields:
			setattr(self.doc, df.fieldname, None)
		self.doc.employee = "EMP-1"
		self.doc.from_date = "2026-09-10"
		self.doc.to_date = "2026-09-12"
		self.doc.status = "Open"
		self.doc.description = "Original reason"
		self.doc.private_note = "Restricted"
		self.doc.workflow_state = "Pending"
		self.doc.meta.fields = self.fields
		self.doc.meta.get_field.side_effect = lambda name: next((df for df in self.fields if df.fieldname == name), None)
		self.doc.get.side_effect = lambda name, default=None: getattr(self.doc, name, default)
		self.doc.set.side_effect = lambda name, value: setattr(self.doc, name, value)
		self.doc.as_dict.side_effect = lambda: {key: getattr(self.doc, key) for key in [
			"doctype", "name", "modified", "docstatus", *[df.fieldname for df in self.fields],
		]}
		self.doc.has_permission.side_effect = lambda permission: permission in self.permissions
		self.doc.get_permlevel_access.side_effect = lambda permission: self.levels[permission]
		def check_permission(permission):
			if permission not in self.permissions:
				raise frappe.PermissionError(permission)
		self.doc.check_permission.side_effect = check_permission
		self.get_doc = self.enterContext(patch.object(frappe, "get_doc", return_value=self.doc))
		self.enterContext(patch.object(frappe, "session", frappe._dict(user="planner@example.com")))
		self.enterContext(patch.object(frappe, "get_roles", return_value=["Leave Approver"]))
		self.workflow = self.enterContext(patch.object(planner_leave, "_workflow", return_value=None))

	def update(self, **kwargs):
		return planner_leave.update(self.doc.name, kwargs.pop("expected_modified", self.doc.modified), **kwargs)

	def assert_no_write(self):
		for method in (self.doc.save, self.doc.submit, self.doc.cancel):
			method.assert_not_called()

	def enable_workflow(self, role="Leave Approver"):
		self.workflow.return_value = frappe._dict(workflow_state_field="workflow_state", states=[
			frappe._dict(state="Pending", allow_edit=role),
		])

	def test_read_and_field_permissions_are_applied_before_returning_values(self):
		self.permissions.remove("read")
		with self.assertRaises(frappe.PermissionError):
			planner_leave.get_details("LEAVE-1")
		self.permissions.add("read")
		self.levels["write"] = [0]
		data = planner_leave.get_details("LEAVE-1")
		fields = {df["fieldname"]: df for df in data["fields"]}
		self.assertNotIn("private_note", fields)
		self.assertNotIn("private_note", data["values"])
		self.assertNotIn("password", data["values"])
		self.assertTrue(fields["status"]["read_only"])
		self.assertTrue(fields["total_leave_days"]["read_only"])
		self.assertFalse(fields["description"]["read_only"])
		self.doc.apply_fieldlevel_read_permissions.assert_called_once()
		self.assertEqual(data["values"]["from_date"], "2026-09-10")
		self.assertEqual(data["modified"], self.doc.modified)

	def test_save_updates_same_document_and_can_clear_optional_values(self):
		self.assertEqual(self.update(values={"description": "", "follow_via_email": True}), {"name": "LEAVE-1"})
		self.get_doc.assert_called_once_with("Leave Application", "LEAVE-1", for_update=True)
		self.assertIsNone(self.doc.description)
		self.assertEqual(self.doc.follow_via_email, 1)
		self.assertEqual((self.doc.from_date, self.doc.to_date), ("2026-09-10", "2026-09-12"))
		self.doc.save.assert_called_once_with()
		self.doc.submit.assert_not_called()

	def test_stale_or_missing_revision_and_read_only_fields_never_write(self):
		for revision in ("older revision", "", None):
			with self.subTest(revision=revision), self.assertRaises(frappe.TimestampMismatchError):
				self.update(expected_modified=revision, values={"description": "Changed"})
		with self.assertRaises(frappe.TimestampMismatchError):
			planner_leave.update(self.doc.name, values={"description": "Changed"})
		for fieldname in ("name", "docstatus", "total_leave_days", "private_note", "password"):
			with self.subTest(fieldname=fieldname), self.assertRaises(frappe.PermissionError):
				self.update(values={fieldname: "Changed"})
		self.assert_no_write()

	def test_status_and_save_require_the_appropriate_permissions(self):
		self.permissions.remove("submit")
		with self.assertRaises(frappe.PermissionError):
			self.update(values={"status": "Approved"})
		self.permissions.remove("write")
		self.assertFalse(planner_leave.get_details("LEAVE-1")["can_write"])
		with self.assertRaises(frappe.PermissionError):
			self.update(values={})
		self.assert_no_write()

	def test_submitted_records_only_accept_fields_allowed_after_submission(self):
		self.doc.docstatus = 1
		data = planner_leave.get_details("LEAVE-1")
		self.assertFalse(data["can_submit"])
		self.assertTrue(data["can_cancel"])
		for fieldname in ("from_date", "to_date", "description", "status"):
			with self.subTest(fieldname=fieldname), self.assertRaises(frappe.PermissionError):
				self.update(values={fieldname: "Changed"})
		self.assert_no_write()
		self.update(values={"follow_via_email": False})
		self.assertEqual(self.doc.follow_via_email, 0)
		self.doc.save.assert_called_once_with()

	def test_submit_and_cancel_delegate_to_the_normal_document_lifecycle(self):
		self.permissions.remove("submit")
		with self.assertRaises(frappe.PermissionError):
			self.update(action="submit")
		self.permissions.add("submit")
		with self.assertRaises(frappe.ValidationError):
			self.update(action="cancel")
		self.assert_no_write()
		self.update(action="submit", values={"status": "Approved"})
		self.doc.submit.assert_called_once_with()
		self.assertEqual(self.doc.status, "Approved")
		self.doc.docstatus = 1
		with self.assertRaises(frappe.ValidationError):
			self.update(action="submit")
		self.permissions.remove("cancel")
		with self.assertRaises(frappe.PermissionError):
			self.update(action="cancel")
		self.doc.cancel.assert_not_called()
		self.permissions.add("cancel")
		self.update(action="cancel")
		self.doc.cancel.assert_called_once_with()

	def test_cancelled_documents_are_view_only_and_cannot_be_cancelled_by_status(self):
		with self.assertRaises(frappe.ValidationError):
			self.update(values={"status": "Cancelled"})
		self.doc.docstatus = 2
		data = planner_leave.get_details("LEAVE-1")
		self.assertEqual(data["status"], "Cancelled")
		self.assertFalse(data["can_write"] or data["can_submit"] or data["can_cancel"])
		for action in ("save", "submit", "cancel", "workflow"):
			with self.subTest(action=action), self.assertRaises(frappe.ValidationError):
				self.update(action=action)
		self.assert_no_write()

	def test_workflow_state_roles_and_actions_cannot_be_bypassed(self):
		self.enable_workflow(role="HR Manager")
		with patch.object(planner_leave, "get_transitions", return_value=[]):
			data = planner_leave.get_details("LEAVE-1")
		self.assertFalse(data["can_write"] or data["can_submit"] or data["can_cancel"])
		for action in ("submit", "cancel"):
			with self.subTest(action=action), self.assertRaises(frappe.ValidationError):
				self.update(action=action)
		for values in ({"status": "Approved"}, {"workflow_state": "Approved"}, {"description": "Changed"}):
			with self.subTest(values=values), self.assertRaises(frappe.PermissionError):
				self.update(values=values)
		self.assert_no_write()

	def test_workflow_filters_self_approval_and_applies_changes_before_transition(self):
		self.enable_workflow()
		with patch.object(planner_leave, "get_transitions", return_value=[
			frappe._dict(action="Approve"), frappe._dict(action="Forbidden"),
		]), patch.object(planner_leave, "has_approval_access", side_effect=[True, False]):
			self.assertEqual(planner_leave.get_details("LEAVE-1")["workflow_actions"], ["Approve"])
		with patch.object(planner_leave, "apply_workflow") as apply:
			calls = Mock()
			calls.attach_mock(self.doc.save, "save")
			calls.attach_mock(apply, "transition")
			self.update(action="workflow", workflow_action="Approve", values={"description": "Ready"})
			self.assertEqual([call[0] for call in calls.mock_calls], ["save", "transition"])
			self.assertEqual(apply.call_args.args[0]["description"], "Ready")
			self.assertEqual(apply.call_args.args[1], "Approve")

	def test_link_search_uses_record_permissions_without_requiring_create(self):
		with patch.object(frappe, "has_permission", return_value=False) as permission, \
			patch.object(frappe, "get_meta", return_value=self.doc.meta), \
			patch.object(frappe.db, "exists", return_value=True), \
			patch.object(planner, "search_link", return_value=[{"value": "EMP-2"}]) as search:
			options = planner.search_leave_application_link_options("Employee", fieldname="employee", name="LEAVE-1")
			self.assertEqual(options[0]["value"], "EMP-2")
			permission.assert_not_called()
			search.assert_called_once()
		for fieldname, doctype in (("employee", "User"), ("total_leave_days", "Employee")):
			with self.subTest(fieldname=fieldname), self.assertRaises(frappe.PermissionError):
				planner_leave.check_link_field_permission("LEAVE-1", fieldname, doctype)
		self.doc.docstatus = 1
		with self.assertRaises(frappe.PermissionError):
			planner_leave.check_link_field_permission("LEAVE-1", "employee", "Employee")
