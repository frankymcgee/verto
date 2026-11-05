import subprocess
from pathlib import Path

import frappe
import verto


def require_login():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)


def get_company_name():
    try:
        company = frappe.db.get_single_value("Global Defaults", "default_company")
    except Exception:
        company = None

    if not company:
        try:
            company = frappe.defaults.get_global_default("company")
        except Exception:
            company = None

    return str(company or frappe.local.site or "").strip()


def get_incremental_app_version():
    base_version = str(getattr(verto, "__version__", "16.0.0") or "16.0.0").strip()

    try:
        app_root = Path(frappe.get_app_path("verto")).resolve().parent
        commit_count = subprocess.check_output(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=app_root,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip()

        if commit_count.isdigit():
            parts = base_version.lstrip("v").split(".")
            major = parts[0] if parts else "16"
            minor = parts[1] if len(parts) > 1 else "0"
            return f"v{major}.{minor}.{commit_count}"
    except Exception:
        pass

    return f"v{base_version.lstrip('v')}"


@frappe.whitelist()
def get_about_info():
    require_login()

    return {
        "company_name": get_company_name(),
        "app_version": get_incremental_app_version(),
        "copyright": "Copyright 2026 Webwire Pty Ltd",
    }
