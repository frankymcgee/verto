from urllib.parse import urlsplit

import frappe
from frappe import _
from frappe.model.document import Document


class VertoWalkieTalkieSettings(Document):
    def validate(self):
        if not 5 <= int(self.max_transmission_seconds or 0) <= 120:
            frappe.throw(_("Maximum transmission must be between 5 and 120 seconds."))
        if self.enabled or self.livekit_url:
            parsed = urlsplit(str(self.livekit_url or "").strip())
            if parsed.scheme != "wss" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
                frappe.throw(_("LiveKit URL must be a secure wss:// server address without a path."))
        if self.enabled and (not self.livekit_api_key or not self.get_password("livekit_api_secret", raise_exception=False)):
            frappe.throw(_("Set the LiveKit API key and secret before enabling walkie talkie."))
