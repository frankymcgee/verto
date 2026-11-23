"""Check Flow entry permissions and session selection without a running site."""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class TestMobilePeriFlow(unittest.TestCase):
    def setUp(self):
        self.settings = {"peri_chat_version": "Flow", "peri_flow_agent": "PERI"}
        self.frappe = ModuleType("frappe")
        self.frappe.whitelist = lambda **kwargs: lambda function: function
        self.frappe.session = SimpleNamespace(user="worker@example.test")
        self.frappe.PermissionError = PermissionError

        def throw(message, exc=ValueError):
            raise exc(message)

        self.frappe.throw = throw
        self.frappe.db = SimpleNamespace(exists=Mock(return_value=True), get_value=Mock(return_value=1))
        self.frappe.has_permission = Mock(return_value=True)
        self.frappe.get_list = Mock(return_value=[])
        self.frappe.get_doc = Mock(return_value=SimpleNamespace(
            name="saved-session", owner=self.frappe.session.user, agent="PERI", source="Manual",
        ))
        boot = ModuleType("verto.api.mobile.boot")
        boot.get_mobile_settings = lambda: self.settings
        boot.get_setting = lambda settings, field, default=None: settings.get(field) or default

        def require_login():
            if self.frappe.session.user == "Guest":
                throw("Login required", PermissionError)

        boot.require_login = require_login
        utils = ModuleType("frappe.utils")
        utils.cint = lambda value: int(value or 0)
        api = ModuleType("frappe.flow.api")
        self.create = api.create_session = Mock(return_value={"name": "new-session"})
        self.enterContext(patch.dict("sys.modules", {
            "frappe": self.frappe, "frappe.utils": utils, "frappe.flow.api": api,
            "verto.api.mobile.boot": boot,
        }))
        spec = importlib.util.spec_from_file_location(
            "mobile_flow_under_test", Path(__file__).parents[1] / "verto/api/mobile/flow.py",
        )
        self.flow = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.flow)

    def test_guest_cannot_open_flow(self):
        self.frappe.session.user = "Guest"
        with self.assertRaisesRegex(PermissionError, "Login required"):
            self.flow.open_peri_chat()
        self.frappe.db.exists.assert_not_called()
        self.create.assert_not_called()

    def test_raven_and_unmigrated_settings_do_not_import_or_start_flow(self):
        for settings in ({}, {"peri_chat_version": "Raven"}):
            self.settings = settings
            with self.assertRaisesRegex(ValueError, "Select Flow"):
                self.flow.open_peri_chat()
        self.frappe.db.exists.assert_not_called()
        self.create.assert_not_called()

    def test_missing_flow_has_an_actionable_error(self):
        self.frappe.db.exists.return_value = False
        with self.assertRaisesRegex(ValueError, "Flow is not installed"):
            self.flow.open_peri_chat()
        self.create.assert_not_called()

    def test_missing_and_disabled_agents_do_not_create_sessions(self):
        self.frappe.db.exists.side_effect = lambda dt, name: dt == "DocType"
        with self.assertRaisesRegex(ValueError, "agent PERI does not exist"):
            self.flow.open_peri_chat()
        self.frappe.db.exists.side_effect = None
        self.frappe.db.get_value.return_value = 0
        with self.assertRaisesRegex(ValueError, "disabled"):
            self.flow.open_peri_chat()
        self.create.assert_not_called()

    def test_denied_flow_or_agent_access_does_not_lookup_or_create_chats(self):
        for denied in ("Flow Session", "Flow Agent"):
            def has_permission(doctype, *args, **kwargs):
                if doctype == denied:
                    raise PermissionError(doctype)
            self.frappe.has_permission.side_effect = has_permission
            with self.assertRaises(PermissionError):
                self.flow.open_peri_chat()
        self.frappe.get_list.assert_not_called()
        self.create.assert_not_called()

    def test_reuses_only_current_users_manual_agent_session(self):
        self.frappe.get_list.return_value = [{"name": "recent-session"}]
        self.assertEqual(self.flow.open_peri_chat()["url"], "/flow/s/recent-session")
        self.assertEqual(self.frappe.get_list.call_args.kwargs["filters"], {
            "owner": "worker@example.test", "agent": "PERI", "source": "Manual",
        })
        self.create.assert_not_called()

    def test_remembered_session_requires_ownership_and_document_permission(self):
        self.assertEqual(self.flow.open_peri_chat(session="saved-session")["session"], "saved-session")
        self.frappe.has_permission.assert_any_call("Flow Session", "read", self.frappe.get_doc.return_value, throw=True)
        self.frappe.get_doc.return_value.owner = "someone-else@example.test"
        with self.assertRaisesRegex(PermissionError, "another user"):
            self.flow.open_peri_chat(session="saved-session")
        self.create.assert_not_called()

    def test_different_agent_and_deleted_session_fall_back_to_peri(self):
        self.frappe.get_doc.return_value.agent = "Other Agent"
        self.assertEqual(self.flow.open_peri_chat(session="saved-session")["session"], "new-session")
        self.frappe.db.exists.side_effect = lambda dt, name: dt != "Flow Session"
        self.assertEqual(self.flow.open_peri_chat(session="deleted")["session"], "new-session")
        self.create.assert_called_with(agent="PERI")

    def test_fresh_project_analysis_uses_native_create_with_normal_approvals(self):
        result = self.flow.open_peri_chat(session="old", new_chat="1")
        self.assertEqual(result, {"url": "/flow/s/new-session", "session": "new-session", "agent": "PERI"})
        self.create.assert_called_once_with(agent="PERI")
        self.frappe.get_list.assert_not_called()
        self.frappe.get_doc.assert_not_called()

    def test_native_permission_and_configuration_errors_are_not_hidden(self):
        self.create.side_effect = PermissionError("Model access denied")
        with self.assertRaisesRegex(PermissionError, "Model access denied"):
            self.flow.open_peri_chat(new_chat=1)

    def test_session_path_is_encoded_not_interpreted_as_a_url(self):
        self.create.return_value = {"name": "chat/with?reserved#characters"}
        self.assertEqual(self.flow.open_peri_chat(new_chat=1)["url"], "/flow/s/chat%2Fwith%3Freserved%23characters")
