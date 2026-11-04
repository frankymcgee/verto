"""Exercise the private SDP bridge without requiring a running Frappe bench."""
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch


class ValidationError(Exception):
    pass


class TestLocalVoiceBridge(unittest.TestCase):
    def setUp(self):
        def throw(message, error=ValidationError):
            raise error(message)

        self.settings = NS(get=Mock(return_value="[]"), get_password=Mock(return_value="private-service-token"))
        frappe = types.ModuleType("frappe")
        frappe.ValidationError = ValidationError
        frappe.throw = throw
        frappe.get_cached_doc = Mock(return_value=self.settings)
        frappe.get_single = Mock(return_value=self.settings)
        frappe.local = NS(site="tenant.test")
        settings_module = types.ModuleType("verto.api.mobile.peri_voice_settings")
        settings_module.SETTINGS_DOCTYPE = "Verto Mobile Settings"
        spec = importlib.util.spec_from_file_location("_local_voice_bridge_test", Path(__file__).parents[1] / "verto/api/mobile/voice_jha_local.py")
        self.bridge = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"frappe": frappe, "verto.api.mobile.peri_voice_settings": settings_module}):
            spec.loader.exec_module(self.bridge)
        self.post = self.enterContext(patch.object(self.bridge.requests, "post", return_value=NS(status_code=200, json=lambda: {"sdp": "v=0\nanswer", "session_reference": "local_1"})))
        self.config = {"local_service_url": "http://127.0.0.1:8090", "local_backend_model": "text-model", "local_reasoning_effort": "low"}
        self.client = NS(api_key="raven-private-key", base_url="https://api.openai.com/v1/", project="project", organization=None)

    def call(self, **kwargs):
        return self.bridge.create_local_call(client=self.client, sdp="v=0\noffer", config=self.config,
                                             instructions="Shared JHA instructions", tools=kwargs.get("tools", []))

    def test_credentials_travel_only_in_authenticated_server_request(self):
        tools = [{"type": "function", "name": "read_jha"}]
        result = self.call(tools=tools)
        self.assertEqual(result, {"sdp": "v=0\nanswer", "model": "text-model", "session_reference": "local_1"})
        self.assertNotIn("raven-private-key", json.dumps(result))
        request = self.post.call_args.kwargs
        self.assertEqual(request["headers"], {"Authorization": "Bearer private-service-token"})
        self.assertEqual(request["json"]["openai_api_key"], "raven-private-key")
        self.assertEqual(request["json"]["tenant"], "tenant.test")
        self.assertFalse(request["allow_redirects"])
        self.assertFalse(request["json"]["tools"][0]["strict"])
        self.assertNotIn("strict", tools[0])

    def test_remote_plain_http_and_embedded_url_credentials_are_rejected(self):
        for url in ("http://other-host:8090", "https://user:password@other-host", "file:///tmp/voice"):
            with self.subTest(url=url):
                self.config["local_service_url"] = url
                with self.assertRaises(ValidationError):
                    self.call()
        self.post.assert_not_called()

    def test_missing_service_token_makes_no_voice_request(self):
        self.settings.get_password.return_value = ""
        with self.assertRaises(ValidationError):
            self.call()
        self.post.assert_not_called()

    def test_redirect_and_capacity_failures_do_not_retry_or_start_another_provider(self):
        for status in (302, 401, 503):
            with self.subTest(status=status):
                self.post.return_value.status_code = status
                with self.assertRaises(ValidationError):
                    self.call()
        self.assertEqual(self.post.call_count, 3)

    def test_ice_config_only_accepts_connection_fields(self):
        self.settings.get.return_value = json.dumps([{"urls": "turns:relay.test:5349", "username": "u", "credential": "c"}])
        self.assertEqual(self.bridge.local_ice_servers()[0]["username"], "u")
        for value in ('{"urls":"stun:relay.test"}', '[{"urls":"https://api.test"}]', '[{"urls":"stun:relay.test","api_key":"secret"}]'):
            self.settings.get.return_value = value
            with self.assertRaises(ValidationError):
                self.bridge.local_ice_servers()


if __name__ == "__main__":
    unittest.main()
