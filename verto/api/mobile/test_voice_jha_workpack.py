import json
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from PIL import Image

from verto.api.mobile import voice_jha_workpack as pack, voice_jha_learning as learning
from verto.api.mobile import voice_jha_review as review
from verto.api.mobile import test_voice_jha_fieldwork as fixture

Record = fixture.Record


class TestJhaWorkpack(TestCase):
    get_doc = fixture.TestJhaFieldwork.get_doc
    get_value = fixture.TestJhaFieldwork.get_value

    def setUp(self):
        fixture.TestJhaFieldwork.setUp(self)
        self.jha.work_steps = [Record(name='STEP-1', sequence=1, activity='Restrain pump', hold_or_pause_point=1)]
        self.jha.reviewed_by = 'checker@example.test'
        self.enterContext(patch.object(learning, '_is_privileged_user', return_value=False))
        self.enterContext(patch.object(pack, 'now_datetime', return_value=datetime(2026, 10, 14, 10)))
        self.enterContext(patch.object(frappe.db, 'exists', side_effect=lambda dtype, value: True if dtype == 'DocType'
            else bool(self.get_all(dtype, filters=value)) if isinstance(value, dict)
            else value in self.docs or any(row.doctype == dtype and row.name == value for row in Record.records)))

    def get_all(self, doctype, filters=None, fields=None, pluck=None, **kwargs):
        def matches(row, key, value):
            if isinstance(value, list):
                return row.get(key) != value[1] if value[0] == '!=' else row.get(key) in value[1]
            return row.get(key) == value
        rows = [row for row in reversed(Record.records) if row.doctype == doctype
                and all(matches(row, key, value) for key, value in (filters or {}).items())]
        return [row.get(pluck) for row in rows] if pluck else rows

    def resource(self, **values):
        args = dict(jha_name='JHA-1', step_row='STEP-1', kind='Permit', reference='PERMIT-123',
                    details='Permit covers pump access.', request_id='resource-1', confirmation=1)
        args.update(values)
        return pack.record_jha_resource(**args)

    def closeout(self, **values):
        args = dict(jha_name='JHA-1', deviations='None observed', control_improvements='Pump restraint access improved.',
                    follow_up='Supervisor to review access.', lesson='Raw unreviewed proposal', request_id='closeout-1', confirmation=1)
        args.update(values)
        return learning.record_jha_closeout(**args)

    def test_resource_is_step_revision_bound_human_recorded_and_replay_safe(self):
        result = self.resource()
        self.assertTrue(self.resource()['replayed'])
        self.assertEqual(len(Record.records), 1)
        row = Record.records[0]
        self.assertEqual((row.jha, row.revision, row.step_row, row.work_step), ('JHA-1', 1, 'STEP-1', 1))
        self.assertEqual(row.recorded_by, 'checker@example.test')
        self.assertEqual(self.jha.review_signature, 'original signature')
        self.assertEqual(result['jha_status'], 'Signed')
        with self.assertRaises(frappe.ValidationError): self.resource(reference='OTHER')

    def test_resource_requires_confirmation_exact_step_and_actual_reference(self):
        for args in ({'confirmation': 0}, {'step_row': 'OLD-STEP'}, {'reference': ''}, {'kind': 'Authorisation'},
                     {'status': 'Approved'}, {'expires_at': 'invalid'}):
            with self.subTest(args=args), self.assertRaises(frappe.ValidationError): self.resource(**args)
        self.jha.replacement_jha = 'JHA-2'
        with self.assertRaises(frappe.ValidationError): self.resource()

    def test_expiry_and_pending_confirmations_are_live_not_frozen_on_the_jha(self):
        self.resource(expires_at='2026-10-14 09:59:00', status='Confirmed')
        state = pack.resource_state(self.jha)
        self.assertEqual(state[0]['effective_status'], 'Expired')
        self.assertEqual(len(pack.outstanding_references(self.jha)), 1)

    def test_existing_ehs_permit_changes_require_a_recheck(self):
        permit = Record(name='PRM-1', modified='2026-10-14 09:00:00', start='2026-10-14 08:00:00',
                        end='2026-10-14 18:00:00', permit_status='Active', docstatus=1)
        self.docs[permit.name] = permit
        self.resource(ehs_permit=permit.name, status='Confirmed')
        original = self.get_value
        with patch.object(frappe.db, 'get_value', side_effect=lambda dtype, *a, **kw: permit if dtype == 'EHS Permit' else original(dtype, *a, **kw)):
            self.assertEqual(pack.resource_state(self.jha)[0]['effective_status'], 'Confirmed')
            permit.modified = '2026-10-14 09:30:00'
            self.assertEqual(pack.resource_state(self.jha)[0]['effective_status'], 'Recheck Required')
        with patch.object(Record, 'has_permission', return_value=False):
            with self.assertRaises(frappe.PermissionError): self.resource(ehs_permit=permit.name, request_id='bad-permit')

    def test_permit_correction_retains_history_and_marks_a_physical_change(self):
        first = self.resource()['name']
        self.resource(request_id='corrected', replaces=first, reference='PERMIT-456', status='Confirmed')
        rows = pack.resource_state(self.jha)
        self.assertEqual(len(rows), 2)
        self.assertTrue(next(row for row in rows if row['name'] == first)['historical'])
        self.assertEqual(self.jha.jha_status, 'Review Required - Work Changed')
        self.assertEqual(self.jha.review_signature, 'original signature')

    def test_confirming_an_unchanged_reference_does_not_invalidate_the_signed_content(self):
        first = self.resource()['name']
        self.resource(request_id='confirmed', replaces=first, status='Confirmed')
        self.assertEqual(self.jha.jha_status, 'Signed')

    def test_resource_cannot_replace_a_different_step_or_revision(self):
        first = self.resource()['name']; Record.records[0].step_row = 'OTHER'
        with self.assertRaises(frappe.ValidationError): self.resource(request_id='bad', replaces=first)

    def test_photo_evidence_is_private_attached_and_actual_image_data(self):
        image = BytesIO(); Image.new('RGB', (32, 32)).save(image, format='PNG')
        file = Record(doctype='File', name='FILE-1', file_url='/private/files/pump.png', attached_to_doctype=review.JHA_DOCTYPE,
                      attached_to_name='JHA-1', is_private=1)
        file.get_content = lambda: image.getvalue()
        Record.records.append(file)
        result = self.resource(kind='Photo', status='Confirmed', evidence=file.file_url,
            annotations=json.dumps([{'x': .25, 'y': .75, 'label': 'Restraint point'}]))
        row = next(row for row in Record.records if row.name == result['name'])
        self.assertEqual(json.loads(row.annotations)[0]['label'], 'Restraint point')
        from verto.api.mobile.voice_jha_print import jha_print_resources
        printed = jha_print_resources(self.jha)
        self.assertTrue(printed[0]['thumbnail'].startswith('data:image/jpeg;base64,'))
        self.assertEqual(printed[0]['annotations'][0]['x'], .25)
        file.attached_to_name = 'OTHER-JHA'
        with self.assertRaises(frappe.PermissionError): self.resource(kind='Photo', status='Confirmed', evidence=file.file_url)
        with self.assertRaises(frappe.ValidationError): self.resource(kind='Photo', status='Confirmed', evidence='/files/public.png')

    def test_photo_annotations_reject_out_of_bounds_nan_and_missing_labels(self):
        for point in ({'x': 2, 'y': .5, 'label': 'No'}, {'x': float('nan'), 'y': .5, 'label': 'No'},
                      {'x': .2, 'y': .5, 'label': ''}, {'x': True, 'y': .5, 'label': 'No'}):
            with self.subTest(point=point), self.assertRaises(frappe.ValidationError): pack._annotations([point])
        with self.assertRaises(frappe.ValidationError): pack._annotations([{'x': .1, 'y': .1, 'label': 'x'}] * 21)

    def test_offline_observation_rechecks_actor_revision_and_current_permissions(self):
        for args in ({'actor': 'another@example.test'}, {'revision': 2}):
            values = dict(jha_name='JHA-1', revision=1, request_id='obs-1', actor='checker@example.test', notes='Pump restraint changed')
            values.update(args)
            with self.assertRaises((frappe.PermissionError, frappe.ValidationError)): pack.record_jha_observation(**values)
        with patch.object(review, '_get_jha', side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError):
                pack.record_jha_observation('JHA-1', 1, 'obs-1', 'checker@example.test', 'Changed restraint')

    def test_offline_old_revision_is_retained_and_changed_work_flags_the_current_signed_jha(self):
        self.jha.jha_status = 'Superseded'; self.jha.replacement_jha = 'JHA-2'
        current = Record(self.jha, name='JHA-2', revision=2, previous_jha='JHA-1', replacement_jha=None, jha_status='Signed', flags=frappe._dict())
        self.docs[current.name] = current
        args = ('JHA-1', 1, 'obs-1', 'checker@example.test', 'Changed restraint')
        result = pack.record_jha_observation(*args, step_row='STEP-1', work_changed=1)
        self.assertTrue(result['stale_revision'])
        self.assertTrue(pack.record_jha_observation(*args, step_row='STEP-1', work_changed=1)['replayed'])
        self.assertEqual(Record.records[0].jha, 'JHA-1')
        self.assertEqual(Record.records[0].revision, 1)
        self.assertEqual(current.jha_status, 'Review Required - Work Changed')
        self.assertEqual(self.jha.jha_status, 'Superseded')

    def test_offline_download_requires_a_current_signed_copy(self):
        for state, replacement in (('Draft', None), ('Review Required - Work Changed', None), ('Signed', 'JHA-2')):
            self.jha.jha_status = state; self.jha.replacement_jha = replacement
            with self.assertRaises(frappe.ValidationError): pack.download_jha_offline('JHA-1')

    def test_template_proposal_omits_people_owners_signatures_and_field_verification(self):
        result = learning.propose_jha_template('JHA-1', 'Pump restraint', 'template-1', 1)
        self.assertEqual(learning.propose_jha_template('JHA-1', 'Pump restraint', 'template-1', 1)['name'], result['name'])
        template = self.get_doc(learning.TEMPLATE, result['name'])
        content = json.loads(template.content)
        self.assertEqual(template.status, 'Pending Review')
        self.assertEqual(content['steps'][0]['activity'], 'Restrain pump')
        self.assertNotIn('control_owner', content['hazards'][0])
        self.assertNotIn('verification_status', content['hazards'][0])
        self.assertNotIn('participants', content)
        self.assertNotIn('signature', template.content)

    def test_template_selection_requires_approval_project_scope_differences_and_draft_stage(self):
        name = learning.propose_jha_template('JHA-1', 'Pump restraint', 'template-1', 1)['name']
        template = self.get_doc(learning.TEMPLATE, name)
        self.jha.jha_status = 'Draft'
        args = ('JHA-1', name, 'Different pump and access', 'use-1', 1)
        with self.assertRaises(frappe.PermissionError): learning.select_jha_template(*args)
        template.status = 'Approved'; template.project = 'OTHER'
        with self.assertRaises(frappe.PermissionError): learning.select_jha_template(*args)
        template.project = self.jha.project
        self.assertTrue(learning.select_jha_template(*args)['name'])
        self.assertEqual(len(self.jha.work_steps), 1)
        self.assertFalse(self.jha.get('job_steps_confirmed'))
        self.assertEqual(self.jha.review_signature, 'original signature')
        with self.assertRaises(frappe.ValidationError): learning.select_jha_template('JHA-1', name, '', 'use-2', 1)
        self.jha.job_steps_confirmed = 1
        with self.assertRaises(frappe.ValidationError): learning.select_jha_template(*args)

    def test_unreviewed_closeout_never_becomes_future_guidance_and_retries_do_not_duplicate(self):
        result = self.closeout()
        self.assertEqual(self.closeout()['name'], result['name'])
        self.assertEqual(len(Record.records), 1)
        self.assertEqual(learning.reviewed_lessons(self.jha), [])
        self.assertEqual(self.jha.jha_status, 'Signed')

    def test_closeout_review_requires_the_jha_reviewer_and_explicit_confirmed_notes(self):
        result = self.closeout()
        self.jha.reviewed_by = 'someone-else'
        with self.assertRaises(frappe.PermissionError): learning.review_jha_closeout('JHA-1', result['name'], 'Approved', 'Checked', 'Pump restraint access', 1)
        self.jha.reviewed_by = 'checker@example.test'
        with self.assertRaises(frappe.ValidationError): learning.review_jha_closeout('JHA-1', result['name'], 'Approved', '', 'Pump restraint access', 1)
        learning.review_jha_closeout('JHA-1', result['name'], 'Approved', 'Checked and de-identified', 'Pump restraint access must be reviewed.', 1)
        lessons = learning.reviewed_lessons(self.jha)
        self.assertEqual(len(lessons), 1)
        self.assertNotIn('Raw unreviewed proposal', json.dumps(lessons, default=str))
        self.assertEqual(lessons[0]['future_guidance'], 'Pump restraint access must be reviewed.')

    def test_guests_cannot_record_or_read_supporting_data(self):
        frappe.session.user = 'Guest'
        with self.assertRaises(frappe.PermissionError): self.resource()
        with self.assertRaises(frappe.PermissionError): pack.get_jha_resources('JHA-1')


