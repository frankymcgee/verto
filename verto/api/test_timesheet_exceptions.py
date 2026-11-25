"""Exercise the exception endpoint against the real v16 database and permissions."""
from datetime import datetime
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from verto.api import timesheet_exceptions as exceptions


class TestTimesheetExceptionsIntegration(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.previous_user = frappe.session.user
        frappe.set_user("Administrator")
        self.addCleanup(frappe.set_user, self.previous_user)
        self.suffix = frappe.generate_hash(length=10)
        self.project = self.make("Project", project_name="Exceptions " + self.suffix, max_ds_hrs=12)
        self.employee = self.make("Employee", employee_name="Exceptions advisor " + self.suffix, first_name="Exceptions", user_id="Administrator", status="Active")
        self.shift_type = self.make("Shift Type", start_time="06:00:00", end_time="18:00:00")
        self.shift = self.make("Shift Assignment", employee=self.employee.name, custom_project=self.project.name,
                               shift_type=self.shift_type.name, start_date="2026-10-05", end_date="2026-10-05", status="Active", docstatus=1)

    def make(self, doctype, **values):
        doc = frappe.get_doc(dict(doctype=doctype, name=f"EX-{doctype.replace(' ', '')}-{frappe.generate_hash(length=10)}", **values))
        doc.db_insert()
        return doc

    def report(self):
        with patch.object(exceptions, "now_datetime", return_value=datetime(2026, 10, 12, 12)):
            return exceptions.get_timesheet_exceptions("2026-10-05", self.project.name)

    def codes(self, report):
        return {issue["code"] for item in report["items"] for issue in item["issues"]}

    def test_live_queue_moves_from_missing_to_processing_to_clean_then_attendance_conflict(self):
        self.assertEqual(self.codes(self.report()), {"missing_hours"})
        daily = self.make("Daily Timesheet", current_user=self.employee.employee_name, date="2026-10-05", project_id=self.project.name,
                          start_time="06:00:00", end_time="18:00:00", duration=43200, shift_allocation=self.shift.name, shift=self.shift_type.name,
                          comments="Work completed", modified="2026-10-12 11:59:00")
        self.assertEqual(self.codes(self.report()), {"weekly_processing"})
        weekly = frappe.get_doc(dict(doctype="Timesheet", name="EX-TS-" + self.suffix, employee=self.employee.name, employee_name=self.employee.employee_name,
                                     parent_project=self.project.name, custom_monday_date="2026-10-05", custom_sunday_date="2026-10-11", start_date="2026-10-05",
                                     total_hours=12, internal_approved=0))
        weekly.append("time_logs", dict(from_time="2026-10-05 06:00:00", to_time="2026-10-05 18:00:00", hours=12, project=self.project.name,
                                        shift_type=self.shift_type.name, daily_timesheet_id=daily.name, description="Work completed"))
        weekly.db_insert()
        for row in weekly.time_logs:
            row.db_insert()
        self.assertEqual(self.report()["items"], [])
        attendance = self.make("Attendance", employee=self.employee.name, attendance_date="2026-10-05", status="Absent", docstatus=1)
        conflicted = self.report()
        self.assertEqual(self.codes(conflicted), {"attendance_conflict"})
        self.assertTrue(any(link["name"] == attendance.name for item in conflicted["items"] for link in item["links"]))
        frappe.db.set_value("Attendance", attendance.name, "docstatus", 2)
        self.assertEqual(self.report()["items"], [])
        self.assertEqual(frappe.db.get_value("Timesheet", weekly.name, "internal_approved"), 0)

    def test_guest_cannot_query_timesheet_exceptions(self):
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            self.report()
