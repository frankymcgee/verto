# Copyright (c) 2026 Pty Ltd, Webwire and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


RATING_MAP = {
    "Yes": 1,
    "Yes (fixed on the spot)": 0.75,
    "No": 0,
    "N/A": 1,
}

COMPLIANCE_SKIP_FIELDNAME_PARTS = [
    "safety_category",
    "improvement_required",
    "peri_used",
]


class CCVWorkingNearWater(Document):
    def validate(self):
        self.set_work_order_number_from_task()
        self.set_task_from_work_order_number()
        self.set_compliance_percentage()

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

        if self.is_compliance_trigger_field(changed_fieldname):
            before = self.get("compliance_percentage")
            self.set_compliance_percentage()

            if self.get("compliance_percentage") != before:
                updates["compliance_percentage"] = self.get("compliance_percentage")

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

    def is_compliance_trigger_field(self, fieldname):
        if not fieldname:
            return True

        df = self.meta.get_field(fieldname)

        if not df:
            return False

        return self.is_compliance_select_field(df)

    def is_compliance_select_field(self, df):
        if df.fieldtype != "Select":
            return False

        fieldname = df.fieldname or ""

        for skip_part in COMPLIANCE_SKIP_FIELDNAME_PARTS:
            if skip_part in fieldname:
                return False

        return True

    def set_compliance_percentage(self):
        if not self.meta.has_field("compliance_percentage"):
            return

        total_rating = 0
        count = 0

        for df in self.meta.fields:
            fieldname = df.fieldname

            if not fieldname:
                continue

            if not self.is_compliance_select_field(df):
                continue

            field_value = self.get(fieldname)

            if not field_value:
                continue

            if field_value in RATING_MAP:
                total_rating += RATING_MAP[field_value]
                count += 1

        average_percentage = (total_rating / count) * 100 if count else 0

        self.set("compliance_percentage", round(average_percentage, 2))
