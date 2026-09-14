import hashlib

import frappe
from frappe.model.document import Document


class DigitalJobHazardAnalysis(Document):
    def validate(self):
        self._set_work_summary_context()
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
        payload = "|".join(str(values.get(key) or "") for key in sorted(values))
        self.source_revision = hashlib.sha256(payload.encode("utf-8")).hexdigest()
