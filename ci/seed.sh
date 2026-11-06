#!/usr/bin/env bash
set -euo pipefail
source /opt/verto-ci/services.sh
start_ci_services
install_ci_site
mariadb-dump --host=127.0.0.1 --user=root --password=root --single-transaction \
  --skip-comments --skip-dump-date --no-tablespaces verto_ci | gzip -1 > /opt/verto-ci/seed.sql.gz
# This seed contains only a newly installed synthetic site and CI credentials.
cp "$VERTO_CI_BENCH/sites/test_site/site_config.json" /opt/verto-ci/site_config.json
