import json
from unittest import TestCase

from verto.safety.inx_sanitisation import (
    TEXT_FIELDS, apply_redactions, draft_inputs, mask_known_identifiers, text_hash,
)


class TestINXSanitisation(TestCase):
    def fields(self, **values):
        return dict.fromkeys(TEXT_FIELDS, "") | values

    def test_known_identifiers_are_masked_without_losing_safety_facts(self):
        fields = self.fields(
            site_name="Port Anderson",
            incident_summary="Ann Anderson's hand entered a pinch point. ANDERSON stopped. Email ann@example.test. Employee ID EMP-4299. DOB: 01/02/1985.",
            immediate_actions="Called 0412 345 678 and (08) 9123 4567. Isolated the conveyor; first aid given.",
        )
        result = mask_known_identifiers(fields, ["Ann Anderson"])
        result = apply_redactions(result, {"redactions": [
            {"field": "incident_summary", "text": "ANDERSON", "kind": "person"},
        ]})
        for value in ("Ann", "ANDERSON", "ann@example.test", "EMP-4299", "01/02/1985"):
            self.assertNotIn(value, result["incident_summary"])
        self.assertEqual(result["site_name"], "Port Anderson")
        self.assertIn("hand entered a pinch point", result["incident_summary"])
        self.assertNotIn("@example.test", result["incident_summary"])
        self.assertIn("Isolated the conveyor; first aid given.", result["immediate_actions"])
        self.assertNotIn("0412", result["immediate_actions"])
        self.assertNotIn("9123", result["immediate_actions"])

    def test_whole_name_aliases_preserve_ordinary_words_that_are_also_names(self):
        result = mask_known_identifiers(self.fields(
            incident_summary="Will Long stopped. The task will take a long time.",
        ), ["Long, Will", "Long"])
        self.assertEqual(result["incident_summary"], "[person] stopped. The task will take a long time.")

    def test_model_can_only_replace_original_spans(self):
        fields = self.fields(incident_summary="Lee caught a hand between the flanges. Lee stopped.")
        result = apply_redactions(fields, {"redactions": [
            {"field": "incident_summary", "text": "Lee", "kind": "person"},
        ]})
        self.assertEqual(result["incident_summary"], "[person] caught a hand between the flanges. [person] stopped.")
        self.assertEqual(result["investigation_actions"], "")
        self.assertEqual(result["recommended_controls"], "")
        for payload in (
            {"incident_summary": "New invented event."},
            {"redactions": [{"field": "incident_summary", "text": "New invented event.", "kind": "person"}]},
            {"redactions": [{"field": "unknown", "text": "Lee", "kind": "person"}]},
            {"redactions": [{"field": "incident_summary", "text": "Lee", "kind": "unsafe"}]},
            {"redactions": [{"field": "incident_summary", "text": "Lee", "kind": "person", "replacement": "Supervisor"}]},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError) as error:
                    apply_redactions(fields, payload)
                self.assertNotIn("Lee", str(error.exception))

    def test_overlapping_names_are_redacted_in_one_pass(self):
        result = apply_redactions(self.fields(incident_summary="Pat Smith stopped."), {"redactions": [
            {"field": "incident_summary", "text": "Pat", "kind": "person"},
            {"field": "incident_summary", "text": "Pat Smith", "kind": "person"},
        ]})
        self.assertEqual(result["incident_summary"], "[person] stopped.")

    def test_mapping_and_curated_wording_survive_source_refresh(self):
        source = {"location": "Port", "detailed_observation": "Original incident.", "immediate_actions": "Stopped."}
        fields, managed = draft_inputs(source, {})
        self.assertEqual(tuple(fields[name] for name in ("site_name", "incident_summary", "immediate_actions")),
                         ("Port", "Original incident.", "Stopped."))
        lesson = dict(fields, sanitisation_field_hashes=json.dumps({key: text_hash(fields[key]) for key in managed}))
        updated = dict(source, detailed_observation="Corrected incident.")
        refreshed, _ = draft_inputs(updated, lesson)
        self.assertEqual(refreshed["incident_summary"], "Corrected incident.")
        lesson["incident_summary"] = "Curator's accurate wording."
        curated, managed = draft_inputs(updated, lesson)
        self.assertEqual(curated["incident_summary"], "Curator's accurate wording.")
        self.assertNotIn("incident_summary", managed)
        self.assertEqual(draft_inputs(dict(source, location=""), {})[0]["site_name"], "")

    def test_redaction_does_not_truncate_long_observations(self):
        text = "The exposure and equipment details. " * 300
        result = apply_redactions(self.fields(incident_summary=text), {"redactions": []})
        self.assertEqual(result["incident_summary"], text)
