import gzip
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from verto.api.mobile import boot, documents, navigation, offline, pwa_manifest, push_notifications


class TestMobileBootPerformance(TestCase):
    def test_boot_contains_navigation_metadata_and_only_public_push_configuration(self):
        with patch.object(frappe, 'session', SimpleNamespace(user='viewer')), \
             patch.object(frappe, 'local', SimpleNamespace(site='dev-site')), \
             patch.object(frappe.sessions, 'get_csrf_token', return_value='csrf'), \
             patch.object(frappe.db, 'get_value', return_value={'full_name': 'Viewer'}), \
             patch.object(boot, 'get_mobile_settings', return_value=None), \
             patch.object(boot, 'get_site_base_url', return_value='https://example.test'), \
             patch.object(boot, 'get_peri_bot_image_from_raven', return_value=''), \
             patch.object(navigation, 'get_navigation_access', return_value={'has_employee_profile': True}), \
             patch.object(pwa_manifest, 'get_pwa_metadata', return_value={'app_name': 'MSS', 'icon': '/icon.png'}), \
             patch.object(push_notifications, '_get_vapid_config', return_value={
                 'configured': True, 'public_key': 'PUBLIC', 'private_key': 'SECRET',
             }), patch.object(frappe.db, 'count') as count:
            result = boot.get_mobile_boot()
        self.assertTrue(result['navigation_access']['has_employee_profile'])
        self.assertEqual(result['pwa_metadata']['app_name'], 'MSS')
        self.assertEqual(result['push_config'], {'configured': True, 'public_key': 'PUBLIC'})
        self.assertNotIn('SECRET', json.dumps(result))
        count.assert_not_called()

    def test_guest_cannot_load_boot_or_public_push_configuration(self):
        with patch.object(frappe, 'session', SimpleNamespace(user='Guest')):
            for getter in (boot.get_mobile_boot, push_notifications.get_push_boot_config):
                with self.assertRaises(frappe.PermissionError):
                    getter()

    def test_existing_push_endpoint_preserves_subscription_count(self):
        with patch.object(frappe, 'session', SimpleNamespace(user='viewer')), \
             patch.object(push_notifications, '_get_vapid_config', return_value={'configured': False, 'public_key': 'HIDDEN'}), \
             patch.object(push_notifications, '_subscription_doctype_exists', return_value=True), \
             patch.object(frappe.db, 'count', return_value=3) as count:
            self.assertEqual(push_notifications.get_push_config(), {
                'configured': False, 'public_key': '', 'subscription_count': 3,
            })
            self.assertEqual(count.call_args.kwargs['filters'], {'user': 'viewer', 'enabled': 1})


