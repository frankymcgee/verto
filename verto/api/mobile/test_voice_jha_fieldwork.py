import base64
import json
from io import BytesIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from PIL import Image

from verto.api.mobile import voice_jha_fieldwork as fieldwork
from verto.api.mobile import voice_jha_revalidation as shifts
from verto.api.mobile import voice_jha_review as review
from verto.api.mobile import voice_jha_progress as progress
from verto.api.mobile.voice_jha_print import jha_workpack_qr


class Record(frappe._dict):
    records = []
    def set(self, key, value): self[key] = value
    def reload(self): return self
    def save(self, **kwargs): return self
    def has_permission(self, *args): return True
    def mark_review_required_if_source_changed(self): return False
    def insert(self, **kwargs):
        self.name = f'RECORD-{len(self.records) + 1}'
        self.records.append(self)
        return self


class TestJhaFieldwork(TestCase):
    def setUp(self):
        Record.records = []
        self.jha = Record(name='JHA-1', revision=1, jha_status='Signed', work_summary='WS-1', project='PROJECT-1',
            work_summary_title='Pump service', review_signature='original signature', flags=frappe._dict(),
            meta=SimpleNamespace(has_field=lambda field: True),
            hazards_and_controls=[Record(name='H-1', work_step_sequence=1, hazard_or_energy_source='Stored energy',
                                         critical_control='Mechanical restraint', control_owner='Supervisor')])
        self.ccv = Record(name='CCV-1', link_task='WS-1', link_project='PROJECT-1', docstatus=0,
            modified='2026-10-14 09:00:00', ccv_selected='Uncontrolled Release of Energy', safety_category='Good Controls',
            signature='human signature', ure_test='Yes', meta=SimpleNamespace(fields=[
                SimpleNamespace(fieldname='ure_test', fieldtype='Select', options='\nYes\nYes (Fixed on the spot)\nNo\nN/A')]))
        self.docs = {self.jha.name: self.jha, self.ccv.name: self.ccv}
        self.enterContext(patch.object(frappe, 'session', SimpleNamespace(user='checker@example.test')))
        self.enterContext(patch.object(review, '_get_jha', side_effect=lambda name, **kwargs: self.docs[name]))
        self.enterContext(patch.object(review, '_reviewer_name', return_value='Field checker'))
        self.enterContext(patch.object(frappe.db, 'sql', return_value=[]))
        self.enterContext(patch.object(frappe.db, 'get_value', side_effect=self.get_value))
        self.enterContext(patch.object(frappe, 'get_doc', side_effect=self.get_doc))
        self.enterContext(patch.object(frappe, 'get_all', side_effect=self.get_all))
        self.enterContext(patch.object(progress, 'serialize_jha', side_effect=lambda doc: {'name': doc.name, 'status': doc.jha_status}))
        self.enterContext(patch.object(shifts, 'today', return_value='2026-10-14'))
        self.enterContext(patch.object(frappe.local, 'response_headers', {}, create=True))

    def get_doc(self, doctype, name=None):
        if isinstance(doctype, dict):
            return Record(doctype, flags=frappe._dict())
        return self.docs.get(name) or next(row for row in Record.records if row.name == name)

    def get_value(self, doctype, filters, fields='name', **kwargs):
        if doctype == fieldwork.CCV_DOCTYPE:
            return Record({key: self.ccv.get(key) for key in fields}) if isinstance(fields, list) else self.ccv.get(fields)
        if isinstance(filters, dict):
            row = next((row for row in Record.records if row.doctype == doctype and all(row.get(key) == value for key, value in filters.items())), None)
            if row:
                return Record({key: row.get(key) for key in fields}) if isinstance(fields, list) else row.get(fields)
        return None

    def get_all(self, doctype, filters=None, fields=None, **kwargs):
        rows = [row for row in Record.records if row.doctype == doctype and all(row.get(key) == value for key, value in (filters or {}).items())]
        return list(reversed(rows))

    def verify(self, **values):
        return fieldwork.record_jha_control_verification('JHA-1', 'H-1', values.pop('result', 'Verified'),
            values.pop('request_id', 'request-1'), ccv=values.pop('ccv', 'CCV-1'), confirmation=values.pop('confirmation', 1), **values)

    def begin_shift(self):
        state = shifts.begin_jha_shift_review('JHA-1', '2026-10-14', 'Day', 1)
        return self.get_doc(shifts.DOCTYPE, state['name'])

    def answer(self, doc, category, changed=False, notes='', call_id=None):
        return shifts.execute_shift_tool('JHA-1', doc.name, 'record_jha_shift_check',
            json.dumps({'category': category, 'changed': changed, 'notes': notes}), call_id or category)

    def test_check_is_revision_bound_human_recorded_and_idempotent(self):
        result = self.verify()
        record = Record.records[0]
        self.assertEqual(record.jha, 'JHA-1')
        self.assertEqual(record.revision, 1)
        self.assertEqual(record.verified_by, 'checker@example.test')
        self.assertEqual(json.loads(record.ccv_snapshot)['answers'], {'ure_test': 'Yes'})
        self.assertTrue(self.verify()['replayed'])
        self.assertEqual(len(Record.records), 1)
        with self.assertRaises(frappe.ValidationError): self.verify(notes='different payload')
        self.assertEqual(result['name'], record.name)
        self.assertEqual(self.jha.review_signature, 'original signature')

    def test_verified_needs_confirmation_and_a_complete_signed_ccv(self):
        with self.assertRaises(frappe.ValidationError): self.verify(confirmation=0)
        with self.assertRaises(frappe.ValidationError): self.verify(ccv='')
        for value in ('', 'No', 'N/A'):
            self.ccv.ure_test = value
            with self.assertRaises(frappe.ValidationError): self.verify()
        self.ccv.ure_test = 'Yes'; self.ccv.signature = ''
        with self.assertRaises(frappe.ValidationError): self.verify()
        self.ccv.signature = 'signature'; self.ccv.safety_category = 'Improvement Required'
        with self.assertRaises(frappe.ValidationError): self.verify()

    def test_failed_check_can_be_recorded_without_a_ccv_but_needs_action_notes(self):
        with self.assertRaises(frappe.ValidationError): self.verify(result='Failed', ccv='')
        self.verify(result='Failed', ccv='', notes='Restraint missing. Hold the affected step.')
        self.assertEqual(fieldwork.control_state(self.jha)[0]['status'], 'Failed')

    def test_cross_job_ccv_and_unreadable_evidence_are_rejected(self):
        self.ccv.link_task = 'ANOTHER-JOB'
        with self.assertRaises(frappe.ValidationError): self.verify()
        self.ccv.link_task = 'WS-1'
        with self.assertRaises(frappe.PermissionError): self.verify(evidence='/private/files/not-attached.jpg')
        with self.assertRaises(frappe.ValidationError): self.verify(evidence='https://example.test/file.jpg')
        with patch.object(Record, 'has_permission', return_value=False):
            with self.assertRaises(frappe.PermissionError): self.verify()

    def test_changed_ccv_requires_a_new_check_and_history_is_kept(self):
        self.verify()
        self.assertEqual(fieldwork.control_state(self.jha)[0]['status'], 'Verified')
        self.ccv.modified = '2026-10-14 10:00:00'
        self.assertEqual(fieldwork.control_state(self.jha)[0]['status'], 'Recheck Required')
        self.verify(request_id='new-check')
        control = fieldwork.control_state(self.jha)[0]
        self.assertEqual(control['status'], 'Verified')
        self.assertEqual(len(control['history']), 2)

    def test_field_checks_reject_old_revisions_and_require_assigned_write_access(self):
        self.jha.replacement_jha = 'JHA-2'
        with self.assertRaises(frappe.ValidationError): self.verify()
        self.jha.replacement_jha = None
        with patch.object(review, '_get_jha', side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError): self.verify()

    def test_shift_resume_keeps_the_completed_questions_and_never_changes_the_signature(self):
        doc = self.begin_shift()
        self.assertEqual(self.begin_shift().name, doc.name)
        result = self.answer(doc, 'crew')
        self.assertEqual(result['result']['shift_review']['next_category'], 'equipment')
        self.assertTrue(self.answer(doc, 'crew')['replayed'])
        self.assertEqual(len(json.loads(doc.tool_audit)), 1)
        self.assertEqual(self.jha.jha_status, 'Signed')
        self.assertEqual(self.jha.review_signature, 'original signature')

    def test_no_change_requires_all_checks_then_a_separate_human_confirmation(self):
        doc = self.begin_shift()
        with self.assertRaises(frappe.ValidationError): shifts.confirm_jha_shift_review('JHA-1', doc.name, 1)
        for category in shifts.CATEGORIES: self.answer(doc, category)
        self.assertEqual(doc.status, 'Awaiting Confirmation')
        self.assertFalse(doc.get('confirmed_by'))
        with self.assertRaises(frappe.ValidationError): shifts.confirm_jha_shift_review('JHA-1', doc.name, 0)
        state = shifts.confirm_jha_shift_review('JHA-1', doc.name, 1)
        self.assertEqual(state['status'], 'No Change')
        self.assertEqual(state['confirmed_by'], 'checker@example.test')
        with self.assertRaises(frappe.PermissionError): self.answer(doc, 'crew', call_id='late-answer')

    def test_identified_change_stops_the_unchanged_flow(self):
        doc = self.begin_shift()
        result = self.answer(doc, 'crew', True, 'A new crew member needs briefing')
        self.assertEqual(doc.status, 'Change Required')
        self.assertEqual(self.jha.jha_status, 'Review Required - Work Changed')
        self.assertTrue(self.answer(doc, 'crew', True, 'A new crew member needs briefing')['replayed'])
        self.assertIn('Review Changes with PERI', result['result']['message'])
        with self.assertRaises(frappe.ValidationError): shifts.confirm_jha_shift_review('JHA-1', doc.name, 1)
        self.assertFalse(doc.get('confirmed_by'))

    def test_shift_tools_cannot_write_the_jha_or_answer_out_of_order(self):
        doc = self.begin_shift()
        with self.assertRaises(frappe.PermissionError): shifts.execute_shift_tool('JHA-1', doc.name, 'record_work_step', '{}', 'bad')
        with self.assertRaises(frappe.ValidationError): self.answer(doc, 'controls')
        with self.assertRaises(frappe.ValidationError): self.answer(doc, 'crew', True)
        with self.assertRaises(frappe.ValidationError): self.answer(doc, 'crew', 'false')
        other = Record(self.jha, name='JHA-OTHER')
        with self.assertRaises(frappe.PermissionError): shifts.get_review(other, doc.name)

    def test_failed_or_changed_ccv_prevents_an_unchanged_confirmation(self):
        self.verify(result='Failed', ccv='', notes='Restraint missing')
        doc = self.begin_shift()
        for category in shifts.CATEGORIES: self.answer(doc, category)
        with self.assertRaises(frappe.ValidationError): shifts.confirm_jha_shift_review('JHA-1', doc.name, 1)

    def test_guest_cannot_read_or_record_status(self):
        with patch.object(frappe, 'session', SimpleNamespace(user='Guest')):
            with self.assertRaises(frappe.PermissionError): fieldwork.get_jha_workpack_status('JHA-1')
            with self.assertRaises(frappe.PermissionError): self.verify()

    def test_qr_status_follows_the_replacement_chain_and_warns_for_a_draft(self):
        new = Record(self.jha, name='JHA-2', previous_jha='JHA-1', revision=2, jha_status='Incomplete - Actions Required')
        self.docs[new.name] = new; self.jha.replacement_jha = new.name
        state = fieldwork.get_jha_workpack_status('JHA-1', 1)
        self.assertFalse(state['is_current'])
        self.assertTrue(state['requires_review'])
        self.assertEqual(state['current']['name'], 'JHA-2')
        self.assertEqual(frappe.local.response_headers['Cache-Control'], 'no-store')
        new.work_summary = 'OTHER-WORK'
        with self.assertRaises(frappe.ValidationError): fieldwork.get_jha_workpack_status('JHA-1', 1)

    def test_qr_status_rejects_cycles_and_revision_mismatches(self):
        self.jha.replacement_jha = 'JHA-1'
        with self.assertRaises(frappe.ValidationError): fieldwork.get_jha_workpack_status('JHA-1', 1)
        self.jha.replacement_jha = None
        state = fieldwork.get_jha_workpack_status('JHA-1', 99)
        self.assertTrue(state['revision_mismatch'])
        self.assertFalse(state['is_current'])

    def test_print_qr_is_an_embedded_image_with_a_revision_specific_url(self):
        with patch('frappe.utils.get_url', side_effect=lambda path: 'https://verto.example.test' + path):
            qr = jha_workpack_qr(self.jha)
        self.assertEqual(qr['url'], 'https://verto.example.test/verto-mobile/jha/JHA-1?revision=1')
        image = Image.open(BytesIO(base64.b64decode(qr['image'].split(',')[1])))
        self.assertEqual(image.format, 'PNG')
        self.assertGreater(image.width, 100)

    def test_starting_shift_voice_keeps_the_signed_jha_and_its_original_voice_reference(self):
        from verto.api.mobile import voice_jha_facilitator as facilitator
        doc = self.begin_shift()
        self.jha.voice_session_reference = 'original-development-call'
        with patch.object(facilitator.base, '_get_jha_doc', return_value=self.jha), \
             patch.object(facilitator.base, '_validate_work_summary', return_value=Record(name='WS-1', subject='Pump service')), \
             patch.object(facilitator.base, '_get_peri_bot_doc', return_value=Record()), \
             patch.object(facilitator, 'serialize_jha', side_effect=lambda doc: {'name': doc.name, 'status': doc.jha_status}), \
             patch.object(facilitator, '_create_voice_call', return_value={'model': 'test-model', 'engine': 'live', 'sdp': 'v=0\nanswer', 'session_reference': 'shift-call'}):
            result = facilitator.start_voice_jha_call('JHA-1', 'v=0\noffer', 1, shift_review=doc.name)
        self.assertEqual(result['jha']['status'], 'Signed')
        self.assertEqual(self.jha.voice_session_reference, 'original-development-call')
        self.assertEqual(doc.voice_session_reference, 'shift-call')
        self.assertEqual(doc.voice_consent_confirmed_by, 'checker@example.test')


