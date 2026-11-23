"""Read only the caller's Desk theme for cross-app consistency."""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class TestMobileTheme(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType('frappe')
        self.frappe.whitelist = lambda **kwargs: lambda function: function
        self.frappe.session = SimpleNamespace(user='worker@example.test')
        self.frappe.db = SimpleNamespace(get_value=Mock(return_value='Dark'))
        self.frappe.PermissionError = PermissionError
        def throw(message, exc):
            raise exc(message)
        self.frappe.throw = throw
        self.enterContext(patch.dict('sys.modules', {'frappe': self.frappe}))
        spec = importlib.util.spec_from_file_location('theme_under_test', Path(__file__).parents[1] / 'verto/api/mobile/theme.py')
        self.theme = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.theme)

    def test_reads_only_the_session_user(self):
        self.assertEqual(self.theme.get_user_theme(), {'user': 'worker@example.test', 'theme': 'Dark'})
        self.frappe.db.get_value.assert_called_once_with('User', 'worker@example.test', 'desk_theme')

    def test_guest_cannot_read_theme(self):
        self.frappe.session.user = 'Guest'
        with self.assertRaises(PermissionError): self.theme.get_user_theme()
        self.frappe.db.get_value.assert_not_called()

    def test_unset_and_invalid_preferences_use_the_existing_light_default(self):
        for value in (None, '', 'Invalid'):
            self.frappe.db.get_value.return_value = value
            self.assertEqual(self.theme.get_user_theme()['theme'], 'Light')
