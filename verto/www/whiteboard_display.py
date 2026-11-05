import frappe

no_cache = 1
no_sitemap = 1


def get_context(context):
    # The shell contains no drawing data; every read is authorized by the API.
    context.no_cache = 1
    context.no_sitemap = 1
    frappe.local.response_headers["Cache-Control"] = "no-store"
    frappe.local.response_headers["Referrer-Policy"] = "no-referrer"
    frappe.local.response_headers["X-Robots-Tag"] = "noindex, nofollow"
