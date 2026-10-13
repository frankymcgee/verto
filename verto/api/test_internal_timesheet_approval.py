"""Internal review, shift validation, permission and atomic signing regressions."""

import copy
from datetime import datetime
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase

from verto.api import internal_timesheet_approval as internal
from verto.api import timesheet_signing as signing

SIGNATURE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j9uoAAAAASUVORK5CYII="


class Document(frappe._dict):
    def __init__(self, **values):
        super().__init__(values)
        object.__setattr__(self, "writes", [])
        object.__setattr__(self, "check_permission", Mock())

    def as_dict(self):
        return dict(self)

    def db_set(self, values):
        self.writes.append(copy.deepcopy(values))
        self.update(values)


def timesheet(name="TS-1", employee="EMP-1", employee_name="Advisor", shift="FG-DS", start="06:00:00", end="18:00:00", **overrides):
    night = shift.endswith("NS")
    values = dict(name=name, employee=employee, employee_name=employee_name, parent_project="PROJ-1", project_name="Shutdown",
                  custom_monday_date="2026-10-05", custom_sunday_date="2026-10-11", start_date="2026-10-05", role="Advisor",
                  total_hours=12, internal_approved=0, docstatus=0, modified="2026-10-12 10:00:00",
                  custom_client_signed=1, custom_client_signature="CLIENT-ORIGINAL", time_logs=[frappe._dict(
                      idx=1, from_time=f"2026-10-05 {start}", to_time=f"2026-10-{'06' if night else '05'} {end}",
                      hours=12, billing_hours=12, project="PROJ-1", shift_type=shift, description="Job complete", daily_timesheet_id="DAILY-" + name,
                  )])
    values.update(overrides)
    return Document(**values)


def context(docs):
    result = dict(employees={}, user_names={}, daily={}, shifts=[], types={}, projects={"PROJ-1": frappe._dict(name="PROJ-1", max_ds_hrs=12, max_ns_hrs=13, max_fly_hrs=8)})
    for doc in docs:
        log = doc.time_logs[0]
        result["employees"][doc.employee] = frappe._dict(name=doc.employee, employee_name=doc.employee_name, user_id=doc.employee + "@example.test")
        result["daily"][log.daily_timesheet_id] = frappe._dict(name=log.daily_timesheet_id, current_user=doc.employee_name, project_id="PROJ-1", date="2026-10-05",
                                                             start_time=str(log.from_time)[11:], end_time=str(log.to_time)[11:], duration=43200, comments="Job complete",
                                                             shift_allocation="SHIFT-" + doc.name, docstatus=0)
        result["shifts"].append(frappe._dict(name="SHIFT-" + doc.name, employee=doc.employee, custom_project="PROJ-1", start_date="2026-10-05",
                                           end_date="2026-10-05", status="Active", docstatus=1, shift_type=log.shift_type))
        result["types"][log.shift_type] = frappe._dict(name=log.shift_type, start_time=str(log.from_time)[11:], end_time=str(log.to_time)[11:])
    return result


