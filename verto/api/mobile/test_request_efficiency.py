"""Permission and compatibility tests for the compact Raven count endpoint."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from verto.api.mobile import raven


class TestThreadCounts(unittest.TestCase):
    def test_returns_counts_only_for_readable_threads(self):
        with (
            patch.object(frappe, "session", SimpleNamespace(user="employee@example.test")),
            patch.object(frappe, "get_all", return_value=[
                SimpleNamespace(name="public-thread"), SimpleNamespace(name="private-thread")
            ]),
            patch.object(frappe, "has_permission", side_effect=lambda *args, **kwargs: kwargs["doc"] == "public-thread") as permission,
            patch("raven.api.threads.get_number_of_replies", return_value=0) as count,
        ):
            self.assertEqual(raven.get_thread_counts('["public-thread", "private-thread"]'), {"public-thread": 0})
            count.assert_called_once_with("public-thread")
            self.assertEqual(permission.call_count, 2)
            self.assertEqual(permission.call_args.kwargs["ptype"], "read")

    def test_deduplicates_ids_and_uses_raven_count_semantics(self):
        with (
            patch.object(frappe, "session", SimpleNamespace(user="employee@example.test")),
            patch.object(frappe, "get_all", return_value=[SimpleNamespace(name="thread")]) as query,
            patch.object(frappe, "has_permission", return_value=True),
            patch("raven.api.threads.get_number_of_replies", return_value=123) as count,
        ):
            self.assertEqual(raven.get_thread_counts(["thread", "thread"]), {"thread": 123})
            self.assertEqual(query.call_args.kwargs["filters"]["name"], ["in", ["thread"]])
            count.assert_called_once_with("thread")

    def test_rejects_guests_before_querying(self):
        with patch.object(frappe, "session", SimpleNamespace(user="Guest")), patch.object(frappe, "get_all") as query:
            with self.assertRaises(frappe.PermissionError):
                raven.get_thread_counts(["thread"])
            query.assert_not_called()

    def test_bounds_and_validates_input(self):
        with patch.object(frappe, "session", SimpleNamespace(user="employee@example.test")), patch.object(frappe, "get_all") as query:
            for invalid in (["thread"] * 51, {"name": "thread"}, [12], [""], ["x" * 141]):
                with self.subTest(invalid=invalid), self.assertRaises(frappe.ValidationError):
                    raven.get_thread_counts(invalid)
            self.assertEqual(raven.get_thread_counts([]), {})
            query.assert_not_called()
