import copy
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from verto.api.mobile import voice_jha_changes as changes
from verto.api.mobile import voice_jha_review as review
from verto.api.mobile import voice_jha_tools as tools
from verto.api.mobile import voice_jha_tools_streamlined as workflow
from verto.api.mobile import voice_jha_facilitator as facilitator
from verto.api.mobile import peri_voice_settings as settings


class Record(frappe._dict):
    def set(self, key, value): self[key] = value
    def as_dict(self): return dict(self)
    def append(self, key, values):
        row = Record(values)
        row.name = f'{key}-{len(self.get(key) or []) + 1}'
        row.idx = len(self.get(key) or []) + 1
        self.setdefault(key, []).append(row)
        return row
    def save(self, **kwargs): return self
    def reload(self): return self
    def insert(self): return self
    def has_permission(self, *args): return True


def completed_jha():
    doc = Record(name='JHA-OLD', jha_status='Signed', revision=1, work_summary='WS-1',
                 job_steps_confirmed=1, review_completed=1, review_signature='old-review-signature',
                 signed_at='2026-10-14 09:00:00', flags=frappe._dict(), incident_references=[],
                 meta=SimpleNamespace(has_field=lambda key: key == 'voice_tool_audit_log'))
    doc.work_steps = [Record(name=f'S-{i}', idx=i, sequence=i, activity=f'Step {i}',
                            source_step_identifier=f'step-{i}', step_discussion_complete=1,
                            critical_controls_reviewed=1, hold_point_confirmed=1, hold_or_pause_point=0)
                      for i in (1, 2)]
    doc.hazards_and_controls = [Record(name=f'H-{i}', source_hazard_identifier=f'hazard-{i}',
                                      work_step_reference=f'step-{i}', work_step_sequence=i,
                                      hazard_or_energy_source='Pinch points', existing_controls='Alignment tool')
                                for i in (1, 2)]
    doc.participants = [Record(name='P-1', source_participant_identifier='person-1',
                              participant_name='Crew member', present_for_discussion=1,
                              transcription_consent=1, acknowledged=1, acknowledgement_signature='old-person-signature')]
    return doc


