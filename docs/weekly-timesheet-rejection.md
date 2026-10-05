# Weekly Timesheet client rejection

The grouped approval page now offers **Reject Week** alongside **Approve and
Sign Timesheets**. The client must enter a full name and a reason. Rejection
records the decision on a **Weekly Timesheet Approval Request** and queues the
reason for email to the **Reply-To address on that approval request**.

Rejection never cancels, changes hours, clears signatures, or changes the
submission status of a Timesheet. Staff can cancel and amend the affected
Timesheets using the usual ERPNext process, then resend the project/week with
the existing Timesheet list action or `verto.api.timesheet_resend.send_grouped_weekly_timesheets`.

## Installation

Run the normal app update and site migration. The migration creates the request
DocType and installs/updates the existing **Web Page** at
`weekly-timesheet-approval` from the versioned HTML and JavaScript in Verto.
The existing DS/NS grid, signature modes and signed PDF ZIP download are retained.
The individual `sign-timesheet` page is not replaced.

Set **Verto Mobile Settings → Reply-To Email** to one valid email address before
sending new grouped approval emails. This address is captured on each request;
later settings changes do not redirect a rejection or change reminder Reply-To
headers. New requests require this setting so rejection notifications always
have a known destination. A failure to queue the approval email rolls back submission and
request replacement, preserving the previous approval link.

## Requests, replacements and reminders

- Every approval send/resend creates a request containing the exact Timesheet
  IDs, the requested hours snapshot, week, recipients and original Reply-To.
- Resending the same project/week supersedes the earlier request. It retains
  its rejection reason, client name, timestamp and notification reference.
  Older links cannot sign or reject outdated figures.
- Rejected/replaced pages retain the original snapshot, including after source
  Timesheets are cancelled and amended. Clients are directed to the newest email.
- Reminders reuse the current pending request and skip rejected/approved weeks.
  They do not silently reopen a rejection.
- Existing version-1 links can still sign until a replacement request is sent.
  They lack an original Reply-To snapshot, so online rejection is available only
  from a newly sent approval email. Resend a week to enable the new button.
- A request's hours must still match the submitted source documents when the
  client signs/rejects. Changed or cancelled sources require a new approval email.

## Notification delivery and history

Search for **Weekly Timesheet Approval Request** in Desk. System Managers,
Projects Managers, HR Managers and Accounts Managers can inspect/export request
history. The request is separate from ERPNext's Timesheet status and cannot be
edited through normal form actions.

Approval emails and reminders use the normal Email Queue and its scheduler.
The latest approval email is linked on the request for delivery troubleshooting.

**Rejection Email Queueing = Queued** means an email was added to Frappe's Email
Queue; use the linked **Rejection Email** record for actual SMTP delivery status.
The normal scheduler/Email Queue handles sending and delivery retries.

If queue creation fails, the rejection is still saved, the page explains the
email problem, and the request shows **Failed**. A System Manager can use
**Retry Rejection Email** on the request. Repeated client submissions and queue
retries cannot add a second notification after one has already been queued.
An SMTP delivery failure on an existing queued email should be retried through
Email Queue rather than creating a new rejection notification.

The endpoints validate signed request tokens and require POST for decisions.
Project/request/Timesheet row locks serialize signing, rejection and resending;
existing signatures remain untouched.

## Validation

```sh
bench --site <site> run-tests --app verto --module verto.api.test_timesheet_approval --skip-before-tests
cd apps/verto/frontend
yarn test:ui tests/weekly-timesheet-approval.test.js
```

GitHub CI includes both checks, plus fresh installation/migration of the new
DocType and the existing asset builds.
