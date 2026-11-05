# Mobile performance (16.3.7)

Branch: `performance/reduce-api-requests`, following planner consolidation in
16.3.6. Develop and test on dev before merging to `version-16` or updating Pilot.

## Findings and changes

The mobile app already has combined Home, calendar, edit-document and chat
endpoints. Earlier changes on this branch deduplicate concurrent supported reads,
batch chat thread counts, reduce connected chat recovery polling and download
offline data once after queued work syncs. This pass targets remaining repeated
startup reads and offline preparation work.

| Path | Before | After |
| --- | --- | --- |
| Startup configuration on a push-capable device | Boot, navigation, push configuration and two PWA metadata calls: 5 | One shared boot response with those sections |
| Push setup | Counts all enabled subscriptions although startup does not use the count | Boot includes only configured status and public VAPID key; the existing full push-config endpoint retains its count |
| PWA icons | Date-based favicon cache busting and repeated icon-node replacement | Stable URLs and preservation of unchanged PWA icon/manifest nodes |
| Offline timesheet form definitions | Build and transmit a full schema inside each timesheet | Build once per form type per request; compact version 2 sends schema references |
| Offline timesheet attachments | One metadata query per readable timesheet | One metadata query covering the timesheets that passed their individual read checks |
| Offline document existence | Existence query followed by document load | Load the document and handle a missing document explicitly |
| Offline cache writes | Per-dataset records plus two full aggregate copies | Per-dataset records and a small user marker for the service worker |
| Rapid calendar navigation during a pending read | A request for every intermediate month; older responses can overwrite the latest month | One active read and at most one latest pending month; obsolete responses are not displayed |

Home data and offline preparation remain separate requests so the shell does
not have to wait for large datasets. Assets, Socket.IO, chat content and push
subscription registration are outside the configuration request count. Existing
subscriptions still register for the authenticated session, preserving shared
device ownership handling. Explicit push configuration refresh/enable actions
still fetch current configuration.

## Offline and compatibility behavior

`get_offline_bootstrap` defaults to the original version 1 response for existing
clients. The updated PWA requests `contract_version=2`, where `edit_schemas`
contains definitions and `edit_docs` contains references. The client restores
the existing editor response before storing it in IndexedDB. Cached values,
attachments, write permissions and the calendar/form coverage ranges are
preserved. Missing definitions reject the download before cache or actor updates.

The service worker reads the same `offline-bootstrap:latest` key to identify the
user; that record now contains only the user and generation time. Queued writes,
attachments awaiting upload and idempotency receipts retain their existing paths.
Changing accounts still clears the previous user's read cache before storing
the next dataset. This does not add an online TTL cache or cross-user response
cache.

Bootstrap sections are optional so newer clients can use the existing endpoints
if an older/cached boot response lacks them. The offline cache writer accepts
both inline schemas and version 2 schema references. Optional boot-section errors
are logged without preventing the basic shell from loading; navigation still
fails closed when its check cannot complete. Only public push configuration is
included in the browser response.

## Evidence

Local tests use mocked network and Frappe/database services:

- 47 mobile UI tests pass, including startup configuration, existing subscription
  registration, employee navigation visibility, older-response fallback, compact
  offline cache reconstruction, account changes and rapid month navigation.
- Nine new Python tests pass for bootstrap access/public fields, unchanged push
  counts, schema reuse, attachment batching, denied/deleted documents and payload
  compatibility. Document-level and File read checks are retained.
- Mobile production build and service worker generation pass. TypeScript
  diagnostics match the pre-change baseline; existing diagnostics remain.

In a synthetic fixture of 30 timesheets with a 50-field schema:

| Measurement | Before | After |
| --- | ---: | ---: |
| JSON bytes | 200,770 | 23,141 |
| Gzip bytes | 2,836 | 1,576 |
| Schema builds | 31 | 1 |
| Attachment queries | 30 | 1 |

The payload is approximately 88% smaller before compression and 44% smaller
with gzip in this fixture. Real timesheet values, signatures, files and form
definitions will change the result. These figures are not deployed-site
bandwidth or CPU measurements.

## Dev verification

Pull this branch, rebuild Verto assets and restart the dev workers. On iOS and
Android, test the installed PWA and browser with the same user and data:

1. Check Network for one boot/configuration request. Home and offline preparation
   should load normally; existing push subscriptions should still register.
2. Check app title, icons, manifest and employee-dependent navigation. Test an
   account without an Employee profile as well.
3. Refresh offline data, then disable connectivity. Open cached shifts and edit
   a cached timesheet, including its attachments. Queue a submission, reconnect
   and confirm it syncs once.
4. Switch accounts and verify cached data belongs to the current user. Check that
   users without document/File permissions do not gain cached access.
5. Throttle the connection and tap through several calendar months quickly. The
   final month should load correctly with only one trailing request.
6. Compare transferred bytes, server request time and SQL counts against 16.3.6.

Further candidates need profiling or broader API changes: completed-form server
pagination (the UI currently pages a downloaded list), combining new-form schema
and prefill calls, and incremental offline refreshes that safely invalidate
schemas and link choices after permission/settings changes.
