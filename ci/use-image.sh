#!/usr/bin/env bash
# Called on an ephemeral GitHub runner with read-only registry credentials.
set -euo pipefail
image=$1
mode=$2
if docker image inspect "$image" >/dev/null 2>&1; then
  echo 'Using the locally prepared Verto CI image.'
elif docker pull "$image"; then
  echo 'Using the prepared Verto CI image.'
else
  echo 'Image unavailable; building locally so this revision still gets tested.'
  mapfile -t settings < <(python ci/build_settings.py)
  docker build --file ci/Dockerfile --tag "$image" \
    --build-arg "CI_IMAGE_KEY=${settings[0]}" --build-arg "BENCH_VERSION=${settings[1]}" \
    --build-arg "PYTHON_IMAGE=${settings[2]}" --build-arg "NODE_IMAGE=${settings[3]}" .
fi
docker run --rm --shm-size=256m --env CI=Yes \
  --volume "$GITHUB_WORKSPACE:/workspace/verto:ro" "$image" bash /opt/verto-ci/run.sh "$mode"
