from __future__ import annotations

from pathlib import Path

import frappe
from frappe import _


REQUIRED_APPS = ("frappe", "erpnext", "hrms", "raven", "gameplan", "verto")
REQUIRED_DOCTYPES = (
    "Verto Mobile Settings",
    "Verto Push Subscription",
    "Verto Timesheet Reminder Exclusion",
)
SCHEDULED_METHODS = (
    "verto.api.mobile.push_notifications.send_previous_day_missing_hours_reminders",
    "verto.api.automate.send_weekly_timesheet_verification",
    "verto.api.automate.send_grouped_weekly_timesheets",
    "verto.api.automate.send_grouped_timesheet_followup_reminders",
)


def _check(label: str, ok: bool, detail: str = "", repairable: bool = False):
    return {
        "label": label,
        "ok": bool(ok),
        "detail": detail,
        "repairable": bool(repairable),
    }


def collect_system_health() -> dict:
    checks = []
    installed_apps = set(frappe.get_installed_apps())

    missing_apps = [app for app in REQUIRED_APPS if app not in installed_apps]
    checks.append(
        _check(
            "Required applications",
            not missing_apps,
            "All required apps installed" if not missing_apps else f"Missing: {', '.join(missing_apps)}",
        )
    )

    missing_doctypes = [doctype for doctype in REQUIRED_DOCTYPES if not frappe.db.exists("DocType", doctype)]
    checks.append(
        _check(
            "Verto schema",
            not missing_doctypes,
            "Required Verto DocTypes are present" if not missing_doctypes else f"Missing: {', '.join(missing_doctypes)}",
            repairable=True,
        )
    )

    app_path = Path(frappe.get_app_path("verto"))
    mobile_js = app_path / "public" / "verto-mobile" / "assets" / "index.js"
    mobile_css = app_path / "public" / "verto-mobile" / "assets" / "index.css"
    service_worker = app_path / "public" / "pwa" / "verto-mobile-sw.js"

    checks.append(
        _check(
            "Verto Mobile assets",
            mobile_js.exists() and mobile_css.exists(),
            "Frontend assets found" if mobile_js.exists() and mobile_css.exists() else "Frontend assets are missing; rebuild Verto assets",
        )
    )
    checks.append(
        _check(
            "PWA service worker",
            service_worker.exists(),
            "/verto-mobile-sw.js source is available" if service_worker.exists() else "Service worker build output is missing",
        )
    )

    manifest = Path(frappe.get_site_path("public", "files", "verto-mobile-manifest.webmanifest"))
    checks.append(
        _check(
            "PWA manifest",
            manifest.exists(),
            "Site manifest generated" if manifest.exists() else "Site manifest has not been generated",
            repairable=True,
        )
    )

    try:
        from verto.runtime_config import get_push_settings_config

        push = get_push_settings_config()
        checks.append(
            _check(
                "Push notifications",
                push["configured"],
                "VAPID keys configured in Verto Mobile Settings" if push["configured"] else "VAPID keys are not configured",
                repairable=True,
            )
        )
    except Exception:
        checks.append(_check("Push notifications", False, "Could not read push configuration", repairable=True))

    try:
        from frappe.utils.scheduler import is_scheduler_inactive

        scheduler_active = not is_scheduler_inactive(verbose=False)
    except Exception:
        scheduler_active = False

    checks.append(
        _check(
            "Scheduler",
            scheduler_active,
            "Scheduler is active" if scheduler_active else "Scheduler is disabled or paused",
        )
    )

    if frappe.db.exists("DocType", "Scheduled Job Type"):
        missing_jobs = [
            method
            for method in SCHEDULED_METHODS
            if not frappe.db.exists("Scheduled Job Type", {"method": method, "stopped": 0})
        ]
        checks.append(
            _check(
                "Verto scheduled jobs",
                not missing_jobs,
                "Scheduled jobs are synced" if not missing_jobs else f"Missing/stopped: {', '.join(missing_jobs)}",
                repairable=True,
            )
        )

    failed = [item for item in checks if not item["ok"]]
    return {
        "healthy": not failed,
        "checks": checks,
        "failed": len(failed),
        "site": frappe.local.site,
    }


@frappe.whitelist()
def get_system_health():
    if not frappe.has_permission("Verto Mobile Settings", ptype="read"):
        frappe.throw(_("You do not have permission to view Verto system health."), frappe.PermissionError)

    return collect_system_health()


@frappe.whitelist()
def repair_setup():
    if not frappe.has_permission("Verto Mobile Settings", ptype="write"):
        frappe.throw(_("You do not have permission to repair Verto setup."), frappe.PermissionError)

    from verto.install import ensure_verto_setup

    repaired = ensure_verto_setup()
    return {
        "repaired": repaired,
        "health": collect_system_health(),
    }
