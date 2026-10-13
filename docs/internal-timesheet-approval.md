# Consolidated internal Timesheet approval

Open **Timesheet → Internal Review**, or select records in the list and choose
**Actions → Review & Approve Selected**. The dedicated Desk page is
`/app/internal-timesheet-approval`. Existing Timesheet list actions are retained.

The page defaults to the last completed Monday–Sunday week. Leave Project blank
to see everyone across projects, choose a project to narrow the view, or include
previously approved records. Each project/week has the familiar daily DS/NS grid,
weekly totals and expandable employee details with start/end times, allocated
shift, recorded shift, current daily comments and weekly comments. Links open the
original Timesheet, Daily Timesheet and Shift Assignment for correction.

## Validation

Checks flag:

- Allocated DS/NS versus both the recorded shift label and actual entered start
  time. Actual DS/NS preserves the existing **16:30 start-time cutoff**; night
  hours remain on the shift's start date when finishing the next morning.
- Claimed hours versus elapsed start/end time, saved daily duration and the
  weekly total; absent, negative or invalid hours/timestamps.
- Project **Max DS Hrs**, **Max NS Hrs** and **Max Fly Hrs**. Split entries for the
  same person, project, date and shift are summed before applying the limit.
- Overlapping periods and duplicated daily sources across reviewed Timesheets.
- Missing, cancelled, unavailable, wrong-employee/project/date and ambiguous
  shift allocations; work dates outside the Timesheet's week.
- Daily start/end times or comments that have changed without reaching the
  weekly Timesheet yet.
- Past allocated days with no positive hours. These become due one hour after
  the configured shift end, use overnight shift timing, and respect the existing
  dated User/Project Timesheet Reminder Exclusions. Approved full-day leave,
  future/not-yet-due days and unavailable shifts do not count as missing hours.

Limits of blank/zero/negative values remain unconfigured. Duration comparisons
allow one minute for rounding; project maximums do not receive that grace.
Unclassifiable labels/allocations require review rather than being silently
treated as correct. Missing-hours checks require usable Shift Type times.

The page checks existing weekly Timesheets; employees with no weekly document
at all continue to receive the separate missing-daily-hours reminders.

## Signing and corrections

Clean pending records start selected. Select/deselect employees individually,
select all pending records, or clear the selection. Already approved records and
records without write permission cannot be selected.

Enter the signatory name and choose **Draw signature** or **Type signature**. One
signature applies to the selected records. Flagged selections require an explicit
confirmation and a review note, allowing a supervisor to approve a justified
exception without hiding the flags. Alternatively exclude the flagged records,
correct the source records and reload the review.

The server locks the reviewed records, checks permissions and recalculates the
review against its exact original group before signing. Changed hours, comments,
allocations, limits or source records require a fresh review. A failed write rolls
back the entire batch and its audit record.

Internal approval sets the existing `internal_approved`, `employee_approved`,
`employee_approval_name` and `approved_signature` fields. The approver User comes
from the authenticated session. Draft/submitted status and client signatures are
preserved. Previously approved internal signatures are preserved on repeat
requests. Editing reviewed hours, comments, shift, employee, project, role or week
later clears the current internal approval and returns the document to review;
the original approval audit remains available.

System Managers can inspect **Verto Internal Timesheet Approval** for each batch's
approver, server approval time, signature method/image, selected records, reviewed
hours/flags and exception note. The audit has no user write permissions.

## Access and update

The page/API require **System Manager**, **Accounts Manager**, **HR Manager**,
**Projects Manager** or **Verto Planner Manager**. Normal Timesheet read/write
permissions and User Permissions continue to apply; having a manager role alone
does not grant access to otherwise restricted Timesheets.

The existing per-record `approve_timesheet_with_signature` action remains for
clean records. It uses the same checks, records an audit and uses the session's
approver identity. Flagged records direct the user to the consolidated page.
Neither API explicitly commits midway through approval or sends client email.

Update Verto normally with migration and a rebuild, then reload Desk. Migration
creates the standard Desk Page and audit DocType, and setup attaches the Verto
manager role after its creation on fresh installations. No Web Page or existing
Timesheet Client Script replacement is required.

The new feature is version **16.3.51**. CI covers validation, access, typed/drawn
signing, stale data, rollback, source privacy, changed-content invalidation, real
database signature/audit writes, UI rendering and preservation of list actions.
