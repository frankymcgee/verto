import json
from types import SimpleNamespace
from typing import Any
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase

from verto.api.mobile import peri_voice_settings as settings
from verto.api.mobile import voice_jha as base
from verto.api.mobile import voice_jha_facilitator as facilitator
from verto.api.mobile import voice_jha_tools as draft_tools
from verto.api.mobile import voice_jha_tools_streamlined as workflow
from verto.api.mobile.voice_jha_live import build_live_session, create_live_call


def live_session(**config):
    return build_live_session(
        config={**settings.DEFAULTS, **config}, conversation_style="One question at a time.",
        backend_instructions="Shared ordered JHA workflow.", tools=facilitator._streamlined_tools(),
        work_summary="WS-TEST", progress={"stage": "Step Analysis", "current_step_sequence": 2, "current_step_activity": "Fit pump"},
    )


class TestVoiceEngineSettings(TestCase):
    def config(self, **values):
        doc = SimpleNamespace(meta=SimpleNamespace(has_field=lambda key: key in values), get=values.get)
        with patch.object(frappe, 'get_cached_doc', return_value=doc):
            return settings.get_peri_voice_settings()

    def test_old_settings_preserve_realtime_and_gain_live_defaults(self):
        config = self.config(peri_voice_voice='cedar', peri_voice_speed=1.2)
        self.assertEqual(config['engine'], 'realtime')
        self.assertEqual((config['voice'], config['speed']), ('cedar', 1.2))
        self.assertEqual((config['live_model'], config['live_voice']), ('gpt-live-1', 'quartz'))

    def test_live_default_ripple_and_invalid_family_choices(self):
        config = self.config(peri_voice_engine='GPT Live', peri_voice_live_voice='ripple', peri_voice_voice='quartz')
        self.assertEqual((config['engine'], config['live_voice'], config['voice']), ('live', 'ripple', 'marin'))
        self.assertEqual(self.config(peri_voice_live_reasoning_effort='minimal')['live_reasoning_effort'], 'low')

    def test_session_uses_configured_engine_without_mutating_defaults(self):
        self.assertEqual(settings.voice_config_for_engine({**settings.DEFAULTS, 'engine': 'live'})['engine'], 'live')
        self.assertEqual(settings.DEFAULTS['engine'], 'realtime')
        with self.assertRaises(frappe.ValidationError):
            settings.voice_config_for_engine({**settings.DEFAULTS, 'engine': 'unknown-provider'})

    def test_public_config_reports_configured_engine_without_user_choices(self):
        config = base._public_voice_configuration({**settings.DEFAULTS, 'engine': 'live', 'live_custom_voice_id': 'voice_authorized'})
        self.assertEqual((config['engine'], config['model'], config['voice']), ('live', 'gpt-live-1', 'voice_authorized'))
        self.assertNotIn('engines', config)
        self.assertNotIn('api_key', config)


