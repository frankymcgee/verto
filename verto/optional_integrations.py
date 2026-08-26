from __future__ import annotations

import json
from pathlib import Path

import frappe
from frappe.modules.utils import sync_customizations_for_doctype


OPTIONAL_CUSTOMIZATIONS = {
    "CRM Deal": "crm_deal.json",
    "Studio Page": "studio_page.json",
}


def _customization_folder() -> Path:
    return Path(frappe.get_app_path("verto", "integrations", "customizations"))


def sync_optional_customizations() -> dict:
    """Apply Verto customizations only when the optional target DocType exists."""
    folder = _customization_folder()
    results = {}

    for doctype, filename in OPTIONAL_CUSTOMIZATIONS.items():
        if not frappe.db.exists("DocType", doctype):
            results[doctype] = "not-installed"
            continue

        path = folder / filename
        if not path.exists():
            results[doctype] = "missing-file"
            continue

        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        sync_customizations_for_doctype(data, str(folder), filename)
        results[doctype] = "synced"

    return results


def after_app_install(app_name: str):
    """Re-check optional integrations after another Frappe app is installed."""
    if app_name == "verto":
        return

    try:
        sync_optional_customizations()
        frappe.clear_cache()
    except Exception:
        frappe.log_error(
            title=f"Verto optional integration setup failed after installing {app_name}",
            message=frappe.get_traceback(),
        )
