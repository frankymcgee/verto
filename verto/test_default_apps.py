"""Regression tests for independent Planner and Mobile default selection."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe import apps as frappe_apps
from frappe.core.doctype.user.user import User

from verto import default_apps, hooks


class CoreUserValidation:
    # Exercise the real Frappe validator; isolate its unrelated profile updates.
    validate = User.validate

    def __init__(self, default_app):
        self.name = "Administrator"
        self.default_app = default_app
        self.new_password = ""
        self.user_emails = []
        self.restrict_ip = ""
        self.language = "en"
        for method in (
            "password_strength_test", "move_role_profile_name_to_role_profiles",
            "populate_role_profile_roles", "check_roles_added", "set_system_user",
            "clean_name", "set_full_name", "check_enable_disable", "ensure_unique_roles",
            "ensure_unique_role_profiles", "sync_role_profile_name",
            "remove_all_roles_for_guest", "validate_username", "remove_disabled_roles",
            "validate_user_email_inbox", "validate_allowed_modules", "validate_user_image",
            "set_time_zone",
        ):
            setattr(self, method, Mock())


class ExtendedUser(default_apps.VertoDefaultAppMixin, CoreUserValidation):
    pass


class TestDefaultApps(TestCase):
    def setUp(self):
        self.installed = ["frappe", "erpnext", "verto"]
        self.app_cards = [
            {"name": "erpnext", "title": "ERPNext", "route": "/desk"},
            {"name": "verto", "title": "Verto Planner", "route": "/planner"},
            {"name": "verto", "title": "Verto Mobile", "route": "/verto-mobile"},
        ]
        self.permission = Mock(return_value=True)
        self.local = SimpleNamespace(flags=SimpleNamespace(home_page=None))
        self.patch(frappe, "session", SimpleNamespace(user="operator@example.com"))
        self.patch(frappe, "local", self.local)
        self.patch(frappe, "get_installed_apps", Mock(side_effect=lambda: self.installed))
        self.patch(frappe, "get_hooks", Mock(side_effect=self.get_hooks))
        self.patch(frappe, "get_attr", Mock(return_value=self.permission))
        self.user_default = self.patch(frappe, "get_cached_value", Mock(return_value=""))
        self.system_default = self.patch(frappe, "get_system_settings", Mock(return_value=""))
        self.patch(frappe_apps, "get_apps", Mock(return_value=self.app_cards))
        # Restore the process-global resolver even when a test raises.
        self.patch(frappe_apps, "get_route", frappe_apps.get_route)

    def patch(self, target, name, value):
        patcher = patch.object(target, name, value)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def get_hooks(self, name, app_name=None):
        if name == "add_to_apps_screen":
            if app_name == "verto":
                return hooks.add_to_apps_screen
            if app_name == "erpnext":
                return [{"name": "erpnext", "route": "/desk"}]
        return []

    def test_dropdown_has_two_distinct_verto_choices(self):
        apps = default_apps.get_apps()
        self.assertEqual([app["name"] for app in apps], ["erpnext", "verto", "verto_mobile"])
        self.assertEqual(apps[2]["title"], "Verto Mobile")
        self.assertEqual(self.app_cards[2]["name"], "verto")

    def test_dropdown_does_not_restore_permission_filtered_apps(self):
        self.app_cards.pop()
        self.assertEqual([app["name"] for app in default_apps.get_apps()], ["erpnext", "verto"])

    def test_user_validate_retains_mobile_alias(self):
        user = ExtendedUser("verto_mobile")
        user.validate()
        self.assertEqual(user.default_app, "verto_mobile")
        user.check_roles_added.assert_called_once()
        user.validate_allowed_modules.assert_called_once()

    def test_core_defaults_and_invalid_values_keep_core_validation(self):
        for value, expected in (("verto", "verto"), ("erpnext", "erpnext"), ("", ""), ("unknown", "")):
            with self.subTest(value=value):
                user = ExtendedUser(value)
                user.validate()
                self.assertEqual(user.default_app, expected)

    def test_user_validation_errors_propagate(self):
        user = ExtendedUser("verto_mobile")
        user.validate_allowed_modules.side_effect = ValueError("Invalid modules")
        with self.assertRaisesRegex(ValueError, "Invalid modules"):
            user.validate()

    def test_alias_is_not_restored_without_verto(self):
        self.installed.remove("verto")
        user = ExtendedUser("verto_mobile")
        user.validate()
        self.assertEqual(user.default_app, "")

    def test_mobile_default_reaches_core_login_resolver(self):
        # Capture the function as Frappe's auth/OAuth/password-reset imports do.
        get_default_path = frappe_apps.get_default_path
        self.user_default.return_value = "verto_mobile"
        default_apps.configure_default_apps(login_manager=SimpleNamespace())
        self.assertEqual(get_default_path(), "/verto-mobile")
        self.assertEqual(self.local.flags.home_page, "/verto-mobile")

    def test_existing_planner_default_keeps_its_route(self):
        self.user_default.return_value = "verto"
        default_apps.configure_default_apps()
        self.assertEqual(frappe_apps.get_default_path(), "/planner")
        self.assertEqual(self.local.flags.home_page, "/planner")

    def test_system_mobile_default_and_user_override(self):
        self.system_default.return_value = "verto_mobile"
        default_apps.configure_default_apps()
        self.assertEqual(frappe_apps.get_default_path(), "/verto-mobile")
        self.user_default.return_value = "verto"
        default_apps.configure_default_apps()
        self.assertEqual(frappe_apps.get_default_path(), "/planner")

    def test_other_app_default_does_not_override_home_page(self):
        self.user_default.return_value = "erpnext"
        self.local.flags.home_page = "/existing-home"
        default_apps.configure_default_apps()
        self.assertEqual(frappe_apps.get_default_path(), "/desk")
        self.assertEqual(self.local.flags.home_page, "/existing-home")

    def test_mobile_permission_denial_falls_back_to_apps(self):
        self.permission.return_value = False
        self.user_default.return_value = "verto_mobile"
        default_apps.configure_default_apps()
        self.assertEqual(frappe_apps.get_default_path(), "/apps")
        self.assertEqual(self.local.flags.home_page, "/apps")

    def test_guest_does_not_get_a_mobile_home_page(self):
        frappe.session.user = "Guest"
        default_apps.configure_default_apps()
        self.assertIsNone(self.local.flags.home_page)
        self.assertEqual(frappe_apps.get_route("verto_mobile"), "/apps")
        self.user_default.assert_not_called()

    def test_resolver_is_idempotent_and_isolated_between_sites(self):
        default_apps.configure_default_apps()
        resolver = frappe_apps.get_route
        default_apps.configure_default_apps()
        self.assertIs(frappe_apps.get_route, resolver)
        self.assertEqual(resolver("verto_mobile"), "/verto-mobile")
        self.installed.remove("verto")
        self.assertEqual(resolver("verto_mobile"), "/apps")
        self.assertEqual(resolver("erpnext"), "/desk")

    def test_set_and_unset_mobile_default(self):
        db = self.patch(frappe, "db", Mock())
        clear_cache = self.patch(frappe, "clear_cache", Mock())
        db.get_value.return_value = "verto"
        default_apps.set_app_as_default("verto_mobile")
        db.set_value.assert_called_with("User", "operator@example.com", "default_app", "verto_mobile")
        db.get_value.return_value = "verto_mobile"
        default_apps.set_app_as_default("verto_mobile")
        db.set_value.assert_called_with("User", "operator@example.com", "default_app", "")
        self.assertEqual(clear_cache.call_count, 2)

    def test_set_mobile_default_requires_visible_app(self):
        self.app_cards.pop()
        db = self.patch(frappe, "db", Mock())
        self.patch(frappe, "throw", Mock(side_effect=frappe.PermissionError))
        with self.assertRaises(frappe.PermissionError):
            default_apps.set_app_as_default("verto_mobile")
        db.set_value.assert_not_called()

    def test_other_default_setters_delegate_to_core(self):
        setter = self.patch(frappe_apps, "set_app_as_default", Mock())
        default_apps.set_app_as_default("verto")
        setter.assert_called_once_with("verto")