class TestLiveSession(TestCase):
    def test_shared_tool_parity_and_saved_stage_with_separate_prompts(self):
        tools = facilitator._streamlined_tools()
        session = live_session()
        responses = session['delegation']['responses']
        self.assertEqual([tool['name'] for tool in responses['tools']], [tool['name'] for tool in tools])
        self.assertIn('find_relevant_incidents', [tool['name'] for tool in responses['tools']])
        self.assertTrue(all(tool['strict'] is False for tool in responses['tools']))
        self.assertTrue(all('strict' not in tool for tool in tools))
        self.assertFalse(responses['parallel_tool_calls'])
        self.assertEqual(responses['model'], 'gpt-6-luna')
        self.assertIn('Shared ordered JHA workflow.', responses['instructions'])
        self.assertIn('current step: 2 Fit pump', session['instructions'])
        self.assertIn('Human review and sign-on', session['instructions'])
        self.assertNotIn('Shared ordered JHA workflow.', session['instructions'])
        self.assertFalse(session['store'])

    def test_live_audio_omits_realtime_only_settings(self):
        session = live_session()
        self.assertEqual(session['audio'], {'output': {'voice': 'quartz'}})
        self.assertNotIn('type', session)
        self.assertNotIn('output_modalities', session)
        self.assertNotIn('tools', session)
        self.assertNotIn('session.update', session['client']['data_channel']['allowed_client_events'])
        self.assertEqual(live_session(live_voice='ripple')['audio']['output']['voice'], 'ripple')
        self.assertEqual(live_session(live_custom_voice_id='voice_allowed')['audio']['output']['voice'], {'id': 'voice_allowed'})

    def test_typed_sdk_preserves_opaque_session_reference_and_disables_retry(self):
        response = SimpleNamespace(model_dump=lambda: {'session': {'id': 'live_opaque-123'}, 'transport': {'sdp': 'v=0\nanswer'}})
        create = Mock(return_value=response)
        client = SimpleNamespace(live=SimpleNamespace(create=create))
        client.with_options = Mock(return_value=client)
        result = create_live_call(client=client, sdp='v=0\noffer', session=live_session())
        self.assertEqual(result['session_reference'], 'live_opaque-123')
        self.assertEqual(result['sdp'], 'v=0\nanswer')
        client.with_options.assert_called_once_with(max_retries=0)
        self.assertEqual(create.call_args.kwargs['transport'], {'type': 'webrtc', 'sdp': 'v=0\noffer'})

    def test_existing_sdk_http_fallback_uses_same_live_request(self):
        post = Mock(return_value={'session': {'id': 'live_1'}, 'transport': {'sdp': 'v=0\nanswer'}})
        client = SimpleNamespace(post=post)
        client.with_options = Mock(return_value=client)
        session = live_session()
        self.assertEqual(create_live_call(client=client, sdp='v=0\noffer', session=session)['model'], 'gpt-live-1')
        post.assert_called_once_with('/live/sessions', cast_to=dict[str, Any], body={'session': session, 'transport': {'type': 'webrtc', 'sdp': 'v=0\noffer'}})

    def test_invalid_answer_and_sdk_request_errors_do_not_create_another_session(self):
        create = Mock(return_value={'session': {'id': 'live_1'}, 'transport': {'sdp': ''}})
        client = SimpleNamespace(live=SimpleNamespace(create=create), post=Mock())
        client.with_options = Mock(return_value=client)
        with self.assertRaises(frappe.ValidationError):
            create_live_call(client=client, sdp='v=0', session=live_session())
        create.side_effect = RuntimeError('Request failed')
        with self.assertRaises(RuntimeError):
            create_live_call(client=client, sdp='v=0', session=live_session())
        client.post.assert_not_called()


