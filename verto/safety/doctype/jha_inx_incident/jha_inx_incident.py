import frappe
from frappe import _
from frappe.model.document import Document

from verto.api.mobile import jha_risk_signals as risk
from verto.safety.inx_import import SOURCE_SYSTEM, source_fingerprint, source_key


class JHAINXIncident(Document):
    def autoname(self):
        self.source_key = source_key(SOURCE_SYSTEM, self.source_reference)
        self.name = self.source_key

    def validate(self):
        self.source_reference = str(self.source_reference or "").strip()
        try:
            self.source_key = source_key(SOURCE_SYSTEM, self.source_reference)
        except ValueError as exc:
            frappe.throw(_(str(exc)), frappe.ValidationError)
        before = self.get_doc_before_save()
        if before and before.source_key != self.source_key:
            frappe.throw(_("The source incident identity cannot be changed."))
        self.source_fingerprint = source_fingerprint(self.as_dict())
        signals = risk.signals(f"{self.short_observation or ''}\n{self.detailed_observation or ''}")
        self.suggested_critical_risks = "\n".join(signals["critical_risks"])
        self.suggested_mechanisms = "\n".join(signals["mechanisms"])

    def on_update(self):
        before = self.get_doc_before_save()
        if (not before or before.source_fingerprint != self.source_fingerprint) and frappe.db.exists("JHA Incident Learning", self.name):
            frappe.db.set_value("JHA Incident Learning", self.name, {
                "available_for_jha": 0, "source_review_required": 1,
                "inx_source_fingerprint": self.source_fingerprint,
                "sanitisation_status": "Not Prepared",
                "sanitisation_job_token": "",
                "sanitisation_note": "The INX source changed. Prepare and review an updated draft.",
            })
