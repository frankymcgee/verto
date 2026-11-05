"""Document lifecycle protection for append-only JHA supporting records."""
import frappe
from frappe import _
from frappe.model.document import Document


class JhaWorkpackRecord(Document):
    def validate(self):
        if not self.flags.get("allow_jha_workpack_mutation") or not self.is_new():
            frappe.throw(_("Use the JHA workpack workflow. Saved supporting records are immutable."), frappe.PermissionError)

    def on_trash(self):
        if not frappe.flags.in_uninstall:
            frappe.throw(_("JHA supporting records must be retained."), frappe.PermissionError)


class JhaLearningRecord(Document):
    def validate(self):
        if not self.flags.get("allow_jha_learning_mutation"):
            frappe.throw(_("Use the JHA job-learning workflow."), frappe.PermissionError)
        review_fields = {"status", "reviewed_by", "reviewed_at", "review_notes", "future_guidance"}
        if self.is_new():
            if self.status != "Pending Review" or any(self.get(key) for key in review_fields - {"status"}):
                frappe.throw(_("New job-learning records need human review."), frappe.PermissionError)
            return
        before = self.get_doc_before_save()
        retiring = self.doctype == "JHA Job Template" and before and before.status == "Approved" and self.status == "Retired"
        if not before or not (retiring or before.status == "Pending Review" and self.status in {"Approved", "Rejected"}):
            frappe.throw(_("A reviewed learning record is immutable."), frappe.PermissionError)
        for field in self.meta.fields:
            if field.fieldname not in review_fields and str(self.get(field.fieldname) or "") != str(before.get(field.fieldname) or ""):
                frappe.throw(_("Review cannot change the original job-learning record."), frappe.PermissionError)

    def on_trash(self):
        if not frappe.flags.in_uninstall:
            frappe.throw(_("JHA job-learning records must be retained."), frappe.PermissionError)
