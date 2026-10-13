"""Shift timing, recipient identity, overdue persistence and delivery regressions."""

from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase

from verto.api.mobile import push_notifications as push
from verto.api.mobile import timesheet_reminders as reminders

USER = "advisor@example.test"
WORK_DATE = date(2026, 10, 12)
NOW = datetime(2026, 10, 12, 19)


def shift(**overrides):
    return dict(shift_assignment="SHIFT-1", shift_type="DS", employee="EMP-1", project="PROJ-1", **overrides)


def allocation(shifts=None):
    return dict(user=USER, user_full_name="Test Advisor", employee_ids={"EMP-1"},
                employee_names={"Test Advisor"}, allocations=shifts or [shift()])


def reminder(**overrides):
    values = dict(name="REMINDER-1", user=USER, shift_assignment="SHIFT-1", work_date=WORK_DATE,
                  due_at=NOW, status="Open", first_notified_on=None, next_day_notified_on=None)
    values.update(overrides)
    return frappe._dict(values)


class TestShiftReminderPolicy(TestCase):
    def test_day_shift_waits_exactly_one_hour_after_configured_end(self):
        self.assertEqual(reminders.shift_reminder_due_at(WORK_DATE, dict(start_time="06:00", end_time="18:00")), NOW)

    def test_night_shift_uses_next_day_but_keeps_the_shift_start_work_date(self):
        due = reminders.shift_reminder_due_at(WORK_DATE, dict(start_time="18:00", end_time="06:00"))
        self.assertEqual(due, datetime(2026, 10, 13, 7))

    def test_midnight_finish_and_one_hour_rollover(self):
        self.assertEqual(reminders.shift_reminder_due_at(WORK_DATE, dict(start_time="18:00", end_time="00:00")), datetime(2026, 10, 13, 1))
        self.assertEqual(reminders.shift_reminder_due_at(WORK_DATE, dict(start_time="12:00", end_time="23:30")), datetime(2026, 10, 13, 0, 30))

    def test_database_time_formats_are_supported(self):
        for start, end in ((timedelta(hours=6), timedelta(hours=18)), (time(6), time(18)), ("06:00:00", "18:00:00")):
            self.assertEqual(reminders.shift_reminder_due_at(WORK_DATE, dict(start_time=start, end_time=end)), NOW)

    def test_invalid_missing_and_equal_times_do_not_guess_shift_hours(self):
        for start, end in ((None, "18:00"), ("06:00", ""), ("bad", "18:00"), ("06:00", "06:00"), ("06:00", timedelta(days=1))):
            self.assertIsNone(reminders.shift_reminder_due_at(WORK_DATE, dict(start_time=start, end_time=end)))

    def test_matching_hours_require_the_person_and_correct_allocation(self):
        for values, expected in ((dict(current_user="Test Advisor", shift_allocation="SHIFT-1"), True),
                                 (dict(current_user="Another Advisor", owner=USER, shift_allocation="SHIFT-1"), False),
                                 (dict(current_user="Test Advisor", shift_allocation="SHIFT-2"), False),
                                 (dict(employee="EMP-1", shift_allocation="SHIFT-1"), True)):
            self.assertEqual(reminders._timesheet_matches(values, allocation(), shift()), expected)

    def test_legacy_hours_require_matching_project_and_shift(self):
        base = dict(owner=USER, _verto_project_id="PROJ-1", shift="DS")
        self.assertTrue(reminders._timesheet_matches(base, allocation(), shift()))
        for changes in ({"_verto_project_id": "PROJ-2"}, {"_verto_project_id": ""}, {"shift": "NS"}):
            self.assertFalse(reminders._timesheet_matches({**base, **changes}, allocation(), shift()))

    def test_occurrences_and_users_have_distinct_stable_keys(self):
        key = reminders._key(USER, "SHIFT-1", WORK_DATE)
        self.assertEqual(key, reminders._key(USER, "SHIFT-1", str(WORK_DATE)))
        self.assertNotEqual(key, reminders._key("other", "SHIFT-1", WORK_DATE))
        self.assertNotEqual(key, reminders._key(USER, "SHIFT-2", WORK_DATE))
        self.assertNotEqual(key, reminders._key(USER, "SHIFT-1", WORK_DATE + timedelta(days=1)))


