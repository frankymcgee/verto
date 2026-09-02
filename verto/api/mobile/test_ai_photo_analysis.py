import unittest

from verto.api.mobile.ai_photo_analysis_parsing import extract_output_text, parse_result


class TestAIPhotoAnalysisParsing(unittest.TestCase):
    def test_extracts_responses_api_output_text(self):
        payload = {
            "output": [
                {"content": [{"type": "output_text", "text": '{"outcome":"pass"}'}]}
            ]
        }
        self.assertEqual(extract_output_text(payload), '{"outcome":"pass"}')

    def test_parses_uncertain_result(self):
        result = parse_result(
            """```json
            {"outcome":"uncertain","confidence":72,"summary":"Guard condition is unclear",\
             "findings_requiring_attention":["Inspect the guard condition on site"]}
            ```"""
        )
        self.assertEqual(result["outcome"], "uncertain")
        self.assertEqual(result["confidence"], 72)
        self.assertEqual(
            result["findings_requiring_attention"],
            ["Inspect the guard condition on site"],
        )

    def test_accepts_original_details_key_during_rolling_deployment(self):
        result = parse_result(
            '{"outcome":"fail","confidence":90,"summary":"Guard missing",'
            '"required_details_not_verified":["Reinstate guard"]}'
        )
        self.assertEqual(result["findings_requiring_attention"], ["Reinstate guard"])

    def test_rejects_unknown_outcome(self):
        with self.assertRaises(ValueError):
            parse_result('{"outcome":"maybe","confidence":50}')
