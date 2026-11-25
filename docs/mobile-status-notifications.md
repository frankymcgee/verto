# Mobile sync notifications

Offline preparation, connection changes and upload status use the Frappe UI toast
provider already mounted at the app root. Status notifications float over the
page instead of reserving space above it.

- One notification updates in place as the state changes.
- Progress stays available while work is running and can be dismissed.
- Successful refreshes and confirmed uploads close after about four seconds.
- Connection changes and waiting work use brief informational/warning messages.
- Errors stay until dismissed, resolved or replaced by a new state. Upload failures
  offer **View uploads**; offline-data refresh failures offer **Retry**.
- Opening a form removes navigation/refresh actions from the toast. The app does
  not navigate away from an open form through a status action.
- Upload queue shows its own detailed status; duplicate floating sync messages
  are suppressed on that page so retry controls stay reachable.

The profile/avatar status and Upload queue remain the durable view of connection
and queued work. Closing a notification does not remove a saved item or clear an
error from the queue. Normal five-second queue polls do not repeat the same toast.
Empty sync checks produce no progress or success message, and failed/skipped
attempts do not claim a successful upload.

Toasts sit above mobile navigation and away from PERI's composer and the JHA
microphone dock. Desktop notifications retain Frappe's bottom-right placement.
The layout accommodates small phones and safe-area insets.

## Implementation and validation

`frontend/src/components/OfflineSyncStatus.vue` publishes notices through the
existing Frappe UI provider. `frontend/src/pwa/useOfflineSync.ts` exposes the last
sync receipt counts and keeps the busy flag set until refreshed queue counts are
available. This changes presentation and completion timing, not queue operations,
server receipts or upload retry rules.

Transient notices have an app-owned close timer because an updated toast may
retain its prior infinite lifetime. Timer cleanup, owner IDs and account changes
are isolated to the sync notification; other app notifications are unaffected.

Tests: `frontend/tests/sync-status-toast.test.js`, the sync lifecycle checks in
`frontend/tests/offline-request-efficiency.test.js`, and the production-build
`frontend/tests/sync-status.e2e.py` suite in Chromium and WebKit. Browser checks
cover one updating toast, persistent errors, Retry, success dismissal, unchanged
page geometry and reachable mobile controls at 320px, 440px and desktop widths.
