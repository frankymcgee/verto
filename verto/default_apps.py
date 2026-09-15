"""Keep Verto's two frontends selectable as independent default apps."""

from functools import wraps

import frappe
from frappe import _
from frappe import apps as frappe_apps


MOBILE_APP = "verto_mobile"


def _mobile_app():
    # Workers can serve multiple sites; never retain site-specific hook data.
    if "verto" not in frappe.get_installed_apps():
        return None
    return next(
        (
            app
            for app in frappe.get_hooks("add_to_apps_screen", app_name="verto")
            if app.get("name") == MOBILE_APP
        ),
        None,
    )


def _mobile_route():
    app = _mobile_app()
    if not app or frappe.session.user == "Guest":
        return "/apps"
    permission = app.get("has_permission")
    if permission and not frappe.get_attr(permission)():
        return "/apps"
    return app.get("route") or "/apps"


@frappe.whitelist()
def get_apps():
    """Preserve core visibility filtering, but give Mobile its own identifier."""
    apps = [dict(app) for app in frappe_apps.get_apps()]
    mobile = _mobile_app()
    if mobile:
        for app in apps:
            if app.get("name") == "verto" and app.get("route") == mobile.get("route"):
                app["name"] = MOBILE_APP
    return apps


@frappe.whitelist()
def set_app_as_default(app_name: str):
    if app_name != MOBILE_APP:
        return frappe_apps.set_app_as_default(app_name)

    if not any(app["name"] == MOBILE_APP for app in get_apps()):
        frappe.throw(_("You do not have access to Verto Mobile."), frappe.PermissionError)

    user = frappe.session.user
    current = frappe.db.get_value("User", user, "default_app")
    frappe.db.set_value("User", user, "default_app", "" if current == app_name else app_name)
    frappe.clear_cache(user=user)


class VertoDefaultAppMixin:
    def validate(self):
        # Core User.validate clears values that are not installed app names.
        # Run every core/extension validation, then restore only our known alias.
        default_app = self.default_app
        super().validate()
        if default_app == MOBILE_APP and _mobile_app():
            self.default_app = default_app


def configure_default_apps(login_manager=None):
    """Handle normal requests and the first login in a freshly started worker."""
    _install_route_resolver()
    if frappe.session.user == "Guest":
        return

    default_app = frappe.get_cached_value("User", frappe.session.user, "default_app")
    default_app = default_app or frappe.get_system_settings("default_app")
    if default_app in ("verto", MOBILE_APP):
        # System-user password login uses get_home_page(), whereas OAuth,
        # password reset and website-user login use get_default_path().
        frappe.local.flags.home_page = frappe_apps.get_route(default_app)


def _install_route_resolver():
    """Bridge the internal resolver, which has no Frappe hook in v16.

    A whitelisted override alone cannot affect Python calls made by login,
    OAuth and password reset. Wrap only get_route, leaving Frappe's default
    precedence and explicit redirect handling in place. The wrapper is
    idempotent and resolves the current site's hooks on every alias lookup.
    """
    original = frappe_apps.get_route
    if getattr(original, "_verto_default_apps", False):
        return

    @wraps(original)
    def get_route(app_name):
        if app_name == MOBILE_APP and _mobile_app():
            return _mobile_route()
        return original(app_name)

    get_route._verto_default_apps = True
    frappe_apps.get_route = get_route