class TestVoiceCallRouting(TestCase):
    def setUp(self):
        self.config = self.enterContext(patch.object(facilitator, 'get_peri_voice_settings', return_value=dict(settings.DEFAULTS)))
        self.client = SimpleNamespace(realtime=SimpleNamespace(calls=SimpleNamespace(create=Mock(return_value=SimpleNamespace(text='v=0\nrealtime-answer')))))
        self.raven = self.enterContext(patch('raven.ai.openai_client.get_open_ai_client', return_value=self.client))
        self.task = SimpleNamespace(name='WS-1', subject='Pump')
        self.doc = SimpleNamespace(name='JHA-1', jha_status='Draft', work_summary='WS-1', has_permission=Mock(return_value=True), save=Mock())

    def test_realtime_request_still_uses_existing_session(self):
        with patch.object(facilitator, '_build_realtime_session', return_value={'type': 'realtime'}):
            result = facilitator._create_voice_call(sdp='v=0', task=self.task, jha=self.doc, bot=None)
        self.assertEqual((result['engine'], result['model']), ('realtime', 'gpt-realtime-2.1'))
        self.client.realtime.calls.create.assert_called_once_with(sdp='v=0', session={'type': 'realtime'})

    def test_live_routes_to_same_permission_checked_start_and_records_model(self):
        self.config.return_value = {**settings.DEFAULTS, 'engine': 'live'}
        with patch.object(base, '_require_login'), patch.object(base, '_get_jha_doc', return_value=self.doc), \
             patch.object(base, '_validate_work_summary', return_value=self.task), patch.object(base, '_get_peri_bot_doc'), \
             patch.object(facilitator, 'sync_facilitation_fields'), patch.object(facilitator, 'serialize_jha', return_value={'name': 'JHA-1'}), \
             patch.object(facilitator, '_build_live_session', return_value=live_session()), \
             patch.object(facilitator, 'create_live_call', return_value={'sdp': 'v=0\nanswer', 'model': 'gpt-live-1', 'session_reference': 'live_1'}) as create:
            # A cached client's Realtime choice cannot override Live in settings.
            result = facilitator.start_voice_jha_call('JHA-1', 'v=0\noffer', 1, 'realtime')
        self.assertEqual((result['engine'], self.doc.voice_model, self.doc.voice_session_reference), ('live', 'gpt-live-1', 'live_1'))
        self.assertEqual(result['jha']['name'], 'JHA-1')
        self.doc.save.assert_called_once()
        create.assert_called_once()
        self.client.realtime.calls.create.assert_not_called()

    def test_client_live_override_cannot_change_configured_realtime(self):
        with patch.object(base, '_require_login'), patch.object(base, '_get_jha_doc', return_value=self.doc), \
             patch.object(base, '_validate_work_summary', return_value=self.task), patch.object(base, '_get_peri_bot_doc'), \
             patch.object(facilitator, 'sync_facilitation_fields'), patch.object(facilitator, 'serialize_jha', return_value={'name': 'JHA-1'}), \
             patch.object(facilitator, '_build_realtime_session', return_value={'type': 'realtime'}), \
             patch.object(facilitator, 'create_live_call') as create:
            result = facilitator.start_voice_jha_call('JHA-1', 'v=0\noffer', 1, 'live')
        self.assertEqual(result['engine'], 'realtime')
        self.client.realtime.calls.create.assert_called_once()
        create.assert_not_called()

    def test_disabled_and_invalid_engine_make_no_api_request(self):
        for engine in ('live', 'realtime', 'unknown'):
            self.config.return_value = {**settings.DEFAULTS, 'enabled': False, 'engine': engine}
            with self.assertRaises(frappe.ValidationError):
                facilitator._create_voice_call(sdp='v=0', task=self.task, jha=self.doc, bot=None)
        self.raven.assert_not_called()

    def test_consent_and_write_permission_are_required_for_live(self):
        with patch.object(base, '_require_login'), patch.object(base, '_get_jha_doc', return_value=self.doc):
            with self.assertRaises(frappe.ValidationError):
                facilitator.start_voice_jha_call('JHA-1', 'v=0', 0, 'live')
            self.doc.has_permission.return_value = False
            with self.assertRaises(frappe.PermissionError):
                facilitator.start_voice_jha_call('JHA-1', 'v=0', 1, 'live')
        self.raven.assert_not_called()
        self.doc.save.assert_not_called()

    def test_signed_jha_cannot_start_either_engine(self):
        self.doc.jha_status = 'Signed'
        with patch.object(base, '_require_login'), patch.object(base, '_get_jha_doc', return_value=self.doc):
            for engine in ('live', 'realtime'):
                with self.assertRaises(frappe.ValidationError):
                    facilitator.start_voice_jha_call('JHA-1', 'v=0', 1, engine)
        self.raven.assert_not_called()


