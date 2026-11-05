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
            {"user": "manager@example.test", "receive_push": True, "receive_email": False},
            {"user": "email-only@example.test", "email": "office@example.test", "receive_push": False, "receive_email": True},
        ]))
        self.queue = self.enterContext(patch.object(limits, "queue_push_to_users"))
        self.sendmail = self.enterContext(patch.object(frappe, "sendmail"))
        self.enterContext(patch.object(limits, "get_url", side_effect=lambda path: "https://verto.example.test" + path))
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

    def test_resaving_unchanged_hours_or_comments_notifies_both_channels_again(self):
        old = timesheet()
        for changes in ({}, {"comments": "Clarified"}, {"signature": "new"},
                        {"start_time": "04:00:00", "end_time": "18:00:00"}, {"duration": "50400"}):
            limits.notify_daily_timesheet_hours_exceeded(timesheet(previous=old, **changes))
        self.assertEqual(self.queue.call_count, 5)
        self.assertEqual(self.sendmail.call_count, 5)
        self.assertEqual(self.recipients.call_count, 5)

    def test_resave_uses_the_current_channel_preferences(self):
        self.recipients.return_value = [dict(user="manager@example.test", email="manager@example.test",
                                             receive_email=True, receive_push=False)]
        limits.notify_daily_timesheet_hours_exceeded(timesheet(previous=timesheet()))
        self.sendmail.assert_called_once()
        self.queue.assert_not_called()
        self.recipients.return_value[0].update(receive_email=False, receive_push=True)
        limits.notify_daily_timesheet_hours_exceeded(timesheet(previous=timesheet()))
        self.sendmail.assert_called_once()
        self.queue.assert_called_once()

    def test_changed_overclaim_and_repeat_after_correction_notify_again(self):
        for previous in (timesheet(duration=13 * 3600), timesheet(duration=12 * 3600)):
            limits.notify_daily_timesheet_hours_exceeded(timesheet(previous=previous))
        self.assertEqual(self.queue.call_count, 2)
        self.assertEqual(self.sendmail.call_count, 2)

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
        self.sendmail.assert_not_called()

    def test_each_recipient_can_choose_email_push_or_both(self):
        for email, push_enabled in ((True, False), (False, True), (True, True)):
            with self.subTest(email=email, push=push_enabled):
                self.queue.reset_mock()
                self.sendmail.reset_mock()
                self.recipients.return_value = [dict(user="manager@example.test", email="office@example.test",
                                                     receive_email=email, receive_push=push_enabled)]
                limits.notify_daily_timesheet_hours_exceeded(timesheet())
                self.assertEqual(self.sendmail.call_count, int(email))
                self.assertEqual(self.queue.call_count, int(push_enabled))
                if email:
                    self.assertEqual(self.sendmail.call_args.kwargs["recipients"], ["office@example.test"])
                if push_enabled:
                    self.assertEqual(self.queue.call_args.args[0], ["manager@example.test"])

    def test_email_has_claim_details_safe_html_and_absolute_document_link(self):
        self.project["project_name"] = 'Shutdown <script>alert("x")</script>'
        doc = timesheet(name='TS-Test / Advisor#1', current_user='<b>Advisor</b> & team')
        limits.notify_daily_timesheet_hours_exceeded(doc)
        self.sendmail.assert_called_once()
        mail = self.sendmail.call_args.kwargs
        self.assertTrue(mail["delayed"])
        self.assertTrue(mail["is_notification"])
        self.assertEqual(mail["reference_doctype"], "Daily Timesheet")
        self.assertEqual(mail["reference_name"], doc.name)
        self.assertIn("&lt;script&gt;", mail["message"])
        self.assertIn("&lt;b&gt;Advisor&lt;/b&gt; &amp; team", mail["message"])
        self.assertNotIn("<script>", mail["message"])
        self.assertIn("https://verto.example.test/app/daily-timesheet/TS-Test%20%2F%20Advisor%231", mail["message"])
        for value in ("PROJ-1", "DS", "<td>14</td>", "<td>12</td>", "Max DS Hrs", "Work date"):
            self.assertIn(value, mail["message"])

    def test_missing_email_address_does_not_prevent_push(self):
        self.recipients.return_value = [dict(user="manager@example.test", email="", receive_email=True, receive_push=True)]
        limits.notify_daily_timesheet_hours_exceeded(timesheet())
        self.sendmail.assert_not_called()
        self.queue.assert_called_once()

    def test_failed_email_does_not_stop_other_recipients_or_push(self):
        self.recipients.return_value = [
            dict(user=user, email=user, receive_email=True, receive_push=True)
            for user in ("first@example.test", "second@example.test")
        ]
        self.sendmail.side_effect = [RuntimeError("outgoing email unavailable"), None]
        limits.notify_daily_timesheet_hours_exceeded(timesheet())
        self.assertEqual(self.sendmail.call_count, 2)
        self.queue.assert_called_once()
        self.assertEqual(self.queue.call_args.args[0], ["first@example.test", "second@example.test"])
        self.errors.assert_called_once()
        self.assertIn("Channel: Email", self.errors.call_args.kwargs["message"])
        self.assertIn("first@example.test", self.errors.call_args.kwargs["message"])

    def test_unconfigured_push_does_not_prevent_email(self):
        with patch.object(limits, "queue_push_to_users", wraps=push.queue_push_to_users), \
             patch.object(push, "_get_vapid_config", return_value={"configured": False}), \
             patch.object(frappe, "enqueue") as enqueue:
            limits.notify_daily_timesheet_hours_exceeded(timesheet())
        self.sendmail.assert_called_once()
        enqueue.assert_not_called()

    def test_queue_failure_is_logged_without_rejecting_timesheet(self):
        self.queue.side_effect = RuntimeError("queue unavailable")
        limits.notify_daily_timesheet_hours_exceeded(timesheet())
        self.errors.assert_called_once()
        self.sendmail.assert_called_once()
        self.assertIn("Channel: Push", self.errors.call_args.kwargs["message"])

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

    def test_notification_accepts_email_push_or_both_and_requires_one_channel(self):
        with self.assertRaises(frappe.ValidationError):
            self.validate([dict(self.row("manager"), receive_push=0, receive_email=0)])
        self.validate([self.row("manager")])
        self.validate([dict(self.row("manager"), receive_push=0)])
        self.validate([dict(self.row("manager"), receive_email=0)])
        self.validate([dict(self.row("manager"), enabled=0, receive_push=0, receive_email=0)])

    def test_routing_retains_email_only_and_push_only_preferences(self):
        rows = [dict(self.row("email"), receive_push=0), dict(self.row("push"), receive_email=0)]
        with patch.object(frappe, "get_cached_doc", return_value={"global_notification_list": rows}):
            recipients = notifications._recipient_rows(limits.NOTIFICATION_FLAG)
        self.assertEqual([(r["receive_email"], r["receive_push"]) for r in recipients], [(True, False), (False, True)])
        self.assertEqual(recipients[0]["email"], "email@example.test")

    def test_existing_po_and_duplicate_user_validation_are_preserved(self):
        with self.assertRaises(frappe.ValidationError):
            self.validate([dict(self.row("manager"), daily_timesheet_hours_exceeded=0,
                                project_missing_purchase_order=1, receive_push=0, receive_email=0)])
        with self.assertRaises(frappe.ValidationError):
            self.validate([self.row("manager"), self.row("manager")])


