"""Rejection, immutable source documents, request replacement and email routing."""

import base64
import copy
import datetime
import json
import re
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase

from verto.api import automate, timesheet_approval as approvals, timesheet_resend as resend, timesheet_signing as signing


SIGNATURE = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()


class MemoryDocument(frappe._dict):
    def __init__(self, store, **values):
        super().__init__(values)
        object.__setattr__(self, "store", store)
        object.__setattr__(self, "writes", [])
        object.__setattr__(self, "check_permission", Mock())

    def insert(self, **kwargs):
        self.name = self.name or f"WTA-{len(self.store):05d}"
        self.store[(self.doctype, self.name)] = self
        return self

    def db_set(self, field, value=None, **kwargs):
        values = field if isinstance(field, dict) else {field: value}
        self.writes.append(copy.deepcopy(values))
        self.update(values)

    def submit(self):
        self.db_set("docstatus", 1)


class TestTimesheetApproval(TestCase):
    def setUp(self):
        self.documents = {}
        self.savepoints = {}
        self.db = Mock()
        self.db.sql.side_effect = self.sql
        self.db.get_value.side_effect = self.get_value
        self.db.get_values.side_effect = lambda doctype, filters, field, **kwargs: [(name,) for name in self.get_all(doctype, filters=filters, pluck=field)]
        self.db.set_value.side_effect = lambda doctype, name, values: self.documents[(doctype, name)].db_set(values)
        self.db.savepoint.side_effect = lambda name: self.savepoints.__setitem__(name, {key: copy.deepcopy(dict(doc)) for key, doc in self.documents.items()})
        self.db.rollback.side_effect = self.rollback
        self.enterContext(patch.object(frappe, "db", self.db))
        self.enterContext(patch.object(frappe, "get_doc", side_effect=self.get_doc))
        self.enterContext(patch.object(frappe, "get_all", side_effect=self.get_all))
        self.enterContext(patch.object(frappe, "get_system_settings", return_value=None))
        self.enterContext(patch.object(frappe, "throw", side_effect=lambda message, *args, **kwargs: (_ for _ in ()).throw(frappe.ValidationError(message))))
        self.errors = self.enterContext(patch.object(frappe, "log_error"))
        self.only_for = self.enterContext(patch.object(frappe, "only_for"))
        self.sendmail = self.enterContext(patch.object(frappe, "sendmail", return_value=frappe._dict(name="MAIL-1")))
        self.settings = frappe._dict(reply_to_email="original@example.test", bcc_email_list=[], email_recipients=["office@example.test"])
        self.enterContext(patch.object(automate, "get_verto_mobile_email_settings", side_effect=lambda: self.settings))
        self.enterContext(patch.object(automate, "get_grouped_timesheet_secret", return_value=b"test-secret"))
        self.enterContext(patch.object(automate, "build_email_body", side_effect=lambda content, *args, **kwargs: content))
        self.enterContext(patch.object(automate, "get_timesheet_date_range", return_value=("2026-09-28", "2026-10-04", ["Monday"])))
        self.enterContext(patch.object(automate.time, "sleep"))
        self.enterContext(patch.object(frappe.utils, "get_url", side_effect=lambda path="": "https://verto.example.test" + path))
        self.enterContext(patch.object(signing, "formatdate", side_effect=lambda date, *args: str(date)))
        self.enterContext(patch.object(approvals, "now_datetime", return_value=datetime.datetime(2026, 10, 5, 16, 0)))
        self.project = self.document("Project", name="PROJ-1", project_name="Shutdown", day_of_the_week="Monday", timesheet_email_list="client@example.test")
        self.timesheets = [self.timesheet("TS-1", "Advisor", "DS", 12), self.timesheet("TS-2", "Supervisor", "NS", 8)]
        self.request = approvals.create_request([doc.name for doc in self.timesheets], self.settings, ["client@example.test"])
        self.token = automate.create_grouped_timesheet_token([doc.name for doc in self.timesheets], request_name=self.request.name)
        self.sendmail.reset_mock()

    def document(self, doctype, **values):
        doc = MemoryDocument(self.documents, doctype=doctype, **values)
        if doc.name:
            self.documents[(doctype, doc.name)] = doc
        return doc

    def timesheet(self, name, employee, shift, hours):
        return self.document("Timesheet", name=name, employee=employee, employee_name=employee, role="Advisor",
            parent_project="PROJ-1", project_name="Shutdown", custom_monday_date="2026-09-28", custom_sunday_date="2026-10-04",
            docstatus=1, custom_client_signed=0, total_hours=hours,
            time_logs=[frappe._dict(from_time="2026-09-28 06:00:00", hours=hours, shift_type=shift)])

    def get_doc(self, doctype, name=None, **kwargs):
        if isinstance(doctype, dict):
            return MemoryDocument(self.documents, **doctype)
        return self.documents[(doctype, name)]

    @staticmethod
    def matches(doc, filters):
        for field, expected in filters.items():
            actual = doc.get(field)
            if isinstance(expected, list):
                op, value = expected
                if (op == "!=" and actual == value) or (op == "in" and actual not in value):
                    return False
            elif str(actual) != str(expected):
                return False
        return True

    def get_value(self, doctype, name, field="name", **kwargs):
        if isinstance(name, dict):
            docs = [doc for (dt, _), doc in self.documents.items() if dt == doctype and self.matches(doc, name)]
            return docs[-1].get(field) if docs else None
        return self.documents[(doctype, name)].get(field)

    def get_all(self, doctype, filters=None, pluck=None, **kwargs):
        docs = [doc for (dt, _), doc in self.documents.items() if dt == doctype and self.matches(doc, filters or {})]
        return [doc.get(pluck) for doc in docs] if pluck else docs

    def sql(self, query, params, **kwargs):
        if "tabProject" in query:
            return [(params[0],)] if ("Project", params[0]) in self.documents else []
        return [frappe._dict(name=name, custom_client_signed=self.documents[("Timesheet", name)].custom_client_signed,
                docstatus=self.documents[("Timesheet", name)].docstatus) for name in params if ("Timesheet", name) in self.documents]

    def rollback(self, save_point=None):
        for key in list(self.documents):
            if key not in self.savepoints[save_point]:
                del self.documents[key]
        for key, values in self.savepoints[save_point].items():
            self.documents[key].clear()
            self.documents[key].update(copy.deepcopy(values))

    def reject(self, reason="Monday hours should be 10, not 12.", name="Client Supervisor"):
        return approvals.reject_grouped_timesheets(self.token, reason, full_name=name)

    def sign(self, token=None):
        return signing.sign_grouped_timesheets(token or self.token, SIGNATURE, "Client Supervisor", "2026-10-05")

    def test_rejection_records_reason_and_never_writes_source_timesheets(self):
        before = [copy.deepcopy(dict(doc)) for doc in self.timesheets]
        result = self.reject("  Wrong Monday hours.\nPlease correct.  ")
        self.assertEqual(result["status"], "Rejected")
        self.assertTrue(result["notification_queued"])
        self.assertEqual(self.request.rejection_reason, "Wrong Monday hours.\nPlease correct.")
        self.assertEqual(self.request.rejected_by, "Client Supervisor")
        self.assertTrue(self.request.rejected_on)
        self.assertEqual([dict(doc) for doc in self.timesheets], before)
        self.assertTrue(all(not doc.writes for doc in self.timesheets))

    def test_rejection_email_uses_original_reply_to_even_when_settings_change(self):
        self.settings.reply_to_email = "new@example.test"
        self.reject("Hours <script>alert(1)</script>\nWrong day.", "Client <img>")
        mail = self.sendmail.call_args.kwargs
        self.assertEqual(mail["recipients"], ["original@example.test"])
        self.assertNotIn("bcc", mail)
        self.assertNotIn("cc", mail)
        self.assertIn("&lt;script&gt;", mail["message"])
        self.assertNotIn("<script>", mail["message"])
        self.assertIn("&lt;img&gt;", mail["message"])
        self.assertTrue(mail["delayed"])
        self.assertEqual(mail["reference_name"], self.request.name)
        self.assertEqual(self.request.rejection_email, "MAIL-1")

    def test_reason_and_name_are_required_and_bounded_before_any_mutation(self):
        for reason, name in [("", "Client"), (" \n ", "Client"), ("x" * 5001, "Client"), ("Incorrect hours", ""), ("Incorrect hours", "x" * 141)]:
            with self.subTest(reason=reason[:20], name=name[:20]), self.assertRaises(frappe.ValidationError):
                self.reject(reason, name)
        self.assertEqual(self.request.status, "Pending")
        self.sendmail.assert_not_called()

    def test_repeat_rejection_does_not_overwrite_history_or_send_twice(self):
        self.reject("Original reason")
        when = self.request.rejected_on
        result = self.reject("Replacement reason", "Different client")
        self.assertEqual(result["status"], "Already rejected")
        self.assertEqual((self.request.rejection_reason, self.request.rejected_by, self.request.rejected_on), ("Original reason", "Client Supervisor", when))
        self.sendmail.assert_called_once()

    def test_email_failure_keeps_rejection_and_allows_one_internal_retry(self):
        self.sendmail.side_effect = RuntimeError("No outgoing email account")
        result = self.reject()
        self.assertFalse(result["notification_queued"])
        self.assertEqual(self.request.status, "Rejected")
        self.assertEqual(self.request.notification_status, "Failed")
        self.db.commit.assert_called_once()
        self.sendmail.side_effect = None
        result = approvals.retry_rejection_notification(self.request.name)
        self.assertTrue(result["notification_queued"])
        self.only_for.assert_called_with("System Manager")
        approvals.retry_rejection_notification(self.request.name)
        self.assertEqual(self.sendmail.call_count, 2)

    def test_muted_email_cannot_be_reported_as_successfully_queued(self):
        self.sendmail.return_value = None
        self.assertFalse(self.reject()["notification_queued"])
        self.assertEqual(self.request.notification_status, "Failed")

    def test_rejected_week_cannot_be_signed_or_downloaded(self):
        self.reject()
        with self.assertRaisesRegex(frappe.ValidationError, "rejected"):
            self.sign()
        with self.assertRaisesRegex(frappe.ValidationError, "rejected"):
            signing.download_grouped_signed_timesheets(self.token)
        self.assertTrue(all(doc.custom_client_signed == 0 for doc in self.timesheets))

    def test_signed_week_cannot_be_rejected_and_repeat_signature_is_idempotent(self):
        with patch.object(signing, "send_grouped_signed_notification") as notification:
            self.assertEqual(self.sign()["status"], "Success")
            self.assertEqual(self.request.status, "Approved")
            self.assertEqual(self.sign()["status"], "Already signed")
            notification.assert_called_once()
        with self.assertRaisesRegex(frappe.ValidationError, "already been signed"):
            self.reject()
        self.sendmail.assert_not_called()

    def test_existing_signatures_are_preserved_during_approval(self):
        self.timesheets[0].update(custom_client_signed=1, custom_signed_full_name="Existing Client", custom_client_signature="original", custom_date_signed="2026-10-04")
        with patch.object(signing, "send_grouped_signed_notification"):
            self.sign()
        self.assertEqual(self.timesheets[0].custom_client_signature, "original")
        self.assertEqual(self.timesheets[0].custom_signed_full_name, "Existing Client")
        self.assertEqual(self.timesheets[1].custom_client_signed, 1)

    def test_cancellation_and_amendment_keep_old_reason_readable_and_old_actions_blocked(self):
        self.reject("Correct the Advisor's hours")
        self.timesheets[0].docstatus = 2
        amended = self.timesheet("TS-1-1", "Advisor", "DS", 10)
        replacement = approvals.create_request([amended.name, self.timesheets[1].name], self.settings, ["client@example.test"])
        self.assertEqual(self.request.status, "Superseded")
        self.assertEqual(self.request.superseded_by, replacement.name)
        with patch.object(signing, "get_grouped_timesheet_docs", side_effect=AssertionError("Historical page must use its snapshot")):
            data = signing.get_grouped_timesheets_public(self.token)
        self.assertEqual(data["totals"]["total"], 20)
        self.assertEqual(data["rejection_reason"], "Correct the Advisor's hours")
        self.assertFalse(data["can_sign"])
        self.assertNotIn("reply_to_email", data)
        self.assertNotIn("recipient_emails", data)
        for action in (lambda: self.sign(), lambda: self.reject()):
            with self.assertRaisesRegex(frappe.ValidationError, "replaced"):
                action()
        new_token = automate.create_grouped_timesheet_token([amended.name, self.timesheets[1].name], request_name=replacement.name)
        data = signing.get_grouped_timesheets_public(new_token)
        self.assertEqual(data["totals"]["total"], 18)
        self.assertTrue(data["can_sign"])

    def test_changed_hours_require_a_new_request(self):
        self.timesheets[0].time_logs[0].hours = 14
        for action in (lambda: self.sign(), lambda: self.reject(), lambda: signing.get_grouped_timesheets_public(self.token)):
            with self.assertRaisesRegex(frappe.ValidationError, "changed"):
                action()
        self.assertEqual(self.request.status, "Pending")
        self.sendmail.assert_not_called()

    def test_cancellation_while_waiting_for_locks_is_detected_before_signature(self):
        original = self.db.sql.side_effect
        def cancel_on_lock(query, params, **kwargs):
            if "tabTimesheet" in query:
                self.timesheets[0].docstatus = 2
            return original(query, params, **kwargs)
        self.db.sql.side_effect = cancel_on_lock
        with self.assertRaisesRegex(frappe.ValidationError, "not submitted"):
            self.sign()
        self.assertFalse(any(doc.custom_client_signed for doc in self.timesheets))

    def test_token_tampering_and_wrong_request_membership_are_rejected(self):
        encoded, signature = self.token.split(".")
        payload = json.loads(automate.decode_grouped_token_part(encoded))
        payload["names"].append("OTHER-TIMESHEET")
        tampered = automate.encode_grouped_token_part(json.dumps(payload).encode()) + "." + signature
        for token in (tampered, "invalid", automate.create_grouped_timesheet_token(["TS-1"], request_name=self.request.name)):
            with self.subTest(token=token[:20]), self.assertRaises(frappe.ValidationError):
                approvals.resolve_request(token)

    def test_legacy_links_keep_signing_until_a_tracked_request_replaces_them(self):
        legacy = automate.create_grouped_timesheet_token([doc.name for doc in self.timesheets])
        with self.assertRaisesRegex(frappe.ValidationError, "replaced"):
            signing.get_grouped_timesheets_public(legacy)
        with self.assertRaisesRegex(frappe.ValidationError, "replaced"):
            signing.sign_timesheet("TS-1", SIGNATURE, "Old Client", "2026-10-05")
        del self.documents[(approvals.REQUEST_DOCTYPE, self.request.name)]
        self.assertFalse(signing.get_grouped_timesheets_public(legacy)["can_reject"])
        with patch.object(signing, "send_grouped_signed_notification"):
            self.assertEqual(self.sign(legacy)["status"], "Success")

    def test_reminders_skip_rejection_and_reuse_pending_request_and_original_reply_to(self):
        self.settings.reply_to_email = "new@example.test"
        result = automate.send_grouped_timesheet_followup_reminders(project_id="PROJ-1")
        self.assertEqual(result["results"][0]["status"], "Sent")
        message = self.sendmail.call_args.kwargs
        self.assertEqual(message["reply_to"], "original@example.test")
        self.assertEqual(message["recipients"], ["client@example.test"])
        self.assertIn(self.token, message["message"])
        self.reject()
        self.sendmail.reset_mock()
        result = automate.send_grouped_timesheet_followup_reminders(project_id="PROJ-1")
        self.assertEqual(result["results"][0]["status"], "Skipped")
        self.sendmail.assert_not_called()

    def test_both_senders_replace_requests_and_roll_back_replacement_on_email_failure(self):
        self.reject()
        for sender in (lambda: automate.send_grouped_weekly_timesheets(project_id="PROJ-1"),
                       lambda: resend.send_grouped_weekly_timesheets(project_id="PROJ-1", week_start="2026-09-28")):
            with self.subTest(sender=sender):
                self.sendmail.side_effect = RuntimeError("SMTP unavailable")
                result = sender()
                self.assertEqual(result["results"][0]["status"], "Failed")
                self.assertEqual(self.request.status, "Rejected")
                self.assertEqual(len(self.get_all(approvals.REQUEST_DOCTYPE)), 1)
                self.sendmail.side_effect = None
        result = resend.send_grouped_weekly_timesheets(project_id="PROJ-1", week_start="2026-09-28")
        self.assertEqual(result["results"][0]["status"], "Sent")
        self.assertEqual(self.request.status, "Superseded")
        self.assertNotEqual(result["results"][0]["approval_request"], self.request.name)

    def test_unconfigured_reply_to_blocks_new_email_without_replacing_existing_request(self):
        self.settings.reply_to_email = ""
        result = resend.send_grouped_weekly_timesheets(project_id="PROJ-1", week_start="2026-09-28")
        self.assertEqual(result["results"][0]["status"], "Failed")
        self.assertEqual(self.request.status, "Pending")
        self.sendmail.assert_not_called()

    def test_scheduled_amendment_send_includes_unchanged_submitted_employees(self):
        self.reject()
        self.timesheets[0].docstatus = 2
        amended = self.timesheet("TS-1-1", "Advisor", "DS", 10)
        amended.docstatus = 0
        with patch.object(automate, "get_grouped_timesheet_candidates", return_value=[amended]):
            result = automate.send_grouped_weekly_timesheets()
        self.assertEqual(result["results"][0]["status"], "Sent")
        latest = self.documents[(approvals.REQUEST_DOCTYPE, result["results"][0]["approval_request"])]
        self.assertEqual(approvals.request_names(latest), ["TS-1-1", "TS-2"])
        self.assertEqual(frappe.parse_json(latest.snapshot)["totals"]["total"], 18)
        self.assertEqual(self.timesheets[1].docstatus, 1)

    def test_sender_permissions_and_retry_permissions_are_enforced(self):
        self.timesheets[0].check_permission.side_effect = frappe.PermissionError
        with self.assertRaises(frappe.PermissionError):
            approvals.create_request(["TS-1", "TS-2"], self.settings, ["client@example.test"])
        self.assertEqual(self.request.status, "Pending")
        self.only_for.side_effect = frappe.PermissionError
        with self.assertRaises(frappe.PermissionError):
            approvals.retry_rejection_notification(self.request.name)
        self.sendmail.assert_not_called()

    def test_page_migration_updates_existing_page_and_is_idempotent(self):
        page = self.document("Web Page", name="existing-page", route="weekly-timesheet-approval")
        page_save = Mock()
        object.__setattr__(page, "save", page_save)
        self.assertTrue(approvals.ensure_approval_page())
        self.assertIn('id="grouped-reject-button"', page.main_section_html)
        self.assertIn("reject_grouped_timesheets", page.javascript)
        self.assertEqual(page.name, "existing-page")
        self.assertFalse(approvals.ensure_approval_page())
        page_save.assert_called_once_with(ignore_permissions=True)


