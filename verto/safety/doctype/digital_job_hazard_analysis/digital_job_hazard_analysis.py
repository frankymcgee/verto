import hashlib

import frappe
from frappe.model.document import Document

from verto.api.mobile.home_child_tasks import get_work_summary_child_tasks


EDITABLE_JHA_STATUSES = {
    "Draft",
    "Voice Discussion in Progress",
    "Incomplete - Actions Required",
}


class DigitalJobHazardAnalysis(Document):
    def validate(self):
        self._set_work_summary_context()
        self._sync_planned_child_tasks()
        self._set_source_revision()

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
        """Mirror direct Task children into the draft JHA as planned work steps.

        The hidden source_task link remains stable if PERI later assigns its own
        source_step_identifier, so repeated validation updates the planned row
        instead of creating duplicates.
        """
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

    def _set_source_revision(self):
        if not self.work_summary or not frappe.db.exists("Task", self.work_summary):
            self.source_revision = ""
            return

        values = frappe.db.get_value(
            "Task",
            self.work_summary,
            ["name", "modified", "subject", "project", "parent_task_name", "work_order_number"],
            as_dict=True,
        ) or {}

        payload_parts = [
            str(values.get(key) or "")
            for key in sorted(values)
        ]

        for child in get_work_summary_child_tasks(self.work_summary):
            payload_parts.extend(
                [
                    str(child.get("name") or ""),
                    str(child.get("modified") or ""),
                    str(child.get("subject") or ""),
                    str(child.get("status") or ""),
                    str(child.get("type") or ""),
                    ",".join(child.get("assigned_users") or []),
                ]
            )

        payload = "|".join(payload_parts)
        self.source_revision = hashlib.sha256(payload.encode("utf-8")).hexdigest()
