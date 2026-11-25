"""Timesheet reconciliation and authorization without a running Frappe site."""
import copy
import importlib.util
from datetime import date, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class Record(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__

    def as_dict(self):
        return dict(self)

    def check_permission(self, action):
        if action in self.get("denied", []):
            raise PermissionError(action)


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTimesheetExceptions(unittest.TestCase):
    def setUp(self):
        import verto.api
        frappe = self.frappe = ModuleType("frappe")
        frappe.whitelist = lambda **kwargs: lambda function: function
        frappe._dict = Record
        frappe.PermissionError = PermissionError
        frappe.session = SimpleNamespace(user="manager@example.test")
        frappe.local = SimpleNamespace(response_headers={})
        frappe.get_roles = Mock(return_value=["HR Manager"])
        frappe.has_permission = Mock(return_value=True)
        frappe.get_all = Mock(side_effect=AssertionError("get_all bypasses user permissions"))
        frappe.get_list = Mock(return_value=[])
        frappe.get_doc = Mock()
        frappe.get_meta = Mock(return_value=SimpleNamespace(has_field=lambda field: True))
        frappe.throw = lambda message, exc=ValueError: (_ for _ in ()).throw(exc(message))
        utils = ModuleType("frappe.utils")
        utils.cint = lambda value: int(value or 0)
        utils.getdate = lambda value=None: date.fromisoformat(str(value or "2026-10-12")[:10])
        utils.get_datetime = lambda value: datetime.fromisoformat(str(value))
        utils.now_datetime = lambda: datetime(2026, 10, 12, 12)
        utils.nowdate = lambda: "2026-10-12"
        push = ModuleType("verto.api.mobile.push_notifications")
        push._get_timesheet_reminder_exclusions = Mock(return_value=set())
        self.enterContext(patch.dict("sys.modules", {"frappe": frappe, "frappe.utils": utils, "verto.api.mobile.push_notifications": push}))
        access = load("timesheet_access_test", "verto/api/timesheet_access.py")
        self.enterContext(patch.dict("sys.modules", {"verto.api.timesheet_access": access}))
        self.review = load("internal_review_test", "verto/api/internal_timesheet_approval.py")
        self.enterContext(patch.object(verto.api, "internal_timesheet_approval", self.review, create=True))
        # Load the actual overnight/due calculation, with the push dependency isolated.
        reminders = load("timesheet_reminders_test", "verto/api/mobile/timesheet_reminders.py")
        self.enterContext(patch.dict("sys.modules", {"verto.api.mobile.timesheet_reminders": reminders}))
        self.api = load("exceptions_test", "verto/api/timesheet_exceptions.py")
        self.monday = date(2026, 10, 5)
        self.now = datetime(2026, 10, 12, 12)
        self.doc = Record(name="TS-1", employee="EMP-1", employee_name="Advisor", parent_project="PROJ-1", project_name="Shutdown",
            custom_monday_date="2026-10-05", custom_sunday_date="2026-10-11", start_date="2026-10-05", total_hours=12, docstatus=0,
            internal_approved=0, time_logs=[Record(idx=1, from_time="2026-10-05 06:00:00", to_time="2026-10-05 18:00:00", hours=12,
                project="PROJ-1", shift_type="FG-DS", description="Job complete", daily_timesheet_id="DAILY-1")])
        self.context = dict(employees={"EMP-1": Record(name="EMP-1", employee_name="Advisor", user_id="worker@example.test")}, user_names={},
            projects={"PROJ-1": Record(name="PROJ-1", project_name="Shutdown", max_ds_hrs=12, max_ns_hrs=13, max_fly_hrs=8)},
            daily={"DAILY-1": Record(name="DAILY-1", owner="admin@example.test", current_user="Advisor", project_id="PROJ-1", date="2026-10-05",
                start_time="06:00:00", end_time="18:00:00", duration=43200, comments="Job complete", shift_allocation="SHIFT-1", shift="FG-DS", docstatus=0, modified="2026-10-12 11:59:00")},
            shifts=[Record(name="SHIFT-1", employee="EMP-1", custom_project="PROJ-1", start_date="2026-10-05", end_date="2026-10-05", status="Active", docstatus=1, shift_type="FG-DS")],
            types={"FG-DS": Record(name="FG-DS", start_time="06:00:00", end_time="18:00:00")})

    def queue(self, docs=None, **kwargs):
        return self.api.build_queue([self.doc] if docs is None else docs, self.context, self.monday, self.now, **kwargs)

    def codes(self, items):
        return {issue["code"] for item in items for issue in item["issues"]}

    def test_clean_day_overnight_and_day_or_night_stand_down_are_clean(self):
        self.assertEqual(self.queue(), [])
        for night in (False, True):
            with self.subTest(night=night):
                label = "FG-NS" if night else "FG-DS"
                start, end = ("18:00:00", "06:00:00") if night else ("06:00:00", "18:00:00")
                self.doc.time_logs[0].update(shift_type="SD", from_time=f"2026-10-05 {start}", to_time=f"2026-10-{'06' if night else '05'} {end}")
                self.context["daily"]["DAILY-1"].update(start_time=start, end_time=end)
                self.context["shifts"][0].shift_type = label
                self.context["types"][label] = Record(start_time=start, end_time=end)
                self.assertEqual(self.queue(), [])

    def test_missing_whole_weekly_document_is_found_from_allocation(self):
        self.context["daily"].clear()
        items = self.queue([])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["categories"], ["missing"])
        self.assertEqual(items[0]["links"], [{"doctype": "Shift Assignment", "name": "SHIFT-1", "label": "Open allocation"}])

    def test_not_due_overnight_shift_is_not_reported_early(self):
        self.context["daily"].clear()
        self.context["shifts"][0].shift_type = "FG-NS"
        self.context["types"]["FG-NS"] = Record(start_time="18:00:00", end_time="06:00:00")
        self.now = datetime(2026, 10, 6, 6, 59)
        self.assertEqual(self.queue([]), [])
        self.now = datetime(2026, 10, 6, 7)
        self.assertEqual(self.codes(self.queue([])), {"missing_hours"})

    def test_unavailable_leave_and_dated_reminder_exclusions_suppress_missing(self):
        self.context["daily"].clear()
        leave = Record(name="LEAVE-1", employee="EMP-1", from_date="2026-10-05", to_date="2026-10-05", half_day=0)
        self.assertEqual(self.queue([], leave=[leave]), [])
        attendance = Record(name="ATT-1", employee="EMP-1", attendance_date="2026-10-05", status="On Leave")
        self.assertEqual(self.queue([], attendance=[attendance]), [])
        self.assertEqual(self.queue([], exclusions={"2026-10-05": {("worker@example.test", "proj-1")}}), [])
        self.context["shifts"][0].shift_type = "Unavailable"
        self.assertEqual(self.queue([]), [])

    def test_half_day_does_not_hide_missing_hours_or_falsely_conflict_with_work(self):
        leave = Record(name="LEAVE-1", employee="EMP-1", from_date="2026-10-05", to_date="2026-10-06", half_day=1, half_day_date="2026-10-05")
        self.assertEqual(self.queue(leave=[leave]), [])
        self.context["daily"].clear()
        self.assertEqual(self.codes(self.queue([], leave=[leave])), {"missing_hours"})
        self.assertTrue(self.api._full_day_leave(leave, date(2026, 10, 6)))

    def test_pending_daily_is_processing_rather_than_missing_and_delayed_is_high_priority(self):
        items = self.queue([])
        self.assertEqual(self.codes(items), {"weekly_processing"})
        self.assertEqual(items[0]["categories"], ["processing"])
        self.context["daily"]["DAILY-1"].modified = "2026-10-12 11:45:00"
        item = self.queue([])[0]
        self.assertEqual(item["severity"], "high")
        self.assertEqual(item["categories"], ["processing"])
        self.assertEqual(self.queue(), [])  # Now linked to the weekly log; never counted twice.

    def test_positive_hours_conflict_with_submitted_absence_and_full_day_leave(self):
        attendance = Record(name="ATT-1", employee="EMP-1", attendance_date="2026-10-05", status="Absent")
        leave = Record(name="LEAVE-1", employee="EMP-1", from_date="2026-10-05", to_date="2026-10-05", half_day=0)
        items = self.queue(attendance=[attendance], leave=[leave])
        self.assertEqual(self.codes(items), {"attendance_conflict", "leave_conflict"})
        self.assertEqual(items[0]["severity"], "high")
        self.assertTrue({"Attendance", "Leave Application"} <= {link["doctype"] for link in items[0]["links"]})

    def test_same_staff_cross_project_overlap_and_project_daily_totals_are_checked(self):
        other = copy.deepcopy(self.doc)
        other.name = "TS-2"
        other.parent_project = "PROJ-2"
        other.time_logs[0].update(project="PROJ-2", daily_timesheet_id="")
        items = self.queue([self.doc, other], project="PROJ-1")
        self.assertEqual(self.codes(items), {"overlap"})
        self.assertTrue(all(item["project"] == "PROJ-1" for item in items))
        other.parent_project = "PROJ-1"
        other.time_logs[0].project = "PROJ-1"
        self.assertIn("hours_exceeded", self.codes(self.queue([self.doc, other])))

    def test_daily_mismatch_and_weekly_total_flags_use_existing_review_rules(self):
        self.context["daily"]["DAILY-1"].duration = 36000
        self.doc.total_hours = 10
        items = self.queue()
        self.assertEqual(self.codes(items), {"daily_hours_mismatch", "total_mismatch"})
        self.assertNotIn("comments", repr(items))

    def test_explicit_daily_identity_wins_over_owner_and_duplicate_names_are_ambiguous(self):
        source = self.context["daily"]["DAILY-1"]
        source.update(current_user="Another employee", owner="worker@example.test")
        self.assertIsNone(self.api._daily_employee(source, self.context["employees"]))
        self.assertIn("daily_identity_mismatch", self.codes(self.queue()))
        source.current_user = "Advisor"
        self.context["employees"]["EMP-2"] = Record(name="EMP-2", employee_name="Advisor", user_id="second@example.test")
        self.assertIsNone(self.api._daily_employee(source, self.context["employees"]))

    def test_unavailable_sources_disable_missing_and_do_not_invent_daily_errors(self):
        self.context["daily"].clear()
        access = dict(daily=False, shifts=True, attendance=True, leave=True, employees=True, types=True)
        self.assertEqual(self.queue([], access=access), [])
        self.assertEqual(self.queue(access=access), [])
        access["daily"] = True
        items = self.queue(access=access)
        self.assertIn("daily_unavailable", self.codes(items))
        self.assertTrue(all(link["doctype"] != "Daily Timesheet" for item in items for link in item["links"]))

    def test_unreadable_shift_configuration_does_not_invent_unknown_shift_flags(self):
        self.doc.time_logs[0].shift_type = "Custom crew"
        self.context["shifts"][0].shift_type = "Custom crew"
        self.context["types"].clear()
        access = dict(daily=True, shifts=True, attendance=True, leave=True, employees=True, types=False)
        self.assertEqual(self.queue(access=access), [])

    def test_guest_role_and_read_permission_are_required_before_queries(self):
        for user, roles, allowed in [("Guest", ["HR Manager"], True), ("worker@example.test", ["Employee"], True), ("manager@example.test", ["HR Manager"], False)]:
            with self.subTest(user=user, allowed=allowed):
                self.frappe.session.user = user
                self.frappe.get_roles.return_value = roles
                self.frappe.has_permission.return_value = allowed
                with self.assertRaises(PermissionError):
                    self.api.get_timesheet_exceptions()
                self.frappe.get_list.assert_not_called()

    def test_endpoint_rejects_non_monday_and_project_read_denial(self):
        with self.assertRaisesRegex(ValueError, "Monday"):
            self.api.get_timesheet_exceptions("2026-10-06")
        self.frappe.get_doc.return_value = Record(denied=["read"])
        with self.assertRaises(PermissionError):
            self.api.get_timesheet_exceptions("2026-10-05", "SECRET")
        self.frappe.get_list.assert_not_called()

    def test_endpoint_uses_bounded_permission_scoped_reads_and_no_store(self):
        result = self.api.get_timesheet_exceptions("2026-10-05")
        self.assertEqual(result["items"], [])
        self.assertEqual(result["week_end"], "2026-10-11")
        self.assertEqual(self.frappe.local.response_headers["Cache-Control"], "no-store")
        for call in self.frappe.get_list.call_args_list:
            self.assertGreater(call.kwargs["limit_page_length"], 0)
            self.assertNotIn("ignore_permissions", call.kwargs)
        self.frappe.get_all.assert_not_called()

    def endpoint_records(self, *, weekly=True, shifts=True):
        def read(doctype, **kwargs):
            return {"Timesheet": [Record(name=self.doc.name)] if weekly else [],
                    "Employee": list(self.context["employees"].values()), "Daily Timesheet": list(self.context["daily"].values()),
                    "Shift Assignment": self.context["shifts"] if shifts else [], "Shift Type": list(self.context["types"].values()),
                    "Project": list(self.context["projects"].values()), "User": [Record(name="worker@example.test", full_name="Advisor")]}.get(doctype, [])
        self.frappe.get_list.side_effect = read
        self.frappe.get_doc.side_effect = lambda dt, name: self.doc if dt == "Timesheet" else self.context["projects"][name]

    def test_endpoint_loads_and_reconciles_a_complete_readable_week(self):
        self.endpoint_records()
        self.assertEqual(self.api.get_timesheet_exceptions("2026-10-05", "PROJ-1")["items"], [])
        self.doc.denied = ["read"]
        with self.assertRaises(PermissionError):
            self.api.get_timesheet_exceptions("2026-10-05", "PROJ-1")

    def test_daily_without_an_allocation_or_weekly_document_is_still_visible(self):
        self.endpoint_records(weekly=False, shifts=False)
        self.context["daily"]["DAILY-1"].duration = 50400
        self.context["daily"]["DAILY-1"].end_time = "20:00:00"
        self.context["daily"]["DAILY-1"].shift_allocation = None
        result = self.api.get_timesheet_exceptions("2026-10-05", "PROJ-1")
        self.assertTrue({"weekly_processing", "missing_allocation", "hours_exceeded"} <= self.codes(result["items"]))
        self.assertNotIn("missing_hours", self.codes(result["items"]))

    def test_record_limit_refuses_incomplete_checks_instead_of_false_missing(self):
        self.frappe.get_list.return_value = [Record(name=str(index)) for index in range(202)]
        with self.assertRaisesRegex(ValueError, "complete check"):
            self.api.get_timesheet_exceptions("2026-10-05")

    def test_permission_denial_is_visible_as_check_coverage(self):
        self.frappe.has_permission.side_effect = lambda dt, action, **kwargs: dt != "Shift Assignment"
        result = self.api.get_timesheet_exceptions("2026-10-05")
        self.assertEqual(result["items"], [])
        self.assertTrue(any("Shift Assignment" in message for message in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
