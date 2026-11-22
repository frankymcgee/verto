import csv
import io
import json
from datetime import date
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from verto.api import internal_timesheet_approval as internal
from verto.verto.report.weekly_timesheet_v2 import weekly_timesheet_v2 as report


class TestWeeklyTimesheetReport(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.project = f"Weekly hours test {frappe.generate_hash(length=10)}"
        self.enterContext(patch.object(internal, "nowdate", return_value="2026-11-23"))

    def add_hours(self, work_date, shift, start_time, hours, project=None):
        frappe.get_doc(
            {
                "doctype": "Daily Timesheet",
                "name": f"Weekly-hours-{frappe.generate_hash(length=12)}",
                "owner": "Administrator",
                "date": work_date,
                "project": project or self.project,
                "shift": shift,
                "start_time": start_time,
                "duration": hours * 3600,
            }
        ).db_insert()

    def test_previous_week_handles_a_new_year(self):
        with patch.object(internal, "nowdate", return_value="2026-01-01"):
            self.assertEqual(internal.last_completed_week(), (date(2025, 12, 22), date(2025, 12, 28)))

    def test_default_week_has_paired_shifts_and_combines_split_entries(self):
        self.add_hours("2026-11-15", "DS", "06:00:00", 8)
        self.add_hours("2026-11-16", "FG-DS", "06:00:00", 4.5)
        self.add_hours("2026-11-16", "Stand Down", "13:00:00", 1.5)
        self.add_hours("2026-11-16", "FG-NS", "18:00:00", 4)
        self.add_hours("2026-11-22", "FG-SD", "16:30:00", 9)
        self.add_hours("2026-11-23", "DS", "06:00:00", 8)

        columns, data = report.execute()
        expected_days = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
        self.assertEqual(
            [column["label"] for column in columns[3:-1]],
            [f"{day} {shift}" for day in expected_days for shift in ("DS", "NS")],
        )
        row, = [row for row in data if row["project_name"] == self.project]
        self.assertEqual(row["week_start"], date(2026, 11, 16))
        self.assertEqual((row["mon_ds"], row["mon_ns"]), (6, 4))
        self.assertEqual((row["sun_ds"], row["sun_ns"]), (0, 9))
        self.assertEqual(row["hours_worked"], 19)

    def test_custom_range_separates_weeks_and_keeps_operations_filter(self):
        operations = f"{self.project} Operations & Execution"
        self.add_hours("2026-11-15", "NS", "18:00:00", 3)
        self.add_hours("2026-11-16", "DS", "06:00:00", 8)
        self.add_hours("2026-11-16", "DS", "06:00:00", 6, project=operations)
        self.add_hours("2026-11-17", "DS", "06:00:00", 4)

        _, rows = report.execute(
            {"start_date": "2026-11-15", "end_date": "2026-11-16", "exclude_operations": "Yes"}
        )
        self.assertFalse(any(row["project_name"] == operations for row in rows))
        rows = [row for row in rows if row["project_name"] == self.project]
        self.assertEqual([row["week_start"] for row in rows], [date(2026, 11, 9), date(2026, 11, 16)])
        self.assertEqual([row["hours_worked"] for row in rows], [3, 8])

    def test_weekly_email_download_uses_current_dates_with_saved_filters(self):
        operations = f"{self.project} Operations & Execution"
        self.add_hours("2026-11-09", "DS", "06:00:00", 12)
        self.add_hours("2026-11-16", "DS", "06:00:00", 8)
        self.add_hours("2026-11-16", "DS", "06:00:00", 5, project=operations)
        self.add_hours("2026-11-22", "NS", "18:00:00", 10)

        for dynamic in ({}, {"dynamic_date_period": "Weekly", "use_first_day_of_period": 1}):
            with self.subTest(dynamic=dynamic):
                email_report = frappe.get_doc(
                    {
                        "doctype": "Auto Email Report",
                        "report": report.REPORT_NAME,
                        "report_type": "Script Report",
                        "user": "Administrator",
                        "frequency": "Weekly",
                        "format": "CSV",
                        "from_date_field": "start_date",
                        "to_date_field": "end_date",
                        "filters": json.dumps(
                            {"start_date": "2026-11-09", "end_date": "2026-11-15", "exclude_operations": "Yes"}
                        ),
                        **dynamic,
                    }
                )
                rows = list(csv.DictReader(io.StringIO(email_report.get_report_content())))
                self.assertFalse(any(row["Project"] == operations for row in rows))
                row, = [row for row in rows if row["Project"] == self.project]
                self.assertEqual(
                    (float(row["Mon DS"]), float(row["Sun NS"]), float(row["Total Hours"])), (8, 10, 18)
                )
                self.assertEqual(email_report.filters["start_date"], "2026-11-16")
                self.assertEqual(email_report.filters["end_date"], "2026-11-22")
