"""Exercise dashboard scope and Insights 3.14 routing without a running bench."""

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).parents[1]
PROJECT = "SPT2603 | PORT MAJOR"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDashboardFilters(unittest.TestCase):
    def setUp(self):
        # The real fallback imports Verto's package; CI invokes this from frontend/.
        self.enterContext(patch.object(sys, "path", [str(ROOT), *sys.path]))
        self.frappe = ModuleType("frappe")
        self.frappe.whitelist = lambda **kwargs: lambda function: function
        self.frappe.session = SimpleNamespace(user="advisor@example.test")
        self.frappe.PermissionError = PermissionError
        self.frappe.parse_json = json.loads
        self.frappe.as_json = json.dumps
        self.frappe.log_error = Mock()

        def throw(message, exc=ValueError):
            raise exc(message)

        self.frappe.throw = throw
        self.enterContext(patch.dict("sys.modules", {"frappe": self.frappe}))
        self.context = load_module("dashboard_context_under_test", "verto/api/peri/insights_context.py")
        self.saved = {
            "name": "dash-1", "title": "Contractor KPI's",
            "items": [
                {"type": "filter", "filter_name": "Project", "filter_type": "String",
                 "default_operator": "in", "default_value": ["Previous project"], "charts": ["chart-1"]},
                {"type": "filter", "filter_name": "Contractor", "filter_type": "String", "charts": ["chart-1", "chart-2"]},
                {"type": "filter", "filter_name": "Period", "filter_type": "Date", "charts": ["chart-1"]},
                {"type": "filter", "filter_name": "Score", "filter_type": "Number", "charts": ["chart-1"]},
                {"type": "filter", "filter_name": "Unused", "filter_type": "String", "charts": []},
                {"type": "chart", "chart": "chart-1", "reading": "latest"},
                {"type": "chart", "chart": "chart-2"},
            ],
            "charts": [
                {"name": "chart-1", "title": "Compliance", "chart_type": "Number", "config": {}},
                {"name": "chart-2", "title": "All contractors", "chart_type": "Table", "config": {}},
            ],
        }
        self.view = SimpleNamespace(
            get_dashboards=Mock(return_value=[{"name": "dash-1", "title": "Contractor KPI's", "route": "kpis"}]),
            get_dashboard=Mock(side_effect=lambda name: deepcopy(self.saved)),
            get_chart_data=Mock(return_value={"columns": [{"name": "score"}], "rows": [{"score": 80}]}),
        )
        self.context.import_module = Mock(return_value=self.view)

    def test_catalogue_and_exact_dashboard_resolution(self):
        self.assertEqual(self.context.get_dashboard_context()["dashboards"][0]["name"], "dash-1")
        self.view.get_chart_data.assert_not_called()
        for reference in ("dash-1", "kpis", "CONTRACTOR KPI'S"):
            self.assertEqual(self.context.get_dashboard_context(reference)["dashboard_id"], "dash-1")

    def test_ambiguous_and_missing_dashboard_do_not_read_charts(self):
        self.assertEqual(self.context.get_dashboard_context("Missing")["status"], "dashboard_not_found")
        self.view.get_dashboards.return_value.append({"name": "dash-2", "title": "Contractor KPI's"})
        self.assertEqual(self.context.get_dashboard_context("Contractor KPI's")["status"], "ambiguous_dashboard")
        self.view.get_dashboard.assert_not_called()
        self.view.get_chart_data.assert_not_called()

    def test_inspection_exposes_typed_filters_without_executing_charts(self):
        result = self.context.set_dashboard_filters("dash-1")
        self.assertEqual(result["mode"], "filter_inspection")
        project = result["filter_definitions"]["Project"]
        self.assertEqual(project["filter_type"], "String")
        self.assertIn("in", project["operators"])
        self.assertEqual(project["linked_charts"], ["chart-1"])
        self.assertEqual(project["unlinked_charts"], ["chart-2"])
        self.assertFalse(result["saved_dashboard_changed"])
        self.view.get_chart_data.assert_not_called()

    def test_project_is_normalized_and_only_sent_to_linked_charts(self):
        result = self.context.set_dashboard_filters("dash-1", json.dumps({
            "Project": {"operator": "in", "value": PROJECT},
        }))
        state = {"operator": "in", "value": [PROJECT]}
        self.assertEqual(result["active_filter_states"], {"Project": state})
        self.assertEqual(result["charts"][0]["linked_filter_states"], {"Project": state})
        self.assertEqual(result["charts"][1]["linked_filter_states"], {})
        self.assertEqual(self.view.get_chart_data.call_args_list[0].kwargs["filters"], {"Project": state})
        self.assertEqual(self.view.get_chart_data.call_args_list[1].kwargs["filters"], {})
        self.assertEqual(self.saved["items"][0]["default_value"], ["Previous project"])

    def test_clear_default_and_keep_other_overrides_for_followup(self):
        first = self.context.set_dashboard_filters("dash-1", {
            "Project": {"operator": "in", "value": [PROJECT]},
            "Contractor": {"operator": "in", "value": ["Contractor A"]},
        })
        overrides = {**first["filter_overrides"], "Project": None}
        result = self.context.set_dashboard_filters("dash-1", overrides)
        self.assertNotIn("Project", result["active_filter_states"])
        self.assertEqual(result["active_filter_states"]["Contractor"]["value"], ["Contractor A"])
        self.assertIsNone(result["filter_overrides"]["Project"])
        restored = self.context.set_dashboard_filters("dash-1", {})
        self.assertEqual(restored["active_filter_states"]["Project"]["value"], ["Previous project"])
        self.assertNotIn("Contractor", restored["active_filter_states"])

    def test_invalid_overrides_are_rejected_atomically_before_execution(self):
        invalid = [
            "not json", "[]", [], "null",  # JSON null cannot stand for a filter object.
            {"Unknown": {"operator": "in", "value": [PROJECT]}},
            {"Project": {}}, {"Project": {"operator": "equals", "value": PROJECT}},
            {"Project": {"operator": "in", "value": []}},
            {"Project": {"operator": "in", "value": [True]}},
            {"Score": {"operator": "=", "value": True}},
            {"Score": {"operator": "=", "value": "NaN"}},
            {"Score": {"operator": "between", "value": [10, 1]}},
            {"Period": {"operator": "between", "value": ["2026-11-10", "2026-11-01"]}},
            {"Period": {"operator": "=", "value": "yesterday"}},
            {"Project": {"operator": "in", "value": [PROJECT]}, "Period": {"operator": "=", "value": "invalid"}},
        ]
        for filters in invalid:
            with self.subTest(filters=filters):
                result = self.context.set_dashboard_filters("dash-1", filters)
                self.assertEqual(result["status"], "invalid_filters")
                self.assertTrue(result["errors"])
        self.view.get_chart_data.assert_not_called()

    def test_number_zero_ranges_dates_and_valueless_filters(self):
        result = self.context.set_dashboard_filters("dash-1", {
            "Project": {"operator": "is_not_set"},
            "Score": {"operator": "=", "value": 0},
            "Period": {"operator": "between", "value": "2026-11-01,2026-11-30"},
        })
        self.assertEqual(result["active_filter_states"]["Score"]["value"], 0)
        self.assertEqual(result["active_filter_states"]["Period"]["value"], ["2026-11-01", "2026-11-30"])
        self.assertIsNone(result["active_filter_states"]["Project"]["value"])

    def test_incomplete_saved_defaults_and_unlinked_filters_are_explicit(self):
        self.saved["items"][0]["default_value"] = []
        result = self.context.set_dashboard_filters("dash-1", {"Unused": {"operator": "contains", "value": "test"}})
        self.assertNotIn("Project", result["active_filter_states"])
        self.assertTrue(result["warnings"])
        self.assertEqual(result["unlinked_active_filters"], ["Unused"])

    def test_guest_and_dashboard_permissions_are_enforced(self):
        self.frappe.session.user = "Guest"
        with self.assertRaises(PermissionError):
            self.context.set_dashboard_filters("dash-1", {})
        self.context.import_module.assert_not_called()
        self.frappe.session.user = "advisor@example.test"
        self.view.get_dashboard.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.context.set_dashboard_filters("dash-1", {})
        self.view.get_chart_data.assert_not_called()

    def test_unavailable_and_empty_charts_remain_in_results(self):
        self.view.get_chart_data.side_effect = [PermissionError, {"rows": [], "columns": []}]
        result = self.context.set_dashboard_filters("dash-1", {})
        self.assertEqual([chart["status"] for chart in result["charts"]], ["unavailable", "no_data"])

    def test_insights_314_filters_reach_the_saved_linked_query(self):
        legacy = load_module("insights_legacy_under_test", "verto/api/peri/insights_legacy.py")
        doc = SimpleNamespace(name="dash-1", title="Example", check_permission=Mock(), items=json.dumps([
            {"type": "chart", "chart": "chart-1"},
            {"type": "filter", "filter_name": "Project", "filter_type": "String",
             "links": {"chart-1": "`source-1`.`project_name`"}},
        ]))
        chart = SimpleNamespace(name="chart-1", title="Number", chart_type="Number", query="source-1", data_query="data-1",
                                config=json.dumps({"number_columns": [{"column_name": "score", "measure_name": "average_score", "aggregation": "avg"}]}), check_permission=Mock())
        source = SimpleNamespace(name="source-1", use_live_connection=1, check_permission=Mock())
        data = SimpleNamespace(check_permission=Mock(), execute=Mock(return_value={"rows": [{"average_score": 80}], "columns": []}))
        docs = {(legacy.DASHBOARD, doc.name): doc, (legacy.CHART, chart.name): chart,
                (legacy.QUERY, source.name): source, (legacy.QUERY, "data-1"): data}
        self.frappe.get_doc = Mock(side_effect=lambda doctype, name: docs[(doctype, name)])
        self.frappe.db = SimpleNamespace(exists=Mock(return_value=True))
        self.frappe.has_permission = Mock(return_value=True)
        self.frappe.get_list = Mock(return_value=[{"name": doc.name, "title": "Example"}])
        decorators = ModuleType("insights.decorators")
        decorators.has_role = Mock(return_value=True)
        self.enterContext(patch.dict("sys.modules", {"insights.decorators": decorators}))
        self.context.import_module.side_effect = ModuleNotFoundError(name="insights.api.view")
        self.enterContext(patch.dict("sys.modules", {"verto.api.peri.insights_legacy": legacy}))
        result = self.context.set_dashboard_filters("dash-1", {"Project": {"operator": "in", "value": [PROJECT]}})
        routed = data.execute.call_args.kwargs["adhoc_filters"]
        self.assertEqual(routed["source-1"]["filters"], [{
            "type": "filter", "column": {"type": "column", "column_name": "project_name"},
            "operator": "in", "value": [PROJECT],
        }])
        self.assertEqual(result["charts"][0]["sample_rows"], [{"average_score": 80}])
        doc.check_permission.assert_called_with("read")
        chart.check_permission.assert_called_with("read")
        source.check_permission.assert_called_with("read")
        data.check_permission.assert_called_with("read")
        self.assertFalse(hasattr(data, "save"))


