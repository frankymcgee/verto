# Webwire Verto

Verto extends **Frappe and ERPNext v16** for shutdown projects, field safety,
rostering, timesheets, investigations and PERI assisted workflows. Webwire
maintains this app for desktop browsers and an installable mobile PWA.

**Active development targets v16 only.** Work goes into `develop`, with pull
requests targeting `version-16`. Version 15 is no longer a development or
compatibility target.

## What is included

### Mobile field work

- Native project/task lists, grouped Gantt charts and maps showing task pins and
  drawn geometry, with task details and linked **+Form / +CCV** actions.
- Configurable forms and project tools from Verto Mobile Settings; conditional
  field/section visibility, child tables, emoji ratings, signatures, attachments
  and quarter-hour time selection. Saving a child row also saves its parent edits.
- Offline forms, daily timesheets and shift access, with stable operation IDs and
  server receipts to prevent duplicate submissions on reconnect. The upload queue
  shows acknowledgement, attachment progress, retry reasons and recent confirmations.
- Photo markup with arrows, circles and notes. The original photograph is retained
  and an annotated copy is attached separately.
- In-app QR scanning for supported documents, a native read-only profile,
  notifications, app/version details, push settings and light/dark/automatic themes.
  Embedded Desk pages use `/desk`; stored same-site `/app` links are converted when opened.
- Desktop sidebar and mobile navigation; employee-only shift/chat access, safe PWA
  updates while forms are open, cached field data and request coalescing.

### Planner and project controls

- Project rosters, day/night/fly/stand-down shifts, staffing roles and allocation
  editing, leave indicators, live collaboration and project-aware task dates.
- Generic task setup and appending task groups to existing projects; linked task
  visibility, project tools, handovers, Gameplan, folders and Raven channels.
- Separate completed/cancelled filters, cancelled-project shading and permission
  checked removal of cancelled leave with conflicting attendance where required.

### Timesheets and attendance

- Daily Timesheet processing into weekly Timesheet logs and attendance, with
  concurrency/duplicate protection and project day/night/fly hour limits.
- A **Frappe UI confirmation dialog** shows entered hours and shift details before
  new or edited daily timesheets are saved, including forms queued offline.
- A **Timesheet exceptions queue** for internal approvers: missing allocated
  hours (including no weekly document), weekly processing delays, hour/shift/source
  mismatches, overlaps and approved leave/attendance conflicts. Filter by week,
  project, employee/record, exception type and priority; open source records and
  the existing internal review directly. Cancelled weekly sheets and their orphaned
  daily sources are excluded; active amended sheets retain their daily links.
- Consolidated internal review with DS/NS columns, validation, comments, one
  signature for selected records, stale-source checks and an immutable audit.
  Stand-down follows the actual entered start time for DS/NS columns and limits.
- Client weekly signing, PDF downloads, rejection with a reason, scheduled email
  verification and shift-end/next-day reminders with dated exclusions.

### Safety, handovers and PERI

- Field Interactions, CCVs, safety/lead safety handovers, safety performance and
  post-shutdown SWOT reporting focused on improvements and follow-up actions.
- PERI draft handover rows from a selected reporting window with readable source
  links and explicit application before saving; signatures and ratings remain manual.
- Photo analysis with form context and failure/uncertainty notifications.
- Digital JHA voice facilitation, paper JHA photo import, guided updates/reopening,
  relevant incident learning, workpack lifecycle, team-leader review and branded
  PDF/email output. Voice engines and Raven/Flow chat are configured per site.
- Dynamic Insights dashboard/chart analysis and filter tools, with readable
  dashboard discovery, saved defaults and quantitative chart context.
- INX incident import and sanitisation; role-aware AI tools and review workflows.

### Investigations

- Native investigations with event timelines, 5 Whys, ICAM factors, evidence,
  corrective actions, verification and PDF reporting.
- Horizontal chronological timeline layout, branch-aware arrangement and full-width
  work areas. Photo annotations become separate unverified evidence linked to the original.

## Supported stack

