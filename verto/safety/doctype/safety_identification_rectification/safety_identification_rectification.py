# Copyright (c) 2026, Webwire Pty Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SafetyIdentificationRectification(Document):
    def validate(self):
        self.set_work_order_number_from_task()
        self.set_task_from_work_order_number()

    def mobile_field_change(self, changed_fieldname=None):
        """
        Called by the Verto Mobile form renderer when a field changes.

        This does not save the document. It only applies the same business
        rules to the in-memory document and returns changed values for Vue.
        """
        updates = {}

        if changed_fieldname in ("link_task", "scope_or_wo"):
            before = self.get("work_order_number")
            self.set_work_order_number_from_task()

            if self.get("work_order_number") != before:
                updates["work_order_number"] = self.get("work_order_number")

        if changed_fieldname in ("work_order_number", "scope_or_wo"):
            before = self.get("link_task")
            self.set_task_from_work_order_number()

            if self.get("link_task") != before:
                updates["link_task"] = self.get("link_task")

        return {
            "values": updates,
            "messages": [],
            "warnings": [],
        }

    def set_work_order_number_from_task(self):
        if self.get("scope_or_wo") != "Work Scope":
            return

        if not self.get("link_task"):
            return

        if not self.meta.has_field("work_order_number"):
            return

        work_order_number = frappe.db.get_value(
            "Task",
            self.get("link_task"),
            "work_order_number",
        )

        if work_order_number:
            self.set("work_order_number", work_order_number)

    def set_task_from_work_order_number(self):
        if self.get("scope_or_wo") != "Work Order Number":
            return

        if not self.get("work_order_number"):
            return

        if not self.meta.has_field("link_task"):
            return

        task_name = frappe.db.get_value(
            "Task",
            {
                "work_order_number": self.get("work_order_number"),
            },
            "name",
        )

        if task_name:
            self.set("link_task", task_name)