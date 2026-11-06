# Reusable Verto CI image

Normal pull requests use a versioned `ghcr.io/frankymcgee/verto-ci:v16-<hash>` image.
It contains Python 3.14, Node 24, Bench, pinned Frappe/ERPNext/HRMS/Gameplan/Raven
checkouts, Verto's Python/frontend dependencies, and a compressed synthetic test
database. It contains no tenant data or production credentials.

Each job runs in a disposable Docker container on a GitHub-hosted runner. It copies
the exact checked-out Verto revision into the prepared bench, preserves the keyed
`node_modules`, installs the current editable Python package without downloading
dependencies, starts isolated MariaDB/Redis processes, restores the clean seed,
migrates the current code, and runs the complete integration suite in
`ci/run-tests.sh`. Test data and processes disappear with the container.

## Workflows

- **Verto v16 CI:** fast checks run on pushes and PRs. Full integration checks run
  on PRs, manual runs and releases. Installation/schema/patch/dependency changes
  additionally install the current Verto onto a completely blank site. Such changes
  merged into `version-16` retain the post-merge fresh-install check.
- **Verto CI image:** trusted `develop`/`version-16` pushes affecting image or
  dependency inputs build the image. Restored-seed integration tests and a fresh
  installation must both pass before it is published to GHCR. There is also a
  manual trigger on these trusted branches.

The first image build is intentionally slower. Later runs pull the prepared image.
If it is missing or registry access is unavailable, the test job builds it locally
and still runs the checks. Pull requests never receive package publishing
permissions. Workflows use the repository's built-in `GITHUB_TOKEN`, with read
access for tests and package write access only for the trusted publisher; no PAT or
extra server is required. OCI source labels link the package to the repository.

## Refreshing the stack

`ci/stack.json` pins each upstream app to a full commit SHA. Update those pins when
adopting new upstream versions. Update its `generation` value to rebuild unchanged
pins against refreshed Python/Node base tags or OS/Python package updates. The
publisher will validate the rebuilt image before publishing it.

`ci/image_key.py` also hashes the Docker/runtime scripts, Python dependency
definition, JavaScript manifests/lockfiles and the `frappe-ui` Git submodule
revision. Ordinary application edits and `verto.__version__` increments do not
rebuild the stack. A run refuses an image whose dependency key does not match the
checkout, so changed requirements cannot silently use stale installed packages.

## Run locally

Initialize the `frappe-ui` submodule, then, on a Linux Docker host with Python 3:

```bash
git submodule update --init --recursive
export GITHUB_WORKSPACE="$PWD"
CI_IMAGE="ghcr.io/frankymcgee/verto-ci:$(python ci/image_key.py)"
bash ci/use-image.sh "$CI_IMAGE" integration
bash ci/use-image.sh "$CI_IMAGE" fresh
```

The registry package may be private; authenticate to GHCR before pulling it when
using a local workstation. Anonymous pulls work if its package visibility is set
to public. Both commands safely fall back to a local build if the image cannot be
pulled. All credentials baked into the synthetic site are disposable CI defaults.
