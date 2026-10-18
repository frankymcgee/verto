"""Authenticated, permission-checked shell for the investigations frontend."""

from urllib.parse import urlencode

import frappe
import frappe.sessions
from frappe import _

from verto.access import can_view_investigations_app

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.redirect("/login?" + urlencode({"redirect-to": "/investigations"}))
    if not can_view_investigations_app():
        frappe.throw(_("You do not have access to Verto Investigations."), frappe.PermissionError)
    context.no_cache = 1
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.frappe_site_name = frappe.local.site
    return context
