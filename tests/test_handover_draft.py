"""Permission, shift-window and evidence boundaries for PERI handover suggestions."""
import importlib.util
import json
from datetime import datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class Record(dict):
    __getattr__ = dict.get

    def check_permission(self, action):
        if action in self.get("denied", []):
            raise PermissionError(action)


def field(name, kind="Small Text", **kwargs):
    return Record(fieldname=name, fieldtype=kind, label=name, **kwargs)


class TestHandoverDraft(unittest.TestCase):
    def setUp(self):
        frappe = self.frappe = ModuleType("frappe")
        frappe._ = lambda message: message
        frappe.whitelist = lambda **kwargs: lambda function: function
        frappe.PermissionError = PermissionError
        frappe.ValidationError = ValueError
        frappe.session = SimpleNamespace(user="advisor@example.test")
        frappe.local = SimpleNamespace(response_headers={})
        frappe.log_error = Mock()
        frappe.get_traceback = Mock(return_value="private server diagnostic")
        frappe.new_doc = Mock()

        def throw(message, exc=ValueError):
            raise exc(message)
        frappe.throw = throw
        utils = ModuleType("frappe.utils")
        utils.get_datetime = lambda value: datetime.fromisoformat(str(value))
        utils.strip_html_tags = str
        utils.get_system_timezone = lambda: "Australia/Perth"
        self.meta = {
            "Handover Information": [field("date", "Datetime"), field("signoff", "Signature"),
                *[field(name, "Text Editor") for name in ("shift_findings", "ccv_snapshot", "actions", "upcoming_shift_focus")]],
            "Safety Handover": [field("table_hhdr", "Table")],
            "Lead Safety Handover": [field("table_hhdr", "Table")],
            "Field Interaction": [field("link_project", "Link", options="Project"), field("comments"), field("secret", permlevel=1)],
            "Shutdown Incident Tracker": [field("project_name", "Data"), field("date_occured", "Date"), field("description")],
            "Verto Investigation": [field("actions", "Table")],
            "Investigation Action": [field(name) for name in ("title", "details", "assigned_to_user", "due_date", "action_status", "completion_notes")],
        }
        self.project = Record(name="PROJ-1", project_name="Shutdown NOV26")
        self.handover = Record(doctype="Safety Handover", name="HANDOVER-1", project="PROJ-1", docstatus=0,
            table_hhdr=[Record(date="2026-11-23 18:00:00", actions="Verify barrier with incoming advisor")])
        self.investigation = Record(doctype="Verto Investigation", name="INV-1", status="Actions in Progress", actions=[
            Record(title="Guarding follow-up", action_status="Completed", completion_notes="Awaiting verifier"),
            Record(title="Closed action", action_status="Verified"), Record(title="Cancelled action", action_status="Cancelled")])
        self.records = {
            "Field Interaction": [Record(name='FI-1"<>', creation="2026-11-24 02:00:00", comments="Guard missing")],
            "Shutdown Incident Tracker": [Record(name="INC-1", date_occured="2026-11-23", description="Incident report")],
            "Verto Investigation": [Record(name="INV-1")],
        }
        frappe.get_meta = Mock(side_effect=lambda doctype: SimpleNamespace(fields=self.meta[doctype]))
        frappe.db = SimpleNamespace(exists=Mock(side_effect=lambda dt, name: name in self.meta))
        frappe.has_permission = Mock(return_value=True)
        frappe.get_list = Mock(side_effect=lambda doctype, **kwargs: self.records.get(doctype, []))
        frappe.get_doc = Mock(side_effect=lambda doctype, name: self.project if doctype == "Project" else self.investigation if doctype == "Verto Investigation" else self.handover)
        ai_tools = ModuleType("verto.api.ai_tools")
        ai_tools.PROJECT_DOCTYPE_MAP = [{"doctype": "Field Interaction"}]
        self.enterContext(patch.dict("sys.modules", {"frappe": frappe, "frappe.utils": utils, "verto.api.ai_tools": ai_tools}))
        spec = importlib.util.spec_from_file_location("handover_draft_under_test", Path(__file__).parents[1] / "verto/api/mobile/handover_draft.py")
        self.api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.api)
        self.real_generate = self.api._generate
        self.generate = self.enterContext(patch.object(self.api, "_generate", return_value=({"actions": "Verify the reported barrier [S1]"}, "test-model")))

    def prepare(self, **overrides):
        arguments = dict(handover_doctype="Safety Handover", project="PROJ-1", docname="HANDOVER-1",
                         period_start="2026-11-23 18:00:00", period_end="2026-11-24 06:00:00")
        return self.api.prepare_handover_draft(**{**arguments, **overrides})

    def test_guest_and_foreign_or_unwritable_handovers_never_reach_sources_or_inference(self):
        self.frappe.session.user = "Guest"
        with self.assertRaises(PermissionError): self.prepare()
        self.frappe.get_doc.assert_not_called()
        self.frappe.session.user = "advisor@example.test"
        self.handover["denied"] = ["write"]
        with self.assertRaises(PermissionError): self.prepare()
        self.handover["denied"] = []
        self.handover["project"] = "OTHER"
        with self.assertRaises(PermissionError): self.prepare()
        self.frappe.get_list.assert_not_called()
        self.generate.assert_not_called()

    def test_new_handover_requires_create_permission_and_project_read_access(self):
        self.frappe.has_permission.return_value = False
        with self.assertRaises(PermissionError): self.prepare(docname=None)
        self.frappe.has_permission.return_value = True
        self.project["denied"] = ["read"]
        with self.assertRaises(PermissionError): self.prepare(docname=None)
        self.generate.assert_not_called()

    def test_unsupported_handovers_and_invalid_periods_are_rejected_without_inference(self):
        with self.assertRaises(ValueError): self.prepare(handover_doctype="User")
        for start, end in (("", ""), ("bad", "date"), ("2026-11-24 06:00", "2026-11-23 18:00"),
                           ("2026-11-23 06:00", "2026-11-25 18:00"), ("2026-11-23T18:00+08:00", "2026-11-24T06:00+08:00")):
            with self.subTest(start=start), self.assertRaises(ValueError): self.prepare(period_start=start, period_end=end)
        self.generate.assert_not_called()

    def test_overnight_window_uses_project_ids_and_titles_and_labels_date_only_evidence(self):
        result = self.prepare()
        calls = {call.args[0]: call.kwargs for call in self.frappe.get_list.call_args_list}
        self.assertIn(["link_project", "=", "PROJ-1"], calls["Field Interaction"]["filters"])
        self.assertIn(["creation", ">=", "2026-11-23 18:00:00"], calls["Field Interaction"]["filters"])
        self.assertIn(["creation", "<", "2026-11-24 06:00:00"], calls["Field Interaction"]["filters"])
        self.assertIn(["project_name", "=", "Shutdown NOV26"], calls["Shutdown Incident Tracker"]["filters"])
        self.assertIn(["date_occured", "between", ["2026-11-23", "2026-11-24"]], calls["Shutdown Incident Tracker"]["filters"])
        self.assertNotIn("secret", calls["Field Interaction"]["fields"])
        self.assertTrue(any("date-only" in warning for warning in result["warnings"]))
        self.assertTrue(any("submission time" in warning for warning in result["warnings"]))
        self.assertEqual(result["scope"]["timezone"], "Australia/Perth")
        self.assertEqual(self.frappe.local.response_headers["Cache-Control"], "no-store")
        self.assertTrue(all("details" not in source for source in result["sources"]))
        self.assertIn("%22%3C%3E", result["sources"][-1]["url"])
        self.frappe.new_doc.assert_not_called()

    def test_carry_over_distinguishes_unverified_handover_notes_and_completed_actions(self):
        self.prepare(period_start="2026-11-23 18:01:00")
        sources = self.generate.call_args.args[0]["sources"]
        self.assertIn("unverified", sources[0]["time_basis"])
        actions = sources[1]["details"]["actions"]
        self.assertEqual([row["action_status"] for row in actions], ["Completed"])
        self.assertIn("Awaiting verifier", json.dumps(actions))
        self.assertNotIn("Closed action", json.dumps(sources))

    def test_inaccessible_form_types_are_not_queried_or_sent_to_peri(self):
        self.frappe.has_permission.side_effect = lambda dt, action: dt != "Field Interaction"
        result = self.prepare()
        self.assertNotIn("Field Interaction", [call.args[0] for call in self.frappe.get_list.call_args_list])
        self.assertTrue(any("read access" in warning for warning in result["warnings"]))
        self.assertNotIn("Guard missing", json.dumps(self.generate.call_args.args[0]))

    def test_empty_sources_return_coverage_notes_without_spending_an_inference(self):
        self.records.clear()
        self.handover["table_hhdr"] = []
        result = self.prepare()
        self.assertEqual(result["fields"], {})
        self.assertIn("No accessible source records", result["warnings"][-1])
        self.generate.assert_not_called()

    def test_truncated_sources_are_explicit_and_unknown_model_citations_are_rejected(self):
        self.records["Field Interaction"] *= 13
        self.assertTrue(any("latest 12" in note for note in self.prepare()["warnings"]))
        self.generate.return_value = ({"actions": "Claim [S999]"}, "test-model")
        with self.assertRaisesRegex(ValueError, "has not changed"): self.prepare()
        self.frappe.log_error.assert_called_once()

    def test_generation_errors_leave_the_handover_unchanged(self):
        before = json.dumps(self.handover)
        self.generate.side_effect = TimeoutError("private provider detail")
        with self.assertRaisesRegex(ValueError, "has not changed"): self.prepare()
        self.assertEqual(json.dumps(self.handover), before)
        self.frappe.new_doc.assert_not_called()

    def test_inference_is_bounded_schema_only_and_rejects_unrequested_fields(self):
        voice = ModuleType("verto.api.mobile.voice_jha")
        voice._get_peri_bot_doc = lambda: Record(name="PERI", model="test-model")
        voice._get_bot_instructions = lambda bot: "PERI personality"
        ai = ModuleType("verto.api.mobile.ai_photo_analysis")
        client = Mock()
        client.with_options.return_value = client
        client.responses.create.return_value = {"output_text": json.dumps({"actions": "Follow up [S1]"})}
        ai._get_raven_ai_client = lambda: client
        ai._serialise_ai_response = lambda response: response
        ai._validate_ai_response = Mock()
        parsing = ModuleType("verto.api.mobile.ai_photo_analysis_parsing")
        parsing.extract_output_text = lambda response: response["output_text"]
        with patch.dict("sys.modules", {"verto.api.mobile.voice_jha": voice,
                "verto.api.mobile.ai_photo_analysis": ai, "verto.api.mobile.ai_photo_analysis_parsing": parsing}):
            self.assertEqual(self.real_generate({"sources": []}, ["actions"])[0], {"actions": "Follow up [S1]"})
            parameters = client.responses.create.call_args.kwargs
            self.assertNotIn("tools", parameters)
            self.assertEqual(parameters["text"]["format"]["schema"]["required"], ["actions"])
            self.assertIn("untrusted data", parameters["instructions"])
            client.with_options.assert_called_with(timeout=90, max_retries=0)
            client.responses.create.return_value = {"output_text": json.dumps({"actions": "Text", "signoff": "forged"})}
            with self.assertRaises(ValueError): self.real_generate({}, ["actions"])


if __name__ == "__main__":
    unittest.main()