class TestHourLimitSaveIntegration(IntegrationTestCase):
    def test_migrated_schema_and_real_saves_recalculate_and_notify_on_resave(self):
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
        with patch.object(limits, "_recipient_rows", return_value=[{
                 "user": "Administrator", "email": "hours-test@example.test", "receive_email": True, "receive_push": True,
             }]), patch.object(limits, "queue_push_to_users") as queue, patch.object(frappe, "sendmail") as sendmail:
            doc.insert(ignore_permissions=True)
            self.assertEqual(doc.duration, 14 * 3600)
            self.assertEqual(frappe.db.get_value("Daily Timesheet", doc.name, "duration"), 14 * 3600)
            queue.assert_called_once()
            sendmail.assert_called_once()
            self.assertEqual(sendmail.call_args.kwargs["reference_name"], doc.name)
            self.assertIn("14 h claimed; 13 h allowed", queue.call_args.args[1]["body"])
            doc.comments = "Comment-only save"
            doc.save(ignore_permissions=True)
            self.assertEqual(queue.call_count, 2)
            self.assertEqual(sendmail.call_count, 2)
            doc.save(ignore_permissions=True)
            self.assertEqual(queue.call_count, 3)
            self.assertEqual(sendmail.call_count, 3)
            doc.end_time = "07:00:00"
            doc.save(ignore_permissions=True)
            self.assertEqual(queue.call_count, 3)
            self.assertEqual(sendmail.call_count, 3)
            doc.end_time = "08:00:00"
            doc.save(ignore_permissions=True)
            self.assertEqual(queue.call_count, 4)
            self.assertEqual(sendmail.call_count, 4)
