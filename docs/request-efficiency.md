# Request efficiency audit and first refactor

Audit baseline: `version-16`, `e4f3829557b91adb83d3c638a2f67e151755a901` (16.3.1).
Branch: `performance/reduce-api-requests`, rebased onto `f1124a7` (16.3.3),
including the separate Mobile default-app option and root redirect fix.
First refactor: 16.3.4.
The 16.3.5 follow-up adds [live planner collaboration](planner-live-collaboration.md)
and serialization of rapid planner filter refreshes.
Version 16.3.6 adds the planner bootstrap and bounded data batches described below.

## Planner data consolidation (16.3.6)

The normal initial planner data load now has two HTTP calls:

1. `verto.api.planner_data.get_bootstrap`: current user, visible apps, default
   company, four permitted planner settings, filter options and open project
   choices. Navbar, Apps, the header and shift dialogs share the result in memory.
2. `verto.api.planner_data.get_planner_data`: the selected company's employees
   and active roster, plus the project timeline in month view. The existing
   annual response already includes project/task summaries; opening project
   details still loads its existing combined details response on demand.

The filter header now watches selected values, not option arrays. Replacing
options does not reload employees, and shift-only filters do not reload employee
lists. Departments are filtered locally from permission-checked reference rows.
Closed shift dialogs share their options. The monthly project timeline mounts
only in month view after a company is selected.

| Tested scenario | Data HTTP requests |
| --- | ---: |
| Initial month or annual data load, including closed dialogs | 2 |
| Company change in month view | 1 batch |
| Refresh dropdown options without changing selections | 1 bootstrap; 0 roster/employee requests |
| Burst of 50 roster notices | 1 batch |
| Socket subscription/reconnect resync | 1 scoped bootstrap + 1 data batch |

The initial socket subscription still triggers a resync to close the gap between
loading data and joining the room. That can add two data calls shortly after
startup. Socket.IO handshake/polling, assets, searches, open detail dialogs and
writes are separate from the two-call initial data budget. This change does not
repair an unavailable Socket.IO server or force a WebSocket transport.

Live refresh starts independent reads together. The transport collects reads
for 10 ms, deduplicates equal pending reads and sends at most 20 logical reads
per batch. Only one data batch runs at a time per tab, within the existing
four-request read limit. Each consumer retains independent cancellation and
receives an independent result. Mutations invalidate pending lookup entries.
There is no persistent or cross-user data cache.

The server accepts only Employee/Project list reads and the three existing
roster/availability methods. It checks planner access and delegates list reads
to `frappe.client.get_list`, preserving field validation and permissions. It
rejects writes, arbitrary method lookup, unsupported document types, unbounded
list pagination and oversized batches. Existing roster handlers and their
response contracts remain unchanged. Permission/validation errors are returned
per dataset, so an inaccessible project list does not prevent employees loading.
Settings are restricted to four fields after document/field permission checks.

Bootstrap refreshes support sections: project notices reload project choices;
reference changes reload dropdowns; settings changes reload planner settings.
An Employee edit does not reload those reference lists. Bootstrap errors are
visible in the page with a retry action, rather than redirecting to login on
every server failure.

Combining HTTP calls does **not** turn distinct database queries into one query.
The reductions come from fewer request dispatches, repeated reads and hidden
component loads. The batch executes its reads sequentially, reducing concurrent
worker demand but making its response wait for its slowest dataset. Measure
transfer bytes, worker time, SQL counts and initial render time on dev before
merging to `version-16`.

Validation: 56 planner UI tests, including mounted Home month/annual startup,
company changes, denied datasets, scoped live refresh, cancellation, mutation
invalidation and batching; 57 Python tests with Frappe/database services mocked;
planner production build and HTML copy; unchanged 25 TypeScript diagnostics.
These checks are local, not a live Bench or dev-server performance measurement.

## Changes

| Path | Previous behavior | Refactored behavior |
| --- | --- | --- |
| Mobile concurrent reads | Independent requests, including duplicates | Identical pending supported reads share transport; up to four supported online reads run at once per tab |
| Planner concurrent reads | Independent requests with no application limit | Up to four supported reads at once; cancellable resources retain independent requests and abort behavior |
| Planner settings | Navbar, Apps and view preferences each invoke an automatic settings resource; cached automatic resources reload on reuse | One resource instance and one settings request per page session |
| Planner project timeline | Reloads all matching projects whenever the displayed month changes, despite no month parameter in the query | Month changes reposition existing projects; filter changes still reload |
| Annual planner | Watches the complete month object for an annual request | Watches the year and filters |
| Disabled planner links | Load search options even when disabled | Wait until enabled |
| Chat recovery polling | Checks every minute while visible and online, including with a connected socket | Five-minute recovery checks while connected; one-minute fallback while disconnected; immediate visibility/online recovery retained |
| Thread badges | Up to 12 thread-body downloads per hydration pass, including document-preview enrichment; zero counts can repeat every pass | One compact request for up to 50 unique thread IDs; uses Raven's cached count semantics and checks each thread's read permission |
| Chat document cards | May fetch previews already embedded in messages and secondary links not displayed | Fetches only missing primary previews; existing per-document pending cache remains |
| Offline startup/reconnect | Full dataset before sync, then another after a successful sync | Sync first, then one fresh dataset; repeated sync callers share the current operation |
| Offline periodic refresh | Refreshes the full dataset in hidden tabs | Periodic dataset refresh only while visible; manual refresh and queued-write sync remain available |
| Whiteboard | Any change event can upload the entire scene, including images; saves may overlap | Content fingerprint ignores selection, hover, pan and zoom; saves run one at a time and retain only the newest queued scene |

