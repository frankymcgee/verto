"""Install the Verto Safety Cross into the compiled Insights v3 frontend.

The implementation remains version-controlled in Verto. The installer applies
the base chart patch and its versioned design update to the local Insights app,
and refuses partial or unsafe changes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TypedDict

import frappe


PATCH_VERSION = "1.1.0"
LEGACY_PATCH_VERSION = "1.0.0"
SUPPORTED_INSIGHTS_RELEASE = "v3.12.2"
SUPPORTED_INSIGHTS_COMMIT = "db795c4"
BASE_PATCH_FILE = Path(__file__).parent / "patches" / "insights-v3-safety-cross.patch"
DIAGONAL_PATCH_FILE = (
    Path(__file__).parent / "patches" / "insights-v3-safety-cross-diagonal.patch"
)


class PatchStatus(TypedDict, total=False):
    state: str
    installed: bool
    patch_version: str
    supported_insights_release: str
    supported_insights_commit: str
    insights_path: str
    message: str
    details: str
    next_step: str


def _insights_root() -> Path:
    """Return the root of apps/insights, not its Python package directory."""
    try:
        root = Path(frappe.get_app_path("insights")).resolve().parent
    except Exception as exc:
        raise RuntimeError(
            "Could not locate the Insights app. Confirm that Insights is installed "
            "on this bench."
        ) from exc

    required_paths = (
        root / "frontend" / "src2" / "charts" / "chart.ts",
        root / "frontend" / "src2" / "types" / "chart.types.ts",
        root / "insights" / "hooks.py",
    )
    missing = [str(path.relative_to(root)) for path in required_paths if not path.exists()]
    if missing:
        raise RuntimeError(
            "The installed Insights app does not have the expected version-3 "
            f"frontend structure. Missing: {', '.join(missing)}"
        )

    return root


def _run_git_apply(
    root: Path,
    patch_file: Path,
    *,
    check: bool = False,
    reverse: bool = False,
) -> subprocess.CompletedProcess[str]:
    args = ["git", "-C", str(root), "apply"]
    if reverse:
        args.append("--reverse")
    if check:
        args.append("--check")
    else:
        args.append("--whitespace=nowarn")
    args.append(str(patch_file))

    return subprocess.run(
        args,
        capture_output=True,
        check=False,
        text=True,
    )


def _result_details(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or "").strip()


def status() -> PatchStatus:
    """Return whether the Safety Cross is installed, available, or incompatible."""
    root = _insights_root()

    diagonal_reverse_check = _run_git_apply(
        root, DIAGONAL_PATCH_FILE, check=True, reverse=True
    )
    if diagonal_reverse_check.returncode == 0:
        return {
            "state": "installed",
            "installed": True,
            "patch_version": PATCH_VERSION,
            "supported_insights_release": SUPPORTED_INSIGHTS_RELEASE,
            "supported_insights_commit": SUPPORTED_INSIGHTS_COMMIT,
            "insights_path": str(root),
            "message": "The Verto Safety Cross patch is installed.",
            "next_step": "No source changes are required.",
        }

    base_reverse_check = _run_git_apply(root, BASE_PATCH_FILE, check=True, reverse=True)
    if base_reverse_check.returncode == 0:
        return {
            "state": "upgrade_available",
            "installed": True,
            "patch_version": LEGACY_PATCH_VERSION,
            "supported_insights_release": SUPPORTED_INSIGHTS_RELEASE,
            "supported_insights_commit": SUPPORTED_INSIGHTS_COMMIT,
            "insights_path": str(root),
            "message": (
                "The horizontal Safety Cross is installed and can be upgraded "
                "to the diagonal design."
            ),
            "next_step": (
                "Run verto.insights_safety_cross.installer.install, then build Insights."
            ),
        }

    apply_check = _run_git_apply(root, BASE_PATCH_FILE, check=True)
    if apply_check.returncode == 0:
        return {
            "state": "available",
            "installed": False,
            "patch_version": PATCH_VERSION,
            "supported_insights_release": SUPPORTED_INSIGHTS_RELEASE,
            "supported_insights_commit": SUPPORTED_INSIGHTS_COMMIT,
            "insights_path": str(root),
            "message": "The Safety Cross is not installed and can be applied safely.",
            "next_step": (
                "Run verto.insights_safety_cross.installer.install, then build Insights."
            ),
        }

    details = (
        _result_details(apply_check)
        or _result_details(base_reverse_check)
        or _result_details(diagonal_reverse_check)
    )
    return {
        "state": "incompatible",
        "installed": False,
        "patch_version": PATCH_VERSION,
        "supported_insights_release": SUPPORTED_INSIGHTS_RELEASE,
        "supported_insights_commit": SUPPORTED_INSIGHTS_COMMIT,
        "insights_path": str(root),
        "message": (
            "The installed Insights source is neither cleanly patched nor compatible "
            "with this Safety Cross patch. No files were changed."
        ),
        "details": details,
        "next_step": (
            "Confirm the Insights version-3 revision and update the Verto patch "
            "before trying again."
        ),
    }


def install() -> PatchStatus:
    """Apply the Safety Cross patch atomically. Safe to call more than once."""
    current = status()
    if current["state"] == "installed":
        current["message"] = "The Verto Safety Cross patch is already installed."
        return current

    if current["state"] == "upgrade_available":
        root = Path(current["insights_path"])
        result = _run_git_apply(root, DIAGONAL_PATCH_FILE)
        if result.returncode != 0:
            raise RuntimeError(
                "Git could not upgrade the Safety Cross to the diagonal design. "
                f"The horizontal version remains installed.\n{_result_details(result)}"
            )

        verified = status()
        if verified["state"] != "installed":
            raise RuntimeError(
                "The diagonal update completed, but post-install verification failed."
            )

        verified["message"] = (
            "The Verto Safety Cross was upgraded to the diagonal design successfully."
        )
        verified["next_step"] = (
            "Run: bench build --app insights && bench clear-cache && bench restart"
        )
        return verified

    if current["state"] != "available":
        raise RuntimeError(
            f"{current['message']}\n{current.get('details', '')}".strip()
        )

    root = Path(current["insights_path"])
    base_result = _run_git_apply(root, BASE_PATCH_FILE)
    if base_result.returncode != 0:
        raise RuntimeError(
            "Git could not apply the Safety Cross patch. No partial installation "
            f"should be retained.\n{_result_details(base_result)}"
        )

    diagonal_result = _run_git_apply(root, DIAGONAL_PATCH_FILE)
    if diagonal_result.returncode != 0:
        rollback = _run_git_apply(root, BASE_PATCH_FILE, reverse=True)
        rollback_details = _result_details(rollback)
        raise RuntimeError(
            "The base Safety Cross was applied, but the diagonal update failed. "
            "The base patch was rolled back.\n"
            f"{_result_details(diagonal_result)}\n{rollback_details}".strip()
        )

    verified = status()
    if verified["state"] != "installed":
        raise RuntimeError(
            "The patch command completed, but post-install verification failed."
        )

    verified["message"] = "The Verto Safety Cross patch was installed successfully."
    verified["next_step"] = (
        "Run: bench build --app insights && bench clear-cache && bench restart"
    )
    return verified


def remove() -> PatchStatus:
    """Remove only the exact Verto Safety Cross patch. Safe to call repeatedly."""
    current = status()
    if current["state"] == "available":
        current["message"] = "The Verto Safety Cross patch is already removed."
        return current

    if current["state"] not in {"installed", "upgrade_available"}:
        raise RuntimeError(
            "The Safety Cross cannot be removed automatically because the Insights "
            "files have changed since installation. Resolve those changes first.\n"
            f"{current.get('details', '')}".strip()
        )

    root = Path(current["insights_path"])
    if current["state"] == "installed":
        diagonal_result = _run_git_apply(root, DIAGONAL_PATCH_FILE, reverse=True)
        if diagonal_result.returncode != 0:
            raise RuntimeError(
                "Git could not remove the diagonal Safety Cross update safely.\n"
                f"{_result_details(diagonal_result)}"
            )

    result = _run_git_apply(root, BASE_PATCH_FILE, reverse=True)
    if result.returncode != 0:
        if current["state"] == "installed":
            _run_git_apply(root, DIAGONAL_PATCH_FILE)
        raise RuntimeError(
            "Git could not remove the Safety Cross patch safely.\n"
            f"{_result_details(result)}"
        )

    verified = status()
    if verified["state"] != "available":
        raise RuntimeError(
            "The reverse patch completed, but post-removal verification failed."
        )

    verified["message"] = "The Verto Safety Cross patch was removed successfully."
    verified["next_step"] = (
        "You can now update Insights. Reinstall the patch and rebuild Insights afterward."
    )
    return verified
