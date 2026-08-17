"""Install the Verto Safety Cross into the compiled Insights v3 frontend.

The implementation remains version-controlled in Verto. The installer applies
the base chart patch and its versioned design update to the local Insights app,
and refuses partial or unsafe changes.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import TypedDict

import frappe


PATCH_VERSION = "1.3.0"
DIAGONAL_PATCH_VERSION = "1.1.0"
LEGACY_PATCH_VERSION = "1.0.0"
SUPPORTED_INSIGHTS_RELEASE = "v3.12.2"
SUPPORTED_INSIGHTS_COMMIT = "db795c4"
BASE_PATCH_FILE = Path(__file__).parent / "patches" / "insights-v3-safety-cross.patch"
DIAGONAL_PATCH_FILE = (
    Path(__file__).parent / "patches" / "insights-v3-safety-cross-diagonal.patch"
)
RESPONSIVE_DIAGONAL_PATCH_FILE = (
    Path(__file__).parent
    / "patches"
    / "insights-v3-safety-cross-responsive-diagonal.patch"
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


def _bench_root(insights_root: Path) -> Path:
    """Return the Bench root containing the apps and sites directories."""
    root = insights_root.resolve().parent.parent
    required_paths = (root / "apps", root / "sites")
    if not all(path.is_dir() for path in required_paths):
        raise RuntimeError(
            f"Could not determine the Bench root from the Insights app at {insights_root}."
        )
    return root


def _run_deployment_command(label: str, command: list[str], bench_root: Path) -> None:
    """Run one visible deployment command and stop immediately on failure."""
    print(f"[Safety Cross] {label}: {shlex.join(command)}")
    result = subprocess.run(
        command,
        cwd=str(bench_root),
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"The Safety Cross source is installed, but deployment stopped while "
            f"running '{label}' (exit code {result.returncode}). Fix the command "
            "error and run deploy again; installation is safe to repeat."
        )


def status() -> PatchStatus:
    """Return whether the Safety Cross is installed, available, or incompatible."""
    root = _insights_root()

    responsive_reverse_check = _run_git_apply(
        root, RESPONSIVE_DIAGONAL_PATCH_FILE, check=True, reverse=True
    )
    if responsive_reverse_check.returncode == 0:
        return {
            "state": "installed",
            "installed": True,
            "patch_version": PATCH_VERSION,
            "supported_insights_release": SUPPORTED_INSIGHTS_RELEASE,
            "supported_insights_commit": SUPPORTED_INSIGHTS_COMMIT,
            "insights_path": str(root),
            "message": "The responsive Verto Safety Cross patch is installed.",
            "next_step": "No source changes are required.",
        }

    diagonal_reverse_check = _run_git_apply(
        root, DIAGONAL_PATCH_FILE, check=True, reverse=True
    )
    if diagonal_reverse_check.returncode == 0:
        return {
            "state": "responsive_upgrade_available",
            "installed": True,
            "patch_version": DIAGONAL_PATCH_VERSION,
            "supported_insights_release": SUPPORTED_INSIGHTS_RELEASE,
            "supported_insights_commit": SUPPORTED_INSIGHTS_COMMIT,
            "insights_path": str(root),
            "message": (
                "The CSS diagonal Safety Cross is installed and can be upgraded "
                "to the corner-perfect responsive design."
            ),
            "next_step": (
                "Run verto.insights_safety_cross.installer.install, then build Insights."
            ),
        }

    base_reverse_check = _run_git_apply(root, BASE_PATCH_FILE, check=True, reverse=True)
    if base_reverse_check.returncode == 0:
        return {
            "state": "diagonal_upgrade_available",
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
        or _result_details(responsive_reverse_check)
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

    patches_by_state = {
        "available": [
            BASE_PATCH_FILE,
            DIAGONAL_PATCH_FILE,
            RESPONSIVE_DIAGONAL_PATCH_FILE,
        ],
        "diagonal_upgrade_available": [
            DIAGONAL_PATCH_FILE,
            RESPONSIVE_DIAGONAL_PATCH_FILE,
        ],
        "responsive_upgrade_available": [RESPONSIVE_DIAGONAL_PATCH_FILE],
    }
    patch_files = patches_by_state.get(current["state"])
    if not patch_files:
        raise RuntimeError(
            f"{current['message']}\n{current.get('details', '')}".strip()
        )

    root = Path(current["insights_path"])
    applied: list[Path] = []
    for patch_file in patch_files:
        result = _run_git_apply(root, patch_file)
        if result.returncode == 0:
            applied.append(patch_file)
            continue

        rollback_errors = []
        for applied_patch in reversed(applied):
            rollback = _run_git_apply(root, applied_patch, reverse=True)
            if rollback.returncode != 0:
                rollback_errors.append(_result_details(rollback))

        details = [_result_details(result), *rollback_errors]
        detail_text = "\n".join(detail for detail in details if detail)
        raise RuntimeError(
            f"Git could not apply {patch_file.name}. The installation was rolled "
            f"back.\n{detail_text}"
        )

    verified = status()
    if verified["state"] != "installed":
        raise RuntimeError(
            "The patch command completed, but post-install verification failed."
        )

    if current["state"] == "available":
        verified["message"] = (
            "The responsive Verto Safety Cross was installed successfully."
        )
    else:
        verified["message"] = (
            f"The Verto Safety Cross was upgraded from version "
            f"{current['patch_version']} to {PATCH_VERSION} successfully."
        )
    verified["next_step"] = (
        "Run: bench build --app insights && bench clear-cache && bench restart"
    )
    return verified


def deploy() -> PatchStatus:
    """Install or upgrade, build Insights, clear the site cache, and restart Bench."""
    installed = install()
    insights_root = Path(installed["insights_path"])
    bench_root = _bench_root(insights_root)

    bench_executable = shutil.which("bench")
    if not bench_executable:
        raise RuntimeError(
            "The Safety Cross source is installed, but the bench executable was not "
            "found in PATH. Activate the Bench environment and run deploy again."
        )

    site = getattr(getattr(frappe, "local", None), "site", None)
    if not site:
        raise RuntimeError(
            "The Safety Cross source is installed, but the active Frappe site could "
            "not be determined. Run this command with: bench --site <site> execute "
            "verto.insights_safety_cross.installer.deploy"
        )

    commands = (
        ("build Insights", [bench_executable, "build", "--app", "insights"]),
        (
            "clear the site cache",
            [bench_executable, "--site", str(site), "clear-cache"],
        ),
        ("restart Bench", [bench_executable, "restart"]),
    )
    for label, command in commands:
        _run_deployment_command(label, command, bench_root)

    installed["message"] = (
        "The responsive Verto Safety Cross was installed, Insights was built, "
        f"the cache for {site} was cleared, and Bench was restarted successfully."
    )
    installed["next_step"] = "No further deployment commands are required."
    return installed


def remove() -> PatchStatus:
    """Remove only the exact Verto Safety Cross patch. Safe to call repeatedly."""
    current = status()
    if current["state"] == "available":
        current["message"] = "The Verto Safety Cross patch is already removed."
        return current

    patches_by_state = {
        "installed": [
            RESPONSIVE_DIAGONAL_PATCH_FILE,
            DIAGONAL_PATCH_FILE,
            BASE_PATCH_FILE,
        ],
        "responsive_upgrade_available": [DIAGONAL_PATCH_FILE, BASE_PATCH_FILE],
        "diagonal_upgrade_available": [BASE_PATCH_FILE],
    }
    patch_files = patches_by_state.get(current["state"])
    if not patch_files:
        raise RuntimeError(
            "The Safety Cross cannot be removed automatically because the Insights "
            "files have changed since installation. Resolve those changes first.\n"
            f"{current.get('details', '')}".strip()
        )

    root = Path(current["insights_path"])
    removed: list[Path] = []
    for patch_file in patch_files:
        result = _run_git_apply(root, patch_file, reverse=True)
        if result.returncode == 0:
            removed.append(patch_file)
            continue

        rollback_errors = []
        for removed_patch in reversed(removed):
            rollback = _run_git_apply(root, removed_patch)
            if rollback.returncode != 0:
                rollback_errors.append(_result_details(rollback))

        details = [_result_details(result), *rollback_errors]
        detail_text = "\n".join(detail for detail in details if detail)
        raise RuntimeError(
            f"Git could not remove {patch_file.name}. The installed version was "
            f"restored.\n{detail_text}"
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
