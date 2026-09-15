import hashlib
import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime

from verto.api.mobile.home_child_tasks import get_work_summary_child_tasks


EDITABLE_JHA_STATUSES = {
    "Draft",
    "Voice Discussion in Progress",
    "Incomplete - Actions Required",
}
REVIEW_LOCKED_STATUSES = {
    "Ready for Team Review",
    "Signed",
}
PROTECTED_STATUS_VALUES = {
    "Signed",
    "Review Required - Work Changed",
}
REVIEW_PROTECTED_FIELDS = {
    "revision",
    "review_completed",
    "reviewed_by",
    "reviewer_name",
    "reviewed_at",
    "review_signature",
    "signed_at",
    "signed_by_user",
    "review_audit_log",
}
PARTICIPANT_PROTECTED_FIELDS = {
    "acknowledged",
    "acknowledged_at",
    "acknowledged_by_user",
    "acknowledgement_signature",
}
MAX_REVIEW_AUDIT_ENTRIES = 300


class DigitalJobHazardAnalysis(Document):
    def validate(self):
        self._validate_protected_review_mutations()
        self._set_work_summary_context()
        self._sync_planned_child_tasks()
        self._guard_source_revision()

    def _validate_protected_review_mutations(self):
        if self.is_new() or self.flags.get("allow_jha_review_mutation"):
            return

        before = self.get_doc_before_save()
        if not before:
            return

        for fieldname in REVIEW_PROTECTED_FIELDS:
            if self.get(fieldname) != before.get(fieldname):
                frappe.throw(
                    _("Human review and sign-on fields can only be changed through the JHA review workflow."),
                    frappe.PermissionError,
                )

        if self.jha_status != before.jha_status and (
            self.jha_status in PROTECTED_STATUS_VALUES
            or before.jha_status in PROTECTED_STATUS_VALUES
        ):
            frappe.throw(
                _("This JHA status transition is controlled by the human review workflow."),
                frappe.PermissionError,
            )

        before_rows = {row.name: row for row in (before.participants or []) if row.name}
        for row in self.participants or []:
            previous = before_rows.get(row.name)
            if previous:
                changed = any(
                    row.get(fieldname) != previous.get(fieldname)
                    for fieldname in PARTICIPANT_PROTECTED_FIELDS
                )
            else:
                changed = any(
                    row.get(fieldname) not in (None, "", 0, "0")
                    for fieldname in PARTICIPANT_PROTECTED_FIELDS
                )
            if changed:
                frappe.throw(
                    _("Participant acknowledgement can only be recorded through the JHA sign-on workflow."),
                    frappe.PermissionError,
                )

    def _set_work_summary_context(self):
        if not self.work_summary or not frappe.db.exists("Task", self.work_summary):
            return

        task = frappe.db.get_value(
            "Task",
            self.work_summary,
            ["project", "subject", "parent_task_name", "work_order_number"],
            as_dict=True,
        ) or {}

        if not self.project:
            self.project = task.get("project")
        if not self.work_summary_title:
            self.work_summary_title = task.get("subject")
        if not self.work_area:
            self.work_area = task.get("parent_task_name")
        if not self.work_order_number:
            self.work_order_number = task.get("work_order_number")

    def _sync_planned_child_tasks(self):
        """Mirror direct Task children into editable JHAs as planned work steps."""
        if not self.work_summary or not frappe.db.exists("Task", self.work_summary):
            return
        if not self.is_new() and self.jha_status not in EDITABLE_JHA_STATUSES:
            return

        child_tasks = get_work_summary_child_tasks(self.work_summary)
        if not child_tasks:
            return

        existing_by_task = {
            row.get("source_task"): row
            for row in (self.work_steps or [])
            if row.get("source_task")
        }

        for sequence, child in enumerate(child_tasks, start=1):
            source_task = child.get("name")
            row = existing_by_task.get(source_task)

            if row is None:
                row = self.append(
                    "work_steps",
                    {
                        "sequence": sequence,
                        "activity": child.get("subject") or source_task,
                        "step_origin": "Planned",
                        "source_task": source_task,
                        "hold_or_pause_point": 0,
                    },
                )
                existing_by_task[source_task] = row
            else:
                row.sequence = sequence
                row.activity = child.get("subject") or source_task
                row.step_origin = "Planned"

    def calculate_source_revision(self) -> str:
        """Hash only work inputs that should invalidate human review/sign-on.

        Generic Task modified/progress/status changes are intentionally excluded so
        normal execution updates do not invalidate a signed JHA. Scope, planned
        step content and personnel assignment changes remain review-significant.
        """
        if not self.work_summary or not frappe.db.exists("Task", self.work_summary):
            return ""

        values = frappe.db.get_value(
            "Task",
            self.work_summary,
            ["name", "subject", "project", "parent_task_name", "work_order_number", "description"],
            as_dict=True,
        ) or {}

        parent_fields = (
            "name",
            "subject",
            "project",
            "parent_task_name",
            "work_order_number",
            "description",
        )
        payload_parts = [str(values.get(key) or "") for key in parent_fields]

        for child in get_work_summary_child_tasks(self.work_summary):
            payload_parts.extend(
                [
                    str(child.get("name") or ""),
                    str(child.get("subject") or ""),
                    str(child.get("type") or ""),
                    str(child.get("description") or ""),
                    ",".join(child.get("assigned_users") or []),
                ]
            )

        payload = "|".join(payload_parts)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def source_has_changed(self) -> bool:
        current = self.calculate_source_revision()
        return bool(self.source_revision and current and current != self.source_revision)

    def _append_review_audit(self, event: str, details: dict | None = None):
        if not self.meta.has_field("review_audit_log"):
            return

        entries = []
        raw = str(self.get("review_audit_log") or "").strip()
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    entries = parsed
            except (TypeError, ValueError, json.JSONDecodeError):
                entries = []

        entries.append(
            {
                "at": str(now_datetime()),
                "user": frappe.session.user,
                "event": event,
                "details": details or {},
            }
        )
        self.review_audit_log = json.dumps(entries[-MAX_REVIEW_AUDIT_ENTRIES:], default=str)

    def mark_review_required_if_source_changed(self) -> bool:
        if self.jha_status not in REVIEW_LOCKED_STATUSES:
            return False
        if not self.source_has_changed():
            return False

        previous_status = self.jha_status
        self.jha_status = "Review Required - Work Changed"
        self._append_review_audit(
            "work_change_detected",
            {"previous_status": previous_status, "revision": cint(self.revision or 1)},
        )
        return True

    def _guard_source_revision(self):
        current = self.calculate_source_revision()
        if not current:
            self.source_revision = ""
            return

        if self.is_new() or not self.source_revision or self.jha_status in EDITABLE_JHA_STATUSES:
            self.source_revision = current
            return

        self.mark_review_required_if_source_changed()


def mark_linked_jhas_for_work_change(doc, method=None):
    """Invalidate reviewed/signed JHAs when a Work Summary or direct child Task changes."""
    work_summary = ""

    if doc.get("type") == "Work Summary":
        work_summary = doc.name
    elif doc.get("parent_task"):
        parent_type = frappe.db.get_value("Task", doc.parent_task, "type")
        if parent_type == "Work Summary":
            work_summary = doc.parent_task

    if not work_summary:
        return

    names = frappe.get_all(
        "Digital Job Hazard Analysis",
        filters={
            "work_summary": work_summary,
            "jha_status": ["in", list(REVIEW_LOCKED_STATUSES)],
        },
        pluck="name",
        limit_page_length=100,
    )

    for name in names:
        try:
            jha = frappe.get_doc("Digital Job Hazard Analysis", name)
            if jha.mark_review_required_if_source_changed():
                jha.flags.allow_jha_review_mutation = True
                jha.save(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                title=f"Digital JHA work-change detection failed: {name}",
                message=frappe.get_traceback(),
            )