class TestInternalValidation(TestCase):
    def setUp(self):
        self.doc = timesheet()
        self.context = context([self.doc])
        self.enterContext(patch.object(frappe, "has_permission", return_value=True))

    def row(self):
        return internal.build_review([self.doc], self.context)["groups"][0]["rows"][0]

    def codes(self):
        row = self.row()
        return {flag["code"] for flag in row["flags"] + [flag for entry in row["entries"] for flag in entry["flags"]]}

    def test_correct_day_and_overnight_shifts_are_clean_and_show_daily_comments(self):
        self.assertEqual(self.row()["flag_count"], 0)
        night = timesheet(shift="FG-NS", start="18:00:00", end="06:00:00")
        row = internal.build_review([night], context([night]))["groups"][0]["rows"][0]
        self.assertEqual(row["flag_count"], 0)
        self.assertEqual(row["days"]["2026-10-05"]["ns"], 12)
        self.assertEqual(row["entries"][0]["daily_comments"], "Job complete")

    def test_document_time_logs_classify_day_and_overnight_hours(self):
        for shift, start, end, expected in (("FG-DS", "06:00:00", "18:00:00", "DS"), ("FG-NS", "18:00:00", "06:00:00", "NS")):
            with self.subTest(shift=shift):
                doc = timesheet(shift=shift, start=start, end=end)
                loaded = context([doc])
                values = dict(doc.time_logs[0])
                # Frappe child documents expose get()/attributes, not [] access.
                doc.time_logs = [SimpleNamespace(**values, get=values.get)]
                row = internal.build_review([doc], loaded)["groups"][0]["rows"][0]
                self.assertEqual(row["entries"][0]["elapsed_hours"], 12)
                self.assertEqual(row["entries"][0]["recorded_shift"], expected)
                self.assertEqual(row["flag_count"], 0)
                self.assertEqual(row["missing_days"], [])

    def test_both_directions_of_opposite_shift_allocation_are_flagged(self):
        for allocated, declared, start, end in (("FG-NS", "FG-DS", "06:00:00", "18:00:00"), ("FG-DS", "FG-NS", "18:00:00", "06:00:00")):
            self.doc = timesheet(shift=declared, start=start, end=end)
            self.context = context([self.doc])
            self.context["shifts"][0].shift_type = allocated
            self.assertTrue({"allocation_time_mismatch", "allocation_label_mismatch"} <= self.codes())

    def test_typed_ds_label_does_not_hide_night_hours_against_day_allocation(self):
        self.doc.time_logs[0].from_time = "2026-10-05 18:00:00"
        self.doc.time_logs[0].to_time = "2026-10-06 06:00:00"
        self.assertTrue({"declared_shift_mismatch", "allocation_time_mismatch"} <= self.codes())

    def test_start_time_cutoff_is_exactly_1630(self):
        for start, expected in (("16:29:59", "DS"), ("16:30:00", "NS")):
            self.doc.time_logs[0].from_time = "2026-10-05 " + start
            self.assertEqual(self.row()["entries"][0]["recorded_shift"], expected)

    def test_claimed_elapsed_daily_and_weekly_totals_are_checked_separately(self):
        self.doc.time_logs[0].hours = 14
        codes = self.codes()
        self.assertTrue({"duration_mismatch", "daily_hours_mismatch", "total_mismatch", "hours_exceeded"} <= codes)

    def test_split_entries_cannot_bypass_the_project_daily_maximum(self):
        self.doc.time_logs = [frappe._dict(idx=1, from_time="2026-10-05 04:00", to_time="2026-10-05 10:00", hours=6, shift_type="DS", project="PROJ-1"),
                              frappe._dict(idx=2, from_time="2026-10-05 10:00", to_time="2026-10-05 18:00", hours=8, shift_type="DS", project="PROJ-1")]
        self.doc.total_hours = 14
        entries = self.row()["entries"]
        self.assertTrue(all("hours_exceeded" in {flag["code"] for flag in row["flags"]} for row in entries))
        self.assertFalse(any("overlap" in {flag["code"] for flag in row["flags"]} for row in entries))

    def test_even_one_second_over_maximum_is_flagged_but_zero_is_unconfigured(self):
        self.doc.time_logs[0].hours += 1 / 3600
        self.assertIn("hours_exceeded", self.codes())
        for maximum in (0, None, -1):
            self.context["projects"]["PROJ-1"]["max_ds_hrs"] = maximum
            self.assertNotIn("hours_exceeded", self.codes())

    def test_invalid_zero_negative_nonfinite_and_backwards_hours_are_flagged(self):
        for hours in (0, -1, float("nan"), "invalid"):
            self.doc.time_logs[0].hours = hours
            self.assertIn("invalid_hours", self.codes())
        self.doc.time_logs[0].hours = 12
        self.doc.time_logs[0].to_time = "2026-10-05 05:00:00"
        self.assertIn("invalid_times", self.codes())

    def test_wrong_daily_identity_hides_its_comments_and_link(self):
        self.context["daily"]["DAILY-TS-1"].current_user = "Someone Else"
        row = self.row()["entries"][0]
        self.assertIn("daily_identity_mismatch", {flag["code"] for flag in row["flags"]})
        self.assertEqual(row["daily_comments"], "")
        self.assertEqual(row["daily_timesheet"], "")

    def test_missing_cancelled_wrong_project_and_ambiguous_allocations_are_flagged(self):
        self.context["shifts"] = []
        self.assertIn("invalid_allocation", self.codes())
        self.context = context([self.doc])
        self.context["shifts"][0].docstatus = 2
        self.assertIn("invalid_allocation", self.codes())
        self.context["shifts"][0].docstatus = 1
        self.context["shifts"][0].custom_project = "PROJ-2"
        self.assertIn("invalid_allocation", self.codes())
        self.context = context([self.doc])
        self.context["daily"]["DAILY-TS-1"].shift_allocation = ""
        self.context["shifts"].append(frappe._dict(dict(self.context["shifts"][0]), name="OTHER"))
        self.assertIn("ambiguous_allocation", self.codes())

    def test_fly_maximum_and_prefixed_shift_names_are_supported(self):
        self.doc.time_logs[0].shift_type = "RH-FI"
        self.context["shifts"][0].shift_type = "RH-FI"
        self.assertIn("hours_exceeded", self.codes())
        self.assertNotIn("allocation_time_mismatch", self.codes())
        for label, expected in (("FG_DS", "DS"), ("RH NS", "NS"), ("Day Shift", "DS"), ("Fly-out", "Fly"), ("FG-U", "Unavailable")):
            self.assertEqual(internal.shift_kind(label), expected)

    def test_ongoing_allocations_and_daily_comment_changes_are_reviewed(self):
        self.context["shifts"][0].end_date = None
        self.assertNotIn("invalid_allocation", self.codes())
        self.assertIn("missing_hours", self.codes())
        self.context["daily"]["DAILY-TS-1"].comments = "New comment"
        self.assertIn("daily_comments_mismatch", self.codes())

    def test_overlapping_entries_in_separate_timesheets_are_flagged(self):
        other = timesheet(name="TS-2")
        data = internal.build_review([self.doc, other], context([self.doc, other]))
        self.assertTrue(all(any(flag["code"] == "overlap" for entry in row["entries"] for flag in entry["flags"]) for row in data["groups"][0]["rows"]))

    def test_past_missing_days_are_flagged_but_future_shifts_and_exclusions_are_skipped(self):
        self.context["shifts"][0].end_date = "2026-10-07"
        with patch.object(internal, "now_datetime", return_value=datetime(2026, 10, 6, 18, 59)):
            self.assertNotIn("missing_hours", self.codes())
        with patch.object(internal, "now_datetime", return_value=datetime(2026, 10, 6, 19)):
            self.assertEqual(self.row()["missing_days"][0]["date"], "2026-10-06")
        self.context["exclusions"] = {"2026-10-06": {("emp-1@example.test", "proj-1")}, "2026-10-07": {("emp-1@example.test", "proj-1")}}
        self.assertNotIn("missing_hours", self.codes())
        self.context["exclusions"] = {}
        self.context["leave"] = {"2026-10-06": {"EMP-1"}, "2026-10-07": {"EMP-1"}}
        self.assertNotIn("missing_hours", self.codes())


