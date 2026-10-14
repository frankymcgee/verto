import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from verto.api.mobile import voice_jha_steps as steps, voice_jha_facilitator as voice
from verto.api.mobile import voice_jha_tools_streamlined as tools
from verto.api.mobile import voice_jha as base
from verto.api.mobile import test_voice_jha_fieldwork as fixture
from verto.api.mobile import test_voice_jha_workpack as workpack_fixture
from verto.api.mobile.peri_voice_settings import DEFAULTS

Record = fixture.Record


class TestJhaStepBriefing(TestCase):
    get_doc = fixture.TestJhaFieldwork.get_doc
    get_value = fixture.TestJhaFieldwork.get_value

    def get_all(self, doctype, filters=None, pluck=None, **kwargs):
        rows = fixture.TestJhaFieldwork.get_all(self, doctype, filters, **kwargs)
        if kwargs.get('limit_page_length'):
            rows = rows[:kwargs['limit_page_length']]
        return [row.get(pluck) for row in rows] if pluck else rows

    def setUp(self):
        fixture.TestJhaFieldwork.setUp(self)
        self.jha.work_steps = [Record(name='STEP-1', sequence=1, activity='Restrain pump', hold_or_pause_point=1),
                               Record(name='STEP-2', sequence=2, activity='Lift pump', hold_or_pause_point=0)]
        self.jha.hazards_and_controls[0].critical_risk_categories = 'Uncontrolled Release of Energy'
        self.jha.hazards_and_controls.append(Record(name='H-2', work_step_sequence=2,
            hazard_or_energy_source='Suspended load', exposure_mechanisms='Line of Fire'))
        self.search = self.enterContext(patch.object(steps, 'find_incident_learning', return_value={
            'status': 'matches', 'incidents': [{'name': 'INC-1', 'modified': '2026-10-14 09:00',
                'incident_summary': 'Stored pressure released', 'matched_on': {'mechanisms': ['Stored Energy Release']}}]}))

    def select(self, step='STEP-1', request='select-1'):
        return steps.select_jha_active_step('JHA-1', step, request)

    def test_selection_is_human_revision_bound_and_does_not_edit_signed_content(self):
        result = self.select()
        self.assertEqual(result['active_step']['step_row'], 'STEP-1')
        self.assertEqual(result['active_step']['selected_by'], 'checker@example.test')
        self.assertEqual(result['active_step']['hazards'][0]['critical_control'], 'Mechanical restraint')
        self.assertEqual(result['active_step']['critical_controls'][0]['status'], 'Pending')
        self.assertEqual(self.jha.review_signature, 'original signature')
        self.assertEqual(self.jha.jha_status, 'Signed')
        self.assertEqual((Record.records[0].jha, Record.records[0].revision), ('JHA-1', 1))
        self.assertNotIn('Stored pressure released', Record.records[0].incident_references)

    def test_incident_search_is_selected_step_only_and_includes_its_risk_tags(self):
        self.select()
        text, risks, mechanisms = self.search.call_args.args
        self.assertIn('Restrain pump', text)
        self.assertIn('Stored energy', text)
        self.assertNotIn('Suspended load', text)
        self.assertEqual(risks, ['Uncontrolled Release of Energy'])
        self.select('STEP-2', 'select-2')
        text, risks, mechanisms = self.search.call_args.args
        self.assertNotIn('Stored energy', text)
        self.assertEqual(mechanisms, ['Line of Fire'])

    def test_duplicate_requests_never_reactivate_an_old_selection(self):
        first = self.select()
        second = self.select('STEP-2', 'select-2')
        replay = self.select()
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['active_step']['name'], second['active_step']['name'])
        self.assertEqual(replay['active_step']['selection_number'], 2)
        self.assertEqual(len(Record.records), 2)
        self.assertNotEqual(first['active_step']['name'], second['active_step']['name'])
        with self.assertRaises(frappe.ValidationError): self.select('STEP-2')

    def test_invalid_step_request_and_unsigned_or_replaced_revisions_are_rejected(self):
        for step, request in [('OTHER-REVISION-STEP', 'id'), ('STEP-1', ''), ('STEP-1', 'x' * 101)]:
            with self.subTest(step=step), self.assertRaises(frappe.ValidationError): self.select(step, request)
        for status in ['Draft', 'Ready for Team Review', 'Review Required - Work Changed', 'Superseded', 'Cancelled']:
            self.jha.jha_status = status
            with self.subTest(status=status), self.assertRaises(frappe.ValidationError): self.select()
        self.jha.jha_status = 'Signed'; self.jha.replacement_jha = 'JHA-2'
        with self.assertRaises(frappe.ValidationError): self.select()

    def test_reads_recheck_evidence_and_keep_unavailable_distinct_from_no_matches(self):
        self.select()
        for status in ['no_matches', 'unavailable']:
            self.search.return_value = {'status': status, 'incidents': []}
            state = steps.get_jha_step_briefing('JHA-1')
            self.assertEqual(state['incident_learning']['status'], status)
            self.assertEqual(state['incident_learning']['incidents'], [])
            self.assertNotIn('Stored pressure released', json.dumps(state))
        self.assertEqual(frappe.local.response_headers['Cache-Control'], 'no-store')

    def test_voice_tools_are_read_only_and_follow_the_latest_human_selection(self):
        self.select(); self.select('STEP-2', 'select-2')
        result = tools.execute_voice_jha_tool('JHA-1', 'get_current_jha_state', step_briefing=1)
        self.assertEqual(result['result']['step_briefing']['active_step']['step_row'], 'STEP-2')
        for name in ['record_work_step', 'record_hazard_and_control', 'record_jha_shift_check', 'select_jha_active_step', 'approve']:
            with self.subTest(name=name), self.assertRaises(frappe.PermissionError):
                tools.execute_voice_jha_tool('JHA-1', name, step_briefing=1)
        self.assertEqual([tool['name'] for tool in steps.step_briefing_tools()], ['get_current_jha_state'])

    def test_guest_and_revoked_job_access_cannot_read_or_select_steps(self):
        frappe.session.user = 'Guest'
        with self.assertRaises(frappe.PermissionError): self.select()
        with self.assertRaises(frappe.PermissionError): steps.get_jha_step_briefing('JHA-1')
        frappe.session.user = 'checker@example.test'
        with patch.object(steps.review, '_get_jha', side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError): self.select()
            with self.assertRaises(frappe.PermissionError): steps.execute_step_tool('JHA-1', 'get_current_jha_state')

    def test_voice_start_requires_selection_consent_and_preserves_signed_voice_metadata(self):
        self.jha.voice_model = 'original-development-model'
        call = {'sdp': 'v=0\nanswer', 'model': 'test-model', 'engine': 'live', 'session_reference': 'opaque-session'}
        with patch.object(base, '_get_jha_doc', return_value=self.jha), \
             patch.object(base, '_validate_work_summary', return_value=SimpleNamespace(name='WS-1', subject='Pump')), \
             patch.object(base, '_get_peri_bot_doc'), patch.object(voice, '_create_voice_call', return_value=call) as create, \
             patch.object(voice, 'serialize_jha', return_value={'name': 'JHA-1', 'status': 'Signed'}), \
             patch.object(voice, 'sync_facilitation_fields') as sync:
            with self.assertRaises(frappe.ValidationError): voice.start_voice_jha_call('JHA-1', 'v=0', 1, step_briefing=1)
            self.select()
            with self.assertRaises(frappe.ValidationError): voice.start_voice_jha_call('JHA-1', 'v=0', 0, step_briefing=1)
            with self.assertRaises(frappe.ValidationError): voice.start_voice_jha_call('JHA-1', 'v=0', 1, shift_review='SHIFT-1', step_briefing=1)
            result = voice.start_voice_jha_call('JHA-1', 'v=0', 1, step_briefing=1)
            self.assertEqual(result['jha']['status'], 'Signed')
            self.assertEqual(self.jha.voice_model, 'original-development-model')
            self.assertEqual(Record.records[0].voice_consent_confirmed_by, 'checker@example.test')
            self.assertEqual(Record.records[0].voice_session_reference, 'opaque-session')
            create.assert_called_once(); sync.assert_not_called()

    def test_both_session_engines_get_only_read_state_and_the_execution_prompt(self):
        self.jha.flags.step_briefing = True
        task = Record(name='WS-1', subject='Pump', project='PROJECT-1')
        realtime = voice._build_realtime_session(task, self.jha, Record(), dict(DEFAULTS))
        live = voice._build_live_session(task, self.jha, Record(), dict(DEFAULTS))
        self.assertEqual([tool['name'] for tool in realtime['tools']], ['get_current_jha_state'])
        self.assertEqual([tool['name'] for tool in live['delegation']['responses']['tools']], ['get_current_jha_state'])
        self.assertIn('read-only', realtime['instructions'])
        self.assertIn('EXECUTION STEP BRIEFING', live['instructions'])
        self.assertIn('EXECUTION STEP BRIEFING', live['delegation']['responses']['instructions'])


