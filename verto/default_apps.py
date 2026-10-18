"""Keep Verto's frontends selectable as independent default apps."""

from functools import wraps

from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect

import frappe
from frappe import _
from frappe import apps as frappe_apps


MOBILE_APP = "verto_mobile"
INVESTIGATIONS_APP = "verto_investigations"
ALIASES = (MOBILE_APP, INVESTIGATIONS_APP)


def _alias_app(app_name):
    # Workers can serve multiple sites; never retain site-specific hook data.
    if "verto" not in frappe.get_installed_apps():
        return None
    return next(
        (
            app
            for app in frappe.get_hooks("add_to_apps_screen", app_name="verto")
            if app.get("name") == app_name
        ),
        None,
    )


def _mobile_app():
    return _alias_app(MOBILE_APP)


def _alias_route(app_name):
    app = _alias_app(app_name)
    if not app or frappe.session.user == "Guest":
        return "/apps"
    permission = app.get("has_permission")
    if permission and not frappe.get_attr(permission)():
        return "/apps"
    return app.get("route") or "/apps"


def _mobile_route():
    return _alias_route(MOBILE_APP)


@frappe.whitelist()
def get_apps():
    """Preserve core visibility filtering, but give Mobile its own identifier."""
    apps = [dict(app) for app in frappe_apps.get_apps()]
    for alias in ALIASES:
        frontend = _alias_app(alias)
        if not frontend:
            continue
        for app in apps:
            if app.get("name") == "verto" and app.get("route") == frontend.get("route"):
                app["name"] = alias
    return apps


@frappe.whitelist()
def set_app_as_default(app_name: str):
    if app_name not in ALIASES:
        return frappe_apps.set_app_as_default(app_name)

    if not any(app["name"] == app_name for app in get_apps()):
        frappe.throw(_("You do not have access to this Verto app."), frappe.PermissionError)

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
        if default_app in ALIASES and _alias_app(default_app):
            self.default_app = default_app


def configure_default_apps(login_manager=None):
    """Handle normal requests and the first login in a freshly started worker."""
    _install_route_resolver()
    if frappe.session.user == "Guest":
        return

    default_app = frappe.get_cached_value("User", frappe.session.user, "default_app")
    default_app = default_app or frappe.get_system_settings("default_app")
    if default_app in ("verto", *ALIASES):
        # System-user password login uses get_home_page(), whereas OAuth,
        # password reset and website-user login use get_default_path().
        route = frappe_apps.get_route(default_app)
        frappe.local.flags.home_page = route
        if login_manager is None:
            _redirect_root_request(route)


def _redirect_root_request(route):
    """Open the app at its actual URL before Frappe resolves the home page.

    Merely setting home_page renders its template at `/`. That breaks the
    frontend's base URL and cannot follow redirect-only routes such as /apps.
    Use a temporary, uncacheable redirect because the default is per user.
    """
    request = getattr(frappe.local, "request", None)
    if (
        not request
        or request.method not in ("GET", "HEAD")
        or request.path not in ("/", "/index", "/index.html")
        or frappe.local.form_dict.get("cmd")
    ):
        return

    response = redirect(route, code=302)
    response.headers["Cache-Control"] = "no-store"
    # before_request is outside the website renderer's frappe.Redirect handler.
    # The WSGI application returns HTTPException.response directly instead.
    raise HTTPException(response=response)


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
        if app_name in ALIASES and _alias_app(app_name):
            return _alias_route(app_name)
        return original(app_name)

    get_route._verto_default_apps = True
    frappe_apps.get_route = get_route
