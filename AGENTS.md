# Verto development guidance

## Branch and platform

- Implement new work on the existing `develop` branch. Prepare pull requests to
  `version-16`; do not create a feature branch unless the user requests one.
- Active support is **Frappe / ERPNext / HRMS v16 only**. Do not introduce v15
  compatibility code or describe v15 as a supported development target.
- Python is 3.14. CI uses Node 24 and Yarn Classic 1.22.22. Read `pyproject.toml`,
  package manifests and `ci/stack.json` for dependency constraints and pinned refs.
- `frappe-ui` is a pinned submodule shared by the three Vue applications. Initialize
  submodules before building; change the pin only for an intentional dependency update.

## Commit requirements

- Every commit must include an incremental increase to `verto.__version__` in
  `verto/__init__.py`. For routine fixes, increment the patch component from the
  latest version on the target branch, unless a different release is requested.
- Include the version increase in the same commit as the change.
- Preserve the mobile About screen's Git commit count version increment in
  `verto/api/mobile/about.py`. A shallow checkout's count may differ from the
  deployed checkout, so do not report a local count as the deployed version.

## Repository map and completed capabilities

| Area | Main locations and responsibilities |
| --- | --- |
| Mobile PWA | `frontend/src/`: native project/tasks, Gantt/maps, forms, profile, notifications, chat, QR scanning, themes and app update handling |
| Mobile form saves | `frontend/src/pages/NewDocument.vue`, `EditDocument.vue`, `components/mobile-fields/`: schema visibility, ratings/time controls, row + parent persistence and daily hours confirmation |
| Offline sync | `frontend/src/pwa/`, `frontend/src/verto-sw.ts`, `verto/api/mobile/offline.py`: durable queue, document receipts, attachment retries/progress and reconnection safety |
| Shared photo markup | `frontend/src/components/PhotoAnnotationEditor.vue`, `frontend/src/lib/photoAnnotation.ts`: shared with investigations; preserve original evidence |
| Handover assistance | `frontend/src/components/HandoverDraftPanel.vue`, `verto/api/mobile/handover_draft.py`: selected shift window, readable sources and explicitly applied draft rows |
| Timesheets | `verto/verto/doctype/daily_timesheet/`, `verto/api/internal_timesheet_approval.py`, `verto/api/timesheet_exceptions.py`, `verto/api/mobile/timesheet_*.py`: processing, validation, queue, reminders and limits |
| Internal review / client signing | `verto/verto/page/internal_timesheet_approval/`, `verto/api/timesheet_approval.py`, `verto/api/timesheet_signing.py`: separate internal and client approvals, rejection and audit |
| Planner | `planner/`, `verto/api/planner*.py`: rosters, allocations, leave, staffing, task groups, project statuses and collaboration |
| Investigations | `investigations/`, `verto/api/investigations.py`, investigation DocTypes: chronological workflow, 5 Whys/ICAM, evidence/actions and PDF reporting |
| PERI and JHA | `verto/api/peri/`, `verto/api/ai_tools.py`, `verto/api/mobile/voice_jha*.py`, related Vue components: dashboards/filters, photo review, voice/paper import, incident learning and lifecycle |
| Site configuration | `verto/install.py`, `verto/hooks.py`, fixtures, custom fields and Verto Mobile Settings: setup, permissions, branding and optional integrations |
| CI | `.github/workflows/`, `ci/`: prepared v16 image, integration/fresh install checks, browser/UI/security regressions |

Use the feature guides linked from `README.md` for behavior and configuration.
Update the relevant guide and the README feature summary when behavior changes.
AGENTS guidance should describe the current implementation, without treating old
feature requests or abandoned approaches as implemented functionality.

## Workflow invariants

- Authenticate server endpoints and enforce normal role, list and document
  permissions. Navigation visibility is a convenience, never authorization.
  Avoid `get_all` or permission bypasses in user-facing review/AI source APIs.
- The exceptions queue is a live, read-only reconciliation. Keep signing in the
  existing internal approval flow. Do not infer missing hours from truncated or
  unavailable sources; show check coverage and refuse incomplete oversized checks.
  Ignore cancelled weekly records and their orphaned daily sources, while retaining
  daily sources reused by active amendments.
- Reuse internal review shift/hour rules: 16:30 start cutoff, overnight duration,
  day/night/fly project limits, and SD classified using actual entered times.
  Missing hours respect shift end + one hour, full-day leave and dated exclusions.
- Keep daily processing idempotent and weekly updates locked. Maintain stable
  offline operation/attachment IDs through retries and server acknowledgement.
- Confirm a snapshot of the daily form values with the shared Frappe UI dialog.
  Cancellation, Escape, closing or navigation must retain form entries and avoid
  writes; repeat taps must not queue duplicate saves.
- Save Row persists existing parent edits and selected attachments together.
  Preserve linked project/task identity and invalidate stale dependency responses
  before saving; failed saves keep the row editor and draft available.
- Keep the submission checklist shared across new/edit forms and row editors.
  Reuse field/section visibility and conditional mandatory/read-only rules;
  numeric zero is valid, and blank editor markup is empty. Preserve native input
  validity checks when aggregating errors across tabs. Block incomplete saves
  before offline queueing. If another parent item blocks Save Row, offer the
  explicit Keep row and review form action without writing or losing attachments.
  Checklist navigation opens the exact tab/row without submitting the form.
- Keep signatures/client approvals separate from internal approval. Preserve
  immutable internal audits and stale-source/changed-content protection.
- Preserve original photographs; save annotated copies as separate attachments.
  Investigation copies remain unverified until reviewed.
- Store queued attachment bytes portably before IndexedDB transactions; WebKit
  cannot reliably clone native File/Blob values. Retain legacy queue readability.
- PERI drafts and photo/JHA analysis respect readable evidence and configured bot
  credentials. Do not fabricate counts, signatures or source links. Keep explicit
  human application/review steps required by each workflow.
- Do not reload the PWA during open forms or lose local drafts/queued work.
  Use theme tokens and accessible Frappe UI controls for responsive native pages.
  Sync status uses one updating Frappe toast without a layout bar. Keep persistent
  state in the avatar/Upload queue, suppress duplicate queue-page notices, and
  keep toast actions from navigating away from an open form.
- Generate current-site Desk links with `/desk`. Normalize stored `/app` links
  when opening browser drawers, preserving queries/fragments and unrelated routes.

## Verification

- Run tests relevant to changed behavior; add regressions for data integrity,
  permissions, async save/cancellation, offline retries and meaningful UI behavior.
- Mobile tests: `yarn --cwd frontend test:ui`. Planner/investigations have their
  own `test:ui` scripts. The root `yarn build` builds all applications.
- Isolated Python regressions in `tests/` can run without a bench. Database and
  permission integration tests need the v16 bench; `ci/run-tests.sh` lists them.
- Real-browser checks use production assets and Playwright Chromium/WebKit.
  For binary upload assertions, inspect bytes at the HTTP receiver; intercepted
  WebKit request text is not a reliable representation of binary multipart data.
- Wire new critical regressions into the appropriate CI job. If a check fails,
  inspect the failure and fix it before reporting the PR as ready.
- A passing build is not a deployment. Report the PR and validation actually
  completed, and call out any check that could not be run.