class TestInternalBulkApproval(TestCase):
    def setUp(self):
        self.docs = [timesheet(), timesheet(name="TS-2", employee="EMP-2", employee_name="Supervisor", shift="FG-NS", start="18:00:00", end="06:00:00", docstatus=1)]
        self.context = context(self.docs)
        self.audit = []
        self.enterContext(patch.object(frappe, "session", SimpleNamespace(user="manager@example.test")))
        self.roles = self.enterContext(patch.object(frappe, "get_roles", return_value=["HR Manager"]))
        self.enterContext(patch.object(frappe, "has_permission", return_value=True))
        self.enterContext(patch.object(frappe.db, "get_value", return_value="Office Manager"))
        self.enterContext(patch.object(internal, "_load_context", side_effect=lambda docs: self.context))
        self.get_doc = self.enterContext(patch.object(frappe, "get_doc", side_effect=self.lookup))
        self.enterContext(patch.object(frappe.db, "savepoint", side_effect=self.savepoint))
        self.rollback = self.enterContext(patch.object(frappe.db, "rollback", side_effect=self.restore))
        self.commit = self.enterContext(patch.object(frappe.db, "commit"))

    def lookup(self, doctype, name=None, **kwargs):
        if isinstance(doctype, dict):
            audit = Mock(name="audit")
            audit.name = "AUDIT-1"
            audit.insert.side_effect = lambda **kw: self.audit.append(doctype) or audit
            return audit
        return next(doc for doc in self.docs if doc.name == name)

    def savepoint(self, name):
        self.before = [copy.deepcopy(dict(doc)) for doc in self.docs]
        self.audit_before = list(self.audit)

    def restore(self, **kwargs):
        for doc, old in zip(self.docs, self.before):
            doc.clear(); doc.update(old)
        self.audit = self.audit_before

    def selections(self):
        data = internal.build_review(self.docs, self.context)
        return [{"name": row["name"], "review_hash": row["review_hash"]} for group in data["groups"] for row in group["rows"]]

    def approve(self, selected=None, **values):
        return internal.approve_internal_timesheets(selected or self.selections(), SIGNATURE, **values)

    def test_one_typed_signature_approves_drafts_and_submitted_without_client_changes(self):
        result = self.approve(signature_mode="type", full_name="Office Manager")
        self.assertEqual(result["approved"], ["TS-1", "TS-2"])
        self.assertEqual(len(self.audit), 1)
        self.assertEqual(self.audit[0]["signature_mode"], "type")
        for doc, status in zip(self.docs, (0, 1)):
            self.assertEqual(doc.docstatus, status)
            self.assertEqual(doc.employee_approved, "manager@example.test")
            self.assertEqual(doc.custom_client_signature, "CLIENT-ORIGINAL")
            doc.check_permission.assert_any_call("read")
            doc.check_permission.assert_any_call("write")
        self.commit.assert_not_called()
        self.assertTrue(all(call.kwargs["for_update"] for call in self.get_doc.call_args_list if isinstance(call.args[0], str)))

    def test_flagged_timesheets_need_acknowledgment_and_recorded_reason(self):
        self.docs[0].time_logs[0].hours = 14
        for values in ({}, {"acknowledge_flags": 1}, {"review_note": "Verified"}):
            with self.assertRaises(frappe.ValidationError):
                self.approve(**values)
            self.assertFalse(self.docs[0].internal_approved)
        self.approve(acknowledge_flags=1, review_note="Overtime checked with project supervisor")
        self.assertEqual(self.audit[0]["review_note"], "Overtime checked with project supervisor")

    def test_changed_times_hours_comments_or_allocations_require_new_review(self):
        selected = self.selections()
        self.context["daily"]["DAILY-TS-1"].comments = "Edited while reviewing"
        with self.assertRaises(frappe.ValidationError):
            self.approve(selected)
        self.assertFalse(self.docs[1].internal_approved)
        self.assertFalse(self.audit)

    def test_only_selected_records_are_signed_and_cross_checks_use_full_review_scope(self):
        selected = self.selections()[:1]
        self.approve(selected, review_timesheets=[doc.name for doc in self.docs])
        self.assertTrue(self.docs[0].internal_approved)
        self.assertFalse(self.docs[1].internal_approved)

    def test_existing_internal_signature_is_preserved(self):
        self.docs[0].update(internal_approved=1, approved_signature="ORIGINAL", employee_approved="previous@example.test")
        result = self.approve()
        self.assertEqual(result["skipped"], ["TS-1"])
        self.assertEqual(self.docs[0].approved_signature, "ORIGINAL")
        self.assertEqual(self.docs[0].employee_approved, "previous@example.test")

    def test_guest_employee_and_readonly_users_cannot_approve(self):
        self.roles.return_value = ["Employee"]
        with self.assertRaises(frappe.PermissionError): self.approve()
        self.roles.return_value = ["HR Manager"]
        self.docs[1].check_permission.side_effect = frappe.PermissionError("Denied")
        with self.assertRaises(frappe.PermissionError): self.approve()
        self.assertFalse(self.docs[0].internal_approved)
        with patch.object(frappe, "session", SimpleNamespace(user="Guest")):
            with self.assertRaises(frappe.PermissionError): self.approve()

    def test_second_write_failure_rolls_back_first_and_audit(self):
        object.__setattr__(self.docs[1], "db_set", Mock(side_effect=RuntimeError("Database write failed")))
        with self.assertRaises(RuntimeError): self.approve()
        self.assertFalse(self.docs[0].internal_approved)
        self.assertFalse(self.audit)
        self.rollback.assert_called_once_with(save_point="verto_internal_approval")

    def test_cancelled_duplicate_unknown_or_unreviewed_selections_are_rejected(self):
        selected = self.selections()
        with self.assertRaises(frappe.ValidationError): self.approve(selected + selected)
        with self.assertRaises(frappe.ValidationError): self.approve(selected, review_timesheets=["TS-1"])
        self.docs[1].docstatus = 2
        with self.assertRaises(frappe.ValidationError): self.approve(selected)
        self.assertFalse(self.docs[0].internal_approved)

    def test_query_uses_permission_filtered_list_and_explicit_documents_check_read(self):
        with patch.object(frappe, "get_list", return_value=[frappe._dict(name="TS-1")]) as query:
            result = internal.get_internal_timesheet_review(week_start="2026-10-05", project="PROJ-1")
        self.assertEqual(result["timesheet_count"], 1)
        self.assertEqual(query.call_args.kwargs["filters"]["internal_approved"], 0)
        self.assertEqual(query.call_args.kwargs["filters"]["parent_project"], "PROJ-1")
        self.docs[0].check_permission.assert_called_with("read")

    def test_legacy_action_uses_current_session_and_requires_validation_page_for_flags(self):
        signing.approve_timesheet_with_signature("TS-1", SIGNATURE, "spoofed@example.test")
        self.assertEqual(self.docs[0].employee_approved, "manager@example.test")
        self.docs[1].time_logs[0].shift_type = "DS"
        with self.assertRaises(frappe.ValidationError): signing.approve_timesheet_with_signature("TS-2", SIGNATURE, "spoofed")