class TestProjectAnalysisPrompt(unittest.TestCase):
    def setUp(self):
        frappe = ModuleType("frappe")
        frappe.whitelist = lambda **kwargs: lambda function: function
        frappe.session = SimpleNamespace(user="advisor@example.test")
        frappe.PermissionError = PermissionError

        def throw(message, exc=ValueError):
            raise exc(message)

        frappe.throw = throw
        self.frappe = frappe
        self.enterContext(patch.dict("sys.modules", {"frappe": frappe}))
        self.prompts = load_module("peri_prompts_under_test", "verto/api/peri/prompts.py")

    def test_prompt_names_dashboard_preserves_project_and_requires_filter_coverage(self):
        result = self.prompts.get_project_dashboard_prompt(PROJECT)
        self.assertIn('"Shutdown Safety Metrics"', result)
        self.assertIn(json.dumps(PROJECT), result)
        self.assertIn("before reading the charts", result)
        self.assertIn("every chart", result)
        self.assertIn("unfiltered figures", result)

    def test_guests_and_empty_projects_cannot_start_analysis(self):
        self.frappe.session.user = "Guest"
        with self.assertRaises(PermissionError):
            self.prompts.get_project_dashboard_prompt(PROJECT)
        self.frappe.session.user = "advisor@example.test"
        for project in (None, "", "  "):
            with self.assertRaises(ValueError):
                self.prompts.get_project_dashboard_prompt(project)


if __name__ == "__main__":
    unittest.main()
