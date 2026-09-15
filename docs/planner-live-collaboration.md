# Live planner collaboration

Branch: `performance/reduce-api-requests`. Version: 16.3.5.
Rebased onto `version-16` at `f1124a7` (16.3.3), preserving the separate
Mobile default-app option and root redirect fix.

The monthly and annual planner now receive saved changes through the existing
Frappe Socket.IO service. An authenticated viewer joins one planner room for
their site. The toolbar shows connection/refresh status and offers manual refresh.
This synchronizes saved records; it does not broadcast unfinished typing or cursors.

## Change coverage

| Saved changes | Refreshed data |
| --- | --- |
| Shifts, shift schedules/types/locations, leave, holidays, events, daily timesheets | Roster and active availability filter |
| Projects, tasks, task assignments, customers | Project timeline, annual project rows, open project details |
| Employees, departments, designations, branches, companies | Employee filters and dependent roster/project data |
| Verto Mobile Settings | Shared settings and roster |

Document hooks cover ordinary saves, inserts, submissions, cancellations,
deletions, renames, and `Document.db_set`, including writes from Desk, mobile,
imports and background jobs. Existing push and Project automation hooks remain.
Known planner paths using direct database updates publish explicitly. Integrations
that use arbitrary SQL or `frappe.db.set_value` must call
`verto.api.planner_realtime.publish_scope` with the affected scope or use normal
document operations to trigger immediate updates.

## Request and conflict behavior

- Notifications contain only a scope, never document contents or record IDs.
  The socket handler checks planner app access or existing Employee read access;
  clients fetch data through their authenticated APIs. Project details now also
  explicitly check Project read permission.
- Notifications publish after a successful transaction. Frappe deduplicates equal
  event/payload/room combinations within that transaction and drops rolled-back
  notifications. A transaction updating 100 shifts therefore emits one roster
  notice, despite multiple document hooks.
- Each viewer batches notices for 350–600 ms, with jitter spreading requests
  between clients. Only one refresh batch runs at a time. Notices received during
  a refresh are retained for a following batch. Sustained imports cannot postpone
  updates indefinitely by continually resetting the timer.
- Hidden/offline tabs retain invalidations without data refreshes. Dragging or
  saving pauses refreshes until the interaction completes. Returning to the tab,
  coming online, and acknowledged socket reconnection reload current data.
- Employee, availability, roster and timeline resources serialize filter/live
  refreshes and retain only the latest trailing request. Frappe list resources
  use the promise returned by `reload`, since their `fetch` discards it. The
  earlier four-request limit still applies to supported planner reads.
- Successful socket subscription triggers a refresh to close the startup and
  reconnection gap. Quiet recovery runs every five minutes while subscribed,
  or every minute when live service is unavailable, only in visible online tabs.
  Failed refresh batches retry after ten seconds.
- An open project editor updates clean fields live. Unsaved project edits remain
  intact; a changed server revision displays a reload notice and disables saving
  until the user explicitly discards their edits and loads current details.
  Project updates and annual date drags send the revision they were based on;
  the server locks the Project row and rejects stale revisions. Existing API
  callers without that optional revision retain their previous behavior.

Scope notifications intentionally refresh the existing API responses, including
the combined annual roster response. They are not a record-delta protocol. Actual
bandwidth and server CPU reductions still require measurement on a realistic
dataset; collaboration adds refreshes when other users make changes.

## Deployment

1. Deploy this branch to the development Bench and install its frontend
   dependencies using the repository's normal build process.
2. Build the planner assets and copy the generated HTML entry to
   `verto/www/planner.html`. Run the normal Bench migration/cache-clear steps to
   load the updated hooks and Python controller.
3. Restart the Frappe Socket.IO service as well as the usual web/workers. Frappe
   loads `realtime/handlers.js` from installed apps and caches it in that process;
   an asset build or browser reload alone cannot load the new handler.
4. Confirm the reverse proxy serves `/socket.io` with WebSocket upgrade support.
   The planner's rendered site-name meta tag supplies the Frappe namespace even
   when the internal site name differs from the public hostname. Vite development
   requests proxy `/socket.io` to the configured socket port (default 9000).

Relevant upstream implementation:
[Frappe Socket.IO app handlers](https://github.com/frappe/frappe/blob/version-16/realtime/index.js)
and [transaction-aware realtime publishing](https://github.com/frappe/frappe/blob/version-16/frappe/realtime.py).

## Validation and development acceptance

Automated coverage includes two simulated viewers, event bursts and mid-refresh
changes, hidden-tab recovery, reconnection acknowledgments, subscription denial,
late subscription cancellation, real Frappe UI list request ordering, project
draft preservation, revision conflicts, notification scopes and existing hook
preservation. Python tests use mocked framework/database services; this workspace
does not contain a running ERPNext Bench.

Local results: 44 planner UI tests, four socket-handler tests and 48 Python
planner/publisher regression tests passed. The planner production build and HTML
copy succeeded. TypeScript reports the same 25 diagnostics as the unchanged
16.3.1 base, with no new diagnostics; the pre-existing type issues remain.

Before promoting the branch, use two separate accounts/browser sessions on the
development server. Verify both monthly and annual views while creating, moving,
deleting and cancelling shifts, approving leave, editing projects/tasks and
entering mobile timesheets. Confirm other viewers update without reloading.
Edit the same project in both sessions and confirm stale saves are rejected.
Disconnect/reconnect one session, change its filters quickly and leave it hidden
during a bulk change; confirm it recovers the current data. Verify restricted
accounts cannot subscribe and record permissions remain enforced by the APIs.
Compare Network request counts/bytes and backend query timings with the base.