class TestOutstandingShifts(TestCase):
    def setUp(self):
        self.allocated = self.enterContext(patch.object(push, "_get_allocated_users_for_date", return_value=({USER: allocation()}, [])))
        self.sheets = self.enterContext(patch.object(push, "_get_daily_timesheets_with_hours", return_value=[]))
        self.leave = self.enterContext(patch.object(reminders, "_employees_on_leave", return_value=set()))
        self.shift_type = self.enterContext(patch.object(frappe.db, "get_value", return_value=dict(start_time="06:00", end_time="18:00")))

    def outstanding(self, row=None):
        return reminders._outstanding_shift(row or reminder(), {}, {})

    def test_missing_hours_are_outstanding_and_office_recorded_hours_clear_them(self):
        self.assertEqual(self.outstanding()[0]["due_at"], NOW)
        self.sheets.return_value = [dict(current_user="Test Advisor", owner="office", shift_allocation="SHIFT-1")]
        self.assertEqual(self.outstanding(), (None, False))

    def test_unavailable_leave_and_removed_allocations_do_not_need_hours(self):
        self.leave.return_value = {"EMP-1"}
        self.assertEqual(self.outstanding(), (None, False))
        self.leave.return_value = set()
        for code in ("U", "FG-U", "On Leave"):
            self.allocated.return_value = ({USER: allocation([dict(shift(), shift_type=code)])}, [])
            self.assertEqual(self.outstanding(), (None, False))
        self.allocated.return_value = ({}, [])
        self.assertEqual(self.outstanding(), (None, False))

    def test_schema_or_timing_failure_keeps_existing_reminder_unresolved(self):
        self.sheets.return_value = None
        self.assertEqual(self.outstanding(), (None, True))
        self.sheets.return_value = []
        self.shift_type.return_value = {}
        self.assertEqual(self.outstanding(), (None, True))

    def test_date_reads_and_shift_type_lookups_are_reused(self):
        contexts, types = {}, {}
        for _ in range(3):
            reminders._outstanding_shift(reminder(), contexts, types, user=USER)
        self.allocated.assert_called_once_with(WORK_DATE, user=USER)
        self.sheets.assert_called_once_with(WORK_DATE)
        self.shift_type.assert_called_once()


