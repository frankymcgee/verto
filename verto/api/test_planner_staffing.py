"""Project requirement persistence and project-specific shift role regressions."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe

from verto.api import planner, planner_staffing as staffing


def requirement(shift="DS", designation="Advisor", required=2):
	return {"shift": shift, "designation": designation, "required_personnel": required}


class RequirementRow(dict):
	def as_dict(self):
		return dict(self)


class TestPlannerStaffing(TestCase):
	def setUp(self):
		self.meta = SimpleNamespace(has_field=lambda field: True)
		self.enterContext(patch.object(frappe, "get_meta", return_value=self.meta))
		self.get_all = self.enterContext(patch.object(frappe, "get_all", return_value=["Advisor", "Labour"]))
		self.enterContext(patch.object(frappe.db, "exists", return_value=True))
		self.enterContext(patch.object(frappe.db, "get_value", return_value="Test company"))
		self.enterContext(patch.object(planner, "publish_scope"))

	def document(self, **values):
		doc = Mock()
		for key, value in values.items():
			setattr(doc, key, value)
		doc.meta = self.meta
		doc.get.side_effect = lambda key, default=None: values.get(key, default)
		doc.set.side_effect = lambda key, value: values.__setitem__(key, value)
		doc.has_permission.return_value = True
		doc.get_doc_before_save.return_value = None
		return doc, values

	def test_requirements_normalise_and_validate_links_in_one_query(self):
		rows = staffing.normalise_requirements([
			requirement(" ds ", " Advisor ", "2"), requirement("NS", "Labour", 3), requirement("NS", "", 1),
		])
		self.assertEqual(rows[0], requirement())
		self.assertIsNone(rows[2]["designation"])
		self.assertEqual(staffing.requirement_totals(rows), {"DS": 2, "NS": 4})
		self.get_all.assert_called_once()

	def test_invalid_requirements_are_rejected(self):
		for rows in [None, {}, [None], [requirement("FI")], [requirement(required=-1)],
			[requirement(required="1.5")], [requirement(designation="Missing")],
			[requirement(), requirement("ds", "advisor")], [requirement()] * 101]:
			with self.subTest(rows=rows), self.assertRaises(frappe.ValidationError):
				staffing.normalise_requirements(rows)

	def test_json_and_blank_designations_are_supported(self):
		self.assertEqual(staffing.normalise_requirements('[{"shift":"DS","required_personnel":0}]'),
			[requirement(designation=None, required=0)])
		self.get_all.assert_not_called()

	def test_desk_validation_derives_totals_and_clearing_rows_resets_them(self):
		rows = [RequirementRow(requirement()), RequirementRow(requirement("NS", "Labour", 3))]
		doc, values = self.document(**{staffing.REQUIREMENTS_FIELD: rows})
		with patch.object(planner, "_project_planner_edit_fields", return_value={"ds_field": "ds_number", "ns_field": "ns_number"}):
			staffing.validate_project_staffing(doc)
			self.assertEqual((values["ds_number"], values["ns_number"]), (2, 3))
			values[staffing.REQUIREMENTS_FIELD] = []
			doc.get_doc_before_save.return_value = frappe._dict({staffing.REQUIREMENTS_FIELD: rows})
			staffing.validate_project_staffing(doc)
			self.assertEqual((values["ds_number"], values["ns_number"]), (0, 0))

	def test_existing_legacy_totals_are_untouched_without_requirement_rows(self):
		doc, values = self.document(ds_number=5, ns_number=4)
		staffing.validate_project_staffing(doc)
		doc.set.assert_not_called()
		self.assertEqual((values["ds_number"], values["ns_number"]), (5, 4))

	def test_planner_save_persists_the_table_and_totals_without_changing_dates(self):
		doc, values = self.document(name="PROJ-1", modified="revision-one",
			expected_start_date="2026-09-01", expected_end_date="2026-09-30")
		with patch.object(frappe, "get_doc", return_value=doc), patch.object(planner, "get_project_planner_details", return_value={}), patch.object(planner, "_project_planner_edit_fields", return_value={"ds_field": "ds_number", "ns_field": "ns_number", "start_date_field": "expected_start_date", "end_date_field": "expected_end_date"}):
			planner.update_project_planner_details("PROJ-1", expected_modified="revision-one",
				personnel_requirements=[requirement(), requirement("NS", "Labour", 3)])
			self.assertEqual(values[staffing.REQUIREMENTS_FIELD], [requirement(), requirement("NS", "Labour", 3)])
			self.assertEqual((values["ds_number"], values["ns_number"]), (2, 3))
			self.assertEqual((values["expected_start_date"], values["expected_end_date"]), ("2026-09-01", "2026-09-30"))
			doc.check_permission.assert_called_once_with("write")
			doc.save.assert_called_once()
			planner.update_project_planner_details("PROJ-1", expected_modified="revision-one", personnel_requirements=[])
			self.assertEqual((values["ds_number"], values["ns_number"]), (0, 0))

	def test_permissions_and_stale_revisions_reject_table_writes(self):
		doc, _ = self.document(name="PROJ-1", modified="revision-two")
		with patch.object(frappe, "get_doc", return_value=doc):
			with self.assertRaises(frappe.ValidationError):
				planner.update_project_planner_details("PROJ-1", expected_modified="revision-one", personnel_requirements=[requirement()])
			doc.check_permission.side_effect = frappe.PermissionError
			with self.assertRaises(frappe.PermissionError):
				planner.update_project_planner_details("PROJ-1", personnel_requirements=[requirement()])
			doc.set.assert_not_called()
			doc.save.assert_not_called()

	def test_role_groups_use_employee_ids_and_exclude_inactive_travel_and_cancelled_shifts(self):
		rows = [{"employee": employee, "employee_name": "Alex", "shift_type": shift,
			staffing.DESIGNATION_FIELD: "Advisor", "status": status, "docstatus": docstatus}
			for employee, shift, status, docstatus in [("EMP-1", "DS", "Active", 1), ("EMP-1", "FG-DS", "Active", 1),
				("EMP-2", "RH-DS-CREW", "Active", 1), ("EMP-3", "DS", "Inactive", 1),
				("EMP-4", "DS", "Active", 2), ("EMP-5", "FI", "Active", 1)]]
		groups = staffing.summarise_staffing(rows, [requirement(), requirement("NS", "Labour", 3)])
		self.assertEqual([person["employee"] for person in groups[0]["personnel"]], ["EMP-1", "EMP-2"])
		self.assertEqual(groups[1]["personnel"], [])
		self.assertEqual(groups[1]["required_personnel"], 3)

	def test_project_details_include_open_ended_shifts_and_derive_totals(self):
		doc, _ = self.document(name="PROJ-1", expected_start_date="2026-09-01", expected_end_date="2026-09-30",
			**{staffing.REQUIREMENTS_FIELD: [requirement()]})
		self.get_all.return_value = [frappe._dict(employee=employee, employee_name=employee, shift_type="DS",
			end_date=end, **{staffing.DESIGNATION_FIELD: "Advisor"})
			for employee, end in [("OPEN-ENDED", None), ("IN-RANGE", "2026-09-14"), ("PAST", "2026-08-31")]]
		data = staffing.project_staffing_details(doc, 10, 20)
		self.assertEqual((data["ds_requested"], data["ns_requested"]), (2, 0))
		self.assertEqual({person["employee"] for person in data["personnel_allocations"][0]["personnel"]}, {"OPEN-ENDED", "IN-RANGE"})
		self.assertEqual(self.get_all.call_args.kwargs["filters"]["start_date"], ["<=", "2026-09-30"])
		self.assertTrue(data["can_update_personnel_requirements"])

	def test_legacy_detail_totals_and_unspecified_assignments_are_kept(self):
		doc, _ = self.document(name="PROJ-1")
		self.get_all.return_value = [frappe._dict(employee="EMP-1", employee_name="Alex", shift_type="NS")]
		data = staffing.project_staffing_details(doc, 2, 3)
		self.assertEqual(data["personnel_requirements"], [])
		self.assertEqual(data["personnel_allocations"][1]["required_personnel"], 3)
		self.assertEqual(data["personnel_allocations"][1]["personnel"][0]["employee"], "EMP-1")

	def test_role_requires_a_project_and_existing_designation(self):
		with self.assertRaises(frappe.ValidationError):
			staffing.validate_designation(None, "Advisor")
		with patch.object(frappe.db, "exists", return_value=False), self.assertRaises(frappe.ValidationError):
			staffing.validate_designation("PROJ-1", "Missing")
		self.assertIsNone(staffing.validate_designation(None, ""))

	def test_shift_creation_stores_role_before_saving(self):
		doc, values = self.document(doctype="Shift Assignment")
		with patch.object(frappe, "new_doc", return_value=doc, create=True):
			planner.create_planner_shift_assignment("EMP-1", "Company", "DS", "2026-09-01", "2026-09-03", "Active",
				custom_project="PROJ-1", custom_project_designation="Advisor")
			self.assertEqual(values[staffing.DESIGNATION_FIELD], "Advisor")
			doc.save.assert_called_once()
			doc.submit.assert_called_once()

	def test_role_is_part_of_adjacent_merge_identity(self):
		def exists(filters):
			return "ADVISOR-BLOCK" if filters[staffing.DESIGNATION_FIELD] == "Advisor" and "end_date" in filters else None
		with patch.object(frappe.db, "exists", side_effect=exists), patch.object(planner, "validate_designation", side_effect=lambda project, role: role), patch.object(frappe.db, "set_value", create=True) as set_value, patch.object(planner, "apply_planner_project_to_shift_assignments"), patch.object(planner, "create_planner_shift_assignment") as create:
			kwargs = dict(employee="EMP-1", company="Company", shift_type="DS", start_date="2026-09-03", end_date="2026-09-03", status="Active", custom_project="PROJ-1")
			planner.insert_shift(**kwargs, custom_project_designation="Advisor")
			create.assert_not_called()
			set_value.assert_called_once_with("Shift Assignment", "ADVISOR-BLOCK", "end_date", "2026-09-03")
			planner.insert_shift(**kwargs, custom_project_designation="Labour")
			self.assertEqual(create.call_args.kwargs[staffing.DESIGNATION_FIELD], "Labour")

	def test_splitting_a_shift_preserves_its_role(self):
		doc, _ = self.document(employee="EMP-1", company="Company", shift_type="DS", start_date="2026-09-01",
			end_date="2026-09-05", status="Active", shift_location="LOC-1", custom_project="PROJ-1",
			**{staffing.DESIGNATION_FIELD: "Advisor"})
		with patch.object(frappe, "get_doc", return_value=doc), patch.object(planner, "create_planner_shift_assignment") as create:
			planner.break_shift("SHIFT-1", "2026-09-03")
			self.assertEqual(create.call_args.kwargs[staffing.DESIGNATION_FIELD], "Advisor")
			self.assertEqual(create.call_args.kwargs["start_date"], "2026-09-04")

	def test_future_schedule_shifts_copy_roles_and_edits_keep_the_selected_role(self):
		doc, values = self.document(shift_schedule_assignment="SCHEDULE-1")
		doc.is_new.return_value = True
		schedule = frappe._dict(custom_project="PROJ-1", **{staffing.DESIGNATION_FIELD: "Advisor"})
		with patch.object(frappe, "get_doc", return_value=schedule) as get_doc:
			staffing.apply_scheduled_staffing(doc)
			self.assertEqual((values["custom_project"], values[staffing.DESIGNATION_FIELD]), ("PROJ-1", "Advisor"))
			doc.is_new.return_value = False
			values[staffing.DESIGNATION_FIELD] = "Labour"
			staffing.apply_scheduled_staffing(doc)
			self.assertEqual(values[staffing.DESIGNATION_FIELD], "Labour")
			get_doc.assert_called_once()

	def test_schedule_background_creation_receives_the_role(self):
		doc, values = self.document(doctype="Shift Schedule Assignment", name="SCHEDULE-1")
		with patch.object(frappe, "new_doc", return_value=doc, create=True), patch.object(planner, "get_or_insert_shift_schedule", return_value="SCHEDULE"), patch.object(frappe, "enqueue", create=True) as enqueue:
			planner.create_shift_schedule_assignment("EMP-1", "Company", "DS", "Active", "2026-09-01", "2027-09-01",
				["Monday"], "Every Week", custom_project="PROJ-1", custom_project_designation="Advisor")
			self.assertEqual(values[staffing.DESIGNATION_FIELD], "Advisor")
			self.assertEqual(enqueue.call_args.kwargs[staffing.DESIGNATION_FIELD], "Advisor")

	def test_annual_project_payload_and_shift_index_keep_role_data(self):
		project = {"project_name": "Project", "expected_start_date": "2026-09-01", "expected_end_date": "2026-09-30",
			"_start_field": "expected_start_date", "_end_field": "expected_end_date", "personnel_requirements": [requirement()]}
		shift = {"name": "SHIFT-1", "employee": "EMP-1", "employee_name": "Alex", "custom_project": "PROJ-1",
			"shift_type": "DS", "start_date": "2026-09-01", "end_date": "2026-09-03", staffing.DESIGNATION_FIELD: "Advisor"}
		with patch.object(planner, "get_project_meta", return_value={"PROJ-1": project}), patch.object(planner, "get_project_task_counts", return_value={}):
			data = planner.get_year_project_rows([shift], "2026-01-01", "2026-12-31", sparse_assignments=True)
			self.assertEqual(data[0]["personnel_requirements"], [requirement()])
			self.assertEqual(data[0]["personnel_allocations"][0]["personnel"], [{"employee": "EMP-1", "employee_name": "Alex"}])
			_, _, shifts = planner.get_year_employee_event_index({}, [shift], "2026-01-01", "2026-12-31")
			self.assertEqual(shifts["SHIFT-1"][staffing.DESIGNATION_FIELD], "Advisor")

	def test_requirement_queries_are_batched_and_scoped_to_projects(self):
		self.get_all.return_value = [frappe._dict(parent="PROJ-1", **requirement())]
		self.assertEqual(staffing.get_project_requirements(["PROJ-1", "PROJ-2"]), {"PROJ-1": [requirement()]})
		self.get_all.assert_called_once()
		self.assertEqual(self.get_all.call_args.kwargs["filters"], {"parent": ["in", ["PROJ-1", "PROJ-2"]],
			"parenttype": "Project", "parentfield": staffing.REQUIREMENTS_FIELD})

	def test_all_rolling_patterns_propagate_roles_including_travel_days(self):
		common = dict(employee="EMP-1", company="Company", status="Active", start_date="2026-09-01", end_date="2026-09-15", custom_project="PROJ-1", custom_project_designation="Advisor")
		for method, options in [(planner.create_rolling_roster_assignment, {"shift_type": "DS", "days_on_site": 4, "days_off_site": 2}),
			(planner.create_dynamic_rolling_roster_assignment, {"shift_type": "DS", "roster_segments": [{"days_on_site": 4, "days_off_site": 2}]}),
			(planner.create_rolling_day_night_roster_assignment, {"days_on_site_ds": 3, "days_on_site_ns": 3, "days_off_site": 2})]:
			with self.subTest(method=method.__name__), patch.object(planner, "insert_shift") as insert:
				method(**common, **options)
				self.assertTrue(insert.call_count)
				self.assertEqual({call.kwargs[staffing.DESIGNATION_FIELD] for call in insert.call_args_list}, {"Advisor"})

	def test_bulk_swaps_preserve_both_project_roles(self):
		source = frappe._dict(name="SOURCE", employee="EMP-1", shift_type="DS", custom_project="PROJ-1", **{staffing.DESIGNATION_FIELD: "Advisor"})
		target = frappe._dict(name="TARGET", employee="EMP-2", shift_type="NS", custom_project="PROJ-2", **{staffing.DESIGNATION_FIELD: "Labour"})
		with patch.object(planner, "_validate_bulk_shift_targets"), patch.object(planner, "_find_shift_assignment_for_date", side_effect=[source, target, source, target]), patch.object(planner, "break_shift"), patch.object(planner, "insert_shift") as insert, patch.object(frappe.db, "savepoint", create=True):
			planner.bulk_move_or_swap_shifts([{"employee": "EMP-1", "date": "2026-09-01", "shift": "SOURCE"}], "EMP-2", "2026-09-02")
			self.assertEqual([call.kwargs[staffing.DESIGNATION_FIELD] for call in insert.call_args_list], ["Advisor", "Labour"])


class TestPlannerStaffingSchema(TestCase):
	def test_migration_installs_a_child_table_and_editable_submitted_shift_role(self):
		self.assertEqual(frappe.get_meta("Project").get_field(staffing.REQUIREMENTS_FIELD).options, staffing.REQUIREMENT_DOCTYPE)
		self.assertTrue(frappe.get_meta(staffing.REQUIREMENT_DOCTYPE).istable)
		self.assertTrue(frappe.get_meta("Shift Assignment").get_field(staffing.DESIGNATION_FIELD).allow_on_submit)
		self.assertEqual(frappe.get_meta("Shift Schedule Assignment").get_field(staffing.DESIGNATION_FIELD).options, "Designation")

	def test_repeated_setup_preserves_existing_custom_field_metadata(self):
		filters = {"dt": "Project", "fieldname": staffing.REQUIREMENTS_FIELD}
		before = frappe.db.get_value("Custom Field", filters, ["name", "modified", "label"])
		staffing.ensure_staffing_fields()
		self.assertEqual(frappe.db.get_value("Custom Field", filters, ["name", "modified", "label"]), before)
