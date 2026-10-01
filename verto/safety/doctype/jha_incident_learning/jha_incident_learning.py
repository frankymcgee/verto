import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from verto.api.mobile import jha_risk_signals as risk
from verto.safety.inx_import import SOURCE_SYSTEM, source_key


class JHAIncidentLearning(Document):
    def _source_key(self):
        try:
            return source_key(self.source_system, self.source_reference)
        except ValueError as exc:
            frappe.throw(_(str(exc)), frappe.ValidationError)

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
        enabled = bool(cint(self.get("available_for_jha")))
        if enabled and not risk.plain_text(self.incident_summary).strip():
            frappe.throw(_("Write a crew-facing incident summary before enabling this lesson."), frappe.ValidationError)
        if self.get("inx_source"):
            source = frappe.db.get_value("JHA INX Incident", self.inx_source,
                ["source_key", "source_reference", "source_fingerprint", "event_datetime", "event_status", "event_type", "event_sub_type"],
                as_dict=True, for_update=True)
            if not source or source.source_key != self.source_key or self.source_system.casefold() != SOURCE_SYSTEM.casefold():
                frappe.throw(_("The INX source must match this lesson's incident reference."), frappe.ValidationError)
            if enabled and self.get("inx_source_fingerprint") != source.source_fingerprint:
                frappe.throw(_("The INX incident has changed. Reload the lesson and review its updated source before enabling it."), frappe.ValidationError)
            self.inx_source_fingerprint = source.source_fingerprint
            self.incident_datetime = source.event_datetime
            self.incident_date = str(source.event_datetime)[:10] if source.event_datetime else None
            self.source_event_status = source.event_status
            self.source_event_type = source.event_type
            self.source_event_sub_type = source.event_sub_type
            if enabled:
                self.source_review_required = 0
        try:
            self.critical_risks = "\n".join(risk.tags(self.critical_risks, risk.CRITICAL_RISKS))
            self.mechanisms = "\n".join(risk.tags(self.mechanisms, risk.MECHANISMS))
            detected = risk.signals(f"{self.title or ''}\n{self.incident_summary or ''}", self.critical_risks, self.mechanisms)
        except (TypeError, ValueError) as exc:
            frappe.throw(_(str(exc)), frappe.ValidationError)
        self.indexed_critical_risks = "\n".join(detected["critical_risks"])
        self.indexed_mechanisms = "\n".join(detected["mechanisms"])
        # Investigation actions/controls are excluded: a recommended control is not proof of an exposure.
        self.search_text = risk.normalise_text(f"{self.title or ''}\n{self.incident_summary or ''}")
