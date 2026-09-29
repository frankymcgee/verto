import secrets

import frappe
from frappe import _
from frappe.model.document import Document


class VertoWhiteboard(Document):
    def validate(self):
        from verto.api.whiteboard import VISIBILITIES, validate_state

        if not isinstance(self.title, str) or not self.title.strip() or len(self.title.strip()) > 140:
            frappe.throw(_("Enter a board name of up to 140 characters."))
        self.title = self.title.strip()
        if self.visibility not in VISIBILITIES:
            frappe.throw(_("Invalid sharing setting."))
        validate_state(self.state)
        previous = self.get_doc_before_save()
        if not previous and self.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
            frappe.throw(_("Create the whiteboard under your own account."), frappe.PermissionError)
        if previous and self.owner != previous.owner:
            frappe.throw(_("The whiteboard owner cannot be changed."))
        # Never accept a caller-supplied token. Leaving public mode revokes the link;
        # publishing again creates a different link, so old links stay revoked.
        if self.visibility == "Public link":
            self.public_token = (
                previous.public_token if previous and previous.visibility == "Public link"
                and previous.public_token else secrets.token_urlsafe(32)
            )
        else:
            self.public_token = None
        self.revision = (previous.revision or 0) + 1 if previous else 1
