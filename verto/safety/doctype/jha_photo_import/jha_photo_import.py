import frappe
from frappe import _
from frappe.model.document import Document


class JHAPhotoImport(Document):
    def validate(self):
        if not self.flags.get("allow_jha_photo_mutation"):
            frappe.throw(_("Use the paper JHA import workflow."), frappe.PermissionError)
        if self.is_new():
            if self.status != "Pending Review" or any(self.get(key) for key in ("reviewed_content", "confirmed_by", "confirmed_at")):
                frappe.throw(_("A paper JHA reading needs human confirmation."), frappe.PermissionError)
            return
        before = self.get_doc_before_save()
        if not before or before.status != "Pending Review" or self.status != "Imported":
            frappe.throw(_("An imported paper JHA reading is immutable."), frappe.PermissionError)
        mutable = {"status", "reviewed_content", "confirmed_by", "confirmed_at"}
        for field in self.meta.fields:
            if field.fieldname not in mutable and self.get(field.fieldname) != before.get(field.fieldname):
                frappe.throw(_("Keep the original paper JHA pages and reading unchanged."), frappe.PermissionError)

    def on_trash(self):
        if not frappe.flags.in_uninstall:
            frappe.throw(_("Paper JHA source readings must be retained."), frappe.PermissionError)
