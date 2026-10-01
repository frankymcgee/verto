import hashlib
import json
import sys
from io import BytesIO
from types import ModuleType, SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase

from verto.api import inx_incident_import as importer
from verto.api import inx_incident_sanitisation as service
from verto.api.mobile import voice_jha_incidents
from verto.safety.inx_import import SHEET_NAME, parse_rows
from verto.safety.inx_sanitisation import TEXT_FIELDS


class TestINXSanitisationAPI(TestCase):
    def setUp(self):
        self.bot = self.enterContext(patch.object(service, "_configured_bot", return_value=frappe._dict(model="gpt-4.1")))

    def client_context(self, client):
        module = ModuleType("raven.ai.openai_client")
        module.get_open_ai_client = lambda: client
        return patch.dict(sys.modules, {"raven.ai.openai_client": module})

    def test_crew_role_is_rejected_before_bot_or_records_are_read(self):
        with patch.object(frappe, "get_roles", return_value=["All"]), patch.object(frappe, "session", frappe._dict(user="crew@example.test")):
            with self.assertRaises(frappe.PermissionError):
                service.prepare_inx_drafts(["DRAFT"])
        self.bot.assert_not_called()

    def test_invalid_selection_cannot_queue_jobs(self):
        with patch.object(service, "_require_manager"), patch.object(service, "queue_drafts") as queue:
            for names in ("not-json", [1], [""] * 2001, {"name": "DRAFT"}):
                with self.subTest(names_type=type(names)):
                    with self.assertRaises(frappe.ValidationError):
                        service.prepare_inx_drafts(names)
        queue.assert_not_called()

    def test_responses_request_has_no_tools_and_does_not_store_response(self):
        client = Mock()
        client.with_options.return_value = client
        client.responses.create.return_value.model_dump.return_value = {
            "status": "completed", "output_text": '{"redactions":[]}',
        }
        fields = dict.fromkeys(TEXT_FIELDS, "")
        fields["incident_summary"] = "A hand entered a pinch point."
        with self.client_context(client):
            self.assertEqual(service._request_redactions(fields), {"redactions": []})
        client.with_options.assert_called_once_with(timeout=60, max_retries=0)
        args = client.responses.create.call_args.kwargs
        self.assertFalse(args["store"])
        self.assertEqual(args["model"], "gpt-4.1")
        self.assertEqual(json.loads(args["input"]), fields)
        self.assertNotIn("tools", args)
        self.assertNotIn("temperature", args)
        self.assertTrue(args["text"]["format"]["strict"])

    def test_incomplete_or_refused_response_is_not_a_draft(self):
        client = Mock()
        client.with_options.return_value = client
        with self.client_context(client):
            for data in (
                {"status": "incomplete", "output_text": '{"redactions":[]}'},
                {"status": "completed", "output": [{"content": [{"type": "refusal", "refusal": "Cannot help"}]}]},
            ):
                client.responses.create.return_value.model_dump.return_value = data
                with self.assertRaises(ValueError):
                    service._request_redactions(dict.fromkeys(TEXT_FIELDS, ""))

    def test_chat_compatibility_preserves_schema_and_model_token_parameter(self):
        completion = Mock()
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completion)))
        client.with_options = Mock(return_value=client)
        completion.return_value.model_dump.return_value = {
            "choices": [{"finish_reason": "stop", "message": {"content": '{"redactions":[]}'}}],
        }
        self.bot.return_value.model = "gpt-6-luna"
        with self.client_context(client):
            self.assertEqual(service._request_redactions(dict.fromkeys(TEXT_FIELDS, "")), {"redactions": []})
        args = completion.call_args.kwargs
        self.assertEqual(args["max_completion_tokens"], 4000)
        self.assertNotIn("max_tokens", args)
        self.assertTrue(args["response_format"]["json_schema"]["strict"])

    def test_approved_lessons_are_skipped_without_reading_source_or_queueing(self):
        lesson = Mock(available_for_jha=1)
        lesson.get.side_effect = {"inx_source": "SOURCE"}.get
        with patch.object(frappe, "get_doc", return_value=lesson) as get_doc, patch.object(frappe, "enqueue", create=True) as enqueue:
            self.assertEqual(service.queue_drafts(["APPROVED"]), {"queued": 0, "skipped": 1})
        self.assertEqual(get_doc.call_count, 1)
        enqueue.assert_not_called()
        lesson.save.assert_not_called()

    def test_jobs_only_contain_record_keys_and_queue_after_commit(self):
        lesson = Mock(available_for_jha=0)
        lesson.get.side_effect = {"inx_source": "SOURCE"}.get
        source = Mock(source_fingerprint="fingerprint")
        with patch.object(frappe, "get_doc", side_effect=[lesson, source]), patch.object(frappe, "generate_hash", return_value="token", create=True), patch.object(frappe, "enqueue", create=True) as enqueue:
            self.assertEqual(service.queue_drafts(["DRAFT"]), {"queued": 1, "skipped": 0})
        args = enqueue.call_args.kwargs
        self.assertTrue(args["enqueue_after_commit"])
        self.assertEqual(args["lesson_name"], "DRAFT")
        self.assertEqual(args["job_token"], "token")
        self.assertEqual(args["source_fingerprint"], "fingerprint")
        self.assertEqual(set(args), {"queue", "timeout", "enqueue_after_commit", "job_id", "lesson_name", "job_token", "source_fingerprint"})