class TestInternalApprovalInvalidation(TestCase):
    def test_hours_comments_shift_changes_clear_internal_approval_but_preserve_client_signature(self):
        for field, value in (("hours", 13), ("description", "Changed"), ("shift_type", "NS")):
            doc = timesheet(internal_approved=1, approved_signature="INTERNAL", employee_approved="manager")
            old = timesheet(internal_approved=1)
            object.__setattr__(doc, "get_doc_before_save", lambda: old)
            doc.time_logs[0][field] = value
            internal.invalidate_changed_internal_approval(doc)
            self.assertEqual(doc.internal_approved, 0)
            self.assertEqual(doc.approved_signature, "")
            self.assertEqual(doc.custom_client_signature, "CLIENT-ORIGINAL")

    def test_client_signing_and_unrelated_metadata_do_not_clear_internal_approval(self):
        doc = timesheet(internal_approved=1)
        old = timesheet(internal_approved=1)
        object.__setattr__(doc, "get_doc_before_save", lambda: old)
        doc.custom_client_signature = "CLIENT-NEW"
        doc.modified = "2026-10-12 13:00:00"
        internal.invalidate_changed_internal_approval(doc)
        self.assertEqual(doc.internal_approved, 1)

    def test_equivalent_datetime_and_numeric_formats_do_not_invalidate_approval(self):
        doc = timesheet(internal_approved=1)
        old = timesheet(internal_approved=1)
        object.__setattr__(doc, "get_doc_before_save", lambda: old)
        doc.time_logs[0].from_time = datetime(2026, 10, 5, 6)
        doc.time_logs[0].to_time = datetime(2026, 10, 5, 18)
        doc.time_logs[0].hours = "12.0"
        internal.invalidate_changed_internal_approval(doc)
        self.assertEqual(doc.internal_approved, 1)


