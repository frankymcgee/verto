# Copyright (c) 2026, Webwire and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint


class VertoMobileSettings(Document):
    def validate(self):
        self._validate_global_notification_list()

    def _validate_global_notification_list(self):
        if not self.meta.has_field("global_notification_list"):
            return

        seen_users = set()
        for row in self.get("global_notification_list") or []:
            user = str(row.get("user") or "").strip()
            if not user:
                continue

            if user in seen_users:
                frappe.throw(f"User {user} appears more than once in Global Notification List.")
            seen_users.add(user)

            if not cint(row.get("enabled")):
                continue

            if cint(row.get("project_missing_purchase_order")) and not (
                cint(row.get("receive_email")) or cint(row.get("receive_push"))
            ):
                frappe.throw(
                    f"Global Notification List row for {user} has Project Missing Purchase Order enabled but no Email or Push channel selected."
                )
