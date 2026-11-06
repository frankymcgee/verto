#!/usr/bin/env python3
"""Select PR integration checks and installation checks without duplicate push runs."""
import fnmatch
import json
import os
from pathlib import Path
import subprocess


INSTALL_INPUTS = (
    "ci/*", ".github/workflows/ci*.yml", "pyproject.toml", ".gitmodules", "frappe-ui",
    "package.json", "yarn.lock", "*/package.json", "*/yarn.lock",
    "verto/install.py", "verto/hooks.py", "verto/modules.txt", "verto/patches.txt",
    "verto/patches/*", "verto/fixtures/*", "verto/**/doctype/*.json", "verto/**/custom/*",
)


def installation_changed(paths):
    return any(fnmatch.fnmatchcase(path, pattern) for path in paths for pattern in INSTALL_INPUTS)


def select_checks(event_name, event, paths, ref=""):
    if event_name == "pull_request":
        return True, installation_changed(paths)
    if event_name == "workflow_dispatch":
        fresh = event.get("inputs", {}).get("fresh_install", True)
        return True, fresh is True or str(fresh).lower() == "true"
    if event_name == "release":
        return True, True
    return False, ref == "refs/heads/version-16" and installation_changed(paths)


def changed_files(event_name, event):
    if event_name == "pull_request":
        base = event["pull_request"]["base"]["sha"]
        head = "HEAD"
    elif event_name == "push" and event.get("before", "").strip("0"):
        base, head = event["before"], "HEAD"
    else:
        return []
    raw = subprocess.check_output(["git", "diff", "--name-only", "-z", base, head])
    return [p for p in raw.decode().split("\0") if p]


if __name__ == "__main__":
    name = os.environ["GITHUB_EVENT_NAME"]
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    checks = select_checks(name, event, changed_files(name, event), os.environ.get("GITHUB_REF", ""))
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write(f"integration={str(checks[0]).lower()}\nfresh={str(checks[1]).lower()}\n")
