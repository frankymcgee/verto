# Daily Timesheet hour-limit alerts

After updating Verto and running the normal site migration, open **Verto Mobile
Settings → Global Notifications → Global Notification List**. On each intended
recipient's row, enable **Enabled**, **Push**, and **Daily Timesheet Hours Exceeded**.
The new option starts unchecked for existing and new recipients. This alert uses
push only; the Email checkbox continues to control existing email notifications.
Recipients need an active push subscription, and Verto push must be configured.

Set the existing numeric limits on each Project (values are hours):

| Daily Timesheet shift | Project limit |
| --- | --- |
| FI / FO, including prefixed codes such as FG-FI | Max Fly Hrs |
| DS, including prefixed codes such as FG-DS | Max DS Hrs |
| NS, including prefixed codes such as RH-NS | Max NS Hrs |

Fly-in, Fly-out, Day Shift and Night Shift labels are also recognised. An unknown
shift or blank/zero/negative limit does not trigger an alert. No default allowance
is assumed and another shift's limit is never substituted.

The server checks a saved Daily Timesheet using its calculated duration, including
overnight shifts, and the linked Shift Assignment's project and shift. For records
without those allocation values, it uses the Daily Timesheet's Project ID and
Shift. Claiming exactly the maximum is allowed; only a greater duration triggers.

Push delivery is queued after the save commits. It identifies the person,
project, work date, shift, claimed hours, maximum and limit applied, with a link to
the Daily Timesheet in Desk. Normal document access permissions still apply.
The claim can still be saved for review. Notification failures are recorded in
Error Log and do not reject a timesheet.

New claims and changes to claim hours, project, shift/allocation, date or person
are checked. Comment/signature-only edits and repeated saves of an unchanged
claim do not alert again. A correction to the limit or below is silent; increasing
it above the limit again triggers a new alert. Each day's timesheet is checked
independently. Editing one timesheet replaces its earlier notification on devices
that support notification tags.

This applies to Desk, mobile and offline-sync saves when they reach the server.
It checks each Daily Timesheet individually; it does not retrospectively scan old
records, aggregate separate timesheets or notify merely because a Project limit
or recipient setting changes. Existing purchase-order reminders are unchanged.

## Development-site verification

1. Set a test Project's DS maximum to 12 and NS maximum to 13. Enable the new
   option for a test recipient whose device has push notifications enabled.
2. Save a 14-hour Daily Timesheet against the Project's DS allocation. Confirm
   the recipient receives the person/project/date and 14 claimed versus 12 allowed.
3. Save a comment edit: no repeat. Reduce it to 12: no alert. Increase to 14: alert.
4. Repeat with an overnight NS timesheet and FI/FO allocation to verify their
   distinct project limits. Test the exact limit and an unconfigured limit.
5. Disable the recipient's notification checkbox and confirm no alert is sent.
