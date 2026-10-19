import json
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase
from pypdf import PdfWriter

from verto.api.mobile import voice_jha_email as mail, voice_jha_review as review
from verto.api.mobile import test_voice_jha_fieldwork as fixture
from verto.api.mobile import test_voice_jha_workpack as pack_fixture

Record = fixture.Record


def _pdf_fixture():
    # Exercise File's real PDF validation, including its JavaScript scan.
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


PDF = _pdf_fixture()
SIGNATURE = 'data:image/png;base64,iVBORw0KGgo='


class TestJhaPrintEmail(TestCase):
    get_all = fixture.TestJhaFieldwork.get_all

    def setUp(self):
        fixture.TestJhaFieldwork.setUp(self)
        self.jha.review_completed = 1; self.jha.reviewed_by = 'checker@example.test'
        self.jha.participants = [Record(name='PERSON-1', present_for_discussion=1, acknowledged=1,
                                       acknowledgement_signature=SIGNATURE)]
        self.jha.get_doc_before_save = lambda: Record(jha_status='Ready for Team Review')
        self.project = Record(name='PROJECT-1', custom_jha_print_email='site@example.test')
        self.docs[self.project.name] = self.project
        self.settings = Record(default_jha_print_email='default@example.test')
        self.enterContext(patch.object(frappe, 'get_cached_doc', return_value=self.settings))
        self.enterContext(patch.object(frappe, 'get_roles', return_value=[]))
        self.enterContext(patch.object(frappe, 'set_user', side_effect=lambda user: setattr(frappe.session, 'user', user)))
        self.enterContext(patch.object(frappe.db, 'exists', return_value=True))
        self.enterContext(patch.object(frappe.db, 'savepoint'))
        self.enterContext(patch.object(frappe.db, 'rollback'))
        self.enterContext(patch.object(frappe.db, 'set_value', side_effect=self.set_value))
        self.enterContext(patch.object(frappe, 'log_error'))
        self.enqueue = self.enterContext(patch.object(frappe, 'enqueue'))
        self.callbacks = []
        self.enterContext(patch.object(frappe.db, 'after_commit', SimpleNamespace(add=self.callbacks.append)))
        self.render = self.enterContext(patch.object(frappe, 'get_print', return_value=PDF))
        self.queue = Record(name='QUEUE-1', status='Not Sent', recipient='site@example.test', modified=datetime.now(), send=Mock())
        self.docs[self.queue.name] = self.queue
        self.sendmail = self.enterContext(patch.object(frappe, 'sendmail', return_value=self.queue))

    def get_doc(self, doctype, name=None):
        if isinstance(doctype, dict):
            return Record(doctype, flags=frappe._dict(), creation=datetime.now(), modified=datetime.now())
        return self.docs.get(name) or next(row for row in Record.records if row.name == name)

    def get_value(self, doctype, filters, fields='name', **kwargs):
        if doctype == 'Email Queue Recipient':
            return self.queue.recipient
        if isinstance(filters, str):
            row = self.docs.get(filters)
            return Record({key: row.get(key) for key in fields}) if row and isinstance(fields, list) else row.get(fields) if row else None
        return fixture.TestJhaFieldwork.get_value(self, doctype, filters, fields, **kwargs)

    def set_value(self, doctype, name, values, **kwargs):
        self.get_doc(doctype, name).update(values)

    def automatic(self):
        mail.jha_updated(self.jha)
        return mail._record(self.jha)

    def test_project_destination_overrides_default_and_only_accepts_one_plain_email(self):
        self.assertEqual(mail._destination(self.jha), 'site@example.test')
        self.project.custom_jha_print_email = ''
        self.assertEqual(mail._destination(self.jha), 'default@example.test')
        self.settings.default_jha_print_email = ''
        self.assertEqual(mail._destination(self.jha), '')
        for invalid in ['not-an-email', 'a@example.test,b@example.test', 'a@example.test\nBcc: b@example.test', 'Office <a@example.test>']:
            with self.subTest(invalid=invalid), self.assertRaises(frappe.ValidationError): mail.printing_address(invalid)

    def test_only_completed_review_and_every_required_signature_create_a_delivery(self):
        for key, value in [('jha_status', 'Ready for Team Review'), ('review_completed', 0), ('review_signature', ''), ('replacement_jha', 'JHA-2')]:
            before = self.jha.get(key); self.jha[key] = value
            self.assertIsNone(self.automatic()); self.jha[key] = before
        self.jha.participants[0].acknowledgement_signature = ''
        self.assertIsNone(self.automatic())
        self.jha.participants[0].acknowledgement_signature = SIGNATURE
        record = self.automatic()
        self.assertEqual(record.status, 'Pending')
        self.assertEqual((record.jha, record.revision, record.recipient), ('JHA-1', 1, 'site@example.test'))

    def test_automatic_dispatch_is_recorded_once_and_only_enqueued_after_commit(self):
        first = self.automatic(); self.automatic()
        self.jha.get_doc_before_save = lambda: Record(jha_status='Signed')
        self.automatic()
        self.assertEqual(len(Record.records), 1)
        self.enqueue.assert_not_called(); self.assertEqual(len(self.callbacks), 1)
        self.callbacks[0]()
        self.assertEqual(self.enqueue.call_args.kwargs['delivery_name'], first.name)
        self.assertTrue(self.enqueue.call_args.kwargs['deduplicate'])

    def test_missing_recipient_and_redis_failure_do_not_undo_signatures(self):
        self.project.custom_jha_print_email = ''; self.settings.default_jha_print_email = ''
        record = self.automatic(); self.assertEqual(record.status, 'Not Configured'); self.assertEqual(self.callbacks, [])
        self.enqueue.side_effect = RuntimeError('Redis unavailable')
        mail._enqueue(record.name)
        self.assertEqual(self.jha.jha_status, 'Signed'); self.assertEqual(self.jha.review_signature, 'original signature')

    def test_a_previously_signed_jha_can_be_explicitly_sent_after_an_address_is_configured(self):
        self.project.custom_jha_print_email = ''; self.settings.default_jha_print_email = ''
        record = self.automatic()
        self.assertEqual(mail._state(self.jha)['status'], 'Not Configured')
        self.project.custom_jha_print_email = 'new-office@example.test'
        self.assertEqual(mail._state(self.jha)['status'], 'Not Requested')
        self.assertTrue(mail._state(self.jha)['can_resend'])
        result = mail.resend_jha_print_email('JHA-1', 'configured-later', 1)
        self.assertEqual(result['status'], 'Pending'); self.assertEqual(record.recipient, 'new-office@example.test')

    def test_sent_history_remains_sent_after_standard_email_queue_retention(self):
        record = self.automatic()
        record.status = 'Sent'; record.sent_at = datetime(2026, 10, 19, 10)
        record.email_queue = 'OLD-QUEUE-REMOVED'
        self.assertEqual(mail._state(self.jha)['status'], 'Sent')
        self.assertEqual(mail._state(self.jha)['sent_at'], '2026-10-19 10:00:00')

    def test_pdf_is_private_frozen_and_queued_once_without_changing_signed_content(self):
        record = self.automatic()
        mail.prepare_print_email(record.name); mail.prepare_print_email(record.name)
        self.render.assert_called_once()
        self.assertTrue(self.render.call_args.kwargs['as_pdf'])
        self.assertEqual(self.render.call_args.kwargs['print_format'], 'Digital JHA Workpack')
        file = self.get_doc('File', record.pdf_file)
        self.assertEqual((file.is_private, file.attached_to_doctype, file.attached_to_name), (1, mail.DOCTYPE, record.name))
        self.assertEqual(file.content, PDF)
        self.sendmail.assert_called_once()
        kwargs = self.sendmail.call_args.kwargs
        self.assertEqual(kwargs['recipients'], ['site@example.test'])
        self.assertEqual(kwargs['attachments'], [{'fid': file.name}])
        self.assertIn('Rev 1', kwargs['subject']); self.assertTrue(kwargs['delayed'])
        self.assertEqual(mail._state(self.jha)['status'], 'Queued')
        self.queue.status = 'Sent'
        self.assertEqual(mail._state(self.jha)['status'], 'Sent')
        self.assertEqual(self.jha.review_signature, 'original signature')
        self.assertEqual(frappe.session.user, 'checker@example.test')

    def test_pdf_or_email_builder_failure_retains_completed_sign_on_and_exposes_a_retry(self):
        record = self.automatic(); self.render.side_effect = RuntimeError('PDF unavailable')
        mail.prepare_print_email(record.name)
        self.assertEqual(record.status, 'Failed'); self.sendmail.assert_not_called()
        self.assertTrue(mail._state(self.jha)['can_resend'])
        self.assertEqual(self.jha.jha_status, 'Signed'); self.assertEqual(frappe.session.user, 'checker@example.test')

    def test_changed_or_superseded_work_cancels_preparation_and_unsent_emails(self):
        record = self.automatic(); self.jha.jha_status = 'Review Required - Work Changed'
        mail.prepare_print_email(record.name)
        self.assertEqual(record.status, 'Cancelled'); self.render.assert_not_called()
        self.jha.jha_status = 'Signed'; record.status = 'Queued'; record.email_queue = self.queue.name
        self.jha.replacement_jha = 'JHA-2'
        mail.jha_updated(self.jha)
        self.assertEqual(self.queue.status, 'Error'); self.queue.send.assert_not_called()

    def test_live_email_queue_result_is_authoritative_and_retries_reuse_the_failed_email(self):
        record = self.automatic(); mail.prepare_print_email(record.name)
        self.queue.status = 'Error'
        result = mail.resend_jha_print_email('JHA-1', 'retry-1', 1)
        self.assertEqual(result['status'], 'Queued'); self.assertEqual(record.email_queue, self.queue.name)
        self.assertEqual(self.queue.status, 'Not Sent'); self.assertEqual(self.queue.retry, 0)
        before = len(self.callbacks)
        mail.resend_jha_print_email('JHA-1', 'retry-1', 1)
        self.assertEqual(len(self.callbacks), before)
        self.sendmail.assert_called_once(); self.assertEqual(len(json.loads(record.request_history)), 1)

    def test_source_change_preserves_an_email_already_sent_before_reconciliation(self):
        record = self.automatic(); mail.prepare_print_email(record.name)
        self.queue.status = 'Sent'
        self.jha.jha_status = 'Review Required - Work Changed'
        with patch.object(frappe, 'get_all', return_value=[record]):
            mail.reconcile_print_deliveries()
        self.assertEqual(record.status, 'Sent'); self.assertEqual(record.sent_at, self.queue.modified)
        self.docs.pop(self.queue.name)
        self.assertEqual(mail._state(self.jha)['status'], 'Sent')

    def test_smtp_result_remains_authoritative_if_sending_overlapped_cancellation(self):
        record = self.automatic(); mail.prepare_print_email(record.name)
        record.status = 'Cancelled'; self.queue.status = 'Sending'
        self.assertEqual(mail._status(record), 'Sending')
        self.queue.status = 'Sent'
        self.assertEqual(mail._status(record), 'Sent')

    def test_resend_requires_reviewer_or_manager_confirmation_and_blocks_pending_delivery(self):
        record = self.automatic()
        for args in [('retry', 0), ('', 1)]:
            with self.subTest(args=args), self.assertRaises(frappe.ValidationError): mail.resend_jha_print_email('JHA-1', *args)
        with self.assertRaises(frappe.ValidationError): mail.resend_jha_print_email('JHA-1', 'busy', 1)
        record.status = 'Failed'; frappe.session.user = 'crew@example.test'
        with self.assertRaises(frappe.PermissionError): mail.resend_jha_print_email('JHA-1', 'unauthorised', 1)
        frappe.session.user = 'Guest'
        with self.assertRaises(frappe.PermissionError): mail.get_jha_print_delivery('JHA-1')

    def test_intentional_resend_after_sent_uses_the_same_pdf_and_keeps_the_old_queue_in_audit(self):
        record = self.automatic(); mail.prepare_print_email(record.name)
        file = record.pdf_file; self.queue.status = 'Sent'
        result = mail.resend_jha_print_email('JHA-1', 'another-copy', 1)
        self.assertEqual(result['status'], 'Pending'); self.assertIsNone(record.email_queue)
        self.assertEqual(record.pdf_file, file)
        self.assertEqual(json.loads(record.request_history)[0]['previous_queue'], 'QUEUE-1')


