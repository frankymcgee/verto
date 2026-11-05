"""Resolve scanned Desk/print links without bypassing document permissions."""
from urllib.parse import quote

import frappe
from frappe import _


def _route_key(value):
    return str(value or "").strip().lower().replace(" ", "-").replace("_", "-")


def _mobile_forms():
    from verto.api.mobile.documents import get_allowed_mobile_doctypes
    return get_allowed_mobile_doctypes()


@frappe.whitelist(methods=["GET"])
def resolve_document(doctype: str, name: str, revision: str | None = None):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)
    if not doctype or not name or len(doctype) > 140 or len(name) > 140:
        frappe.throw(_("Invalid document link."), frappe.ValidationError)
    matches = [item for item in frappe.get_all("DocType", pluck="name") if _route_key(item) == _route_key(doctype)]
    if len(matches) != 1:
        frappe.throw(_("This document type was not found."), frappe.DoesNotExistError)
    doctype = matches[0]
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    frappe.local.response_headers["Cache-Control"] = "no-store"
    if doctype == "Digital Job Hazard Analysis":
        version = str(revision or doc.get("revision") or 1)
        if not version.isdecimal() or int(version) < 1:
            frappe.throw(_("Invalid JHA revision."), frappe.ValidationError)
        url = f"/verto-mobile/jha/{quote(doc.name, safe='')}?revision={int(version)}"
        return {"kind": "mobile", "url": url}
    slug = next((slug for slug, mapped in _mobile_forms().items() if mapped == doctype), None)
    if slug:
        return {"kind": "mobile", "url": f"/verto-mobile/edit/{quote(slug, safe='')}/{quote(doc.name, safe='')}"}
    # Other readable documents keep their normal Desk permissions in the drawer.
    return {"kind": "desk", "url": f"/app/{quote(_route_key(doctype), safe='')}/{quote(doc.name, safe='')}"}