class IntegrationTestJhaFieldwork(IntegrationTestCase):
    def test_field_records_are_retained_and_cannot_be_forged_or_edited_through_document_writes(self):
        suffix = frappe.generate_hash(length=8)
        project = frappe.get_doc({'doctype': 'Project', 'project_name': f'JHA field test {suffix}'})
        project.name = f'JHA-FIELD-PROJECT-{suffix}'; project.db_insert()
        task = frappe.get_doc({'doctype': 'Task', 'subject': 'JHA field work', 'type': 'Work Summary', 'project': project.name})
        task.name = f'JHA-FIELD-TASK-{suffix}'; task.db_insert()
        jha = frappe.get_doc({'doctype': review.JHA_DOCTYPE, 'project': project.name, 'work_summary': task.name,
            'jha_status': 'Signed', 'revision': 1, 'hazards_and_controls': [{'work_step_sequence': 1,
            'hazard_or_energy_source': 'Stored energy', 'critical_control': 'Mechanical restraint', 'control_owner': 'Supervisor'}]})
        jha.insert()
        recorded = fieldwork.record_jha_control_verification(jha.name, jha.hazards_and_controls[0].name,
            'Failed', 'integration-failure', notes='Restraint missing. Hold the affected work.', confirmation=1)
        check = frappe.get_doc(fieldwork.VERIFICATION_DOCTYPE, recorded['name'])
        self.assertEqual(check.revision, jha.revision)
        check.result = 'Verified'
        with self.assertRaises(frappe.PermissionError): check.save(ignore_permissions=True)
        check.flags.allow_jha_field_mutation = True
        with self.assertRaises(frappe.PermissionError): check.save(ignore_permissions=True)
        review_state = shifts.begin_jha_shift_review(jha.name, shifts.today(), 'Day', 1)
        revalidation = frappe.get_doc(shifts.DOCTYPE, review_state['name'])
        revalidation.status = 'No Change'
        with self.assertRaises(frappe.PermissionError): revalidation.save(ignore_permissions=True)
        jha.reload()
        self.assertEqual(jha.jha_status, 'Signed')

    def test_completed_real_ccv_can_support_an_immutable_check_on_the_exact_revision(self):
        suffix = frappe.generate_hash(length=8)
        project = frappe.get_doc({'doctype': 'Project', 'project_name': f'CCV link test {suffix}'})
        project.name = f'JHA-CCV-PROJECT-{suffix}'; project.db_insert()
        task = frappe.get_doc({'doctype': 'Task', 'subject': 'CCV linkage work', 'type': 'Work Summary', 'project': project.name})
        task.name = f'JHA-CCV-TASK-{suffix}'; task.db_insert()
        jha = frappe.get_doc({'doctype': review.JHA_DOCTYPE, 'project': project.name, 'work_summary': task.name,
            'jha_status': 'Signed', 'revision': 1, 'hazards_and_controls': [{'work_step_sequence': 1,
            'hazard_or_energy_source': 'Stored energy', 'critical_control': 'Mechanical restraint', 'control_owner': 'Supervisor'}]}).insert()
        ccv = frappe.get_doc({'doctype': fieldwork.CCV_DOCTYPE, 'link_project': project.name,
            'link_task': task.name, 'ccv_selected': 'Uncontrolled Release of Energy',
            'safety_category': 'Good Controls', 'signature': 'test-signature'})
        for field in ccv.meta.fields:
            if field.fieldname.startswith('ure_') and field.fieldtype == 'Select':
                ccv.set(field.fieldname, 'Yes')
        ccv.name = f'JHA-CCV-{suffix}'; ccv.db_insert()
        result = fieldwork.record_jha_control_verification(jha.name, jha.hazards_and_controls[0].name,
            'Verified', 'integration-verified', ccv=ccv.name, confirmation=1)
        record = frappe.get_doc(fieldwork.VERIFICATION_DOCTYPE, result['name'])
        self.assertEqual(record.ccv, ccv.name)
        self.assertEqual(fieldwork.control_state(jha)[0]['status'], 'Verified')
        self.assertEqual(json.loads(record.ccv_snapshot)['name'], ccv.name)
        ccv.db_set('safety_category', 'Stop Work - Reset Required')
        self.assertEqual(fieldwork.control_state(jha)[0]['status'], 'Recheck Required')