class IntegrationTestJhaStepBriefing(IntegrationTestCase):
    make_jha = workpack_fixture.IntegrationTestJhaWorkpack.make_jha

    def test_real_selection_history_retains_signed_content_and_rejects_manual_edits(self):
        jha, _ = self.make_jha()
        original_modified = jha.modified
        first = steps.select_jha_active_step(jha.name, jha.work_steps[0].name, 'first')
        second = steps.select_jha_active_step(jha.name, jha.work_steps[0].name, 'second')
        replay = steps.select_jha_active_step(jha.name, jha.work_steps[0].name, 'first')
        self.assertEqual(replay['active_step']['name'], second['active_step']['name'])
        self.assertEqual(second['active_step']['selection_number'], 2)
        row = frappe.get_doc(steps.DOCTYPE, first['active_step']['name'])
        row.work_step = 99
        with self.assertRaises(frappe.PermissionError): row.save(ignore_permissions=True)
        row.reload(); row.flags.allow_jha_step_mutation = True; row.work_step = 99
        with self.assertRaises(frappe.PermissionError): row.save(ignore_permissions=True)
        row.reload()
        with self.assertRaises(frappe.PermissionError): row.delete(ignore_permissions=True)
        jha.reload()
        self.assertEqual(jha.jha_status, 'Signed')
        self.assertEqual(jha.review_signature, 'original-review')
        self.assertEqual(frappe.utils.get_datetime(jha.modified), frappe.utils.get_datetime(original_modified))

    def test_real_voice_metadata_lives_on_the_briefing_and_old_revision_cannot_reconnect(self):
        jha, _ = self.make_jha()
        selected = steps.select_jha_active_step(jha.name, jha.work_steps[0].name, 'voice')
        call = {'sdp': 'v=0\nanswer', 'model': 'fixture-model', 'engine': 'realtime', 'session_reference': 'fixture-session'}
        with patch.object(voice, '_create_voice_call', return_value=call), patch.object(base, '_get_peri_bot_doc'):
            voice.start_voice_jha_call(jha.name, 'v=0\noffer', 1, step_briefing=1)
        row = frappe.get_doc(steps.DOCTYPE, selected['active_step']['name'])
        self.assertEqual(row.voice_session_reference, 'fixture-session')
        self.assertEqual(row.voice_consent_confirmed_by, 'Administrator')
        jha.reload(); self.assertFalse(jha.voice_started_at); self.assertEqual(jha.jha_status, 'Signed')
        jha.jha_status = 'Review Required - Work Changed'; jha.flags.allow_jha_review_mutation = True
        jha.save(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError): steps.select_jha_active_step(jha.name, jha.work_steps[0].name, 'stale')
        with self.assertRaises(frappe.ValidationError): steps.execute_step_tool(jha.name, 'get_current_jha_state')
