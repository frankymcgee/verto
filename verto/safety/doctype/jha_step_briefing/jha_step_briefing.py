import frappe
from frappe import _
from frappe.model.document import Document


class JHAStepBriefing(Document):
    def validate(self):
        if not self.flags.get("allow_jha_step_mutation"):
            frappe.throw(_("Use the JHA active-step workflow to record selections."), frappe.PermissionError)
        if not self.is_new():
            previous = self.get_doc_before_save()
            mutable = {"voice_consent_confirmed", "voice_consent_confirmed_by", "voice_consent_confirmed_at",
                       "voice_model", "voice_started_at", "voice_session_reference", "modified", "modified_by"}
            for field in self.meta.get_valid_columns():
                if field not in mutable and self.get(field) != previous.get(field):
                    frappe.throw(_("Step selections are retained. Select a step again to record a new briefing."), frappe.PermissionError)

    def on_trash(self):
        if not frappe.flags.in_uninstall:
            frappe.throw(_("JHA step briefing history must be retained."), frappe.PermissionError)
