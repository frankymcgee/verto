# Daily Timesheet hour-limit alerts

After updating Verto and running the normal site migration, open **Verto Mobile
Settings → Global Notifications → Global Notification List**. On each intended
recipient's row, enable **Enabled** and **Daily Timesheet Hours Exceeded**, then
select **Email**, **Push**, or both. At least one delivery channel must be selected
for an enabled recipient. The notification option starts unchecked; existing
Email/Push selections are respected without changing them.

Email uses the recipient User's email address and the site's normal outgoing Email
Account. Push recipients need an active push subscription, and Verto push must be
configured. Email-only delivery does not require push configuration or a device.

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

Push delivery is queued after the save commits, and emails use the normal delayed
Email Queue within the save transaction. Both identify the person,
project, work date, shift, claimed hours, maximum and limit applied, with a link to
the Daily Timesheet in Desk. Normal document access permissions still apply.
The claim can still be saved for review. A failure to queue one channel does not
prevent attempts for the other channel or subsequent email recipients. Queueing
errors are recorded in Error Log with the channel and recipient and do not reject
a timesheet.

To check delivery, open **Email Queue** and filter **Reference Document Type** to
**Daily Timesheet** and **Reference DocName** to the timesheet ID. Open the entry to
inspect its recipient, status and any send error. Push delivery status remains
under the recipient's **Verto Push Subscription** record. This notification does
not currently create a separate Verto Global Notification Log entry.

Every successful save of an over-limit Daily Timesheet triggers the currently
selected notification channels, including re-saving unchanged hours and
comment/signature-only edits. This allows an existing entry to be saved again to
retrigger delivery after changing recipient/channel settings. A correction to the
limit or below is silent. Each day's timesheet is checked independently. A repeat
push uses the same notification tag; the service worker requests another alert
while replacing the older notification on supported devices.

This applies to Desk, mobile and offline-sync saves when they reach the server.
It checks each Daily Timesheet individually; it does not retrospectively scan old
records, aggregate separate timesheets or notify merely because a Project limit
or recipient setting changes. Existing purchase-order reminders are unchanged.

## Development-site verification

1. Set a test Project's DS maximum to 12 and NS maximum to 13. Enable the new
   option for a test recipient and select the desired delivery channels.
2. Save a 14-hour Daily Timesheet against the Project's DS allocation. Confirm
   the recipient receives the person/project/date and 14 claimed versus 12 allowed.
3. Re-save the existing over-limit timesheet (or edit its comments): another alert.
   Reduce it to 12: no alert. Increase to 14: another alert.
4. Repeat with an overnight NS timesheet and FI/FO allocation to verify their
   distinct project limits. Test the exact limit and an unconfigured limit.
5. Disable the recipient's notification checkbox and confirm no alert is sent.
6. Repeat with email only, push only, and both channels selected. Inspect Email
   Queue and the recipient's push subscription for delivery status. Re-save the
   existing over-limit timesheet after each settings change to trigger delivery.
