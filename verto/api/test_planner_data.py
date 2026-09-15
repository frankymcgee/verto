import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from verto.api import planner_data


class TestPlannerData(TestCase):
    def setUp(self):
        patches = [
            patch.object(planner_data, 'can_subscribe', return_value=True),
            patch.object(frappe, 'local', SimpleNamespace(message_log=[])),
            patch.object(frappe, 'call', side_effect=lambda fn, **kwargs: fn(**kwargs)),
            patch.object(frappe, 'log_error'),
        ]
        for context in patches:
            context.start()
            self.addCleanup(context.stop)

    def test_access_is_checked_before_bootstrap_or_batch_queries(self):
        with patch.object(planner_data, 'can_subscribe', return_value=False), patch.object(planner_data, '_list') as read:
            with self.assertRaises(frappe.PermissionError):
                planner_data.get_bootstrap()
            with self.assertRaises(frappe.PermissionError):
                planner_data.get_planner_data([])
            read.assert_not_called()

    def test_rejects_writes_unknown_types_and_unbounded_batches_before_reading(self):
        valid = {'method': 'frappe.client.get_list', 'params': {'doctype': 'Employee'}}
        invalids = [
            [], [valid] * 21, '{bad json', {},
            [valid, {'method': 'frappe.client.delete', 'params': {'doctype': 'Employee', 'name': 'EMP-1'}}],
            [{'method': 'frappe.client.get_list', 'params': {'doctype': 'User'}}],
            [{'method': 'frappe.client.get_list', 'params': {'doctype': 'Employee', 'limit_page_length': 0}}],
            [{'method': 'frappe.client.get_list', 'params': {'doctype': 'Employee', 'limit_page_length': 100001}}],
            [{'method': 'frappe.client.get_list', 'params': {'doctype': 'Employee', 'limit_start': -1}}],
            [{'method': 'frappe.client.get_list', 'params': []}],
            [{'method': [], 'params': {}}],
            [{'method': 'frappe.client.get_list', 'params': {'doctype': []}}],
        ]
        with patch.object(planner_data, '_list') as read:
            for requests in invalids:
                with self.subTest(requests=requests), self.assertRaises(frappe.ValidationError):
                    planner_data.get_planner_data(requests)
            read.assert_not_called()

    def test_lists_delegate_to_the_permission_aware_frappe_client_handler(self):
        with patch('frappe.client.get_list', return_value=[{'name': 'EMP-1'}]) as get_list:
            response = planner_data.get_planner_data(json.dumps([{
                'method': 'frappe.client.get_list', 'params': {
                    'doctype': 'Employee', 'fields': ['name'], 'filters': {'company': 'MSS'},
                    'limit_page_length': 99999, 'limit_start': 0,
                    'limit': 99999, 'start': 0, 'ignore_permissions': True,
                },
            }]))
            self.assertEqual(response, {'results': [{'data': [{'name': 'EMP-1'}]}]})
            get_list.assert_called_once_with(doctype='Employee', fields=['name'], filters={'company': 'MSS'},
                                            limit_page_length=99999, limit_start=0)

    def test_denied_read_does_not_hide_successful_roster_or_leak_messages(self):
        original_messages = ['outer message']
        frappe.local.message_log = original_messages

        def denied(**kwargs):
            frappe.local.message_log.append('private failure')
            raise frappe.PermissionError('Project access denied')

        with patch.object(planner_data, '_list', side_effect=denied), patch.object(
            planner_data.planner, 'get_year_events', return_value={'contract_version': 2}
        ) as events:
            response = planner_data.get_planner_data([
                {'method': 'frappe.client.get_list', 'params': {'doctype': 'Project'}},
                {'method': 'verto.api.planner.get_year_events', 'params': {
                    'year': 2026, 'employee_filters': {'company': 'MSS'}, 'contract_version': 2,
                }},
            ])
            self.assertEqual(response['results'][0]['error']['exc_type'], 'PermissionError')
            self.assertEqual(response['results'][1]['data'], {'contract_version': 2})
            self.assertIs(frappe.local.message_log, original_messages)
            self.assertEqual(original_messages, ['outer message'])
            events.assert_called_once_with(year=2026, employee_filters={'company': 'MSS'}, contract_version=2)

    def test_unexpected_error_is_logged_without_returning_tracebacks(self):
        with patch.object(planner_data, '_list', side_effect=RuntimeError('private database connection')):
            response = planner_data.get_planner_data([{'method': 'frappe.client.get_list', 'params': {'doctype': 'Project'}}])
        self.assertNotIn('private', json.dumps(response))
        frappe.log_error.assert_called_once()

    def test_bootstrap_only_sends_allowed_settings_and_permission_checked_options(self):
        values = {'planner_app_name': 'Planner', 'desk_icon': 'masked', 'api_secret': 'never send'}
        doc = Mock(get=values.get)
        with patch.object(frappe, 'get_doc', return_value=doc), patch.object(planner_data, '_list', return_value=[]) as read:
            data = planner_data.get_bootstrap(['settings', 'references', 'projects'])
        self.assertEqual(set(data['settings']), set(planner_data.SETTINGS_FIELDS))
        self.assertNotIn('never send', json.dumps(data))
        doc.check_permission.assert_called_once_with('read')
        doc.apply_fieldlevel_read_permissions.assert_called_once()
        self.assertEqual(read.call_count, 7)
        self.assertTrue(all(call.kwargs['limit_page_length'] > 0 for call in read.call_args_list))
        self.assertIn('company', next(call.kwargs['fields'] for call in read.call_args_list if call.kwargs['doctype'] == 'Department'))

    def test_project_refresh_does_not_reload_settings_employees_or_reference_lists(self):
        with patch.object(planner_data, '_list', return_value=[{'name': 'PROJ-1'}]) as read, patch.object(frappe, 'get_doc') as doc:
            data = planner_data.get_bootstrap(['projects'])
            self.assertEqual(set(data), {'sections', 'errors', 'projects'})
            self.assertEqual(data['projects'], [{'name': 'PROJ-1'}])
            read.assert_called_once()
            self.assertEqual(read.call_args.kwargs['doctype'], 'Project')
            doc.assert_not_called()

    def test_bootstrap_preserves_available_options_when_one_reference_is_denied(self):
        def read(**params):
            if params['doctype'] == 'Company':
                raise frappe.PermissionError('Company access denied')
            return [{'name': 'Allowed'}]
        with patch.object(planner_data, '_list', side_effect=read):
            data = planner_data.get_bootstrap(['references'])
        self.assertEqual(data['references']['company'], [])
        self.assertEqual(data['references']['branch'], [{'name': 'Allowed'}])
        self.assertEqual(data['errors']['references.company']['exc_type'], 'PermissionError')

    def test_invalid_bootstrap_sections_are_rejected(self):
        for sections in [[], {}, ['unknown'], [None], 'invalid']:
            with self.subTest(sections=sections), self.assertRaises(frappe.ValidationError):
                planner_data.get_bootstrap(sections)
