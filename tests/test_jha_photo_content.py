import copy
import json
from unittest import TestCase

from verto.api.mobile.jha_photo_content import content_schema, normalise_content


def paper_content():
    return {"job_description": "Pump maintenance", "uncertainties": ["Page 2: check control owner."],
            "steps": [{"page": 1, "activity": "Restrain pump", "hold_point": "Check restraint",
                       "hazards": [{"hazard": "Stored energy", "controls": "Mechanical restraint",
                                    "critical_control": "", "control_owner": ""}]}]}


class TestPaperJhaContent(TestCase):
    def test_preserves_step_hazard_control_associations_and_uncertainties(self):
        data = paper_content()
        data["steps"].append({"page": 2, "activity": "Disconnect", "hold_point": "", "hazards": []})
        self.assertEqual(normalise_content(json.dumps(data), 2, for_import=True), data)

    def test_incomplete_reading_can_be_reviewed_but_cannot_be_imported(self):
        for field in ("activity", "hazard"):
            data = paper_content()
            if field == "activity": data["steps"][0][field] = ""
            else: data["steps"][0]["hazards"][0][field] = ""
            normalise_content(data, 2)
            with self.assertRaises(ValueError): normalise_content(data, 2, for_import=True)
        data["steps"] = []
        normalise_content(data, 2)
        with self.assertRaises(ValueError): normalise_content(data, 2, for_import=True)

    def test_missing_controls_are_left_blank_for_discussion_without_fabrication(self):
        data = paper_content(); data["steps"][0]["hazards"][0]["controls"] = ""
        self.assertEqual(normalise_content(data, 2, for_import=True)["steps"][0]["hazards"][0]["controls"], "")

    def test_rejects_unuploaded_pages_wrong_types_truncated_and_oversized_data(self):
        for page in (0, 3, True, 1.5, "1"):
            data = paper_content(); data["steps"][0]["page"] = page
            with self.subTest(page=page), self.assertRaises(ValueError): normalise_content(data, 2)
        for bad in ('{"steps":', '[]', '{}', 'x' * 500001):
            with self.subTest(bad=bad[:20]), self.assertRaises(ValueError): normalise_content(bad, 2)
        data = paper_content(); data["steps"][0]["activity"] = "x" * 2001
        with self.assertRaises(ValueError): normalise_content(data, 2)

    def test_rejects_signatures_approval_and_unknown_fields_in_model_output(self):
        for field in ("review_signature", "approved", "acknowledged", "transcription_consent"):
            data = paper_content(); data[field] = "forged"
            with self.subTest(field=field), self.assertRaises(ValueError): normalise_content(data, 2)

    def test_bounds_step_and_total_hazard_counts(self):
        data = paper_content(); data["steps"] *= 61
        with self.assertRaises(ValueError): normalise_content(data, 2)
        data = paper_content(); data["steps"][0]["hazards"] *= 30
        data["steps"] = [copy.deepcopy(data["steps"][0]) for _ in range(11)]
        with self.assertRaises(ValueError): normalise_content(data, 2)

    def test_schema_is_strict_and_every_property_is_required_recursively(self):
        def check(schema):
            if schema.get("type") == "object":
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual(set(schema["required"]), set(schema["properties"]))
                for child in schema["properties"].values(): check(child)
            if schema.get("type") == "array": check(schema["items"])
        check(content_schema())