class TestVoiceFacilitationProgression(TestCase):
    def setUp(self):
        self.doc = frappe._dict(
            name='JHA-FLOW', jha_status='Voice Discussion in Progress', revision=1,
            work_summary='WS-FLOW', job_steps_confirmed=0, participants=[],
            work_steps=[frappe._dict(
                name=f'STEP-{sequence}', idx=sequence, sequence=sequence,
                source_step_identifier=f'step-{sequence}', activity=activity,
                hold_point_confirmed=1, hold_or_pause_point=0,
            ) for sequence, activity in [(1, 'Isolate pump'), (2, 'Fit pump')]],
            hazards_and_controls=[frappe._dict(
                name=f'HAZARD-{sequence}', work_step_sequence=sequence,
                hazard_or_energy_source='Pinch points', existing_controls='Alignment tooling',
            ) for sequence in (1, 2)],
            meta=SimpleNamespace(has_field=lambda key: False),
            has_permission=Mock(return_value=True), save=Mock(),
        )
        self.enterContext(patch.object(draft_tools, '_require_login'))
        self.enterContext(patch.object(draft_tools, '_get_jha', return_value=self.doc))

    def execute(self, name, **arguments):
        return workflow.execute_voice_jha_tool(
            self.doc.name, name, json.dumps(arguments), call_id=f'flow-{name}'
        )['result']

    def complete_steps(self):
        self.execute('confirm_job_steps')
        for sequence in (1, 2):
            self.execute('complete_current_step', step_sequence=sequence)

    def record_team(self):
        self.doc.participants = [frappe._dict(
            name='PERSON-1', participant_name='Crew member',
            present_for_discussion=1, transcription_consent=1,
        )]

    def test_confirmed_steps_advance_without_an_extra_readiness_gate(self):
        result = self.execute('confirm_job_steps')
        self.assertEqual(result['facilitation']['current_step_sequence'], 1)
        self.assertNotIn('review_voice_guidance', result)
        for sequence in (1, 2):
            result = self.execute('complete_current_step', step_sequence=sequence)
            self.assertTrue(result['changed'])
            self.assertEqual(result['completed_step_sequence'], sequence)
            self.assertEqual(result['facilitation']['current_step_sequence'], 2 if sequence == 1 else 0)
            self.assertNotIn('review_voice_guidance', result)
        self.assertEqual(result['facilitation']['stage'], 'Development Team')

    def test_a_missing_hold_point_answer_still_blocks_progression(self):
        self.execute('confirm_job_steps')
        self.doc.work_steps[0].hold_point_confirmed = 0
        result = self.execute('complete_current_step', step_sequence=1)
        self.assertFalse(result['changed'])
        self.assertEqual(result['facilitation']['current_step_sequence'], 1)
        self.assertTrue(any('hold-point' in issue for issue in result['issues']))
        self.assertNotIn('review_voice_guidance', result)

    def test_a_missing_critical_control_owner_still_blocks_progression(self):
        self.execute('confirm_job_steps')
        self.doc.hazards_and_controls[0].critical_control = 'Isolation'
        result = self.execute('complete_current_step', step_sequence=1)
        self.assertFalse(result['changed'])
        self.assertTrue(any('owner' in issue for issue in result['issues']))
        self.assertNotIn('review_voice_guidance', result)

    def test_incomplete_drafts_do_not_receive_the_review_waiting_guidance(self):
        result = self.execute('mark_ready_for_human_review')
        self.assertFalse(result['complete'])
        self.assertFalse(result['changed'])
        self.assertEqual(self.doc.jha_status, 'Voice Discussion in Progress')
        self.assertNotIn('review_voice_guidance', result)
        state = self.execute('get_current_jha_state')
        self.assertEqual(state['facilitation']['stage'], 'Job Steps')
        self.assertNotIn('review_voice_guidance', state)

    def test_review_guidance_arrives_only_after_the_draft_becomes_ready(self):
        self.complete_steps()
        self.record_team()
        result = self.execute('run_jha_completeness_check')
        self.assertTrue(result['complete'])
        self.assertNotIn('review_voice_guidance', result)
        result = self.execute('mark_ready_for_human_review')
        self.assertEqual(self.doc.jha_status, 'Ready for Team Review')
        self.assertEqual(result['facilitation']['stage'], 'Ready for Team Review')
        self.assertIn('Disconnect Voice', result['review_voice_guidance'])
        self.assertIn('Print JHA', result['review_voice_guidance'])
        state = self.execute('get_current_jha_state')
        self.assertEqual(state['review_voice_guidance'], result['review_voice_guidance'])
        with self.assertRaises(frappe.PermissionError):
            self.execute('record_work_step', step_identifier='step-1', sequence=1, activity='Changed work')
        self.assertEqual(self.doc.work_steps[0].activity, 'Isolate pump')

    def test_development_prompts_do_not_include_the_post_review_waiting_mode(self):
        task = frappe._dict(name='WS-FLOW', subject='Pump service')
        with patch.object(base, '_get_bot_instructions', return_value=''):
            for silent in (True, False):
                config = {**settings.DEFAULTS, 'silent_tool_success': silent}
                realtime = facilitator._build_realtime_session(task, self.doc, None, config)
                live = facilitator._build_live_session(task, self.doc, None, config)
                for instructions in (
                    realtime['instructions'], live['instructions'],
                    live['delegation']['responses']['instructions'],
                ):
                    self.assertNotIn(workflow.REVIEW_VOICE_GUIDANCE, instructions)
                    self.assertNotIn('Stay available to explain the recorded JHA', instructions)
                    self.assertIn('next', instructions.lower())
                self.assertIn("Do not wait for 'next question'", realtime['instructions'])


