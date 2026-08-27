"""Desk actions for the optional Verto Safety Cross integration."""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.utils import now
from frappe.utils.synchronization import filelock

from verto.insights_safety_cross import installer


SETTINGS_DOCTYPE = "Verto Mobile Settings"
DEPLOYMENT_CACHE_KEY = "verto:insights-safety-cross:deployment"
DEPLOYMENT_CACHE_TTL = 24 * 60 * 60
DEPLOYMENT_JOB_ID = "verto-insights-safety-cross-deploy"
DEPLOYMENT_TIMEOUT = 60 * 60
DEPLOYMENT_LOCK = "verto-insights-safety-cross-deploy"


def _require_permission(ptype: str) -> None:
    if not frappe.has_permission(SETTINGS_DOCTYPE, ptype=ptype):
        frappe.throw(
            _("You do not have permission to manage the Verto Safety Cross."),
            frappe.PermissionError,
        )

    if (
        ptype == "write"
        and frappe.session.user != "Administrator"
        and "System Manager" not in frappe.get_roles(frappe.session.user)
    ):
        frappe.throw(
            _("Only Administrator or a System Manager can patch and rebuild Insights."),
            frappe.PermissionError,
        )


def _deployment_state() -> dict[str, Any]:
    state = frappe.cache.get_value(
        DEPLOYMENT_CACHE_KEY,
        expires=True,
    )
    if isinstance(state, dict):
        return state

    return {
        "state": "idle",
        "message": "No Safety Cross deployment has been started from this site.",
        "error": "",
        "updated_on": None,
        "site": frappe.local.site,
    }


def _set_deployment_state(
    state: str,
    message: str,
    *,
    error: str = "",
    patch_version: str | None = None,
    requested_by: str | None = None,
) -> dict[str, Any]:
    payload = {
        "state": state,
        "message": message,
        "error": error,
        "patch_version": patch_version,
        "updated_on": now(),
        "site": frappe.local.site,
        "requested_by": requested_by,
    }
    frappe.cache.set_value(
        DEPLOYMENT_CACHE_KEY,
        payload,
        expires_in_sec=DEPLOYMENT_CACHE_TTL,
    )
    return payload