class TestOfflinePayloadPerformance(TestCase):
    def setUp(self):
        self.schema = {'mobile_doctype': 'daily-timesheet', 'doctype': 'Daily Timesheet', 'fields': [
            {'fieldname': f'field_{i}', 'fieldtype': 'Data', 'label': f'Field {i}',
             'description': f'Enter the information for field {i}'} for i in range(50)
        ]}
        self.names = [f'TS-{i}' for i in range(30)]
        self.get_doc = Mock(side_effect=lambda doctype, name: SimpleNamespace(doctype=doctype, name=name, docstatus=0))
        self.schema_builder = Mock(return_value=self.schema)
        self.file_read = Mock(side_effect=lambda *args, **kwargs: [
            {'attached_to_name': name, 'name': f'FILE-{name}', 'file_name': f'{name}.jpg',
             'file_url': f'/private/files/{name}.jpg', 'is_private': 1, 'file_size': 100}
            for name in kwargs['filters']['attached_to_name'][1]
        ])
        patches = [
            patch.object(frappe, 'session', SimpleNamespace(user='viewer')),
            patch.object(frappe, 'has_permission', return_value=True),
            patch.object(frappe.db, 'exists', return_value=True),
            patch.object(frappe, 'get_doc', self.get_doc),
            patch.object(frappe, 'get_all', self.file_read),
            patch.object(documents, 'get_allowed_mobile_doctypes', return_value={'daily-timesheet': 'Daily Timesheet'}),
            patch.object(documents, 'get_schema_response', self.schema_builder),
            patch.object(documents, 'has_desk_read_permission', side_effect=lambda doc: doc.name != 'DENIED'),
            patch.object(documents, 'has_desk_write_permission', side_effect=lambda doc: doc.name != 'READ-ONLY'),
            patch.object(documents, 'serialise_doc_for_mobile', side_effect=lambda doc, doctype: {'name': doc.name, 'notes': 'Saved notes'}),
            patch.object(offline.shifts, 'get_shift_calendar', side_effect=lambda **kwargs: {'timesheets': [{'name': n} for n in self.names], 'shifts': []}),
            patch.object(offline.fetch_records, 'fetch_created_records', return_value=[]),
            patch.object(offline, '_get_link_options', return_value={}),
        ]
        for context in patches:
            context.start()
            self.addCleanup(context.stop)

    def test_thirty_timesheets_use_one_schema_build_and_one_attachment_query(self):
        result = offline.get_offline_bootstrap(2)
        self.assertEqual(len(result['edit_docs']), 30)
        self.schema_builder.assert_called_once()
        self.file_read.assert_called_once()
        self.assertEqual(len(result['edit_schemas']), 1)
        for payload in result['edit_docs'].values():
            self.assertNotIn('schema', payload)
            self.assertEqual(result['edit_schemas'][payload['schema_key']], self.schema)
            self.assertEqual(payload['files'][0]['name'], f"FILE-{payload['name']}")
            self.assertNotIn('attached_to_name', payload['files'][0])

    def test_version_two_round_trips_legacy_editor_data_and_reduces_payload(self):
        old = offline.get_offline_bootstrap()
        new = offline.get_offline_bootstrap('2')
        for key, original in old['edit_docs'].items():
            restored = dict(new['edit_docs'][key])
            restored['schema'] = new['edit_schemas'][restored.pop('schema_key')]
            self.assertEqual(restored, original)
        old_bytes = json.dumps(old, default=str).encode()
        new_bytes = json.dumps(new, default=str).encode()
        self.assertLess(len(new_bytes), len(old_bytes) / 4)
        self.assertLess(len(gzip.compress(new_bytes)), len(gzip.compress(old_bytes)))
        # This fixture is a comparison, not a measurement of a deployed site.
        print(f'Offline fixture bytes: JSON {len(old_bytes)} -> {len(new_bytes)}; gzip {len(gzip.compress(old_bytes))} -> {len(gzip.compress(new_bytes))}')

    def test_denied_documents_do_not_enter_cache_or_attachment_query(self):
        self.names = ['TS-1', 'DENIED', 'READ-ONLY']
        data = offline.get_offline_bootstrap(2)
        self.assertNotIn('daily-timesheet:DENIED', data['edit_docs'])
        self.assertFalse(data['edit_docs']['daily-timesheet:READ-ONLY']['can_write'])
        self.assertEqual(self.file_read.call_args.kwargs['filters']['attached_to_name'], ['in', ['TS-1', 'READ-ONLY']])

    def test_missing_document_is_skipped_but_unexpected_read_error_is_not_hidden(self):
        self.get_doc.side_effect = frappe.DoesNotExistError('Deleted')
        self.assertEqual(offline.get_offline_bootstrap(2)['edit_docs'], {})
        self.file_read.assert_not_called()
        self.get_doc.side_effect = RuntimeError('Database offline')
        with self.assertRaises(RuntimeError):
            offline.get_offline_bootstrap(2)

    def test_file_permission_is_preserved(self):
        with patch.object(frappe, 'has_permission', side_effect=lambda doctype, *args: doctype != 'File'):
            result = offline.get_offline_bootstrap(2)
        self.file_read.assert_not_called()
        self.assertTrue(all(not doc['files'] for doc in result['edit_docs'].values()))

    def test_invalid_versions_are_rejected_before_loading_documents(self):
        for version in (0, 3, 'invalid', None):
            with self.subTest(version=version), self.assertRaises(frappe.ValidationError):
                offline.get_offline_bootstrap(version)
        self.get_doc.assert_not_called()
