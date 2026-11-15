"""Verify the evidence and counts passed to Raven using the Verto form schemas."""
import importlib.util
import json
import re
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch


REPO = Path(__file__).parents[1]
FIELD_INTERACTION = "Field Interaction"
HOT_WORKS = "CCV - Hot Works"
INCIDENT_TRACKER = "Shutdown Incident Tracker"
PROJECT = "Example  Shutdown"


class TestShutdownSafetyReport(unittest.TestCase):
    def setUp(self):
        self.fields = {
            FIELD_INTERACTION: self.load_fields("safety", "field_interaction"),
            HOT_WORKS: self.load_fields("safety", "ccv___hot_works"),
            INCIDENT_TRACKER: self.load_fields("safety", "shutdown_incident_tracker"),
        }
        self.rows = {doctype: [] for doctype in self.fields}
        self.unreadable = set()
        self.frappe = ModuleType("frappe")
        self.frappe.whitelist = Mock(return_value=lambda fn: fn)
        self.frappe.session = SimpleNamespace(user="advisor@example.test")
        self.frappe.PermissionError = PermissionError
        self.frappe.DoesNotExistError = LookupError
        self.frappe.ValidationError = ValueError
        self.frappe.has_permission = lambda doctype, permission: doctype not in self.unreadable
        self.frappe.get_meta = Mock(side_effect=self.get_meta)
        self.frappe.get_list = Mock(side_effect=self.get_list)
        self.frappe.log_error = Mock()
        self.frappe.get_traceback = Mock()
        utils = ModuleType("frappe.utils")
        utils.cint = int
        utils.strip_html_tags = lambda value: re.sub(r"<[^>]+>", "", value)

        self.enterContext(patch.dict("sys.modules", {"frappe": self.frappe, "frappe.utils": utils}))
        spec = importlib.util.spec_from_file_location("ai_tools_under_test", REPO / "verto/api/ai_tools.py")
        self.ai = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.ai)
        self.ai.PROJECT_DOCTYPE_MAP = [
            {"doctype": doctype, "project_field": "project_name"}
            for doctype in (HOT_WORKS, FIELD_INTERACTION)
        ]

    def load_fields(self, module, name):
        schema = REPO / f"verto/{module}/doctype/{name}/{name}.json"
        return [
            SimpleNamespace(**({"options": None, "label": None} | field))
            for field in json.loads(schema.read_text())["fields"]
        ]

    def get_meta(self, doctype):
        return SimpleNamespace(fields=self.fields[doctype])

    def get_list(self, doctype, *, filters, fields, limit_page_length, order_by=None):
        allowed_fields = {"name", "creation", "modified", "owner"}
        allowed_fields.update(field.fieldname for field in self.fields[doctype])
        self.assertLessEqual(set(fields), allowed_fields)
        self.assertEqual(filters["docstatus"], ["!=", 2])
        rows = [
            row for row in self.rows[doctype]
            if row["project_name"] == filters["project_name"]
            and row.get("docstatus") != 2
            and row.get("visible", True)
        ]
        if "name" in filters:
            operator, value = filters["name"]
            if operator == ">":
                rows = [row for row in rows if row["name"] > value]
            elif operator == "in":
                rows = [row for row in rows if row["name"] in value]
            else:
                self.fail(f"Unexpected name filter {operator}")
        if order_by:
            self.assertEqual(order_by, "name asc")
            rows.sort(key=lambda row: row["name"])
        return [{field: row.get(field) for field in fields} for row in rows[:limit_page_length]]

    def add(self, doctype, name, **values):
        self.rows[doctype].append({"name": name, "project_name": PROJECT, **values})

    def test_counts_and_checklist_denominators_cover_all_54_interactions(self):
        self.ai.SUMMARY_BATCH_SIZE = 20
        for index in range(54):
            self.add(
                FIELD_INTERACTION,
                f"FI-{index:02d}",
                modified=f"2026-11-15 09:{index:02d}:00",
                safety_category="Good Controls",
                barricading_and_signs_in_place="Yes",
                peri_used="No",
            )
        rows = self.rows[FIELD_INTERACTION]
        rows[0].update(
            safety_category="Stop Work – Reset Required",
            improvement_required="Barricading & Demarcation",
            barricading_and_signs_in_place="No",
            work_area="Crusher feed",
            fl_comments="Exclusion zone was incomplete.",
            photo="/private/files/evidence.png",
        )
        rows[1].update(
            safety_category="Improvement Required",
            improvement_required="Barricading & Demarcation",
            barricading_and_signs_in_place="Yes (Fixed on the spot)",
        )
        rows[2]["barricading_and_signs_in_place"] = "N/A"
        rows[3]["barricading_and_signs_in_place"] = None
        self.add(FIELD_INTERACTION, "FI-other", project_name="Unrelated")
        self.add(FIELD_INTERACTION, "FI-cancelled", docstatus=2)
        self.add(FIELD_INTERACTION, "FI-inaccessible", visible=False)
        self.add(INCIDENT_TRACKER, "INC-1", classification="Near Miss", current_status="Investigation")
        self.add(INCIDENT_TRACKER, "INC-2", classification="Near Miss", project_name="Unrelated")

        result = self.ai.get_project_documents_for_swot(" " + PROJECT + " ")

        self.assertEqual(result["total_matching_records"], 54)
        self.assertEqual(result["total_returned_records"], 25)
        self.assertEqual(result["safety_performance"]["outcome_counts"], {
            "good_controls": 52, "improvement_required": 1, "stop_work_reset_required": 1,
            "other_recorded": 0, "uncategorised": 0,
        })
        summary = result["doctype_summary"][1]
        self.assertTrue(summary["limited"])
        self.assertEqual(summary["top_improvement_categories"], {"Barricading & Demarcation": 2})
        self.assertEqual(result["safety_performance"]["forms_with_failed_checks"], 1)
        self.assertEqual(result["safety_performance"]["forms_with_immediate_fixes"], 1)
        gap = summary["top_checklist_gaps"][0]
        self.assertEqual((gap["no"], gap["fixed_on_the_spot"], gap["applicable_answers"]), (1, 1, 52))
        first = result["records"][0]
        self.assertEqual(first["name"], "FI-00")
        self.assertEqual(first["control_exceptions"], [{"question": gap["question"], "answer": "No"}])
        self.assertEqual(first["data"]["fl_comments"], "Exclusion zone was incomplete.")
        self.assertEqual(first["data"]["work_area"], "Crusher feed")
        self.assertNotIn("photo", first["data"])
        self.assertEqual(result["incident_context"]["matching_records"], 1)
        self.assertEqual(result["incident_context"]["counts_by"]["classification"], {"Near Miss": 1})

    def test_stop_work_and_failed_checks_take_priority_over_newer_good_scores(self):
        self.add(HOT_WORKS, "HW-1", safety_category="Good Controls", modified="2026-11-11")
        self.add(
            HOT_WORKS, "HW-2", safety_category="Good Controls", modified="2026-11-10",
            compliance_percentage=100, hw_spotters="No", hw_spotters_com="Fire watch was out of position.",
        )
        self.add(FIELD_INTERACTION, "FI-1", safety_category="Stop Work - Reset Required")
        self.ai.MAX_TOTAL_RECORDS = 2

        result = self.ai.get_project_documents_for_swot(PROJECT, limit_per_doctype=1)

        self.assertEqual([record["name"] for record in result["records"]], ["FI-1", "HW-2"])
        self.assertEqual(result["records"][1]["data"]["compliance_percentage"], 100)
        self.assertEqual(result["records"][1]["control_exceptions"][0]["note"], "Fire watch was out of position.")
        self.assertEqual(result["total_matching_records"], 3)

    def test_legacy_field_interaction_categories_remain_distinct(self):
        self.fields[FIELD_INTERACTION] = self.load_fields("verto", "field_interaction")
        self.add(FIELD_INTERACTION, "FI-legacy-1", category="No Risk")
        self.add(
            FIELD_INTERACTION, "FI-legacy-2", category="Improvement Required",
            room_for_improvement_category="Procedures",
        )

        result = self.ai.get_project_documents_for_swot(PROJECT)

        summary = result["doctype_summary"][1]
        self.assertEqual(summary["outcome_counts"]["good_controls"], 0)
        self.assertEqual(summary["outcome_counts"]["other_recorded"], 1)
        self.assertEqual(summary["outcome_counts"]["improvement_required"], 1)
        self.assertEqual(summary["top_improvement_categories"], {"Procedures": 1})

    def test_unavailable_sources_have_unknown_counts(self):
        self.unreadable.update({FIELD_INTERACTION, INCIDENT_TRACKER})
        self.ai.PROJECT_DOCTYPE_MAP.append({"doctype": "Missing DocType", "project_field": "project_name"})

        result = self.ai.get_project_documents_for_swot(PROJECT)

        available, unreadable, missing = result["doctype_summary"]
        self.assertEqual(available["matching_records"], 0)
        self.assertIsNone(unreadable["matching_records"])
        self.assertIn("cannot read", unreadable["error"])
        self.assertIn("unavailable", missing["error"])
        self.assertEqual(result["safety_performance"]["sources_counted"], 1)
        self.assertIsNone(result["incident_context"]["matching_records"])
        self.assertNotIn(FIELD_INTERACTION, {call.args[0] for call in self.frappe.get_list.call_args_list})
        self.assertNotIn(INCIDENT_TRACKER, {call.args[0] for call in self.frappe.get_list.call_args_list})

    def test_evidence_uses_ravens_escaped_json_size(self):
        self.ai.MAX_RESPONSE_BYTES = 20 * 1024
        for index in range(10):
            self.add(FIELD_INTERACTION, f"FI-{index}", fl_comments="\U0001f4dd" * 700)

        result = self.ai.get_project_documents_for_swot(PROJECT)

        self.assertEqual(result["total_matching_records"], 10)
        self.assertGreater(result["total_returned_records"], 0)
        self.assertLess(result["total_returned_records"], 10)
        self.assertLess(len(json.dumps(result).encode()), self.ai.MAX_RESPONSE_BYTES)

    def test_guest_is_denied_before_any_sources_are_queried(self):
        self.frappe.session.user = "Guest"
        with self.assertRaises(PermissionError):
            self.ai.get_project_documents_for_swot(PROJECT)
        self.frappe.get_meta.assert_not_called()
        self.frappe.get_list.assert_not_called()