class IntegrationTestJhaPrintEmail(IntegrationTestCase):
    def ready_jha(self):
        jha, project = pack_fixture.IntegrationTestJhaWorkpack.make_jha(self, status='Draft')
        frappe.db.set_value('Project', project.name, mail.PROJECT_FIELD, 'site@example.test')
        jha.set('participants', [{'participant_name': name, 'present_for_discussion': 1} for name in ['Crew One', 'Crew Two']])
        jha.jha_status = 'Ready for Team Review'; jha.flags.allow_jha_review_mutation = True; jha.save()
        return jha

    def finish(self, jha):
        review.complete_human_review(jha.name, SIGNATURE, 1)
        for row in jha.participants:
            review.acknowledge_jha_participant(jha.name, row.name, SIGNATURE, 1)
        jha.reload()
        return mail._record(jha)

    def queued_email(self, **kwargs):
        return frappe.get_doc({'doctype': 'Email Queue', 'sender': 'printing@example.test', 'status': 'Not Sent',
            'message': 'Subject: Signed JHA\n\nPrint fixture', 'reference_doctype': kwargs['reference_doctype'],
            'reference_name': kwargs['reference_name'], 'attachments': json.dumps(kwargs['attachments']),
            'recipients': [{'recipient': email, 'status': 'Not Sent'} for email in kwargs['recipients']]}).insert(ignore_permissions=True)

    def test_real_final_sign_on_creates_one_delivery_and_private_pdf_with_all_signatures_retained(self):
        jha = self.ready_jha()
        with patch.object(mail, '_schedule') as schedule:
            review.complete_human_review(jha.name, SIGNATURE, 1)
            review.acknowledge_jha_participant(jha.name, jha.participants[0].name, SIGNATURE, 1)
            self.assertIsNone(mail._record(jha)); schedule.assert_not_called()
            review.acknowledge_jha_participant(jha.name, jha.participants[1].name, SIGNATURE, 1)
            jha.reload(); record = mail._record(jha)
            self.assertEqual(record.status, 'Pending'); schedule.assert_called_once()
            modified = frappe.utils.get_datetime(jha.modified)
            with patch.object(frappe, 'get_print', return_value=PDF) as render, patch.object(frappe, 'sendmail', side_effect=self.queued_email) as send, patch.object(frappe, 'log_error') as errors:
                mail.prepare_print_email(record.name); mail.prepare_print_email(record.name)
            self.assertFalse(errors.called, errors.call_args_list)
            send.assert_called_once(); render.assert_called_once()
            record.reload(); file = frappe.get_doc('File', record.pdf_file)
            self.assertTrue(file.is_private); self.assertEqual(file.get_content(), PDF)
            self.assertEqual(file.attached_to_name, record.name)
            jha.reload(); self.assertEqual(frappe.utils.get_datetime(jha.modified), modified)
            self.assertEqual(jha.jha_status, 'Signed'); self.assertTrue(jha.review_signature)
            self.assertTrue(all(row.acknowledgement_signature for row in jha.participants))
            self.assertEqual(frappe.db.count(mail.DOCTYPE, {'jha': jha.name}), 1)
            record.status = 'Sent'
            with self.assertRaises(frappe.PermissionError): record.save(ignore_permissions=True)

    def test_real_failed_email_reuses_its_queue_and_source_changes_cancel_future_delivery(self):
        jha = self.ready_jha()
        with patch.object(mail, '_schedule'):
            record = self.finish(jha)
            with patch.object(frappe, 'get_print', return_value=PDF), patch.object(frappe, 'sendmail', side_effect=self.queued_email), patch.object(frappe, 'log_error') as errors:
                mail.prepare_print_email(record.name)
            self.assertFalse(errors.called, errors.call_args_list)
            record.reload(); queue_name = record.email_queue
            frappe.db.set_value('Email Queue', queue_name, {'status': 'Error', 'retry': 4})
            mail.resend_jha_print_email(jha.name, 'retry', 1)
            mail.resend_jha_print_email(jha.name, 'retry', 1)
            record.reload(); self.assertEqual(record.email_queue, queue_name)
            self.assertEqual(frappe.db.get_value('Email Queue', queue_name, 'status'), 'Not Sent')
            self.assertEqual(len(json.loads(record.request_history)), 1)
            jha.reload(); jha.jha_status = 'Review Required - Work Changed'; jha.flags.allow_jha_review_mutation = True; jha.save()
            record.reload(); self.assertEqual(record.status, 'Cancelled')
            self.assertEqual(frappe.db.get_value('Email Queue', queue_name, 'status'), 'Error')
            with self.assertRaises(frappe.ValidationError): mail.resend_jha_print_email(jha.name, 'old', 1)

    def test_real_pdf_failure_does_not_roll_back_review_or_signatures(self):
        jha = self.ready_jha()
        with patch.object(mail, '_schedule'):
            record = self.finish(jha)
            with patch.object(frappe, 'get_print', side_effect=RuntimeError('PDF unavailable')), patch.object(frappe, 'sendmail') as send:
                mail.prepare_print_email(record.name)
            send.assert_not_called(); record.reload(); jha.reload()
            self.assertEqual(record.status, 'Failed'); self.assertEqual(jha.jha_status, 'Signed')
            self.assertTrue(all(row.acknowledged and row.acknowledgement_signature for row in jha.participants))
