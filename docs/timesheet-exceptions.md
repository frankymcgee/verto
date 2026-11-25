# Timesheet exceptions and daily hours confirmation

## Open the queue

In Verto Mobile, open the profile menu and select **Timesheet exceptions**.
The same queue is linked from the Desk Timesheet list and Internal Timesheet
Approval page. Its route is `/verto-mobile/timesheet-exceptions`.

Access requires Timesheet read permission and Administrator or one of: System
Manager, Accounts Manager, HR Manager, Projects Manager, Verto Planner Manager.
The backend enforces access independently of the menu.

The default is the last completed Monday–Sunday week. Choose another Monday and
an optional project, then check/refresh the queue. Search employee names, IDs or
source records; narrow by exception type or high priority. Results are paged in
groups of 25. The checked week and server timestamp remain visible.

## Checks

| Category | Conditions |
| --- | --- |
| Missing hours | An active submitted allocation is due and has no accessible valid weekly or daily hours, even if no weekly Timesheet exists |
| Weekly processing | An unlinked daily submission, or daily hours/comments/times that differ from the weekly log |
| Hours and totals | Invalid times/durations, weekly total mismatch, project hour limits, overlaps/duplicate source logs and source identity/date mismatches |
| Shift allocation | Recorded vs allocated shift, invalid/missing/ambiguous allocation, unavailable shift, unknown labels and fly-day mismatches |
| Attendance and leave | Positive hours conflict with submitted Absent/On Leave attendance or approved full-day leave |

A shift becomes due one hour after its configured end, including an overnight
end on the next date. Full-day leave, On Leave attendance and dated reminder
exclusions suppress missing-hour warnings. A half day still requires checking
worked hours. SD uses entered start time for the existing DS/NS split and limits.

Daily entries are counted once when linked to a weekly log. An unlinked daily
record appears under weekly processing instead of asking for a duplicate entry;
a wait of at least 10 minutes is high priority. This is a reconciliation signal,
not a claim that the background worker has definitely failed.

The queue reuses the internal review's validation rules. Readable neighboring
weeks and other projects for the same employees participate in overlap checks.
Source records are read through normal list/document permissions. Check coverage
explains unavailable checks; missing-hour inference is disabled if a required
source cannot be read. Restricted individual records can still need administrator
verification. Oversized reads fail with an instruction to narrow the project,
instead of silently truncating records and reporting false missing hours.

## Resolve an exception

Open the linked weekly/daily timesheet, allocation, attendance or leave application
and correct it using your normal permissions. Refresh the queue to check the new
state. **Review for approval** opens the existing internal review with the exact
weekly record selected; the general link opens the selected week/project.

The queue does not alter hours, attendance, leave or approvals. Already internally
approved records are included if the current checks find an exception and are
labelled accordingly. Client signing/rejection and internal approval audits keep
their existing behavior. Responses use `no-store`; offline cached data is not used
as a current exception report.

## Daily hours popup

New and edited Daily Timesheet forms show a Frappe UI **Dialog** before saving:
total hours, work date, start/end, shift and project when available. **Review hours**,
close, Escape or dismissal cancels saving and keeps the entered form. The positive
action explicitly says **Submit/Save N.NN hours**.

The dialog confirms a snapshot of the submitted values. Repeated taps cannot
start another save, and late form-dependency responses cannot change the payload
being confirmed. The same dialog runs before an offline submission is queued and
when Save Row persists an existing Daily Timesheet's parent edits.

## Implementation and checks

- API: `verto.api.timesheet_exceptions.get_timesheet_exceptions` (`week_start`,
  optional `project`); shared role capability in `verto/api/timesheet_access.py`.
- UI: `frontend/src/pages/TimesheetExceptions.vue` and
  `frontend/src/components/TimesheetHoursConfirmation.vue`.
- Reconciliation: `tests/test_timesheet_exceptions.py`; database/permission checks:
  `verto/api/test_timesheet_exceptions.py`.
- UI: queue, child-row save, profile-menu and internal-review regression suites;
  phone/desktop popup and queue checks in `frontend/tests/timesheets.e2e.py`.
