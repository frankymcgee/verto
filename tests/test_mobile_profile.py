"""Verify self-service profile scope without requiring a running Frappe site."""
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class TestMobileProfile(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe.whitelist = lambda **kwargs: lambda function: function
        self.frappe.session = SimpleNamespace(user="worker@example.test")
        self.frappe.local = SimpleNamespace(response_headers={})
        self.frappe.PermissionError = PermissionError

        def throw(message, exc):
            raise exc(message)

        self.frappe.throw = throw
        self.frappe.db = SimpleNamespace(exists=Mock(return_value=True), get_value=Mock())
        self.frappe.get_meta = Mock(return_value=SimpleNamespace(has_field=lambda field: True))
        self.account = {"full_name": "Worker", "email": "worker@example.test"}
        self.employee = {"name": "HR-EMP-001", "employee_name": "Worker", "employee_number": "12345"}
        self.frappe.db.get_value.side_effect = self.read
        self.enterContext(patch.dict("sys.modules", {"frappe": self.frappe}))
        self.profile = self.load("profile")

    def load(self, name):
        spec = importlib.util.spec_from_file_location(
            f"mobile_{name}_under_test", Path(__file__).parents[1] / f"verto/api/mobile/{name}.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def read(self, doctype, filters, fields, **options):
        if doctype == "User":
            self.assertEqual(filters, self.frappe.session.user)
            return {field: self.account.get(field) for field in fields}
        self.assertEqual(filters["user_id"], self.frappe.session.user)
        return self.employee["name"] if fields == "name" else {field: self.employee.get(field) for field in fields}

    def test_reads_only_session_user_and_linked_employee_with_explicit_fields(self):
        result = self.profile.get_my_profile()
        self.assertEqual(result["employee"]["name"], "HR-EMP-001")
        self.assertEqual(result["employee"]["employee_number"], "12345")
        self.assertEqual(result["user"]["email"], self.account["email"])
        self.assertEqual(self.frappe.local.response_headers["Cache-Control"], "no-store")
        user_read, employee_read = self.frappe.db.get_value.call_args_list
        self.assertEqual(user_read.args[2], ["full_name", "email", "mobile_no", "phone"])
        self.assertEqual(set(employee_read.args[2]), {"name", *self.profile.EMPLOYEE_FIELDS})
        self.assertEqual(employee_read.args[1], {"user_id": self.frappe.session.user, "status": "Active"})

    def test_guest_cannot_read_account_or_employee_information(self):
        self.frappe.session.user = "Guest"
        with self.assertRaises(PermissionError):
            self.profile.get_my_profile()
        self.frappe.db.get_value.assert_not_called()

    def test_no_employee_doctype_returns_account_only(self):
        self.frappe.db.exists.return_value = False
        self.assertIsNone(self.profile.get_my_profile()["employee"])
        self.assertEqual(self.frappe.db.get_value.call_count, 1)

    def test_unlinked_user_returns_account_only(self):
        self.frappe.db.get_value.side_effect = [self.account, None, None]
        self.assertIsNone(self.profile.get_my_profile()["employee"])

    def test_absent_optional_employee_fields_are_not_queried(self):
        self.frappe.get_meta.return_value = SimpleNamespace(has_field=lambda field: field == "employee_name")
        self.assertEqual(self.profile.get_my_profile()["employee"], {"name": "HR-EMP-001", "employee_name": "Worker"})

    def test_inactive_record_is_used_only_when_no_active_employee_is_linked(self):
        self.frappe.db.get_value.side_effect = [None, "HR-EMP-OLD"]
        self.assertEqual(self.profile.get_user_employee(), "HR-EMP-OLD")
        self.assertEqual(self.frappe.db.get_value.call_args.args[1], {"user_id": self.frappe.session.user})

    def test_boot_navigation_returns_the_same_employee_id(self):
        with patch.dict("sys.modules", {"verto.api.mobile.profile": self.profile}):
            navigation = self.load("navigation")
        self.assertEqual(navigation.get_navigation_access(), {"has_employee_profile": True, "employee_id": "HR-EMP-001"})
        self.frappe.db.get_value.return_value = None
        self.frappe.db.get_value.side_effect = None
        self.assertEqual(navigation.get_navigation_access(), {"has_employee_profile": False, "employee_id": ""})


if __name__ == "__main__":
    unittest.main()