## Scope and behavior

The request coordinator uses an explicit endpoint allowlist. A GET request can
create records in this app (`get_or_create_*`), so neither GET nor a `get_` prefix
is treated as proof that a request is safe to combine. Mutations, uploads, form
submission and field-change handlers retain their existing execution paths.
Unknown methods run normally. The four-request limit covers supported API reads,
not sockets, asset downloads, every third-party call, or all users on a server.

Read results are shared only while pending, not cached for an online TTL. Each
caller receives independent data. Mutation boundaries invalidate pending lookup
entries so later refreshes do not join pre-mutation reads. Cache reads bypass the
queue while offline, preventing slow online requests from blocking cached forms.
Outside the new planner batches, Frappe resource requests with independent
cancellation signals are limited but not combined. Batched planner reads detach
an aborted consumer without cancelling other consumers or datasets.

Whiteboard content detection includes element IDs/versions/deletion state, file
IDs and canvas background. UI preferences and viewport state are included on the
next drawing save; changing only the view no longer triggers an upload. Failed
saves keep the pending scene for the next save attempt. Page exit uses the same
queue; as before, browsers can cancel outstanding requests on navigation. This
does not introduce guaranteed unload delivery or whiteboard offline storage.
A failed initial load now displays a load error instead of enabling a blank
canvas to overwrite existing work.

## Evidence and limits

These are deterministic request-path reductions, not production measurements:

| Scenario | Before | After |
| --- | ---: | ---: |
| 20 identical overlapping supported mobile reads (test fixture) | 20 | 1 |
| Visible connected idle chat recovery ticks per hour | 60 | 12 |
| 12 thread badges lacking counts | Up to 12 body requests, plus possible previews | 1 count request |
| Planner settings initialization | 3 resource fetch invocations | 1 |
| Successful queued-work startup/reconnect dataset downloads | 2 | 1 |
| Whiteboard selection/pan/zoom after a completed save | Full-scene upload after debounce | 0 |

Validation performed:

- Frontend Vitest suites, including request coordination, offline ordering,
  Raven metadata, whiteboard save ordering, and existing UI regression tests.
- Planner Vitest suites, including shared settings and cancellation/filter snapshots.
- Four Python endpoint tests covering guest rejection, inaccessible threads,
  zero counts, input bounds, duplicates, and Raven count semantics. Executed
  locally with framework/database services mocked; no live Bench was available.
- Mobile production build including service worker; planner Vite production
  build and HTML copy step (copy invoked through npm because this environment
  does not have the `yarn` command).
- Whiteboard esbuild syntax/import smoke build with existing React/Excalidraw
  dependencies externalized; not a full Frappe asset build.
- Mobile TypeScript diagnostics compared against the unchanged base: no new
  diagnostics, and two existing API error-handler diagnostics removed. The
  existing Frappe UI/socket/router type-check issues remain.

## Larger opportunities

1. **Incremental offline bootstrap.** `get_offline_bootstrap` rebuilds all allowed
   form schemas, a -62/+124 day calendar, 28 days of completed forms, editable
   timesheets and link choices. Separate schemas/reference data from frequently
   changing records, with user/permission-aware change tokens. This should be
   measured before deciding cache intervals or changing offline coverage.
2. **Planner project details.** `_get_project_execution_tasks` bulk-loads related
   data but checks write permission via a Task document per task. Profile this
   path with realistic task counts before changing permission evaluation.
3. **Chat stream metadata.** Counts and missing document previews could accompany
   native Raven message responses, reducing remaining metadata requests. That
   requires coordinating with the Raven repository while preserving rich
   message content and version compatibility.
4. **Whiteboard image payloads.** Every genuine scene save still contains image
   data. Storing files separately and saving scene references could substantially
   reduce large-board upload bytes; that needs a compatible storage migration.

## Development-server verification

Use the same account and dataset on the base and refactor branches. In browser
Network tools, filter to `/api/`, enable Preserve log, and compare request count,
transferred bytes and waterfall overlap for:

1. Planner startup, month navigation, year navigation, filter changes, assignment
   creation, swaps and project edits. Confirm post-save data refreshes.
2. Mobile startup, opening forms, saving a form, offline save, reconnect and
   refreshed offline data. Test browser and installed PWA on Android and iOS.
3. A chat with many threads/document cards, an empty thread, new replies,
   disconnection, reconnection, and return from background. Confirm private
   threads do not disclose counts and live messages still arrive immediately.
4. Whiteboard draw/edit/undo, selection and panning, image insertion, slow saves,
   reload and navigation away after saving.

Measure backend request durations and database query counts on the same flows.
Do not infer overall bandwidth or CPU savings from the isolated percentages.