class TestJhaChanges(TestCase):
    def setUp(self):
        self.original = completed_jha()
        self.docs = {self.original.name: self.original}
        def clone(original):
            doc = copy.deepcopy(original)
            doc.name = 'JHA-NEW'
            self.docs[doc.name] = doc
            return doc
        self.copy = self.enterContext(patch.object(frappe, 'copy_doc', side_effect=clone))
        self.enterContext(patch.object(frappe.db, 'sql', return_value=[]))
        self.enterContext(patch.object(frappe, 'get_doc', side_effect=lambda doctype, name: self.docs[name]))
        self.enterContext(patch.object(review, '_require_login'))
        self.enterContext(patch.object(review, '_get_jha', side_effect=lambda name, **kw: self.docs[name]))
        self.enterContext(patch.object(tools, '_require_login'))
        self.enterContext(patch.object(tools, '_get_jha', side_effect=lambda name: self.docs[name]))
        self.counter = 0

    def begin(self):
        changes.begin_jha_change(self.original.name, 1)
        return self.docs['JHA-NEW']

    def call(self, name, arguments=None, call_id=None):
        self.counter += 1
        return workflow.execute_voice_jha_tool('JHA-NEW', name, json.dumps(arguments or {}), call_id or f'change-{self.counter}')

    def scope(self, sequences=(2,)):
        return self.call('record_jha_change_request', {'summary': 'Add an additional pinch-point control',
                                                     'affected_step_sequences': list(sequences)})

    def test_start_preserves_the_original_signatures_and_duplicate_taps_resume(self):
        draft = self.begin()
        self.assertEqual(draft.previous_jha, self.original.name)
        self.assertEqual(draft.revision, 2)
        self.assertEqual(draft.change_management_stage, 'Describe Change')
        self.assertEqual(draft.review_completed, 0)
        self.assertIsNone(draft.review_signature)
        self.assertFalse(draft.participants[0].acknowledged)
        self.assertIsNone(draft.participants[0].acknowledgement_signature)
        self.assertEqual(self.original.review_signature, 'old-review-signature')
        self.assertEqual(self.original.participants[0].acknowledgement_signature, 'old-person-signature')
        self.assertEqual(self.original.replacement_jha, draft.name)
        self.assertEqual(self.original.jha_status, 'Review Required - Work Changed')
        self.assertEqual(changes.begin_jha_change(self.original.name, 1)['name'], draft.name)
        self.copy.assert_called_once()

    def test_only_the_confirmed_affected_step_is_reopened_and_editable(self):
        draft = self.begin()
        result = self.scope()['result']
        self.assertEqual(result['facilitation']['current_step_sequence'], 2)
        self.assertEqual(draft.work_steps[0].step_discussion_complete, 1)
        self.assertEqual(draft.work_steps[1].hold_point_confirmed, 0)
        with self.assertRaises(frappe.PermissionError):
            self.call('record_work_step', {'step_identifier': 'step-1', 'sequence': 1, 'activity': 'Wrong target'})
        with self.assertRaises(frappe.PermissionError):
            self.call('record_hazard_and_control', {'hazard_identifier': 'hazard-1', 'work_step_identifier': 'step-2', 'work_step_sequence': 2})
        self.assertEqual(self.original.work_steps[1].hold_point_confirmed, 1)

    def test_insertion_renumbers_steps_hazards_and_scope_together_and_is_replay_safe(self):
        draft = self.begin()
        self.scope()
        self.call('add_jha_change_step', {'activity': 'Fit lifting fixture', 'after_step_sequence': 1}, 'insert-once')
        self.assertEqual(draft.work_steps[1].sequence, 3)
        self.assertEqual(draft.hazards_and_controls[1].work_step_sequence, 3)
        self.assertEqual(changes.target_steps(draft), [2, 3])
        result = self.call('add_jha_change_step', {'activity': 'Fit lifting fixture', 'after_step_sequence': 1}, 'insert-once')
        self.assertTrue(result['replayed'])
        self.assertEqual(len(draft.work_steps), 3)
        self.assertEqual(self.original.work_steps[1].sequence, 2)

    def test_changed_work_needs_its_hold_point_and_crew_change_confirmation(self):
        draft = self.begin()
        self.scope()
        incomplete = self.call('complete_current_step', {'step_sequence': 2})['result']
        self.assertFalse(incomplete['changed'])
        with self.assertRaises(frappe.ValidationError): self.call('confirm_jha_changes')
        self.call('record_work_step', {'step_identifier': 'step-2', 'sequence': 2, 'hold_or_pause_point': False})
        self.call('complete_current_step', {'step_sequence': 2})
        self.assertEqual(self.call('get_current_jha_state')['result']['facilitation']['stage'], 'Change Confirmation')
        self.assertFalse(self.call('mark_ready_for_human_review')['result']['complete'])
        self.call('confirm_jha_changes')
        self.call('record_participant', {'participant_identifier': 'person-1', 'participant_name': 'Crew member', 'transcription_consent': True})
        self.assertEqual(draft.change_management_stage, 'Confirmed')
        ready = self.call('mark_ready_for_human_review')['result']
        self.assertTrue(ready['complete'])
        self.assertEqual(draft.jha_status, 'Ready for Team Review')
        self.assertEqual(draft.review_completed, 0)
        self.assertFalse(draft.participants[0].acknowledged)

    def test_changes_cannot_be_started_by_a_voice_tool_or_without_access(self):
        self.docs['JHA-NEW'] = self.original
        self.original.jha_status = 'Draft'
        with self.assertRaises(frappe.PermissionError): self.scope()
        with patch.object(review, '_get_jha', side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError): changes.begin_jha_change(self.original.name, 1)
        self.copy.assert_not_called()

    def test_scope_rejects_unknown_or_invalid_step_numbers(self):
        self.begin()
        for values in ([99], [True], ['2'], [{}]):
            with self.assertRaises(frappe.ValidationError):
                self.call('record_jha_change_request', {'summary': 'Changed work', 'affected_step_sequences': values})

    def test_signing_the_replacement_supersedes_only_its_linked_predecessor(self):
        draft = self.begin()
        draft.jha_status = 'Signed'
        changes.supersede_previous_revision(draft)
        self.assertEqual(self.original.jha_status, 'Superseded')
        self.assertEqual(self.original.review_signature, 'old-review-signature')
        self.original.replacement_jha = 'A-DIFFERENT-JHA'
        with self.assertRaises(frappe.ValidationError): changes.supersede_previous_revision(draft)

    def test_change_sessions_use_the_change_interview_instead_of_restarting_the_job(self):
        draft = self.begin()
        task = frappe._dict(name='WS-1', subject='Pump service')
        with patch.object(facilitator.base, '_get_bot_instructions', return_value=''):
            realtime = facilitator._build_realtime_session(task, draft, None, settings.DEFAULTS)
            live = facilitator._build_live_session(task, draft, None, settings.DEFAULTS)
        for instructions in (realtime['instructions'], live['delegation']['responses']['instructions']):
            self.assertIn('record_jha_change_request', instructions)
            self.assertIn('JHA-OLD', instructions)
            self.assertNotIn('PHASE 2 — ESTABLISH THE COMPLETE JOB-STEP LIST', instructions)


class IntegrationTestJhaChanges(IntegrationTestCase):
    def test_revision_copy_uses_real_documents_and_protects_the_signed_content(self):
        suffix = frappe.generate_hash(length=8)
        # Minimal real linked fixtures; unrelated Project/Raven provisioning is
        # outside this test. The JHA itself uses the complete document lifecycle.
        project = frappe.get_doc({'doctype': 'Project', 'project_name': f'JHA change test {suffix}'})
        project.name = f'JHA-CHANGE-PROJECT-{suffix}'
        project.db_insert()
        task = frappe.get_doc({'doctype': 'Task', 'subject': 'JHA change work summary', 'type': 'Work Summary', 'project': project.name})
        task.name = f'JHA-CHANGE-TASK-{suffix}'
        task.db_insert()
        source = completed_jha()
        source.pop('meta'); source.pop('flags'); source.pop('name')
        source['doctype'] = 'Digital Job Hazard Analysis'
        source['project'] = project.name
        source['work_summary'] = task.name
        for field in ('work_steps', 'hazards_and_controls', 'participants'):
            source[field] = [{key: value for key, value in row.items() if key not in ('name', 'idx')} for row in source[field]]
        original = frappe.get_doc(dict(source)).insert()
        snapshot = changes.begin_jha_change(original.name, 1)
        draft = frappe.get_doc('Digital Job Hazard Analysis', snapshot['name'])
        original.reload()
        self.assertNotEqual(draft.name, original.name)
        self.assertEqual(draft.previous_jha, original.name)
        self.assertEqual(original.review_signature, 'old-review-signature')
        self.assertEqual(draft.revision, 2)
        self.assertFalse(draft.review_completed)
        original.hazards_and_controls[0].existing_controls = 'Overwrite signed content'
        with self.assertRaises(frappe.PermissionError): original.save()
        draft.change_summary = 'Bypass the controlled workflow'
        with self.assertRaises(frappe.PermissionError): draft.save()
