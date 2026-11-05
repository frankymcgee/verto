"""Server-side context for the Verto Mobile application shell."""

import frappe

from verto.api.mobile.pwa_manifest import get_pwa_metadata

# The shell includes session and site-specific metadata.
no_cache = 1


def get_context(context):
    # Jinja's restricted frappe namespace does not expose frappe.local.
    # Resolve the actual routed site in Python, not from the public domain.
    context.frappe_site_name = frappe.local.site
    context.pwa_metadata = get_pwa_metadata()
