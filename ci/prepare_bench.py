#!/usr/bin/env python3
"""Install pinned upstream apps and Verto's dependencies once per image key."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tomllib


BENCH = Path(os.environ.get("VERTO_CI_BENCH", "/opt/frappe-bench"))
SOURCE = Path("/opt/verto-source")
STACK = json.loads((SOURCE / "ci/stack.json").read_text())


def run(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)


sources = Path("/tmp/verto-ci-upstream")
for app in STACK["apps"]:
    if not re.fullmatch(r"[0-9a-f]{40}", app["ref"]):
        raise ValueError(f"Pin {app['name']} to a complete commit SHA.")
    path = sources / app["name"]
    path.mkdir(parents=True)
    run("git", "init", str(path))
    run("git", "remote", "add", "origin", "https://github.com/" + app["repository"] + ".git", cwd=path)
    run("git", "fetch", "--depth=1", "origin", app["ref"], cwd=path)
    run("git", "checkout", "-B", "ci-pinned", "FETCH_HEAD", cwd=path)

run("bench", "init", "--ignore-exist", "--frappe-path", str(sources / "frappe"),
    "--frappe-branch", "ci-pinned", "--skip-assets", "--skip-redis-config-generation",
    "--no-backups", "--python", shutil.which("python"), str(BENCH))
for app in STACK["apps"]:
    if app["name"] != "frappe":
        run("bench", "get-app", "--branch", "ci-pinned", "--skip-assets", str(sources / app["name"]), cwd=BENCH)
    run("git", "remote", "set-url", "upstream", "https://github.com/" + app["repository"] + ".git",
        cwd=BENCH / "apps" / app["name"])

shutil.copytree(SOURCE, BENCH / "apps/verto", symlinks=True)
apps = BENCH / "sites/apps.txt"
apps.write_text(apps.read_text().rstrip() + "\nverto\n")
build_requirements = tomllib.loads((SOURCE / "pyproject.toml").read_text())["build-system"]["requires"]
run(str(BENCH / "env/bin/pip"), "install", *build_requirements)
run(str(BENCH / "env/bin/pip"), "install", "-e", str(BENCH / "apps/verto"))
run("bench", "setup", "requirements", "--dev", cwd=BENCH)
for directory in (".", "frontend", "planner", "investigations"):
    run("yarn", "install", "--frozen-lockfile", "--non-interactive", cwd=BENCH / "apps/verto" / directory)

config = BENCH / "sites/common_site_config.json"
data = json.loads(config.read_text())
data.update(redis_cache="redis://127.0.0.1:13000", redis_queue="redis://127.0.0.1:11000",
    redis_socketio="redis://127.0.0.1:13000", developer_mode=0)
config.write_text(json.dumps(data, indent=2) + "\n")
shutil.rmtree(sources)
