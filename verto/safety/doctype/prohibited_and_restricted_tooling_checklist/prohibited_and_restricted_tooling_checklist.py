# Copyright (c) 2026, Webwire Pty Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


RATING_MAP = {
    "Compliant": 1,
    "Not Compliant": 0,
    "N/A": 1,
}

COMPLIANCE_SKIP_FIELDNAME_PARTS = [
    "safety_category",
    "improvement_required",
]


class ProhibitedandRestrictedToolingChecklist(Document):
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
        warnings = []

        if changed_fieldname in ("link_task", "scope_or_wo"):
            before = self.get("work_order_number")
            warning = self.set_work_order_number_from_task()

            if warning:
                warnings.append(warning)

            if self.get("work_order_number") != before:
                updates["work_order_number"] = self.get("work_order_number")

        if changed_fieldname in ("work_order_number", "scope_or_wo"):
            before = self.get("link_task")
            warning = self.set_task_from_work_order_number()

            if warning:
                warnings.append(warning)

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
            "warnings": warnings,
        }

    def set_work_order_number_from_task(self):
        if self.get("scope_or_wo") != "Work Scope":
            return None

        if not self.get("link_task"):
            return None

        if not self.meta.has_field("work_order_number"):
            return None

        work_order_number = frappe.db.get_value(
            "Task",
            self.get("link_task"),
            "work_order_number",
        )

        if work_order_number:
            self.set("work_order_number", work_order_number)
            return None

        return "No Work Order Number found for this Task."

    def set_task_from_work_order_number(self):
        if self.get("scope_or_wo") != "Work Order Number":
            return None

        if not self.get("work_order_number"):
            return None

        if not self.meta.has_field("link_task"):
            return None

        task_name = frappe.db.get_value(
            "Task",
            {
                "work_order_number": self.get("work_order_number"),
            },
            "name",
        )

        if task_name:
            self.set("link_task", task_name)
            return None

        self.set("link_task", "")

        return "No task found for this Work Order Number."

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
        rated_fields_count = 0

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
                rated_fields_count += 1

        compliance_percentage = (
            (total_rating / rated_fields_count) * 100
            if rated_fields_count
            else 0
        )

        self.set("compliance_percentage", round(compliance_percentage, 2))