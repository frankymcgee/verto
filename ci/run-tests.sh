#!/usr/bin/env bash
# Preserve the complete existing integration suite on the prepared test bench.
set -euo pipefail
export CI=Yes
export VERTO_CI_BENCH=${VERTO_CI_BENCH:-/opt/frappe-bench}

echo '::group::Run planner task, leave and staffing regressions'
(
  cd "$VERTO_CI_BENCH"
bench --site test_site run-tests \
  --app verto \
  --module verto.api.test_planner \
  --case TestPlannerAppendGenericTasks \
  --skip-before-tests
bench --site test_site run-tests \
  --app verto \
  --module verto.api.test_planner_leave \
  --skip-before-tests
bench --site test_site run-tests \
  --app verto \
  --module verto.api.test_planner_staffing \
  --skip-before-tests
bench --site test_site run-tests \
  --app verto \
  --module verto.api.test_planner_employee_colours \
  --skip-before-tests
bench --site test_site run-tests \
  --app verto \
  --module verto.api.test_planner_shift \
  --skip-before-tests
bench --site test_site run-tests \
  --app verto \
  --module verto.api.test_planner_projects \
  --skip-before-tests
)
echo '::endgroup::'

echo '::group::Verify project walkie talkie permissions, floor leases and mobile capture'
(
  cd "$VERTO_CI_BENCH"
./env/bin/python -m unittest discover -s apps/verto/tests -p 'test_walkie_talkie.py' -v
cd apps/verto/frontend
yarn test:ui tests/walkie-talkie.test.js
)
echo '::endgroup::'

echo '::group::Verify whiteboard pages and access controls'
(
  cd "$VERTO_CI_BENCH"
node --test apps/verto/tests/whiteboard-pages.test.mjs
bench --site test_site set-config allow_tests true
bench --site test_site run-tests --app verto --module verto.api.test_whiteboard --skip-before-tests
)
echo '::endgroup::'

echo '::group::Build Verto assets'
(
  cd "$VERTO_CI_BENCH"
bench build --app verto
)
echo '::endgroup::'

echo '::group::Verify mobile form location expansion'
(
  cd "$VERTO_CI_BENCH/apps/verto/frontend"
yarn test:ui tests/home-location.test.js
)
echo '::endgroup::'

echo '::group::Verify native mobile profile and self-service access'
(
  cd "$VERTO_CI_BENCH"
./env/bin/python -m unittest discover -s apps/verto/tests -p 'test_mobile_profile.py'
cd apps/verto/frontend
yarn test:ui tests/profile-menu.test.js tests/my-profile.test.js tests/mobile-startup.test.js
)
echo '::endgroup::'

echo '::group::Verify reusable public Web Form attachments'
(
  cd "$VERTO_CI_BENCH"
./env/bin/python -m unittest discover -s apps/verto/tests -p 'test_web_form_attachments.py'
bench --site test_site run-tests --app verto --module verto.api.test_web_form_attachments --skip-before-tests
)
echo '::endgroup::'

