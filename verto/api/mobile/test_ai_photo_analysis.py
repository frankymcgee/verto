import unittest

from verto.api.mobile.ai_photo_analysis_parsing import (
    build_dm_notification_name,
    build_review_dm_html,
    deliver_direct_messages,
    extract_output_text,
    parse_assigned_users,
    parse_result,
)


class TestAIPhotoAnalysisParsing(unittest.TestCase):
    def test_parses_unique_project_assignees(self):
        self.assertEqual(
            parse_assigned_users(
                '["supervisor@example.com", "worker@example.com", '
                '"supervisor@example.com", "Guest"]'
            ),
            ["supervisor@example.com", "worker@example.com"],
        )

    def test_rejects_malformed_project_assignments(self):
        self.assertEqual(parse_assigned_users("not-json"), [])

    def test_extracts_responses_api_output_text(self):
        payload = {
            "output": [
                {"content": [{"type": "output_text", "text": '{"outcome":"pass"}'}]}
            ]
        }
        self.assertEqual(extract_output_text(payload), '{"outcome":"pass"}')

    def test_extracts_chat_completions_output_text(self):
        payload = {
            "choices": [
                {"message": {"content": '{"outcome":"uncertain"}'}}
            ]
        }
        self.assertEqual(
            extract_output_text(payload),
            '{"outcome":"uncertain"}',
        )

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

    def test_extracts_json_object_from_short_model_preface(self):
        result = parse_result(
            'Review result:\n{"outcome":"pass","confidence":88,'
            '"summary":"No issue visible","findings_requiring_attention":[]}'
        )
        self.assertEqual(result["outcome"], "pass")

    def test_dm_notification_name_is_recipient_specific_and_stable(self):
        first = build_dm_notification_name("ANALYSIS-1", "user@example.com")
        self.assertEqual(
            first,
            build_dm_notification_name("ANALYSIS-1", "user@example.com"),
        )
        self.assertNotEqual(
            first,
            build_dm_notification_name("ANALYSIS-1", "other@example.com"),
        )
        self.assertLessEqual(len(first), 140)

    def test_dm_html_escapes_ai_generated_content(self):
        message = build_review_dm_html(
            {
                "outcome": "fail",
                "confidence": 91,
                "summary": '<script>alert("x")</script>',
                "findings_requiring_attention": ["Replace <guard>"],
            },
            source_doctype="Field Interaction",
            source_name="FLD-1",
            project_label="Project A",
        )
        self.assertIn("Photo review identified an issue", message)
        self.assertIn("&lt;script&gt;", message)
        self.assertIn("Replace &lt;guard&gt;", message)
        self.assertNotIn("<script>", message)

    def test_dm_delivery_fans_out_deduplicates_and_isolates_failures(self):
        sent = []
        errors = []

        def send_message(user, notification_name):
            sent.append((user, notification_name))
            if user == "failed@example.com":
                raise RuntimeError("Raven unavailable")
            return f"MSG-{user}"

        delivery = deliver_direct_messages(
            [
                "submitter@example.com",
                "already@example.com",
                "missing-raven@example.com",
                "failed@example.com",
            ],
            analysis_name="ANALYSIS-1",
            can_receive=lambda user: user != "missing-raven@example.com",
            was_sent=lambda key: key
            == build_dm_notification_name("ANALYSIS-1", "already@example.com"),
            send_message=send_message,
            on_error=lambda user, error: errors.append((user, str(error))),
        )

        self.assertEqual(
            delivery["sent"],
            [
                {
                    "user": "submitter@example.com",
                    "message": "MSG-submitter@example.com",
                }
            ],
        )
        self.assertEqual(delivery["already_sent"], ["already@example.com"])
        self.assertEqual(delivery["skipped"], ["missing-raven@example.com"])
        self.assertEqual(delivery["failed"], ["failed@example.com"])
        self.assertEqual(errors, [("failed@example.com", "Raven unavailable")])
        self.assertEqual(
            [user for user, _key in sent],
            ["submitter@example.com", "failed@example.com"],
        )

    def test_rejects_unknown_outcome(self):
        with self.assertRaises(ValueError):
            parse_result('{"outcome":"maybe","confidence":50}')
