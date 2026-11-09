"""Radio permissions and concurrent floor ownership without a running Frappe site."""
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
from threading import Lock
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class Cache:
    def __init__(self):
        self.values = {}
        self.mutex = Lock()

    def make_key(self, key):
        return "tenant|" + key

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)

    @contextmanager
    def lock(self, key, **kwargs):
        with self.mutex:
            yield


class Doc(dict):
    __getattr__ = dict.get


class TestWalkieTalkie(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe._ = lambda value: value
        self.frappe.whitelist = lambda **kwargs: lambda fn: fn
        self.frappe.session = SimpleNamespace(user="worker@example.test")
        self.frappe.local = SimpleNamespace(site="tenant.test", response_headers={})
        self.frappe.PermissionError = PermissionError

        def throw(message, exc=ValueError):
            raise exc(message)

        self.frappe.throw = throw
        self.frappe.get_roles = Mock(return_value=[])
        self.frappe.db = SimpleNamespace(exists=Mock(return_value=True), sql=Mock(return_value=[]),
                                          get_value=Mock(return_value="Worker"), escape=lambda v: repr(v))
        self.channel = Doc(name="RADIO-00001", project="PROJ-1", enabled=1, raven_channel=None)
        self.frappe.get_doc = Mock(return_value=self.channel)
        self.frappe.get_list = Mock(return_value=[self.channel])
        self.settings = SimpleNamespace(enabled=1, livekit_url="wss://radio.test", livekit_api_key="key",
                                        get_password=Mock(return_value="secret"), max_transmission_seconds=60)
        self.frappe.get_single = Mock(return_value=self.settings)
        self.frappe.cache = Cache()
        self.enterContext(patch.dict("sys.modules", {"frappe": self.frappe}))
        spec = importlib.util.spec_from_file_location("radio_under_test", Path(__file__).parents[1] / "verto/api/mobile/walkie_talkie.py")
        self.radio = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.radio)
        self.now = 1000
        self.enterContext(patch.object(self.radio.time, "time", side_effect=lambda: self.now))
        self.real_publish = self.radio._publish
        self.publish = self.enterContext(patch.object(self.radio, "_publish", return_value=True))

    def join(self):
        return self.radio.join_channel(self.channel.name)["session_id"]

    def test_join_is_listen_only_with_short_lived_microphone_scoped_token(self):
        result = self.radio.join_channel(self.channel.name)
        header, payload, signature = result["token"].split(".")
        decode = lambda value: base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        claims = json.loads(decode(payload))
        self.assertFalse(claims["video"]["canPublish"])
        self.assertFalse(claims["video"]["canPublishData"])
        self.assertEqual(claims["video"]["canPublishSources"], ["microphone"])
        self.assertEqual(claims["exp"], 1300)
        expected = hmac.new(b"secret", (header + "." + payload).encode(), hashlib.sha256).digest()
        self.assertEqual(decode(signature), expected)
        self.assertEqual(self.frappe.local.response_headers["Cache-Control"], "no-store")
        self.assertNotIn("secret", json.dumps(result))

    def test_guest_disabled_and_nonmember_cannot_join(self):
        self.frappe.session.user = "Guest"
        with self.assertRaises(PermissionError): self.join()
        self.frappe.session.user = "worker@example.test"
        self.channel["enabled"] = 0
        with self.assertRaises(PermissionError): self.join()
        self.channel["enabled"] = 1
        self.frappe.db.exists.return_value = False
        with self.assertRaises(PermissionError): self.join()

    def test_assigned_worker_can_join_but_optional_raven_membership_is_required(self):
        self.frappe.db.exists.return_value = False
        self.frappe.db.sql.return_value = [("TASK-1",)]
        self.assertTrue(self.radio.has_permission(self.channel))
        self.channel["raven_channel"] = "private-team"
        self.assertFalse(self.radio.has_permission(self.channel))
        self.frappe.db.exists.side_effect = lambda dt, filters: dt == "Raven Channel Member"
        self.assertTrue(self.radio.has_permission(self.channel))
        self.assertFalse(self.radio.has_permission(self.channel, ptype="write"))

    def test_disabled_settings_and_insecure_urls_do_not_issue_sessions(self):
        self.settings.enabled = 0
        with self.assertRaises(ValueError): self.join()
        self.settings.enabled = 1
        for url in ("ws://radio.test", "wss://secret@radio.test", "wss://radio.test/path", "wss://radio.test?token=private"):
            self.settings.livekit_url = url
            with self.subTest(url=url), self.assertRaises(ValueError): self.join()

    def test_two_simultaneous_claims_grant_exactly_one_speaker(self):
        sessions = [self.join(), self.join()]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda value: self.radio.floor_action(value, "claim"), sessions))
        self.assertEqual(sum(result["granted"] for result in results), 1)
        self.publish.assert_called_once()
        self.assertTrue(self.publish.call_args.args[2])
        self.assertNotIn("session_id", json.dumps(results))

    def test_other_session_cannot_release_or_extend_the_speakers_lease(self):
        first, other = self.join(), self.join()
        self.radio.floor_action(first, "claim")
        self.now += 5
        for action in ("heartbeat", "release"):
            self.assertFalse(self.radio.floor_action(other, action)["granted"])
        self.now += 6
        self.assertTrue(self.radio.floor_action(other, "claim")["granted"])
        self.assertEqual([call.args[2] for call in self.publish.call_args_list], [True, False, True])

    def test_expiry_revokes_the_old_speaker_before_granting_the_next(self):
        first, second = self.join(), self.join()
        self.radio.floor_action(first, "claim")
        self.now += 11
        self.publish.reset_mock()
        self.radio.floor_action(second, "claim")
        self.assertEqual([call.args[2] for call in self.publish.call_args_list], [False, True])
        self.assertNotEqual(self.publish.call_args_list[0].args[1]["identity"], self.publish.call_args_list[1].args[1]["identity"])

    def test_cannot_grant_new_floor_if_revoking_previous_speaker_fails(self):
        first, second = self.join(), self.join()
        self.radio.floor_action(first, "claim")
        self.now += 11
        self.publish.side_effect = ValueError("unreachable")
        with self.assertRaises(ValueError): self.radio.floor_action(second, "claim")
        self.assertFalse(self.publish.call_args.args[2])

    def test_heartbeats_do_not_extend_maximum_transmission_duration(self):
        session = self.join()
        self.radio.floor_action(session, "claim")
        for _ in range(19):
            self.now += 3
            self.assertTrue(self.radio.floor_action(session, "heartbeat")["granted"])
        self.now += 3
        self.assertIsNone(self.radio.floor_action(session, "heartbeat")["floor"])
        self.assertFalse(self.publish.call_args.args[2])

    def test_session_owner_is_bound_to_authenticated_user(self):
        session = self.join()
        self.frappe.session.user = "different@example.test"
        for action in ("claim", "heartbeat", "release"):
            with self.subTest(action=action), self.assertRaises(PermissionError): self.radio.floor_action(session, action)
        with self.assertRaises(PermissionError): self.radio.leave_channel(session)
        self.publish.assert_not_called()

    def test_access_is_rechecked_on_every_heartbeat_and_removes_the_participant(self):
        session = self.join()
        self.radio.floor_action(session, "claim")
        self.frappe.db.exists.return_value = False
        with patch.object(self.radio, "_service") as service:
            with self.assertRaises(PermissionError): self.radio.floor_action(session, "heartbeat")
            self.assertEqual(service.call_args.args[2], "RemoveParticipant")

    def test_leave_cleans_up_even_after_channel_is_disabled(self):
        session = self.join()
        self.radio.floor_action(session, "claim")
        self.channel["enabled"] = 0
        self.settings.enabled = 0
        with patch.object(self.radio, "_service", return_value=True):
            self.assertTrue(self.radio.leave_channel(session)["left"])
        with self.assertRaises(PermissionError): self.radio.floor_action(session, "claim")
        self.assertFalse(self.frappe.cache.values)

    def test_room_names_are_isolated_by_site_and_channel(self):
        result = self.radio.join_channel(self.channel.name)
        first = self.radio._get("session:" + result["session_id"])["room"]
        self.frappe.local.site = "other-tenant.test"
        second = self.radio._get("session:" + self.join())["room"]
        self.assertNotEqual(first, second)

    def test_server_protocol_grants_only_microphone_publish_for_the_current_identity(self):
        session = self.radio._get("session:" + self.join())
        requests = ModuleType("requests")
        requests.RequestException = RuntimeError
        requests.post = Mock(return_value=SimpleNamespace(status_code=200, raise_for_status=lambda: None))
        with patch.dict("sys.modules", {"requests": requests}):
            result = self.real_publish(self.radio._config(), session, True)
        self.assertTrue(result)
        args, options = requests.post.call_args
        self.assertEqual(args[0], "https://radio.test/twirp/livekit.RoomService/UpdateParticipant")
        self.assertEqual(options["json"]["room"], session["room"])
        self.assertEqual(options["json"]["identity"], session["identity"])
        self.assertEqual(options["json"]["permission"]["canPublishSources"], ["MICROPHONE"])
        self.assertTrue(options["json"]["permission"]["canPublish"])
        self.assertFalse(options["json"]["permission"]["canPublishData"])
        claims = json.loads(base64.urlsafe_b64decode(options["headers"]["Authorization"].split('.')[1] + '=='))
        self.assertEqual(claims["video"], {"room": session["room"], "roomAdmin": True})
        self.assertFalse(options["allow_redirects"])


if __name__ == "__main__":
    unittest.main()
