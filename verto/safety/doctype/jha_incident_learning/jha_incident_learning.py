import hashlib

import frappe
from frappe import _
from frappe.model.document import Document

from verto.api.mobile import jha_risk_signals as risk


class JHAIncidentLearning(Document):
    def _source_key(self):
        system = str(self.source_system or "").strip()
        reference = str(self.source_reference or "").strip()
        if not system or not reference:
            frappe.throw(_("Source system and incident reference are required."), frappe.ValidationError)
        return hashlib.sha256(f"{system.casefold()}\0{reference.casefold()}".encode()).hexdigest()

    def autoname(self):
        self.source_key = self._source_key()
        self.name = self.source_key

    def validate(self):
        self.source_system = str(self.source_system or "").strip()
        self.source_reference = str(self.source_reference or "").strip()
        self.source_key = self._source_key()
        before = self.get_doc_before_save()
        if before and before.source_key != self.source_key:
            frappe.throw(_("The source incident identity cannot be changed. Import a separate incident instead."))
        try:
            self.critical_risks = "\n".join(risk.tags(self.critical_risks, risk.CRITICAL_RISKS))
            self.mechanisms = "\n".join(risk.tags(self.mechanisms, risk.MECHANISMS))
            detected = risk.signals(self.incident_summary, self.critical_risks, self.mechanisms)
        except (TypeError, ValueError) as exc:
            frappe.throw(_(str(exc)), frappe.ValidationError)
        self.indexed_critical_risks = "\n".join(detected["critical_risks"])
        self.indexed_mechanisms = "\n".join(detected["mechanisms"])
        # Investigation actions/controls are excluded: a recommended control is not proof of an exposure.
        self.search_text = risk.normalise_text(f"{self.title or ''}\n{self.incident_summary or ''}")