class TestTimesheetApprovalDatabase(IntegrationTestCase):
    """Use real request/Timesheet rows to cover schema, locks and persistence."""
    def test_rejection_preserves_submitted_rows_and_survives_source_cancellation(self):
        frappe.set_user("Administrator")
        self.enterContext(patch.object(automate, "get_grouped_timesheet_secret", return_value=b"database-test-key"))
        suffix = frappe.generate_hash(length=10)
        project = frappe.get_doc({"doctype": "Project", "name": "TEST-APPROVAL-" + suffix, "project_name": "Approval Regression"})
        project.db_insert()
        timesheet = frappe.get_doc({
            "doctype": "Timesheet", "name": "TEST-TS-" + suffix, "parent_project": project.name,
            "project_name": project.project_name, "employee_name": "Approval Test Employee",
            "custom_monday_date": "2026-09-28", "custom_sunday_date": "2026-10-04",
            "docstatus": 1, "custom_client_signed": 0, "total_hours": 12,
        })
        timesheet.db_insert()
        log = timesheet.append("time_logs", {"from_time": "2026-09-28 06:00:00", "hours": 12, "shift_type": "DS"})
        log.name = "TEST-LOG-" + suffix
        log.db_insert()
        settings = frappe._dict(reply_to_email="original@example.test")
        request = approvals.create_request([timesheet.name], settings, ["client@example.test"])
        token = automate.create_grouped_timesheet_token([timesheet.name], request_name=request.name)
        with patch.object(frappe, "sendmail", return_value=frappe._dict(name="test-email")) as email, \
             patch.object(automate, "get_verto_mobile_email_settings", return_value=settings), \
             patch.object(automate, "build_email_body", side_effect=lambda content, *args: content), \
             patch.object(frappe.db, "commit"):
            result = approvals.reject_grouped_timesheets(token, "Wrong Monday hours", "Client Supervisor")
            self.assertTrue(result["notification_queued"])
            self.assertEqual(frappe.db.get_value("Timesheet", timesheet.name, "docstatus"), 1)
            self.assertEqual(frappe.db.get_value("Timesheet", timesheet.name, "custom_client_signed"), 0)
            self.assertEqual(frappe.db.get_value("Timesheet Detail", log.name, "hours"), 12)
            approvals.reject_grouped_timesheets(token, "New reason", "Other client")
            email.assert_called_once()
            frappe.db.set_value("Timesheet", timesheet.name, "docstatus", 2)
            data = signing.get_grouped_timesheets_public(token)
            self.assertEqual(data["approval_status"], "Rejected")
            self.assertEqual(data["rejection_reason"], "Wrong Monday hours")
            self.assertEqual(data["totals"]["total"], 12)
            self.assertEqual(frappe.get_doc(approvals.REQUEST_DOCTYPE, request.name).reply_to_email, "original@example.test")