class IntegrationTestINXSanitisation(IntegrationTestCase):
    def _case(self, import_records=True):
        from openpyxl import Workbook

        reference = f"TEST-INX-REDACT-{frappe.generate_hash(length=10)}"
        rows = [
            ["Reference", "Event Date", "Short Observation", "Detailed Observation", "Immediate Action Taken", "Location", "Reported By Name"],
            [reference, "06/01/2025 03:30", "Hand entered a pinch point",
             "Ann Anderson caught a hand between the flanges. Witness Jo Lane stopped the task.",
             "Ann Anderson isolated the conveyor; first aid given. Contact 0412 345 678.",
             "Port Anderson", "Ann Anderson"],
        ]
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = SHEET_NAME
        for row in rows:
            sheet.append(row)
        content = BytesIO()
        workbook.save(content)
        workbook.close()
        uploaded = frappe.get_doc({
            "doctype": "File", "file_name": f"{reference}.xlsx", "is_private": 1, "content": content.getvalue(),
        }).insert()
        record = parse_rows(rows)["records"][0]
        if import_records:
            importer._upsert(record, uploaded.file_url)
        return uploaded, record["source_key"]

    def _queue(self, key):
        with patch.object(service, "_configured_bot"), patch.object(frappe, "enqueue") as enqueue:
            result = service.prepare_inx_drafts([key])
        self.assertEqual(result["queued"], 1)
        return {name: enqueue.call_args.kwargs[name] for name in ("lesson_name", "job_token", "source_fingerprint")}

    def _prepare(self, job):
        spans = {"redactions": [{"field": "incident_summary", "text": "Jo Lane", "kind": "person"}]}
        with patch.object(service, "_request_redactions", return_value=spans):
            return service.prepare_one_draft(**job)

    def test_import_populates_sanitised_mappings_and_requires_review(self):
        uploaded, key = self._case(import_records=False)
        preview = importer.import_inx_export(uploaded.name)
        with patch.object(frappe, "enqueue") as enqueue:
            result = importer.import_inx_export(uploaded.name, dry_run=False,
                expected_sha256=preview["file_sha256"], prepare_drafts=True)
        self.assertEqual(result["sanitised_drafts_queued"], 1)
        job = {name: enqueue.call_args.kwargs[name] for name in ("lesson_name", "job_token", "source_fingerprint")}
        self.assertEqual(self._prepare(job), {"status": "prepared"})
        lesson = frappe.get_doc(importer.LEARNING_DOCTYPE, key)
        source = frappe.get_doc(importer.SOURCE_DOCTYPE, key)
        self.assertEqual(lesson.site_name, "Port Anderson")
        self.assertEqual(lesson.incident_summary, "[person] caught a hand between the flanges. Witness [person] stopped the task.")
        self.assertIn("isolated the conveyor; first aid given.", lesson.immediate_actions)
        self.assertNotIn("0412", lesson.immediate_actions)
        self.assertEqual(lesson.sanitisation_status, service.PREPARED)
        self.assertEqual((lesson.available_for_jha, lesson.source_review_required), (0, 1))
        self.assertFalse(lesson.investigation_actions)
        self.assertFalse(lesson.recommended_controls)
        self.assertIn("Ann Anderson", source.detailed_observation)
        self.assertNotIn(key, [row["name"] for row in voice_jha_incidents.find_incident_learning("Pinch point")["incidents"]])
        versions = frappe.get_all("Version", filters={"ref_doctype": importer.LEARNING_DOCTYPE, "docname": key}, fields=["data"])
        self.assertNotIn("Ann Anderson", json.dumps(versions))
        self.assertNotIn("Jo Lane", json.dumps(versions))
        lesson.available_for_jha = 1
        lesson.save()
        self.assertEqual(lesson.source_review_required, 0)
        uploaded.reload()
        self.assertEqual(uploaded.is_private, 1)
        self.assertEqual(hashlib.sha256(uploaded.get_content()).hexdigest(), preview["file_sha256"])

    def test_failure_has_no_raw_text_fallback_or_personal_error_details(self):
        _, key = self._case()
        job = self._queue(key)
        with patch.object(service, "_request_redactions", side_effect=ValueError("Ann Anderson's private details")), patch.object(frappe, "log_error") as log:
            self.assertEqual(service.prepare_one_draft(**job), {"status": "failed"})
        lesson = frappe.get_doc(importer.LEARNING_DOCTYPE, key)
        self.assertFalse(lesson.incident_summary)
        self.assertFalse(lesson.immediate_actions)
        self.assertFalse(lesson.site_name)
        self.assertEqual(lesson.sanitisation_status, service.FAILED)
        self.assertEqual(lesson.available_for_jha, 0)
        self.assertNotIn("Ann", log.call_args.kwargs["message"])
        self.assertNotIn("Ann", lesson.sanitisation_note)
        self.assertEqual(self._prepare(self._queue(key)), {"status": "prepared"})

    def test_curated_wording_is_retained_and_generated_fields_refresh(self):
        _, key = self._case()
        lesson = frappe.get_doc(importer.LEARNING_DOCTYPE, key)
        lesson.incident_summary = "A worker entered the flange pinch point."
        lesson.recommended_controls = "Use alignment tooling."
        lesson.save()
        with patch.object(service, "_request_redactions", return_value={"redactions": []}):
            service.prepare_one_draft(**self._queue(key))
        source = frappe.get_doc(importer.SOURCE_DOCTYPE, key)
        source.location = "Port Beta"
        source.detailed_observation = "Corrected source event wording."
        source.immediate_actions = "Stopped and isolated the task."
        source.save()
        with patch.object(service, "_request_redactions", return_value={"redactions": []}):
            self.assertEqual(service.prepare_one_draft(**self._queue(key)), {"status": "prepared"})
        lesson.reload()
        self.assertEqual(lesson.site_name, "Port Beta")
        self.assertEqual(lesson.incident_summary, "A worker entered the flange pinch point.")
        self.assertEqual(lesson.immediate_actions, "Stopped and isolated the task.")
        self.assertEqual(lesson.recommended_controls, "Use alignment tooling.")
        self.assertEqual(lesson.available_for_jha, 0)

    def test_concurrent_edits_are_preserved_and_queued_drafts_cannot_be_enabled(self):
        _, key = self._case()
        job = self._queue(key)
        lesson = frappe.get_doc(importer.LEARNING_DOCTYPE, key)
        lesson.incident_summary = "Attempted early approval."
        lesson.available_for_jha = 1
        with self.assertRaises(frappe.ValidationError):
            lesson.save()

        def concurrent_edit(fields):
            frappe.db.set_value(importer.LEARNING_DOCTYPE, key, "incident_summary", "Saved while preparing.")
            return {"redactions": []}

        with patch.object(service, "_request_redactions", side_effect=concurrent_edit):
            self.assertEqual(service.prepare_one_draft(**job), {"status": "failed"})
        lesson.reload()
        self.assertEqual(lesson.incident_summary, "Saved while preparing.")
        self.assertFalse(lesson.site_name)
        self.assertEqual(lesson.available_for_jha, 0)

    def test_legacy_personal_history_is_manager_only_on_both_desk_endpoints(self):
        _, key = self._case()
        self._prepare(self._queue(key))
        lesson = frappe.get_doc(importer.LEARNING_DOCTYPE, key)
        lesson.available_for_jha = 1
        lesson.save()
        history = frappe.get_doc({
            "doctype": "Version", "ref_doctype": importer.LEARNING_DOCTYPE, "docname": key,
            "data": json.dumps({"changed": [["incident_summary", "Ann Anderson's previous text", "Reviewed text"]]}),
        }).insert()
        service.get_learning_docinfo(doctype=importer.LEARNING_DOCTYPE, name=key)
        self.assertIn("Ann Anderson", json.dumps(frappe.response["docinfo"]["versions"]))
        crew = frappe.get_doc({
            "doctype": "User", "email": f"inx-crew-{frappe.generate_hash(length=10)}@example.test",
            "first_name": "Synthetic Crew", "send_welcome_email": 0,
        }).insert()
        original_user = frappe.session.user
        try:
            frappe.set_user(crew.name)
            service.get_learning_docinfo(doctype=importer.LEARNING_DOCTYPE, name=key)
            self.assertEqual(frappe.response["docinfo"]["versions"], [])
            self.assertFalse(frappe.has_permission("Version", "read", doc=history))
            service.get_learning_document(importer.LEARNING_DOCTYPE, key)
            self.assertEqual(frappe.response["docinfo"]["versions"], [])
            current = frappe.response.docs[-1]
            self.assertEqual(current.site_name, "Port Anderson")
            self.assertNotIn("Ann Anderson", current.incident_summary)
            self.assertFalse(current.get("inx_source"))
        finally:
            frappe.set_user(original_user)
        self.assertIn("verto.api.inx_incident_sanitisation.get_learning_document",
                      frappe.get_hooks("override_whitelisted_methods")["frappe.desk.form.load.getdoc"])
        self.assertIn("verto.api.inx_incident_sanitisation.get_learning_docinfo",
                      frappe.get_hooks("override_whitelisted_methods")["frappe.desk.form.load.get_docinfo"])