class TestInternalApprovalIntegration(IntegrationTestCase):
    def test_real_review_signature_fields_audit_and_stale_source_protection(self):
        suffix = frappe.generate_hash(length=10)
        project = frappe.get_doc(dict(doctype="Project", name="IA-PROJ-" + suffix, project_name="Internal approval test", max_ds_hrs=12))
        project.db_insert()
        employee = frappe.get_doc(dict(doctype="Employee", name="IA-EMP-" + suffix, employee_name="Internal Advisor " + suffix, first_name="Internal", user_id="Administrator", status="Active"))
        employee.db_insert()
        shift_type = frappe.get_doc(dict(doctype="Shift Type", name="IA-" + suffix + "-DS", start_time="06:00", end_time="18:00"))
        shift_type.db_insert()
        shift = frappe.get_doc(dict(doctype="Shift Assignment", name="IA-SHIFT-" + suffix, employee=employee.name, start_date="2026-10-05", end_date="2026-10-05", shift_type=shift_type.name, status="Active", docstatus=1, custom_project=project.name))
        shift.db_insert()
        daily = frappe.get_doc(dict(doctype="Daily Timesheet", name="IA-DAILY-" + suffix, current_user=employee.employee_name, date="2026-10-05", start_time="06:00", end_time="18:00", duration=43200, comments="Job complete", shift_allocation=shift.name, project_id=project.name))
        daily.db_insert()
        doc = frappe.get_doc(dict(doctype="Timesheet", name="IA-TS-" + suffix, employee=employee.name, employee_name=employee.employee_name,
                                 parent_project=project.name, custom_monday_date="2026-10-05", custom_sunday_date="2026-10-11", start_date="2026-10-05",
                                 total_hours=12, internal_approved=0, custom_client_signed=1, custom_client_signature=SIGNATURE))
        doc.append("time_logs", dict(from_time="2026-10-05 06:00:00", to_time="2026-10-05 18:00:00", hours=12, project=project.name,
                                     shift_type=shift_type.name, daily_timesheet_id=daily.name, description="Job complete"))
        doc.db_insert()
        for log in doc.time_logs: log.db_insert()
        review = internal.get_internal_timesheet_review(timesheets=[doc.name])
        row = review["groups"][0]["rows"][0]
        self.assertEqual(row["flag_count"], 0)
        selected = [{"name": row["name"], "review_hash": row["review_hash"]}]
        frappe.db.set_value("Daily Timesheet", daily.name, "comments", "Updated during review")
        with self.assertRaises(frappe.ValidationError):
            internal.approve_internal_timesheets(selected, SIGNATURE)
        self.assertFalse(frappe.db.get_value("Timesheet", doc.name, "internal_approved"))
        frappe.db.set_value("Daily Timesheet", daily.name, "comments", "Job complete")
        review = internal.get_internal_timesheet_review(timesheets=[doc.name])
        row = review["groups"][0]["rows"][0]
        result = internal.approve_internal_timesheets([{ "name": doc.name, "review_hash": row["review_hash"] }], SIGNATURE, signature_mode="type")
        approved = frappe.get_doc("Timesheet", doc.name)
        self.assertEqual(approved.docstatus, 0)
        self.assertEqual(approved.internal_approved, 1)
        self.assertEqual(approved.employee_approved, frappe.session.user)
        self.assertEqual(approved.custom_client_signature, SIGNATURE)
        audit = frappe.get_doc(internal.AUDIT_DOCTYPE, result["approval"])
        self.assertEqual(audit.signature_mode, "type")
        self.assertEqual(audit.approved_by, frappe.session.user)
        self.assertTrue(frappe.db.exists("Page", "internal-timesheet-approval"))
