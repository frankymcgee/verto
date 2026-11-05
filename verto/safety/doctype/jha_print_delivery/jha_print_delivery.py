import frappe
from frappe import _
from frappe.model.document import Document


class JHAPrintDelivery(Document):
    def validate(self):
        if not self.flags.get("allow_jha_print_mutation"):
            frappe.throw(_("Use the JHA print email workflow to change deliveries."), frappe.PermissionError)
        if not self.is_new():
            before = self.get_doc_before_save()
            if any(str(self.get(key)) != str(before.get(key)) for key in (
                "jha", "revision", "work_summary", "project", "delivery_key")):
                frappe.throw(_("A print delivery belongs to its original JHA revision."), frappe.PermissionError)

    def on_trash(self):
        if not frappe.flags.in_uninstall:
            frappe.throw(_("JHA print delivery records must be retained."), frappe.PermissionError)
