from pathlib import Path

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer


SERVICE_WORKER_ROUTE = "verto-mobile-sw.js"
SERVICE_WORKER_RELATIVE_PATH = ("public", "pwa", "verto-mobile-sw.js")


class VertoServiceWorkerRenderer(BaseRenderer):
    """Serve the Verto Mobile service worker from the site root.

    Keeping the worker at /verto-mobile-sw.js allows it to control the
    /verto-mobile application without requiring a custom nginx location block.
    """

    def can_render(self):
        return self.path == SERVICE_WORKER_ROUTE

    def render(self):
        service_worker_path = Path(frappe.get_app_path("verto")).joinpath(
            *SERVICE_WORKER_RELATIVE_PATH
        )

        if not service_worker_path.exists():
            raise frappe.PageDoesNotExistError

        response = self.build_response(
            service_worker_path.read_text(encoding="utf-8"),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Service-Worker-Allowed": "/",
                "X-Content-Type-Options": "nosniff",
            },
        )
        response.mimetype = "application/javascript"
        return response