echo '::group::Verify Voice JHA engines and incident learning'
(
  cd "$VERTO_CI_BENCH"
./env/bin/python -m unittest discover -s apps/verto/tests -p 'test_jha_risk_signals.py'
./env/bin/python -m unittest discover -s apps/verto/tests -p 'test_jha_photo_content.py'
./env/bin/python -m unittest discover -s apps/verto/tests -p 'test_inx_import.py'
./env/bin/python -m unittest discover -s apps/verto/tests -p 'test_inx_sanitisation.py'
node --test apps/verto/tests/inx-import-ui.test.mjs
bench --site test_site run-tests --app verto --module verto.api.test_inx_incident_import --skip-before-tests
bench --site test_site run-tests --app verto --module verto.api.test_inx_incident_sanitisation --skip-before-tests
bench --site test_site run-tests --app verto --module verto.api.mobile.test_voice_jha_incidents --skip-before-tests
bench --site test_site run-tests --app verto --module verto.api.mobile.test_voice_jha_live --skip-before-tests
bench --site test_site run-tests --app verto --module verto.api.mobile.test_voice_jha_changes --skip-before-tests
bench --site test_site run-tests --app verto --module verto.api.mobile.test_voice_jha_fieldwork --skip-before-tests
bench --site test_site run-tests --app verto --module verto.api.mobile.test_voice_jha_workpack --skip-before-tests
bench --site test_site run-tests --app verto --module verto.api.mobile.test_voice_jha_steps --skip-before-tests
bench --site test_site run-tests --app verto --module verto.api.mobile.test_voice_jha_email --skip-before-tests
bench --site test_site run-tests --app verto --module verto.api.mobile.test_voice_jha_print --skip-before-tests
bench --site test_site run-tests --app verto --module verto.api.mobile.test_voice_jha_photos --skip-before-tests
bench --site test_site run-tests --app verto --module verto.api.mobile.test_qr_scanner --skip-before-tests
cd apps/verto/frontend
yarn test:ui tests/jha-incident-learning.test.js tests/jha-voice-protocol.test.js tests/jha-voice-engines.test.js tests/jha-voice-panel.test.js tests/jha-fieldwork.test.js tests/jha-workpack-ui.test.js tests/jha-active-step.test.js tests/jha-print-email.test.js tests/jha-offline.test.js tests/offline-payload.test.js tests/qr-links.test.js tests/qr-scanner.test.js tests/jha-photo-import.test.js
)
echo '::endgroup::'

echo '::group::Verify Investigations app, approvals and evidence privacy'
(
  cd "$VERTO_CI_BENCH"
./env/bin/python -m unittest discover -s apps/verto/tests -p 'test_investigation_rules.py'
./env/bin/python -m unittest discover -s apps/verto/tests -p 'test_investigation_report.py'
bench --site test_site run-tests --app verto --module verto.api.test_investigations --skip-before-tests
bench --site test_site run-tests --app verto --module verto.test_default_apps --skip-before-tests
cd apps/verto/investigations
yarn test:ui
)
echo '::endgroup::'

echo '::group::Verify Daily Timesheet reminders and hour-limit alerts'
(
  cd "$VERTO_CI_BENCH"
./env/bin/python -m unittest discover -s apps/verto/tests -p 'test_offline_sync.py'
bench --site test_site run-tests --app verto --module verto.api.mobile.test_offline_sync --skip-before-tests
bench --site test_site run-tests --app verto --module verto.api.mobile.test_timesheet_hour_limits --skip-before-tests
bench --site test_site run-tests --app verto --module verto.api.mobile.test_timesheet_reminders --skip-before-tests
cd apps/verto/frontend
yarn test:ui tests/offline-sync.test.js tests/offline-request-efficiency.test.js tests/offline-payload.test.js tests/form-controls.test.js tests/timesheet-reminders.test.js tests/shift-navigation-performance.test.js
)
echo '::endgroup::'

echo '::group::Verify weekly Timesheet client rejection'
(
  cd "$VERTO_CI_BENCH"
bench --site test_site run-tests --app verto --module verto.api.test_timesheet_approval --skip-before-tests
cd apps/verto/frontend
yarn test:ui tests/weekly-timesheet-approval.test.js
)
echo '::endgroup::'

echo '::group::Verify automated Verto setup'
(
  cd "$VERTO_CI_BENCH"
bench --site test_site execute verto.install.ensure_verto_setup
bench --site test_site execute verto.runtime_config.get_push_settings_config
bench --site test_site execute verto.health.collect_system_health
)
echo '::endgroup::'

echo '::group::Verify consolidated internal Timesheet approval'
(
  cd "$VERTO_CI_BENCH"
bench --site test_site run-tests --app verto --module verto.api.test_internal_timesheet_approval --skip-before-tests
cd apps/verto/frontend
yarn test:ui tests/internal-timesheet-approval.test.js
)
echo '::endgroup::'