class TestShiftReminderScheduler(TestCase):
    def setUp(self):
        self.enterContext(patch.object(reminders, "reminders_enabled", return_value=True))
        self.enterContext(patch.object(reminders, "now_datetime", return_value=NOW))
        self.open_rows = self.enterContext(patch.object(reminders, "_open_reminders", return_value=[]))
        self.context = self.enterContext(patch.object(reminders, "_date_context", side_effect=lambda day, cache, **kw:
                                      ({USER: allocation()} if day == WORK_DATE else {}, [], set())))
        self.outstanding = self.enterContext(patch.object(reminders, "_outstanding_shift", return_value=({**shift(), "due_at": NOW}, False)))
        self.enterContext(patch.object(frappe.db, "get_single_value", return_value=None))
        self.cursor = self.enterContext(patch.object(frappe.db, "set_single_value"))
        self.exists = self.enterContext(patch.object(frappe.db, "exists", return_value=False))
        self.get_doc = self.enterContext(patch.object(frappe, "get_doc"))
        self.enterContext(patch.object(frappe.db, "get_value", return_value=reminder()))
        self.update = self.enterContext(patch.object(frappe.db, "set_value"))
        self.queue = self.enterContext(patch.object(reminders, "_queue", return_value=True))

    def test_no_reminder_before_one_hour_but_create_and_queue_when_due(self):
        self.assertEqual(reminders.send_shift_missing_hours_reminders(reference_datetime=NOW - timedelta(seconds=1))["due"], 0)
        self.get_doc.assert_not_called()
        self.queue.assert_not_called()
        result = reminders.send_shift_missing_hours_reminders()
        self.assertEqual((result["created"], result["queued"]), (1, 1))
        self.get_doc.return_value.insert.assert_called_once_with(ignore_permissions=True)

    def test_dry_run_is_read_only(self):
        result = reminders.send_shift_missing_hours_reminders(dry_run=True)
        self.assertEqual(result["due"], 1)
        self.get_doc.assert_not_called()
        self.update.assert_not_called()
        self.cursor.assert_not_called()
        self.queue.assert_not_called()

    def test_saved_hours_resolve_an_existing_reminder(self):
        self.open_rows.return_value = [reminder()]
        self.context.side_effect = lambda *a, **kw: ({}, [], set())
        self.outstanding.return_value = (None, False)
        result = reminders.send_shift_missing_hours_reminders()
        self.assertEqual(result["resolved"], 1)
        self.assertEqual(self.update.call_args.args[2]["status"], "Resolved")
        self.queue.assert_not_called()

    def test_old_unresolved_reminders_are_retained_beyond_the_discovery_window(self):
        self.open_rows.return_value = [reminder(work_date=date(2026, 8, 1), first_notified_on=NOW)]
        self.context.side_effect = lambda *a, **kw: ({}, [], set())
        self.outstanding.return_value = ({**shift(), "due_at": datetime(2026, 8, 1, 19)}, False)
        self.assertEqual(reminders.send_shift_missing_hours_reminders()["due"], 1)
        self.get_doc.assert_not_called()

    def test_scheduler_resumes_from_saved_cursor_after_a_multi_day_outage(self):
        with patch.object(frappe.db, "get_single_value", return_value=datetime(2026, 10, 8, 12)):
            reminders.send_shift_missing_hours_reminders()
        dates = {args[0] for args, _ in self.context.call_args_list}
        self.assertTrue({date(2026, 10, day) for day in range(7, 13)} <= dates)

    def test_next_morning_followup_respects_night_shift_finish_day_and_deduplication(self):
        self.open_rows.return_value = [reminder()]
        for due, current, expected in ((NOW, datetime(2026, 10, 13, 8, 59), 0),
                                      (NOW, datetime(2026, 10, 13, 9), 1),
                                      (datetime(2026, 10, 13, 7), datetime(2026, 10, 13, 9), 0),
                                      (datetime(2026, 10, 13, 7), datetime(2026, 10, 14, 9), 1)):
            self.queue.reset_mock()
            self.outstanding.return_value = ({**shift(), "due_at": due}, False)
            with patch.object(reminders, "now_datetime", return_value=current):
                self.assertEqual(reminders.send_next_day_missing_hours_reminders()["queued"], expected)
        self.open_rows.return_value = [reminder(next_day_notified_on=NOW)]
        self.assertEqual(reminders.send_next_day_missing_hours_reminders()["queued"], 0)


