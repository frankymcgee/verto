from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from verto.api import planner_realtime


class TestPlannerRealtime(TestCase):
    def test_notices_contain_only_scope_and_wait_for_commit(self):
        with patch.object(frappe, "publish_realtime") as publish:
            doc = SimpleNamespace(doctype="Employee", name="private-employee", salary=100000)
            planner_realtime.document_changed(doc, "on_update")
            self.assertEqual(publish.call_count, 2)
            for call in publish.call_args_list:
                self.assertEqual(call.args[0], "verto:planner_changed")
                self.assertEqual(set(call.args[1]), {"scope"})
                self.assertEqual(call.kwargs, {"room": "verto:planner", "after_commit": True})

    def test_bulk_hooks_emit_equal_entries_for_frappe_transaction_deduplication(self):
        with patch.object(frappe, "publish_realtime") as publish:
            for i in range(100):
                planner_realtime.document_changed(SimpleNamespace(doctype="Shift Assignment", name=str(i)), "on_submit")
            self.assertEqual(len({repr(call) for call in publish.call_args_list}), 1)

    def test_task_assignments_publish_but_unrelated_todos_do_not(self):
        with patch.object(frappe, "publish_realtime") as publish:
            planner_realtime.document_changed(SimpleNamespace(doctype="ToDo", get={"reference_type": "Employee"}.get))
            publish.assert_not_called()
            planner_realtime.document_changed(SimpleNamespace(doctype="ToDo", get={"reference_type": "Task"}.get))
            publish.assert_called_once()

    def test_guests_cannot_subscribe(self):
        with patch.object(frappe, "session", SimpleNamespace(user="Guest")), patch.object(frappe, "has_permission") as permission:
            self.assertFalse(planner_realtime.can_subscribe())
            permission.assert_not_called()

    def test_subscription_allows_app_roles_or_existing_employee_readers(self):
        with patch.object(frappe, "session", SimpleNamespace(user="viewer")), patch("verto.access.can_view_planner_app", return_value=False), patch.object(frappe, "has_permission", return_value=True):
            self.assertTrue(planner_realtime.can_subscribe())
        with patch.object(frappe, "session", SimpleNamespace(user="viewer")), patch("verto.access.can_view_planner_app", return_value=False), patch.object(frappe, "has_permission", return_value=False):
            self.assertFalse(planner_realtime.can_subscribe())

    def test_hooks_preserve_existing_push_and_project_automation(self):
        from verto.hooks import doc_events

        self.assertIn("verto.api.mobile.push_notifications.notify_shift_assigned", doc_events["Shift Assignment"]["on_submit"])
        self.assertIn("verto.api.hooks.create_project_handover_records", doc_events["Project"]["on_update"])
        for doctype in planner_realtime.DOCTYPE_SCOPES:
            for event in ("on_update", "on_submit", "on_cancel", "after_delete", "on_change"):
                self.assertIn("verto.api.planner_realtime.document_changed", doc_events[doctype][event])
