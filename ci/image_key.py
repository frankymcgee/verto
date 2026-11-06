#!/usr/bin/env python3
"""Content-address the reusable stack without keying on ordinary Verto edits."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    "ci/Dockerfile", "ci/Dockerfile.dockerignore", "ci/stack.json",
    "ci/image_key.py", "ci/build_settings.py", "ci/use-image.sh", "ci/prepare_bench.py", "ci/services.sh",
    "ci/seed.sh", "ci/run.sh", "ci/run-tests.sh",
    "pyproject.toml", ".gitmodules", "package.json", "yarn.lock",
    "frontend/package.json", "frontend/yarn.lock",
    "planner/package.json", "planner/yarn.lock",
    "investigations/package.json", "investigations/yarn.lock",
)


def image_key(root=ROOT, submodule_ref=None):
    root = Path(root)
    if submodule_ref is None:
        entry = subprocess.check_output(
            ["git", "-C", str(root), "ls-tree", "HEAD", "--", "frappe-ui"], text=True
        ).split()
        if len(entry) < 3 or entry[0] != "160000":
            raise ValueError("The frappe-ui submodule revision is missing.")
        submodule_ref = entry[2]
    if not re.fullmatch(r"[0-9a-f]{40}", submodule_ref):
        raise ValueError("Invalid frappe-ui revision.")
    digest = hashlib.sha256()
    for name in INPUTS:
        data = (root / name).read_bytes()
        digest.update(name.encode() + b"\0" + str(len(data)).encode() + b"\0" + data)
    digest.update(b"frappe-ui\0" + submodule_ref.encode())
    return "v16-" + digest.hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(image_key(args.root))
