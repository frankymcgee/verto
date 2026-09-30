"""Claim limits, recipient routing and server-side save lifecycle regressions."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase

from verto.api.mobile import global_notifications as notifications
from verto.api.mobile import push_notifications as push
from verto.api.mobile import timesheet_hour_limits as limits
from verto.verto.doctype.daily_timesheet.daily_timesheet import DailyTimesheet
from verto.verto.doctype.verto_mobile_settings.verto_mobile_settings import VertoMobileSettings


def timesheet(previous=None, **overrides):
    values = dict(name="TS-Advisor-2026-09-30", date="2026-09-30", duration=14 * 3600,
                  project_id="PROJ-1", shift="DS", current_user="Test Advisor",
                  owner="advisor@example.test", docstatus=0, shift_allocation="")
    values.update(overrides)
    doc = Mock()
    doc.name = values["name"]
    doc.get.side_effect = lambda field, default=None: values.get(field, default)
    doc.get_doc_before_save.return_value = previous
    return doc


class TestTimesheetHourLimits(TestCase):
    def setUp(self):
        self.project = dict(project_name="Shutdown", max_fly_hrs=8, max_ds_hrs=12, max_ns_hrs=13)
        self.allocation = {}
        self.get_value = self.enterContext(patch.object(frappe.db, "get_value", side_effect=self.lookup))
        self.meta = self.enterContext(patch.object(frappe, "get_meta", return_value=SimpleNamespace(has_field=lambda field: True)))
        self.recipients = self.enterContext(patch.object(limits, "_recipient_rows", return_value=[
            {"user": "manager@example.test", "receive_push": True},
            {"user": "email-only@example.test", "receive_push": False},
        ]))
        self.queue = self.enterContext(patch.object(limits, "queue_push_to_users"))
        self.errors = self.enterContext(patch.object(frappe, "log_error"))

    def lookup(self, doctype, *args, **kwargs):
        return self.allocation if doctype == "Shift Assignment" else self.project

    def test_uses_each_shift_limit_including_prefixed_codes_and_fly_days(self):
        for shift, field in (("DS", "max_ds_hrs"), ("FG-DS", "max_ds_hrs"),
                             ("RH NS", "max_ns_hrs"), ("Night Shift", "max_ns_hrs"),
                             ("FI", "max_fly_hrs"), ("FO", "max_fly_hrs"),
                             ("FG-FI", "max_fly_hrs"), ("RH-FO", "max_fly_hrs"),
                             ("Fly-in", "max_fly_hrs"), ("Fly-out", "max_fly_hrs")):
            with self.subTest(shift=shift):
                claim = limits.get_hours_exceeded(timesheet(shift=shift))
                self.assertEqual(claim["limit_field"], field)
                self.assertEqual(claim["maximum"], self.project[field])

    def test_equal_and_below_are_silent_but_one_second_over_is_detected(self):
        for shift, maximum in (("DS", 12), ("NS", 13), ("FI", 8)):
            for seconds in (0, maximum * 3600 - 1, maximum * 3600):
                with self.subTest(shift=shift, seconds=seconds):
                    self.assertIsNone(limits.get_hours_exceeded(timesheet(shift=shift, duration=seconds)))
            self.assertIsNotNone(limits.get_hours_exceeded(timesheet(shift=shift, duration=maximum * 3600 + 1)))

    def test_blank_zero_negative_and_invalid_limits_are_unconfigured(self):
        for value in (None, "", 0, -1, "bad", float("nan"), float("inf")):
            with self.subTest(value=value):
                self.project["max_ds_hrs"] = value
                self.assertIsNone(limits.get_hours_exceeded(timesheet()))

    def test_fractional_limits_are_hours_not_seconds(self):
        self.project["max_ds_hrs"] = "12.5"
        self.assertIsNone(limits.get_hours_exceeded(timesheet(duration=45000)))
        self.assertIsNotNone(limits.get_hours_exceeded(timesheet(duration=45001)))

    def test_unknown_shift_missing_project_missing_field_and_cancelled_are_silent(self):
        for overrides in ({"shift": "SD"}, {"project_id": ""}, {"docstatus": 2},
                          {"date": ""}, {"duration": -1}, {"duration": "bad"}):
            with self.subTest(overrides=overrides):
                self.assertIsNone(limits.get_hours_exceeded(timesheet(**overrides)))
        self.meta.return_value.has_field = lambda field: False
        self.assertIsNone(limits.get_hours_exceeded(timesheet()))
        self.meta.return_value.has_field = lambda field: True
        self.project = {}
        self.assertIsNone(limits.get_hours_exceeded(timesheet()))

    def test_allocation_data_wins_over_stale_mobile_display_fields(self):
        self.allocation = dict(custom_project="PROJ-2", shift_type="NS", employee_name="Allocated Advisor")
        claim = limits.get_hours_exceeded(timesheet(shift_allocation="SHIFT-1", project_id="wrong", shift="FI"))
        self.assertEqual((claim["project"], claim["maximum"], claim["person"]), ("PROJ-2", 13, "Allocated Advisor"))
        self.assertEqual(self.get_value.call_args.args[:2], ("Project", "PROJ-2"))

    def test_new_claim_push_contains_review_details_and_encoded_link(self):
        limits.notify_daily_timesheet_hours_exceeded(timesheet(name="TS-Test / Advisor"))
        self.recipients.assert_called_once_with(limits.NOTIFICATION_FLAG)
        self.queue.assert_called_once()
        users, payload = self.queue.call_args.args
        self.assertEqual(users, ["manager@example.test"])
        self.assertIn("Test Advisor", payload["body"])
        self.assertIn("Shutdown", payload["body"])
        self.assertIn("14 h claimed; 12 h allowed (Max DS Hrs)", payload["body"])
        self.assertEqual(payload["url"], "/app/daily-timesheet/TS-Test%20%2F%20Advisor")
        self.assertEqual(self.queue.call_args.kwargs["notification_type"], limits.NOTIFICATION_FLAG)
        self.errors.assert_not_called()

    def test_unchanged_comment_signature_or_clock_time_edit_does_not_repeat(self):
        old = timesheet()
        for changes in ({}, {"comments": "Clarified"}, {"signature": "new"},
                        {"start_time": "04:00:00", "end_time": "18:00:00"}, {"duration": "50400"}):
            limits.notify_daily_timesheet_hours_exceeded(timesheet(previous=old, **changes))
        self.queue.assert_not_called()
        self.recipients.assert_not_called()

    def test_changed_overclaim_and_repeat_after_correction_notify_again(self):
        for previous in (timesheet(duration=13 * 3600), timesheet(duration=12 * 3600)):
            limits.notify_daily_timesheet_hours_exceeded(timesheet(previous=previous))
        self.assertEqual(self.queue.call_count, 2)

    def test_another_day_project_shift_or_person_is_a_new_claim(self):
        for changes in ({"date": "2026-10-01"}, {"project_id": "PROJ-2"},
                        {"shift": "NS"}, {"current_user": "Another Advisor"}):
            limits.notify_daily_timesheet_hours_exceeded(timesheet(previous=timesheet(), **changes))
        self.assertEqual(self.queue.call_count, 4)

    def test_correction_cancellation_and_no_recipients_are_silent(self):
        limits.notify_daily_timesheet_hours_exceeded(timesheet(previous=timesheet(), duration=12 * 3600))
        limits.notify_daily_timesheet_hours_exceeded(timesheet(docstatus=2))
        self.recipients.return_value = []
        limits.notify_daily_timesheet_hours_exceeded(timesheet())
        self.queue.assert_not_called()

    def test_queue_failure_is_logged_without_rejecting_timesheet(self):
        self.queue.side_effect = RuntimeError("queue unavailable")
        limits.notify_daily_timesheet_hours_exceeded(timesheet())
        self.errors.assert_called_once()

    def test_server_duration_includes_overnight_hours(self):
        doc = SimpleNamespace(current_user="Test Advisor", date="2026-09-30", start_time="18:00:00",
                              end_time="08:00:00", duration=1, shift_allocation="SHIFT-1")
        DailyTimesheet.validate(doc)
        self.assertEqual(doc.duration, 14 * 3600)
        self.assertEqual(limits.get_hours_exceeded(timesheet(shift="NS", duration=doc.duration))["maximum"], 13)

    def test_push_service_defers_delivery_until_save_commits(self):
        with patch.object(push, "_get_vapid_config", return_value={"configured": True}), patch.object(frappe, "enqueue") as enqueue:
            push.queue_push_to_users(["manager@example.test"], {"title": "Hour limit"}, limits.NOTIFICATION_FLAG)
        self.assertTrue(enqueue.call_args.kwargs["enqueue_after_commit"])
        self.assertEqual(enqueue.call_args.args, ("verto.api.mobile.push_notifications.send_push_to_users",))


class TestHourLimitRecipients(TestCase):
    def setUp(self):
        self.enterContext(patch.object(frappe.db, "exists", return_value=True))
        self.enterContext(patch.object(notifications, "_field_exists", return_value=True))
        self.enterContext(patch.object(frappe.db, "get_value", side_effect=lambda doctype, user, *a, **kw:
                                     dict(enabled=user != "disabled", email=f"{user}@example.test", full_name=user)))

    def row(self, user, **values):
        return dict(user=user, enabled=1, receive_push=1, receive_email=1,
                    project_missing_purchase_order=0, daily_timesheet_hours_exceeded=1, **values)

    def test_enabled_opt_in_users_only_with_existing_po_routing_preserved(self):
        rows = [self.row("manager"), self.row("disabled"), self.row("manager"),
                dict(self.row("off"), enabled=0), dict(self.row("po-only"), daily_timesheet_hours_exceeded=0,
                                                       project_missing_purchase_order=1),
                dict(self.row("no-channel"), receive_email=0, receive_push=0)]
        with patch.object(frappe, "get_cached_doc", return_value={"global_notification_list": rows}):
            self.assertEqual([r["user"] for r in notifications._recipient_rows(limits.NOTIFICATION_FLAG)], ["manager"])
            self.assertEqual([r["user"] for r in notifications._recipient_rows()], ["po-only"])

    def validate(self, rows):
        settings = SimpleNamespace(meta=SimpleNamespace(has_field=lambda field: True), get=lambda field: rows)
        VertoMobileSettings._validate_global_notification_list(settings)

    def test_new_notification_requires_push_even_if_email_is_enabled(self):
        with self.assertRaises(frappe.ValidationError):
            self.validate([dict(self.row("manager"), receive_push=0)])
        self.validate([dict(self.row("manager"), receive_email=0)])
        self.validate([dict(self.row("manager"), enabled=0, receive_push=0)])

    def test_existing_po_and_duplicate_user_validation_are_preserved(self):
        with self.assertRaises(frappe.ValidationError):
            self.validate([dict(self.row("manager"), daily_timesheet_hours_exceeded=0,
                                project_missing_purchase_order=1, receive_push=0, receive_email=0)])
        with self.assertRaises(frappe.ValidationError):
            self.validate([self.row("manager"), self.row("manager")])


class TestHourLimitSaveIntegration(IntegrationTestCase):
    def test_migrated_schema_and_real_saves_recalculate_and_notify_once_per_claim(self):
        field = frappe.get_meta(notifications.RECIPIENT_DOCTYPE).get_field(limits.NOTIFICATION_FLAG)
        self.assertIsNotNone(field)
        self.assertEqual(field.fieldtype, "Check")
        self.assertEqual(str(field.default), "0")

        # Minimal DB fixture avoids unrelated Project provisioning integrations.
        project = frappe.get_doc(dict(doctype="Project", name="HOURS-" + frappe.generate_hash(length=10),
                                      project_name="Hour limit test", status="Open", max_ds_hrs=12, max_ns_hrs=13))
        project.db_insert()
        doc = frappe.get_doc(dict(doctype="Daily Timesheet", current_user=project.name,
                                  date="2026-09-30", start_time="18:00:00", end_time="08:00:00",
                                  duration=1, project_id=project.name, shift="NS"))
        doc.flags.ignore_links = True
        with patch.object(limits, "_recipient_rows", return_value=[{"user": "Administrator", "receive_push": True}]), \
             patch.object(limits, "queue_push_to_users") as queue:
            doc.insert(ignore_permissions=True)
            self.assertEqual(doc.duration, 14 * 3600)
            self.assertEqual(frappe.db.get_value("Daily Timesheet", doc.name, "duration"), 14 * 3600)
            queue.assert_called_once()
            self.assertIn("14 h claimed; 13 h allowed", queue.call_args.args[1]["body"])
            doc.comments = "Comment-only save"
            doc.save(ignore_permissions=True)
            self.assertEqual(queue.call_count, 1)
            doc.end_time = "07:00:00"
            doc.save(ignore_permissions=True)
            self.assertEqual(queue.call_count, 1)
            doc.end_time = "08:00:00"
            doc.save(ignore_permissions=True)
            self.assertEqual(queue.call_count, 2)
