import frappe
import frappe.sessions
from urllib.parse import urlencode
from frappe import _

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.response["status_code"] = 403
		frappe.msgprint(_("Log in to access this page."))
		frappe.redirect(f"/login?{urlencode({'redirect-to': frappe.request.path})}")

	context.no_cache = 1
	context.csrf_token = frappe.sessions.get_csrf_token()

	return context