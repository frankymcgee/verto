"""Employee colour configuration, permission-aware reads and live refreshes."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from verto.api import planner_data, planner_realtime
from verto.api.planner_employee_colours import COLOUR_FIELD, ensure_employee_colour_field


class TestPlannerEmployeeColours(TestCase):
    def setUp(self):
        self.enterContext(patch.object(planner_data, "can_subscribe", return_value=True))
        self.meta = self.enterContext(patch.object(frappe, "get_meta",
            return_value=SimpleNamespace(has_field=lambda field: True)))

    def test_colours_use_the_existing_permission_checked_reference_query(self):
        rows = [{"name": "Casual", COLOUR_FIELD: "#eab308"}]
        with patch.object(planner_data, "_list", return_value=rows) as read:
            result = planner_data.get_bootstrap(["references"])
        self.assertEqual(result["references"]["employment_type"], rows)
        call = next(call for call in read.call_args_list if call.kwargs["doctype"] == "Employment Type")
        self.assertEqual(call.kwargs, {"doctype": "Employment Type", "fields": ["name", COLOUR_FIELD],
            "order_by": "name asc", "limit_page_length": 1000})

    def test_denied_employment_types_allow_other_references_and_the_blue_fallback(self):
        def read(**params):
            if params["doctype"] == "Employment Type":
                raise frappe.PermissionError("Employment Type access denied")
            return [{"name": "Allowed"}]
        with patch.object(planner_data, "_list", side_effect=read):
            result = planner_data.get_bootstrap(["references"])
        self.assertEqual(result["references"]["employment_type"], [])
        self.assertEqual(result["references"]["designation"], [{"name": "Allowed"}])
        self.assertEqual(result["errors"]["references.employment_type"]["exc_type"], "PermissionError")

    def test_a_site_without_the_custom_field_can_still_load_reference_names(self):
        self.meta.return_value = SimpleNamespace(has_field=lambda field: False)
        with patch.object(planner_data, "_list", return_value=[{"name": "Casual"}]) as read:
            result = planner_data.get_bootstrap(["references"])
        call = next(call for call in read.call_args_list if call.kwargs["doctype"] == "Employment Type")
        self.assertEqual(call.kwargs["fields"], ["name"])
        self.assertEqual(result["references"]["employment_type"], [{"name": "Casual"}])
        self.assertNotIn("references.employment_type", result["errors"])

    def test_employment_type_changes_refresh_colours_without_broadcasting_record_data(self):
        with patch.object(frappe, "publish_realtime") as publish:
            planner_realtime.document_changed(SimpleNamespace(doctype="Employment Type", name="Casual"))
        publish.assert_called_once_with("verto:planner_changed", {"scope": "references"},
            room="verto:planner", after_commit=True)


class TestPlannerEmployeeColourMigration(TestCase):
    def test_migration_adds_an_optional_colour_picker_to_employment_type(self):
        field = frappe.get_meta("Employment Type").get_field(COLOUR_FIELD)
        self.assertEqual(field.fieldtype, "Color")
        self.assertEqual(field.label, "Planner Colour")
        self.assertFalse(field.reqd)
        self.assertFalse(field.default)

    def test_repeated_migration_preserves_saved_colours_and_existing_field_configuration(self):
        doc = frappe.get_doc({"doctype": "Employment Type",
            "employee_type_name": f"_Test Planner Colour {frappe.generate_hash(length=8)}",
            COLOUR_FIELD: "#9333ea"}).insert(ignore_permissions=True)
        self.addCleanup(frappe.delete_doc, "Employment Type", doc.name, ignore_permissions=True)
        filters = {"dt": "Employment Type", "fieldname": COLOUR_FIELD}
        before = frappe.db.get_value("Custom Field", filters, ["name", "modified", "label"])
        ensure_employee_colour_field()
        self.assertEqual(frappe.db.get_value("Employment Type", doc.name, COLOUR_FIELD), "#9333ea")
        self.assertEqual(frappe.db.get_value("Custom Field", filters, ["name", "modified", "label"]), before)
