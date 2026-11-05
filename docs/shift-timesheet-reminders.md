# Missing daily hours after an assigned shift

Verto checks for missing daily hours every five minutes. A reminder becomes due
one hour after the configured **Shift Type → End Time**, using the site's
timezone. It is sent on the next scheduler tick. End times earlier than start
times finish the following calendar day; the timesheet retains the shift's start
date. For example, a night shift on 12 October from 18:00 to 06:00 is due at
07:00 on 13 October, for hours dated 12 October.

The assigned Employee's enabled User receives the push. Submitted, active Shift
Assignments are checked, including ongoing allocations without an end date.
Unavailable shifts, approved full-day leave, and the existing dated User/Project
Timesheet Reminder Exclusions are skipped. Shift Types without usable start/end
times are skipped and listed by the administrator's preview.

Daily Timesheet is not submittable. A **saved, positive duration**, with the
correct employee and shift allocation, satisfies the reminder; cancelling a
weekly Timesheet is unnecessary. Legacy daily entries without an allocation
link match by employee, project and shift where available. A different project's
hours or a different linked allocation do not satisfy it. Hours entered by the
office for the employee are accepted.

## Persistent app alert and following-day push

The app shows an outstanding-hours banner across all pages. Review opens the
existing full-width bottom drawer, and each entry opens the work date in Shifts,
including previous months. Closing the drawer leaves the banner visible. The
banner clears after a successful daily save, or after offline hours reach the
server. The app refreshes on return, navigation, sync and once per visible minute.

At 09:00 on the calendar day after the one-hour reminder is due, Verto sends one
follow-up if hours are still outstanding. A night shift due at 07:00 on 13 October
gets its follow-up at 09:00 on 14 October. This replaces the previous yesterday-only
09:00 push while the new feature is enabled, avoiding two reminders on the same
morning. The banner continues beyond that day until the hours are saved.

Pushes share one occurrence tag. They require an enabled device subscription and
the existing web-push configuration. Persisting an alert in the app does not
require push permission. Device notification retention is controlled by the OS;
the server-backed app banner provides the persistent reminder.

## Settings, update and verification

After updating, run the normal Verto asset build and site migration, then restart
workers/scheduler and reload the mobile app. Migration creates **Verto Timesheet
Reminder**, adds the five-minute scheduled job, and adds **Verto Mobile Settings →
Push Notifications → Remind After Shift**, enabled by default. The existing
09:00 scheduler entry is reused. Turning this checkbox off hides the new banner
and restores the legacy 09:00 previous-day reminder.

System Managers can inspect **Verto Timesheet Reminder** for work date, due time,
status, first and following-day push delivery times, and the last delivery error.
Delivery timestamps are recorded only after at least one device receives a
successful Web Push response. Queued workers recheck saved hours and shift
eligibility before delivery, and use row locks to suppress duplicate deliveries.

A read-only System Console preview:

```python
frappe.call("verto.api.mobile.timesheet_reminders.preview_shift_missing_hours_reminders")
```

The first scan starts with yesterday and today so rollout does not send a flood
of historic reminders. Subsequent scans keep a durable cursor and catch up after
scheduler downtime. Previously discovered outstanding reminders have no age
cutoff. Existing explicit `target_date`/`dry_run` calls to
`send_previous_day_missing_hours_reminders` retain the historical preview.

CI covers day/night timing, midnight, missing hours, recipient identity, leave,
ongoing allocations, scheduler catch-up, persistence, retries, duplicate jobs,
saved-while-queued races, per-user API access, migration and a real daily save,
plus drawer behavior and links into older calendar months.
