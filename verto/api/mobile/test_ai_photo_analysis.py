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
            {"outcome":"uncertain","confidence":72,"summary":"Detail obscured",\
             "required_details_not_verified":["Guard condition"]}
            ```"""
        )
        self.assertEqual(result["outcome"], "uncertain")
        self.assertEqual(result["confidence"], 72)
        self.assertEqual(result["required_details_not_verified"], ["Guard condition"])

    def test_rejects_unknown_outcome(self):
        with self.assertRaises(ValueError):
            parse_result('{"outcome":"maybe","confidence":50}')
