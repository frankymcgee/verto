from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase

from verto.api.mobile import peri_voice_settings as settings
from verto.api.mobile import voice_jha as base
from verto.api.mobile import voice_jha_facilitator as facilitator
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

    def test_session_override_validates_engine_without_mutating_defaults(self):
        self.assertEqual(settings.voice_config_for_engine(settings.DEFAULTS, 'live')['engine'], 'live')
        self.assertEqual(settings.DEFAULTS['engine'], 'realtime')
        with self.assertRaises(frappe.ValidationError):
            settings.voice_config_for_engine(settings.DEFAULTS, 'unknown-provider')

    def test_public_config_reports_both_engines_and_selected_voice(self):
        config = base._public_voice_configuration({**settings.DEFAULTS, 'engine': 'live', 'live_custom_voice_id': 'voice_authorized'})
        self.assertEqual((config['engine'], config['model'], config['voice']), ('live', 'gpt-live-1', 'voice_authorized'))
        self.assertEqual([row['id'] for row in config['engines']], ['realtime', 'live'])
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
        post.assert_called_once_with('/live/sessions', cast_to=dict, body={'session': session, 'transport': {'type': 'webrtc', 'sdp': 'v=0\noffer'}})

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
        with patch.object(base, '_require_login'), patch.object(base, '_get_jha_doc', return_value=self.doc), \
             patch.object(base, '_validate_work_summary', return_value=self.task), patch.object(base, '_get_peri_bot_doc'), \
             patch.object(facilitator, 'sync_facilitation_fields'), patch.object(facilitator, 'serialize_jha', return_value={'name': 'JHA-1'}), \
             patch.object(facilitator, '_build_live_session', return_value=live_session()), \
             patch.object(facilitator, 'create_live_call', return_value={'sdp': 'v=0\nanswer', 'model': 'gpt-live-1', 'session_reference': 'live_1'}) as create:
            result = facilitator.start_voice_jha_call('JHA-1', 'v=0\noffer', 1, 'live')
        self.assertEqual((result['engine'], self.doc.voice_model, self.doc.voice_session_reference), ('live', 'gpt-live-1', 'live_1'))
        self.assertEqual(result['jha']['name'], 'JHA-1')
        self.doc.save.assert_called_once()
        create.assert_called_once()
        self.client.realtime.calls.create.assert_not_called()

    def test_disabled_and_invalid_engine_make_no_api_request(self):
        self.config.return_value = {**settings.DEFAULTS, 'enabled': False}
        for engine in ('live', 'realtime', 'unknown'):
            with self.assertRaises(frappe.ValidationError):
                facilitator._create_voice_call(sdp='v=0', task=self.task, jha=self.doc, bot=None, voice_engine=engine)
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
        from openai import _base_client
        from openai import OpenAI
        # Exercise the HTTP implementation used by the installed Raven SDK.
        httpx = getattr(_base_client, 'httpx2', None) or _base_client.httpx
        requests = []

        def answer(request):
            requests.append(request)
            return httpx.Response(201, json={'session': {'id': 'live_test'}, 'transport': {'type': 'webrtc', 'sdp': 'v=0\nanswer'}})

        with httpx.Client(transport=httpx.MockTransport(answer)) as http_client:
            with OpenAI(api_key='test-dummy-key', http_client=http_client) as client:
                result = create_live_call(client=client, sdp='v=0\noffer', session=live_session())
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.path, '/v1/live/sessions')
        self.assertEqual(requests[0].headers['authorization'], 'Bearer test-dummy-key')
        self.assertEqual(result['session_reference'], 'live_test')
        self.assertNotIn('test-dummy-key', str(result))
