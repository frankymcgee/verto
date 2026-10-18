import frappe
from frappe import _
from frappe.model.document import Document


class VertoInvestigation(Document):
    def validate(self):
        from verto.api.investigations import validate_document
        validate_document(self)

    def on_trash(self):
        if not frappe.flags.in_uninstall:
            frappe.throw(_("Investigation records and their history must be retained."), frappe.PermissionError)