class TestShiftReminderDelivery(TestCase):
    def setUp(self):
        self.enterContext(patch.object(reminders, "reminders_enabled", return_value=True))
        self.enterContext(patch.object(reminders, "now_datetime", return_value=NOW))
        self.lookup = self.enterContext(patch.object(frappe.db, "get_value", return_value=reminder()))
        self.outstanding = self.enterContext(patch.object(reminders, "_outstanding_shift", return_value=({**shift(), "due_at": NOW}, False)))
        self.send = self.enterContext(patch.object(push, "send_push_to_users", return_value=dict(sent=1, failed=0)))
        self.update = self.enterContext(patch.object(frappe.db, "set_value"))

    def test_rechecks_before_sending_to_only_the_assigned_user_and_records_delivery(self):
        reminders.deliver_missing_hours_reminder("REMINDER-1")
        self.assertTrue(self.lookup.call_args.kwargs["for_update"])
        self.assertEqual(self.send.call_args.args[0], [USER])
        payload = self.send.call_args.args[1]
        self.assertIn("date=2026-10-12", payload["url"])
        self.assertIn("shift=SHIFT-1", payload["url"])
        self.assertEqual(payload["tag"], "missing-hours-REMINDER-1")
        self.assertEqual(self.update.call_args.args[2][reminders.FIRST_SENT_FIELD], NOW)

    def test_hours_saved_while_push_is_queued_prevent_stale_delivery(self):
        self.outstanding.return_value = (None, False)
        reminders.deliver_missing_hours_reminder("REMINDER-1")
        self.send.assert_not_called()
        self.assertEqual(self.update.call_args.args[2]["status"], "Resolved")

    def test_duplicate_jobs_and_resolved_records_are_silent(self):
        for row in (reminder(first_notified_on=NOW), reminder(status="Resolved"), None):
            self.lookup.return_value = row
            reminders.deliver_missing_hours_reminder("REMINDER-1")
        self.send.assert_not_called()

    def test_failed_push_is_visible_and_can_be_retried(self):
        self.send.return_value = dict(sent=0, failed=1)
        reminders.deliver_missing_hours_reminder("REMINDER-1")
        updates = self.update.call_args.args[2]
        self.assertIn("failed: 1", updates["last_error"])
        self.assertNotIn(reminders.FIRST_SENT_FIELD, updates)

    def test_changed_shift_end_prevents_a_queued_push_before_new_due_time(self):
        self.outstanding.return_value = ({**shift(), "due_at": NOW + timedelta(hours=2)}, False)
        reminders.deliver_missing_hours_reminder("REMINDER-1")
        self.send.assert_not_called()

    def test_queue_is_deduplicated_and_waits_for_commit_without_marking_delivery(self):
        with patch.object(push, "_get_vapid_config", return_value=dict(configured=True)), \
             patch.object(frappe.db, "exists", return_value=True), patch.object(frappe, "enqueue") as enqueue:
            reminders._queue(reminder())
        self.assertTrue(enqueue.call_args.kwargs["enqueue_after_commit"])
        self.assertTrue(enqueue.call_args.kwargs["deduplicate"])
        self.assertIn("REMINDER-1", enqueue.call_args.kwargs["job_id"])
        self.update.assert_not_called()


class TestMyReminderAccess(TestCase):
    def test_api_only_reads_current_user_and_hides_resolved_hours_and_future_shifts(self):
        with patch.object(frappe, "session", SimpleNamespace(user=USER)), \
             patch.object(reminders, "reminders_enabled", return_value=True), \
             patch.object(reminders, "now_datetime", return_value=NOW), \
             patch.object(reminders, "_open_reminders", return_value=[reminder(), reminder(name="DONE"), reminder(name="LATER")]) as read, \
             patch.object(reminders, "_outstanding_shift", side_effect=[({**shift(), "due_at": NOW}, False), (None, False), ({**shift(), "due_at": NOW + timedelta(hours=1)}, False)]) as outstanding:
            result = reminders.get_my_missing_hours_reminders()
        read.assert_called_once_with(user=USER)
        self.assertEqual([row["name"] for row in result["reminders"]], ["REMINDER-1"])
        self.assertTrue(all(call.kwargs["user"] == USER for call in outstanding.call_args_list))

    def test_guest_cannot_read_reminders(self):
        with patch.object(frappe, "session", SimpleNamespace(user="Guest")):
            with self.assertRaises(frappe.PermissionError):
                reminders.get_my_missing_hours_reminders()

    def test_disabling_setting_hides_alert_and_prevents_scheduler_delivery(self):
        with patch.object(frappe, "session", SimpleNamespace(user=USER)), patch.object(reminders, "reminders_enabled", return_value=False), patch.object(reminders, "_open_reminders") as read:
            self.assertEqual(reminders.get_my_missing_hours_reminders(), dict(enabled=False, reminders=[]))
            self.assertFalse(reminders.send_shift_missing_hours_reminders()["enabled"])
            self.assertFalse(reminders.send_next_day_missing_hours_reminders()["enabled"])
        read.assert_not_called()