| Component | Development target |
| --- | --- |
| Frappe, ERPNext, HRMS | v16 |
| Python | 3.14 (`>=3.14,<3.15` in `pyproject.toml`) |
| Node / Yarn | Node 24 / Yarn Classic 1.22.22 in CI |
| Frontends | Vue 3 / Vite / Frappe UI |
| Frappe UI | Pinned repository submodule; currently 1.2.0 |
| Integrations | Raven, Gameplan; Insights and PERI/Flow features require site configuration |

Dependency ranges live in `pyproject.toml` and the package manifests. The exact
integration-test stack and dependency revisions are recorded in `ci/stack.json`.

## Install or update

Use an existing v16 bench with the required apps from `pyproject.toml` installed.
Back up the site before updating it. Replace `SITE` with your site name.

```bash
cd frappe-bench
bench get-app --branch version-16 https://github.com/frankymcgee/verto.git
cd apps/verto
git submodule update --init --recursive
cd ../..
bench --site SITE install-app verto
bench build --app verto
bench restart
```

For an existing installation, update the `version-16` checkout and its submodules,
then run `bench --site SITE migrate`, `bench build --app verto` and `bench restart`.
The root build script installs locked dependencies and builds mobile, planner and
investigations assets. Use `/verto-mobile` to open the mobile app.

Configure Verto Mobile Settings for forms/tools, branding, notifications, PERI,
voice engines and review recipients. Also configure the site's normal role/user
permissions, workers, scheduler and integration credentials. Features that depend
on external services require those integrations to be enabled.

## Development and verification

Use `develop` for implementation and open a PR into `version-16`. Follow
[AGENTS.md](AGENTS.md) for version increments, repository layout and critical
workflow invariants.

```bash
git submodule update --init --recursive
yarn install --frozen-lockfile
yarn --cwd frontend install --frozen-lockfile
yarn --cwd planner install --frozen-lockfile
yarn --cwd investigations install --frozen-lockfile
yarn dev:frontend
```

- Mobile UI: `yarn --cwd frontend test:ui`.
- Planner / investigations: `yarn --cwd planner test:ui` and
  `yarn --cwd investigations test:ui`.
- Isolated exceptions checks: `python -m unittest discover -s tests -p 'test_timesheet_exceptions.py'`.
- Build: `yarn build` (all three applications).
- Frappe integration and fresh installation: see [CI test image](docs/ci-test-image.md).
  Real-browser regressions use the production build and Playwright Chromium/WebKit.

CI validates the v16 stack, cached test image, migration/fresh install where
required, frontend regressions, browser layout and security. It does not deploy
or merge a change automatically.

## Feature guides

| Area | Documentation |
| --- | --- |
| Timesheet exceptions and hours popup | [Queue and confirmation](docs/timesheet-exceptions.md) |
| Internal review and signing | [Internal approval](docs/internal-timesheet-approval.md) |
| Reminders, limits and client rejection | [Shift reminders](docs/shift-timesheet-reminders.md), [hour limits](docs/timesheet-hour-limit-alerts.md), [weekly rejection](docs/weekly-timesheet-rejection.md) |
| Handover drafts, photo markup and upload progress | [Mobile field tools](docs/mobile-field-tools.md) |
| Offline/mobile performance | [Mobile performance](docs/mobile-performance.md), [request efficiency](docs/request-efficiency.md) |
| QR codes and public web forms | [QR scanner](docs/mobile-qr-scanner.md), [web form attachments](docs/web-form-attachments.md) |
| Planner | [Live collaboration](docs/planner-live-collaboration.md) |
| Investigations | [Investigations](docs/incident-investigations.md) |
| PERI dashboards and chat | [Dashboard analysis/filter tools](docs/peri-dashboard-analysis.md), [Flow chat](docs/mobile-peri-flow.md) |
| JHA voice and paper import | [Voice engines](docs/voice-jha-engines.md), [fieldwork](docs/voice-jha-fieldwork.md), [paper import](docs/voice-jha-paper-import.md) |
| JHA lifecycle and learning | [Change management](docs/voice-jha-change-management.md), [workpacks](docs/voice-jha-workpack-lifecycle.md), [incidents](docs/voice-jha-incident-learning.md), [PDF/email](docs/voice-jha-print-email.md) |

## License and maintainer

Apache License 2.0; see [license.txt](license.txt). Maintained by
[Webwire](https://webwire.com.au).