class IntegrationTestJhaWorkpack(IntegrationTestCase):
    def make_jha(self, status='Signed', project=None):
        suffix = frappe.generate_hash(length=8)
        if not project:
            project = frappe.get_doc({'doctype': 'Project', 'project_name': f'JHA lifecycle {suffix}'})
            project.name = f'JHA-LIFECYCLE-{suffix}'; project.db_insert()
        task = frappe.get_doc({'doctype': 'Task', 'subject': 'Pump restraint', 'type': 'Work Summary', 'project': project.name})
        task.name = f'JHA-LIFECYCLE-TASK-{suffix}'; task.db_insert()
        jha = frappe.get_doc({'doctype': review.JHA_DOCTYPE, 'project': project.name, 'work_summary': task.name,
            'jha_status': status, 'revision': 1, 'reviewed_by': 'Administrator', 'review_signature': 'original-review',
            'work_steps': [{'sequence': 1, 'activity': 'Restrain pump'}], 'hazards_and_controls': [
                {'work_step_sequence': 1, 'hazard_or_energy_source': 'Stored energy', 'critical_control': 'Restraint'}]}).insert()
        return jha, project

    def test_real_supporting_records_are_immutable_and_do_not_change_signed_content(self):
        jha, _ = self.make_jha()
        result = pack.record_jha_resource(jha.name, jha.work_steps[0].name, 'Permit', 'integration-resource',
            reference='EXTERNAL-123', details='Pending issuer check.', confirmation=1)
        row = frappe.get_doc(pack.DOCTYPE, result['name'])
        row.reference = 'FORGED'
        with self.assertRaises(frappe.PermissionError): row.save(ignore_permissions=True)
        row.reload(); row.reference = 'FORGED'; row.flags.allow_jha_workpack_mutation = True
        with self.assertRaises(frappe.PermissionError): row.save(ignore_permissions=True)
        row.reload(); self.assertEqual(row.reference, 'EXTERNAL-123')
        with self.assertRaises(frappe.PermissionError): row.delete(ignore_permissions=True)
        jha.reload(); self.assertEqual(jha.jha_status, 'Signed'); self.assertEqual(jha.review_signature, 'original-review')
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc({'doctype': pack.DOCTYPE, 'jha': jha.name, 'revision': 1,
                'work_summary': jha.work_summary, 'kind': 'Permit', 'details': 'Forged', 'status': 'Confirmed',
                'recorded_by': 'Administrator', 'recorded_at': frappe.utils.now_datetime(),
                'request_key': frappe.generate_hash(), 'request_fingerprint': 'forged'}).insert(ignore_permissions=True)

    def test_real_template_review_and_reuse_never_copy_a_signature_or_confirm_steps(self):
        jha, project = self.make_jha()
        proposed = learning.propose_jha_template(jha.name, 'Pump restraint template', 'integration-template', 1)
        learning.review_jha_template(jha.name, proposed['name'], 'Approved', 'Reviewed reusable guidance.', 1)
        draft, _ = self.make_jha(status='Draft', project=project)
        learning.select_jha_template(draft.name, proposed['name'], 'Different pump model and access.', 'integration-use', 1)
        draft.reload(); self.assertFalse(draft.job_steps_confirmed)
        self.assertEqual(draft.jha_status, 'Draft')
        template = frappe.get_doc(learning.TEMPLATE, proposed['name'])
        self.assertNotIn('original-review', template.content)
        template.content = '{}'; template.flags.allow_jha_learning_mutation = True
        with self.assertRaises(frappe.PermissionError): template.save(ignore_permissions=True)
        learning.review_jha_template(jha.name, proposed['name'], 'Retired', 'Replaced guidance.', 1)
        with self.assertRaises(frappe.PermissionError):
            learning.select_jha_template(draft.name, proposed['name'], 'Old template', 'old-use', 1)

    def test_real_closeout_is_reviewed_separately_and_signed_revision_is_retained(self):
        jha, _ = self.make_jha()
        result = learning.record_jha_closeout(jha.name, 'No deviations', 'Improve pump access', 'Supervisor follow-up',
            'integration-closeout', lesson='Original crew proposal', confirmation=1)
        self.assertEqual(learning.reviewed_lessons(jha), [])
        learning.review_jha_closeout(jha.name, result['name'], 'Approved', 'Reviewed for future use.',
            future_guidance='Review pump restraint access before starting.', confirmation=1)
        self.assertEqual(len(learning.reviewed_lessons(jha)), 1)
        row = frappe.get_doc(learning.CLOSEOUT, result['name'])
        row.lesson = 'Changed'; row.flags.allow_jha_learning_mutation = True
        with self.assertRaises(frappe.PermissionError): row.save(ignore_permissions=True)
        jha.reload(); self.assertEqual(jha.jha_status, 'Signed'); self.assertEqual(jha.review_signature, 'original-review')