class TestShiftReminderIntegration(IntegrationTestCase):
    def test_migration_timing_ongoing_allocation_and_saved_daily_hours(self):
        setting = frappe.get_meta(push.SETTINGS_DOCTYPE).get_field(reminders.SETTING_FIELD)
        self.assertEqual(str(setting.default), "1")
        self.assertTrue(frappe.db.exists("DocType", reminders.REMINDER_DOCTYPE))
        suffix = frappe.generate_hash(length=10)
        employee_name = f"Reminder Employee {suffix}"
        employee = frappe.get_doc(dict(doctype="Employee", name=f"REM-EMP-{suffix}",
                                      employee_name=employee_name, first_name="Reminder", status="Active", user_id="Administrator"))
        employee.db_insert()
        shift_type = frappe.get_doc(dict(doctype="Shift Type", name=f"REM-DS-{suffix}", start_time="06:00", end_time="18:00"))
        shift_type.db_insert()
        shift_doc = frappe.get_doc(dict(doctype="Shift Assignment", name=f"REM-SHIFT-{suffix}",
                                       employee=employee.name, employee_name=employee_name, docstatus=1,
                                       start_date=WORK_DATE, end_date=None, status="Active", shift_type=shift_type.name))
        shift_doc.db_insert()
        key = reminders._key("Administrator", shift_doc.name, WORK_DATE)
        doc = frappe.get_doc(dict(doctype=reminders.REMINDER_DOCTYPE, reminder_key=key,
                                  user="Administrator", shift_assignment=shift_doc.name, work_date=WORK_DATE, due_at=NOW))
        doc.insert(ignore_permissions=True)
        with patch.object(reminders, "reminders_enabled", return_value=True), \
             patch.object(reminders, "now_datetime", return_value=NOW), \
             patch.object(push, "_get_timesheet_reminder_exclusions", return_value=set()):
            from verto.api.mobile import documents
            from verto.api.mobile.shifts import get_shift_calendar

            calendar = get_shift_calendar(str(WORK_DATE), str(WORK_DATE))
            self.assertIn(shift_doc.name, [row["name"] for row in calendar["shifts"]])

            with patch.object(documents, "get_allowed_doctype", return_value="Daily Timesheet"), \
                 patch.object(frappe, "has_permission", return_value=True):
                values = documents.get_prefill_values("daily-timesheet", date=str(WORK_DATE), shift_allocation=shift_doc.name)["values"]
                self.assertEqual(values["shift_allocation"], shift_doc.name)
                self.assertEqual(values["shift"], shift_type.name)
                self.assertEqual(values["current_user"], employee_name)
                with self.assertRaises(frappe.PermissionError):
                    documents.get_prefill_values("daily-timesheet", date="2026-10-01", shift_allocation=shift_doc.name)
                with patch.object(frappe, "session", SimpleNamespace(user="someone-else@example.test")):
                    with self.assertRaises(frappe.PermissionError):
                        documents.get_prefill_values("daily-timesheet", date=str(WORK_DATE), shift_allocation=shift_doc.name)
            result = reminders.get_my_missing_hours_reminders()
            self.assertIn(key, [row["name"] for row in result["reminders"]])
            # Daily Timesheet is non-submittable: a positive saved duration (docstatus 0) satisfies it.
            timesheet = frappe.get_doc(dict(doctype="Daily Timesheet", current_user=employee_name,
                                            date=WORK_DATE, shift_allocation=shift_doc.name, shift=shift_type.name,
                                            start_time="06:00", end_time="18:00", duration=43200))
            timesheet.flags.ignore_links = True
            with patch("verto.verto.doctype.daily_timesheet.daily_timesheet.DailyTimesheet.on_update"), \
                 patch("verto.api.mobile.timesheet_hour_limits.notify_daily_timesheet_hours_exceeded"):
                timesheet.insert(ignore_permissions=True)
            self.assertEqual(timesheet.docstatus, 0)
            result = reminders.get_my_missing_hours_reminders()
            self.assertNotIn(key, [row["name"] for row in result["reminders"]])
            reminders.deliver_missing_hours_reminder(key)
            self.assertEqual(frappe.db.get_value(reminders.REMINDER_DOCTYPE, key, "status"), "Resolved")
