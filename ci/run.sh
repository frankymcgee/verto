#!/usr/bin/env bash
set -euo pipefail
mode=${1:-integration}
[[ "$mode" == integration || "$mode" == fresh ]] || { echo 'Expected integration or fresh.' >&2; exit 2; }
source /opt/verto-ci/services.sh
source_root=/workspace/verto
expected_key=$(cat /opt/verto-ci/image-key)
actual_key=$(python "$source_root/ci/image_key.py" --root "$source_root")
[[ "$actual_key" == "$expected_key" ]] || { echo 'The image does not match this checkout dependency key.' >&2; exit 1; }

# Overlay the exact tested revision, including Git/submodule metadata needed by
# bench build, while preserving only the keyed node_modules already installed.
rsync -a --delete --exclude=node_modules --exclude=__pycache__ \
  "$source_root/" "$VERTO_CI_BENCH/apps/verto/"
cd "$VERTO_CI_BENCH"
./env/bin/pip install --no-deps --no-build-isolation -e apps/verto
start_ci_services

if [[ "$mode" == fresh ]]; then
  install_ci_site
  bench --site test_site execute verto.install.ensure_verto_setup
  bench --site test_site execute verto.runtime_config.get_push_settings_config
  bench --site test_site execute verto.health.collect_system_health
else
  mkdir -p sites/test_site
  cp /opt/verto-ci/site_config.json sites/test_site/site_config.json
  mariadb --host=127.0.0.1 --user=root --password=root <<'SQL'
CREATE DATABASE verto_ci CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'verto_ci'@'127.0.0.1' IDENTIFIED BY 'verto_ci';
GRANT ALL PRIVILEGES ON verto_ci.* TO 'verto_ci'@'127.0.0.1';
SQL
  gzip -dc /opt/verto-ci/seed.sql.gz | mariadb --host=127.0.0.1 --user=root --password=root verto_ci
  bench --site test_site migrate
  bench --site test_site set-config allow_tests true
  bash /opt/verto-ci/run-tests.sh
fi