def _git_revision(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        check=False,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _source_status() -> dict[str, Any]:
    if "insights" not in frappe.get_installed_apps():
        return {
            "state": "not_installed",
            "installed": False,
            "message": "Insights is not installed on this site.",
            "next_step": "Install Insights before deploying the Safety Cross.",
            "deployment": _deployment_state(),
            "bench_wide": True,
        }

    try:
        current = dict(installer.status())
    except Exception as exc:
        return {
            "state": "unavailable",
            "installed": False,
            "message": str(exc),
            "next_step": "Check the installed Insights version and server error log.",
            "deployment": _deployment_state(),
            "bench_wide": True,
        }

    try:
        import insights

        current["installed_insights_release"] = getattr(insights, "__version__", "")
    except Exception:
        current["installed_insights_release"] = ""

    root = Path(current["insights_path"])
    current["installed_insights_commit"] = _git_revision(root)
    current["deployment"] = _deployment_state()
    current["bench_wide"] = True
    return current


def _bench_python(bench_root: Path) -> str:
    """Return the Bench virtualenv Python used by Pilot and Frappe workers."""
    candidate = bench_root / "env" / "bin" / "python"
    if candidate.is_file():
        return str(candidate)

    # A normal Frappe background worker itself runs inside the Bench virtualenv,
    # so sys.executable is the safest fallback when the conventional path differs.
    if sys.executable and Path(sys.executable).is_file():
        return sys.executable

    raise RuntimeError(
        "The Safety Cross source was installed, but the Bench Python executable "
        "could not be located. Rebuild Insights from Pilot or the Bench console."
    )


def _build_insights(insights_root: Path) -> None:
    bench_root = installer._bench_root(insights_root)
    sites_root = bench_root / "sites"
    if not sites_root.is_dir():
        raise RuntimeError(
            f"The Safety Cross source was installed, but the Bench sites directory "
            f"could not be found at {sites_root}."
        )

    # Pilot does not install a standalone `bench` executable inside every Bench.
    # It invokes the Frappe CLI through the Bench virtualenv Python instead:
    #   <bench>/env/bin/python -m frappe.utils.bench_helper frappe ...
    # Running from sites/ is required so bench_helper can resolve apps.txt and
    # common_site_config.json for this Bench.
    command = [
        _bench_python(bench_root),
        "-m",
        "frappe.utils.bench_helper",
        "frappe",
        "build",
        "--app",
        "insights",
    ]
    print(f"[Safety Cross] build Insights: {shlex.join(command)}")
    result = subprocess.run(
        command,
        cwd=str(sites_root),
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode == 0:
        return

    details = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if len(details) > 6000:
        details = details[-6000:]
    raise RuntimeError(
        "The Safety Cross source was installed, but the Insights build failed "
        f"with exit code {result.returncode}.\n{details}".strip()
    )


@frappe.whitelist()
def get_status() -> dict[str, Any]:
    """Return source compatibility and the latest queued deployment state."""
    _require_permission("read")
    return _source_status()


@frappe.whitelist()
def queue_install_and_rebuild() -> dict[str, Any]:
    """Queue a bench-wide Safety Cross patch and Insights frontend rebuild."""
    _require_permission("write")

    current = _source_status()
    allowed_states = {
        "available",
        "installed",
        "diagonal_upgrade_available",
        "responsive_upgrade_available",
    }
    if current.get("state") not in allowed_states:
        detail = current.get("details") or current.get("next_step") or ""
        message = _("The Safety Cross cannot be deployed against the installed Insights source.")
        if detail:
            message = f"{message}\n\n{detail}"
        frappe.throw(message)

    requested_by = frappe.session.user
    _set_deployment_state(
        "queued",
        "Safety Cross deployment is queued on the long worker.",
        patch_version=current.get("patch_version"),
        requested_by=requested_by,
    )

    try:
        job = frappe.enqueue(
            "verto.insights_safety_cross.actions.install_and_rebuild",
            queue="long",
            timeout=DEPLOYMENT_TIMEOUT,
            job_id=DEPLOYMENT_JOB_ID,
            deduplicate=True,
            requested_by=requested_by,
        )
    except Exception as exc:
        _set_deployment_state(
            "failed",
            "Safety Cross deployment could not be queued.",
            error=str(exc),
            patch_version=current.get("patch_version"),
            requested_by=requested_by,
        )
        raise

    return {
        "queued": bool(job),
        "already_running": job is None,
        "job_id": getattr(job, "id", DEPLOYMENT_JOB_ID),
        "status": _source_status(),
    }


def install_and_rebuild(requested_by: str | None = None) -> dict[str, Any]:
    """Apply the patch and rebuild Insights from a long background worker."""
    requested_by = requested_by or frappe.session.user
    _set_deployment_state(
        "running",
        "Applying or upgrading the Verto Safety Cross patch.",
        requested_by=requested_by,
    )

    try:
        with filelock(DEPLOYMENT_LOCK, timeout=5, is_global=True):
            installed = installer.install()
            patch_version = installed.get("patch_version")
            _set_deployment_state(
                "running",
                "The Safety Cross source is installed. Rebuilding Insights assets.",
                patch_version=patch_version,
                requested_by=requested_by,
            )

            insights_root = Path(installed["insights_path"])
            _build_insights(insights_root)

        # The rebuilt frontend is static; clearing Frappe's cache is sufficient.
        # A process restart from inside the worker would terminate the job itself.
        frappe.clear_cache()
        deployment = _set_deployment_state(
            "completed",
            (
                "The Verto Safety Cross is installed and Insights was rebuilt. "
                "Refresh any open Insights tabs to load the new assets."
            ),
            patch_version=installed.get("patch_version"),
            requested_by=requested_by,
        )
        installed["deployment"] = deployment
        installed["message"] = deployment["message"]
        installed["next_step"] = "Refresh Insights in the browser."
        return installed
    except Exception as exc:
        error = str(exc).strip() or exc.__class__.__name__
        _set_deployment_state(
            "failed",
            "Safety Cross deployment failed. No further build steps were run.",
            error=error,
            requested_by=requested_by,
        )
        frappe.log_error(
            title="Verto Safety Cross deployment failed",
            message=frappe.get_traceback(),
        )
        raise