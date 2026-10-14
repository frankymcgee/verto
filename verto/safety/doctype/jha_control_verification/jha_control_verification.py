import frappe
from frappe import _
from frappe.model.document import Document


class JHAControlVerification(Document):
    def validate(self):
        if not self.flags.get("allow_jha_field_mutation"):
            frappe.throw(_("Use the JHA field workflow to record checks."), frappe.PermissionError)
        if not self.is_new() and self.doctype == "JHA Control Verification":
            frappe.throw(_("Field verifications are immutable. Record a new check instead."), frappe.PermissionError)

    def on_trash(self):
        if not frappe.flags.in_uninstall:
            frappe.throw(_("JHA field records must be retained."), frappe.PermissionError)
