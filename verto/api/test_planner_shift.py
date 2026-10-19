"""Submitted shift edits retain document validation, permissions and history."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from verto.api import planner_shift


class TestPlannerShiftUpdate(TestCase):
	def setUp(self):
		self.values = dict(name="SHIFT-1", docstatus=1, employee="EMP-1", shift_type="DS",
			start_date="2026-11-01", end_date="2026-11-02", status="Active", modified="revision-one")
		self.fields = {field: frappe._dict(fieldname=field, permlevel=0) for field in planner_shift.EDITABLE_FIELDS}
		self.doc = Mock()
		for field, value in self.values.items():
			setattr(self.doc, field, value)
		self.doc.flags = frappe._dict()
		self.doc.get.side_effect = self.values.get
		def set_value(field, value):
			self.values[field] = value
			setattr(self.doc, field, value)
		self.doc.set.side_effect = set_value
		self.doc.meta.get_field.side_effect = self.fields.get
		self.doc.get_permlevel_access.return_value = [0]
		self.get_doc = self.enterContext(patch.object(frappe, "get_doc", return_value=self.doc))
		self.refresh = self.enterContext(patch.object(planner_shift, "_refresh_link_details"))

	def update(self, values, **kwargs):
		return planner_shift.update("SHIFT-1", expected_modified=kwargs.get("revision", "revision-one"), values=values)

	def test_submitted_fields_use_the_normal_save_and_validation_without_cancelling(self):
		self.update({"employee": "EMP-2", "shift_type": "NS", "shift_location": "LOC-2",
			"start_date": "2026-11-03", "end_date": "", "note": "Changed allocation"})
		self.get_doc.assert_called_once_with("Shift Assignment", "SHIFT-1", for_update=True)
		self.assertEqual([call.args[0] for call in self.doc.check_permission.call_args_list], ["read", "write", "submit"])
		self.assertEqual(self.values["docstatus"], 1)
		self.assertEqual(self.values["name"], "SHIFT-1")
		self.assertEqual(self.values["start_date"], getdate("2026-11-03"))
		self.assertIsNone(self.values["end_date"])
		self.assertTrue(self.doc.flags.ignore_validate_update_after_submit)
		self.doc.run_method.assert_called_once_with("validate")
		self.doc.save.assert_called_once_with(ignore_version=False)
		self.doc.cancel.assert_not_called()
		self.refresh.assert_called_once_with(self.doc, ["employee", "shift_type"])

	def test_json_payloads_and_clearing_fields_are_supported(self):
		self.update('{"shift_location":"","custom_project":"","custom_project_designation":"","note":""}')
		self.assertEqual(self.values["shift_location"], "")
		self.assertEqual(self.values["note"], "")
		self.doc.save.assert_called_once()

	def test_all_permissions_are_checked_before_any_changes(self):
		for denied in ("read", "write", "submit"):
			with self.subTest(denied=denied):
				def permission(perm):
					if perm == denied:
						raise frappe.PermissionError
				self.doc.check_permission.side_effect = permission
				with self.assertRaises(frappe.PermissionError):
					self.update({"shift_location": "LOC-2"})
		self.doc.set.assert_not_called()
		self.doc.save.assert_not_called()

	def test_stale_and_missing_revisions_cannot_overwrite_another_edit(self):
		for revision in ("old-revision", None, ""):
			with self.subTest(revision=revision), self.assertRaises(frappe.TimestampMismatchError):
				self.update({"shift_location": "LOC-2"}, revision=revision)
		self.doc.set.assert_not_called()
		self.doc.save.assert_not_called()

	def test_only_editor_fields_and_scalar_values_are_accepted(self):
		for values in (["shift_location"], None, {"docstatus": "0"}, {"company": "Other"},
			{"shift_schedule_assignment": "SCHEDULE-2"}, {"flags": "ignore_permissions"},
			{"note": {"value": "Nested payload"}}, {"employee": ["EMP-2"]}):
			with self.subTest(values=values), self.assertRaises((frappe.ValidationError, frappe.PermissionError)):
				self.update(values)
		self.doc.set.assert_not_called()
		self.doc.save.assert_not_called()

	def test_higher_field_permission_levels_are_not_bypassed(self):
		self.fields["note"].permlevel = 1
		with patch.object(frappe, "session", SimpleNamespace(user="planner@example.test")):
			with self.assertRaises(frappe.PermissionError):
				self.update({"note": "Restricted"})
		self.doc.save.assert_not_called()

	def test_cancelled_shifts_and_invalid_required_values_cannot_be_saved(self):
		self.doc.docstatus = 2
		with self.assertRaises(frappe.ValidationError):
			self.update({"shift_location": "LOC-2"})
		self.doc.docstatus = 1
		for values in ({"employee": ""}, {"shift_type": ""}, {"start_date": ""}, {"status": "Cancelled"}):
			original = self.values.copy()
			with self.subTest(values=values), self.assertRaises(frappe.ValidationError):
				self.update(values)
			for field, value in original.items():
				self.doc.set(field, value)
		self.doc.save.assert_not_called()

	def test_validation_failures_prevent_saving_and_drafts_use_the_regular_lifecycle(self):
		self.doc.run_method.side_effect = frappe.ValidationError("Overlapping shifts")
		with self.assertRaises(frappe.ValidationError):
			self.update({"shift_type": "NS"})
		self.doc.save.assert_not_called()
		self.doc.docstatus = 0
		self.doc.flags.clear()
		self.doc.run_method.reset_mock()
		self.update({"note": "Draft note"})
		self.assertFalse(self.doc.flags.get("ignore_validate_update_after_submit"))
		self.doc.run_method.assert_not_called()
		self.doc.save.assert_called_once_with(ignore_version=False)


class TestPlannerShiftLinkDetails(TestCase):
	def test_changed_links_refresh_fetch_if_empty_fields_and_cleared_links_clear_details(self):
		fields = [frappe._dict(fieldname="custom_project_name", fetch_from="custom_project.project_name", fetch_if_empty=1),
			frappe._dict(fieldname="custom_color", fetch_from="custom_project.color", fetch_if_empty=1)]
		doc = Mock()
		doc.meta.get_fields_to_fetch.return_value = fields
		doc.meta.get_field.return_value = frappe._dict(options="Project")
		doc.get.return_value = "PROJECT-2"
		with patch.object(frappe.db, "get_value", return_value={"project_name": "New project", "color": "#123456"}) as query:
			planner_shift._refresh_link_details(doc, ["custom_project"])
			query.assert_called_once_with("Project", "PROJECT-2", ["project_name", "color"], as_dict=True)
		self.assertEqual([call.args for call in doc.set.call_args_list], [("custom_project_name", "New project"), ("custom_color", "#123456")])
		doc.get.return_value = ""
		doc.set.reset_mock()
		planner_shift._refresh_link_details(doc, ["custom_project"])
		self.assertEqual([call.args for call in doc.set.call_args_list], [("custom_project_name", None), ("custom_color", None)])


class TestPlannerShiftIntegration(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.suffix = frappe.generate_hash(length=8)
		def record(doctype, prefix, **values):
			doc = frappe.get_doc(dict(doctype=doctype, name=f"SHIFT-EDIT-{prefix}-{self.suffix}", **values))
			doc.db_insert()
			return doc
		self.company = record("Company", "CO", company_name="Planner shift edit", abbr=self.suffix, default_currency="AUD")
		self.employee = record("Employee", "EMP", employee_name="First employee", first_name="First", company=self.company.name, status="Active")
		self.other_company = record("Company", "CO2", company_name="Other shift company", abbr="X" + self.suffix, default_currency="AUD")
		self.other_employee = record("Employee", "EMP2", employee_name="Second employee", first_name="Second", company=self.other_company.name, status="Active")
		self.shift_type = record("Shift Type", "DS", start_time="06:00:00", end_time="18:00:00")
		self.other_shift_type = record("Shift Type", "NS", start_time="18:00:00", end_time="06:00:00")
		self.location = record("Shift Location", "LOC")
		self.other_location = record("Shift Location", "LOC2")
		self.project = record("Project", "PROJ", project_name="First project", color="#112233")
		self.other_project = record("Project", "PROJ2", project_name="Second project", color="#445566")
		self.designation = record("Designation", "ROLE", designation_name="Shift advisor")
		self.assignment = frappe.get_doc(dict(doctype="Shift Assignment", employee=self.employee.name,
			company=self.company.name, shift_type=self.shift_type.name, shift_location=self.location.name,
			start_date="2026-11-01", end_date="2026-11-02", custom_project=self.project.name, status="Active"))
		self.assignment.insert().submit()

	def update(self, values):
		return planner_shift.update(self.assignment.name, str(self.assignment.modified), values)

	def test_location_edit_keeps_submitted_identity_history_and_field_configuration(self):
		df = self.assignment.meta.get_field("shift_location")
		with patch.object(df, "allow_on_submit", 0):
			self.update({"shift_location": self.other_location.name})
			self.assertEqual(df.allow_on_submit, 0)
		self.assignment.reload()
		self.assertEqual(self.assignment.shift_location, self.other_location.name)
		self.assertEqual(self.assignment.docstatus, 1)
		versions = frappe.get_all("Version", filters={"ref_doctype": "Shift Assignment", "docname": self.assignment.name}, pluck="data")
		self.assertTrue(any("shift_location" in data and self.other_location.name in data for data in versions))

	def test_all_assignment_fields_and_their_fetched_details_persist(self):
		self.update(dict(employee=self.other_employee.name, shift_type=self.other_shift_type.name,
			start_date="2026-11-03", end_date="2026-11-04", shift_location=self.other_location.name,
			custom_project=self.other_project.name, custom_project_designation=self.designation.name,
			status="Inactive", note="Reallocated to night shift"))
		self.assignment.reload()
		self.assertEqual(self.assignment.docstatus, 1)
		self.assertEqual(self.assignment.employee, self.other_employee.name)
		self.assertEqual(self.assignment.employee_name, "Second employee")
		self.assertEqual(self.assignment.company, self.other_company.name)
		self.assertEqual(self.assignment.shift_type, self.other_shift_type.name)
		self.assertEqual(self.assignment.start_date, getdate("2026-11-03"))
		self.assertEqual(self.assignment.end_date, getdate("2026-11-04"))
		self.assertEqual(self.assignment.shift_location, self.other_location.name)
		self.assertEqual(self.assignment.custom_project, self.other_project.name)
		self.assertEqual(self.assignment.custom_project_name, "Second project")
		self.assertEqual(self.assignment.custom_color, "#445566")
		self.assertEqual(self.assignment.custom_project_designation, self.designation.name)
		self.assertEqual(self.assignment.status, "Inactive")
		self.assertEqual(self.assignment.note, "Reallocated to night shift")

	def test_hrms_rejects_reversed_dates_overlaps_and_missing_links(self):
		conflict = frappe.copy_doc(self.assignment)
		conflict.start_date, conflict.end_date = "2026-11-03", "2026-11-04"
		conflict.insert().submit()
		for values in ({"end_date": "2026-10-31"}, {"start_date": "2026-11-03", "end_date": "2026-11-04"},
			{"shift_location": "MISSING-LOCATION-" + self.suffix}):
			with self.subTest(values=values), self.assertRaises(frappe.ValidationError):
				self.update(values)
			self.assignment.reload()
			self.assertEqual(self.assignment.start_date, getdate("2026-11-01"))
			self.assertEqual(self.assignment.end_date, getdate("2026-11-02"))
			self.assertEqual(self.assignment.shift_location, self.location.name)
