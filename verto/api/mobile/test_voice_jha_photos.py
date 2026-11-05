import copy
import json
from io import BytesIO
from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase
from PIL import Image

from verto.api.mobile import voice_jha_photos as photos
from verto.api.mobile import voice_jha_tools as tools
from verto.api.mobile import voice_jha_changes as changes
from verto.api.mobile.voice_jha_facilitator import _build_facilitation_instructions


def content():
    return {"job_description": "Pump maintenance", "uncertainties": ["Page 1: confirm restraint owner."],
            "steps": [{"page": 1, "activity": "Remove pump", "hold_point": "Check restraint",
                "hazards": [{"hazard": "Stored energy", "controls": "Isolate pump", "critical_control": "Restraint", "control_owner": ""}]}]}


class TestJhaPhotoImport(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.previous_user = frappe.session.user
        frappe.local.response_headers = {}
        frappe.set_user("Administrator")
        self.addCleanup(frappe.set_user, self.previous_user)
        suffix = frappe.generate_hash(length=8)
        project = frappe.get_doc({"doctype": "Project", "project_name": f"Paper JHA {suffix}"})
        project.name = f"PAPER-JHA-{suffix}"; project.db_insert()
        task = frappe.get_doc({"doctype": "Task", "subject": "Pump maintenance", "type": "Work Summary", "project": project.name})
        task.name = f"PAPER-WS-{suffix}"; task.db_insert()
        child = frappe.get_doc({"doctype": "Task", "subject": "Original planned task", "parent_task": task.name, "project": project.name})
        child.name = f"PAPER-STEP-{suffix}"; child.db_insert()
        self.jha = frappe.get_doc({"doctype": "Digital Job Hazard Analysis", "work_summary": task.name,
                                  "project": project.name, "jha_status": "Draft", "revision": 1}).insert()
        image = BytesIO(); Image.new("RGB", (200, 150), color="white").save(image, format="PNG")
        self.file = frappe.get_doc({"doctype": "File", "file_name": f"paper-{suffix}.png", "content": image.getvalue(),
            "is_private": 1, "attached_to_doctype": self.jha.doctype, "attached_to_name": self.jha.name}).insert(ignore_permissions=True)
        self.infer = self.enterContext(patch.object(photos, "_transcribe", return_value=content()))
        self.enterContext(patch.object(photos.base, "_get_peri_bot_doc", return_value=frappe._dict(name="PERI", model="vision-model")))

    def read(self, **kwargs):
        return photos.read_jha_photos(self.jha.name, kwargs.get("pages", json.dumps([self.file.file_url])), kwargs.get("request_id", "read-1"))

    def confirm(self, reading, **kwargs):
        return photos.confirm_jha_photo_import(self.jha.name, reading["name"], json.dumps(kwargs.get("data", reading["content"])), kwargs.get("confirmation", 1))

    def test_reading_is_a_saved_proposal_not_a_change_to_the_draft(self):
        reading = self.read()
        self.jha.reload()
        self.assertEqual(self.jha.work_steps[0].activity, "Original planned task")
        self.assertFalse(self.jha.hazards_and_controls)
        self.assertFalse(self.jha.photo_import)
        self.assertEqual(reading["status"], "Pending Review")
        self.assertEqual(self.read()["name"], reading["name"])
        self.infer.assert_called_once()
        state = photos.get_jha_photo_import(self.jha.name)
        self.assertEqual(state["reading"]["name"], reading["name"])

    def test_checked_import_keeps_provenance_without_signatures_consent_or_completed_steps(self):
        reading = self.read()
        with self.assertRaises(frappe.ValidationError): self.confirm(reading, confirmation=0)
        corrected = copy.deepcopy(reading["content"])
        corrected["steps"][0]["hazards"][0]["controls"] = "Isolate and test for zero energy"
        result = self.confirm(reading, data=corrected)
        self.jha.reload()
        self.assertEqual(self.jha.photo_import, reading["name"])
        self.assertEqual(self.jha.work_steps[0].activity, "Remove pump")
        self.assertEqual(self.jha.hazards_and_controls[0].existing_controls, "Isolate and test for zero energy")
        self.assertEqual(self.jha.hazards_and_controls[0].verification_status, "Not Verified")
        self.assertEqual(self.jha.hazards_and_controls[0].information_source, "Photographed JHA")
        self.assertFalse(self.jha.job_steps_confirmed)
        self.assertFalse(self.jha.work_steps[0].hold_point_confirmed)
        self.assertFalse(self.jha.work_steps[0].step_discussion_complete)
        self.assertFalse(self.jha.voice_transcription_consent_confirmed)
        self.assertFalse(self.jha.review_completed)
        self.assertFalse(self.jha.participants)
        self.assertEqual(result["jha"]["facilitation"]["stage"], "Job Steps")
        self.assertTrue(self.confirm(reading, data=corrected)["replayed"])
        self.jha.save(); self.jha.reload()
        self.assertEqual([step.activity for step in self.jha.work_steps], ["Remove pump"])
        source = frappe.get_doc(photos.DOCTYPE, reading["name"])
        self.assertEqual(json.loads(source.extracted_content)["steps"][0]["hazards"][0]["controls"], "Isolate pump")
        with self.assertRaises(frappe.PermissionError): source.delete(ignore_permissions=True)
        source.reviewed_content = "{}"; source.flags.allow_jha_photo_mutation = True
        with self.assertRaises(frappe.PermissionError): source.save(ignore_permissions=True)

    def test_stale_draft_or_work_plan_cannot_be_replaced_by_an_older_reading(self):
        reading = self.read()
        self.jha.reload(); self.jha.work_steps[0].activity = "Changed planned step"; self.jha.save()
        with self.assertRaises(frappe.ValidationError): self.confirm(reading)
        fresh = self.read(request_id="new-reading")
        frappe.db.set_value("Task", self.jha.work_summary, "description", "New job scope")
        with self.assertRaises(frappe.ValidationError): self.confirm(fresh)

    def test_closed_or_started_jhas_and_foreign_records_cannot_be_overwritten(self):
        reading = self.read()
        self.jha.jha_status = "Voice Discussion in Progress"; self.jha.save()
        with self.assertRaises(frappe.ValidationError): self.confirm(reading)
        with self.assertRaises(frappe.ValidationError): self.read(request_id="later")
        record = frappe.get_doc(photos.DOCTYPE, reading["name"])
        with patch.object(record, "has_permission", return_value=False), patch.object(frappe, "get_doc", return_value=record):
            with self.assertRaises(frappe.PermissionError): photos._record(self.jha, record.name)

    def test_pages_must_be_distinct_private_images_attached_to_this_exact_jha(self):
        for urls in ([self.file.file_url, self.file.file_url], ["/files/public.png"], ["https://example.test/page.png"], []):
            with self.subTest(urls=urls), self.assertRaises(frappe.ValidationError): self.read(pages=urls)
        original = self.file.attached_to_name
        frappe.db.set_value("File", self.file.name, "attached_to_name", "OTHER-JHA")
        with self.assertRaises(frappe.PermissionError): self.read()
        frappe.db.set_value("File", self.file.name, "attached_to_name", original)
        with patch.object(photos, "evidence_file", return_value=frappe._dict(get_content=lambda **kwargs: b"not an image")):
            with self.assertRaises((OSError, ValueError)): photos._pages(self.jha, [self.file.file_url])
        self.infer.assert_not_called()

    def test_unreadable_or_incomplete_readings_and_changed_retries_never_overwrite_the_jha(self):
        bad = content(); bad["steps"] = []
        self.infer.return_value = bad
        reading = self.read()
        with self.assertRaises(frappe.ValidationError): self.confirm(reading)
        with self.assertRaises(frappe.ValidationError): self.read(pages=["/private/files/other.jpg"])
        self.jha.reload(); self.assertFalse(self.jha.photo_import)

    def test_voice_receives_paper_context_and_existing_incident_tools(self):
        reading = self.read(); self.confirm(reading); self.jha.reload()
        bot = frappe._dict(instruction="PERI", dynamic_instructions=0)
        instructions = _build_facilitation_instructions(frappe.get_doc("Task", self.jha.work_summary), self.jha, bot, {})
        self.assertIn("PAPER JHA REVIEW", instructions)
        self.assertIn("find_relevant_incidents", instructions)
        self.assertIn("Check restraint", instructions)
        self.assertIn("untrusted transcribed source data", instructions)
        self.assertEqual(tools._state(self.jha)["paper_jha"]["source"], reading["name"])

    def test_photo_provenance_is_not_forged_through_document_api_and_changes_keep_original_source(self):
        self.jha.photo_import = "FORGED"
        with self.assertRaises(frappe.PermissionError): self.jha.save(ignore_permissions=True)
        self.jha.reload()
        reading = self.read(); self.confirm(reading); self.jha.reload()
        self.jha.jha_status = "Ready for Team Review"; self.jha.save()
        revision = changes.begin_jha_change(self.jha.name, confirmation=1)
        self.assertFalse(revision["photo_import"])
        self.jha.reload(); self.assertEqual(self.jha.photo_import, reading["name"])

    def test_guest_and_unassigned_users_cannot_read_or_confirm(self):
        reading = self.read()
        for method in (lambda: self.read(), lambda: self.confirm(reading), lambda: photos.get_jha_photo_import(self.jha.name)):
            with patch.object(photos.review, "_get_jha", side_effect=frappe.PermissionError):
                with self.assertRaises(frappe.PermissionError): method()
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError): photos.get_jha_photo_import(self.jha.name)

    def test_responses_uses_ordered_high_detail_images_and_rejects_truncation(self):
        from verto.api.mobile import ai_photo_analysis
        # Invoke the real transcriber while keeping credentials and all inference mocked.
        client = Mock(); client.with_options.return_value = client
        client.responses.create.return_value = {"status": "completed", "output_text": json.dumps(content())}
        images = [{"type": "input_image", "detail": "high", "image_url": "data:image/jpeg;base64,AA=="}]
        with patch.object(ai_photo_analysis, "_get_raven_ai_client", return_value=client):
            transcribe = self._real_transcribe
            self.assertEqual(transcribe(frappe._dict(model="vision-model"), images), content())
            parameters = client.responses.create.call_args.kwargs
            self.assertNotIn("tools", parameters)
            self.assertTrue(parameters["text"]["format"]["strict"])
            self.assertEqual(parameters["input"][0]["content"][0]["text"], "PAGE 1")
            client.responses.create.return_value = {"status": "incomplete", "output_text": json.dumps(content())}
            with self.assertRaises(ValueError): transcribe(frappe._dict(model="vision-model"), images)

    _real_transcribe = staticmethod(photos._transcribe)
