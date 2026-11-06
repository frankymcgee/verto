#!/usr/bin/env bash
# Private, disposable MariaDB/Redis processes. Never connect to a tenant site.
set -euo pipefail
export VERTO_CI_BENCH=${VERTO_CI_BENCH:-/opt/frappe-bench}
CI_RUNTIME_DIR=$(mktemp -d /tmp/verto-ci.XXXXXX)
CI_SERVICE_PIDS=()

cleanup_ci_services() {
  local status=$?
  trap - EXIT
  if (( status != 0 )); then
    for log in "$CI_RUNTIME_DIR"/*.log; do
      [[ ! -f "$log" ]] || tail -n 60 "$log"
    done
  fi
  for pid in "${CI_SERVICE_PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${CI_SERVICE_PIDS[@]}"; do wait "$pid" 2>/dev/null || true; done
  rm -rf "$CI_RUNTIME_DIR"
  exit "$status"
}
trap cleanup_ci_services EXIT

start_ci_services() {
  mariadb-install-db --user="$(id -un)" --datadir="$CI_RUNTIME_DIR/mysql" \
    --auth-root-authentication-method=normal --skip-test-db > "$CI_RUNTIME_DIR/install.log" 2>&1
  mariadbd --user="$(id -un)" --datadir="$CI_RUNTIME_DIR/mysql" --socket="$CI_RUNTIME_DIR/mysql.sock" \
    --pid-file="$CI_RUNTIME_DIR/mysql.pid" --port=3306 --bind-address=127.0.0.1 \
    --skip-log-bin --innodb-buffer-pool-size=128M --innodb-flush-log-at-trx-commit=2 \
    > "$CI_RUNTIME_DIR/mariadb.log" 2>&1 &
  CI_SERVICE_PIDS+=("$!")
  local ready=false
  for (( attempt=0; attempt<120; attempt++ )); do
    if mariadb-admin --socket="$CI_RUNTIME_DIR/mysql.sock" --user=root ping --silent 2>/dev/null; then
      ready=true; break
    fi
    sleep 0.5
  done
  [[ "$ready" == true ]] || { echo 'CI MariaDB did not start.' >&2; return 1; }
  mariadb --socket="$CI_RUNTIME_DIR/mysql.sock" --user=root <<'SQL'
ALTER USER 'root'@'localhost' IDENTIFIED BY 'root';
SET GLOBAL character_set_server = 'utf8mb4';
SET GLOBAL collation_server = 'utf8mb4_unicode_ci';
SQL
  for port in 13000 11000; do
    redis-server --bind 127.0.0.1 --port "$port" --save '' --appendonly no \
      > "$CI_RUNTIME_DIR/redis-$port.log" 2>&1 &
    CI_SERVICE_PIDS+=("$!")
    ready=false
    for (( attempt=0; attempt<60; attempt++ )); do
      if redis-cli -h 127.0.0.1 -p "$port" ping >/dev/null 2>&1; then ready=true; break; fi
      sleep 0.25
    done
    [[ "$ready" == true ]] || return 1
  done
}

install_ci_site() {
  cd "$VERTO_CI_BENCH"
  rm -rf sites/test_site
  bench new-site --db-host 127.0.0.1 --db-port 3306 --db-name verto_ci \
    --db-password verto_ci --db-root-password root --admin-password admin \
    --mariadb-user-host-login-scope=127.0.0.1 test_site
  bench --site test_site install-app verto
  bench --site test_site migrate
  bench --site test_site set-config allow_tests true
}