class IntegrationTestVoiceEngineSettings(IntegrationTestCase):
    def test_migrated_live_fields_preserve_existing_realtime_values(self):
        doc = frappe.get_single(settings.SETTINGS_DOCTYPE)
        doc.peri_voice_voice = 'cedar'
        doc.peri_voice_engine = 'GPT Live'
        doc.peri_voice_live_voice = 'ripple'
        doc.save(ignore_permissions=True)
        self.assertTrue(settings.ensure_peri_voice_settings())
        config = settings.get_peri_voice_settings()
        self.assertEqual((config['engine'], config['voice'], config['live_voice']), ('live', 'cedar', 'ripple'))
        self.assertEqual(frappe.get_meta(settings.SETTINGS_DOCTYPE).get_field('peri_voice_live_voice').default, 'quartz')
        self.assertIn('GPT Live', frappe.get_meta(settings.SETTINGS_DOCTYPE).get_field('peri_voice_engine').options)

    def test_raven_sdk_can_create_live_request_without_transmitting_credentials_to_browser(self):
        self._assert_sdk_live_request(force_legacy=False)

    def test_legacy_sdk_http_fallback_parses_the_real_response(self):
        self._assert_sdk_live_request(force_legacy=True)

    def _assert_sdk_live_request(self, *, force_legacy):
        from openai import _base_client
        from openai import OpenAI

        # Disable only the typed Live resource. with_options and post still use
        # the real SDK, including the parser that rejected a bare dict on older
        # Raven installs. Exercise this path even when CI installs a newer SDK.
        if force_legacy:
            self.enterContext(patch.object(OpenAI, 'live', None, create=True))
        httpx = getattr(_base_client, 'httpx2', None) or _base_client.httpx
        requests = []

        def answer(request):
            requests.append(request)
            return httpx.Response(201, json={'session': {'id': 'live_test'}, 'transport': {'type': 'webrtc', 'sdp': 'v=0\nanswer'}})

        with httpx.Client(transport=httpx.MockTransport(answer)) as http_client:
            with OpenAI(api_key='test-dummy-key', project='proj_test', http_client=http_client) as client:
                result = create_live_call(client=client, sdp='v=0\noffer', session=live_session())
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.path, '/v1/live/sessions')
        self.assertEqual(requests[0].headers['authorization'], 'Bearer test-dummy-key')
        self.assertEqual(requests[0].headers['openai-project'], 'proj_test')
        self.assertEqual(json.loads(requests[0].content)['transport'], {'type': 'webrtc', 'sdp': 'v=0\noffer'})
        self.assertEqual(result['session_reference'], 'live_test')
        self.assertEqual(result['sdp'], 'v=0\nanswer')
        self.assertNotIn('test-dummy-key', str(result))

    def test_legacy_sdk_does_not_retry_a_failed_session_creation(self):
        from openai import InternalServerError, OpenAI, _base_client

        self.enterContext(patch.object(OpenAI, 'live', None, create=True))
        httpx = getattr(_base_client, 'httpx2', None) or _base_client.httpx
        requests = []

        def fail(request):
            requests.append(request)
            return httpx.Response(500, json={'error': {'message': 'Session creation failed'}})

        with httpx.Client(transport=httpx.MockTransport(fail)) as http_client:
            with OpenAI(api_key='test-dummy-key', max_retries=2, http_client=http_client) as client:
                with self.assertRaises(InternalServerError):
                    create_live_call(client=client, sdp='v=0\noffer', session=live_session())
        self.assertEqual(len(requests), 1)
