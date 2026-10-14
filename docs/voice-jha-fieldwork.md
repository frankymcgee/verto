# JHA field checks, printed revision access and shift reviews

Run the normal Verto migration, dependency installation and asset build after
updating to 16.3.58. This adds **JHA Control Verification** and **JHA Shift
Revalidation**, updates the Digital JHA Workpack print format, and adds the
authenticated `/verto-mobile/jha/:jhaName` route. Existing downloaded PDFs need
to be regenerated to include the QR code. QR images are embedded in the PDF;
generation does not send a URL or JHA content to an external QR service.

## Critical-control checks

Open a reviewed or signed JHA, then expand **Critical-control checks**. Each
critical hazard/control shows its owner and its revision-specific field-check
status. **Record field check** captures Verified or Failed, the logged-in
verifier, server timestamp, observations, an optional attached evidence file
and a supporting Critical Control Verification form.

A Verified result needs a readable CCV for the same Work Summary and project.
Its selected checklist must be answered, include an applicable Yes, contain no
No, have an advisor signature, and have a Good Controls closeout. A Failed
result can be recorded immediately without a CCV and requires action notes.
The verifier must explicitly confirm performing the on-site check. PERI has
no tool to create these records or mark a control verified.
Verbal reports are stored as Reported by Team, including requests from cached
older voice clients. A new revision resets the older hazard-level verification
flag as well as starting with no field-check records.

The CCV's answers and modified timestamp are retained as evidence. If it is
subsequently edited, cancelled, removed or moved to another job, the linked
Verified check displays Recheck Required. Record a fresh check after resolving
the issue; previous records remain in history. Evidence must be an accessible
File attached to that JHA or its selected CCV. Uploads from this panel are private.

Signed JHA content and signatures are untouched. Checks are separate immutable
records for one revision and do not carry into a replacement. They do not
release hold points, renew permits or authorise work. Failed/recheck results
remain visible even when the details panel is collapsed. The printed CCV log
includes historical checks and adds pages when needed; it directs crews to the
QR page for the current revision status.

The existing CCV roles and mobile-form settings still apply. A **Complete a
CCV for this job** link appears when that form is enabled for mobile and the
user can create it. It opens separately with Work Summary/project prefilled;
refresh the field checks after completing it. Linking a form does not grant
access to a CCV the user could not already read.

## Printed QR code

The cover QR identifies the exact printed JHA record and revision. Scanning
requires login and the same Work Summary assignment/document permission as
opening the JHA normally. It displays the scanned copy's status and the latest
linked revision, including a replacement still being developed. Superseded,
changed and mismatched copies receive a warning. **Open Current JHA** opens
that exact latest record, rather than an unrelated or older draft.

Status checks use live requests with no offline fallback or stored API status.
Refresh occurs when the page returns to view. If a check cannot complete,
the previous result is removed and the screen says status could not be
confirmed. A current Signed revision still does not constitute site work
authorisation or proof that every control has been verified.

## Start-of-shift review

From the current signed JHA, expand **Start-of-shift review**, choose the shift
start date and Day/Night, then select **Review Shift with PERI**. Dates today
and yesterday are accepted to accommodate night shifts crossing midnight.
There is one persisted review per JHA/date/shift; repeated taps resume it.
Microphone/transcription consent is required before connecting. Engine and
voice selection continue to come from Verto Mobile Settings.

PERI asks about changes to crew/roles, equipment/isolations, environment/nearby
work, scope/method and hazards/controls/hold points. It records explicit crew
answers, immediately asks the next missing question and resumes from the saved
check after reconnecting. The signed JHA stays Signed and retains its content
and signatures throughout this discussion.

If nothing changed, the review becomes Awaiting Confirmation. A person reads
the recorded checks and selects **Confirm No Changes**. PERI cannot perform
that final confirmation. Failed or stale critical-control checks must be
resolved first. The result records who confirmed and when; it records this
shift's unchanged-condition discussion without renewing work authorisations.

If a change is identified, the unchanged checklist stops and the existing JHA
immediately becomes Review Required - Work Changed. Its prior content and
signatures remain as history, and its mobile print action is blocked. Select **Review
Changes with PERI** to finish the existing call, open/resume a separate change
revision, and reconnect using the configured engine. The identified change
description is carried into the new interview; the crew still confirms its
placement and scope. Fresh review and sign-on are required under the existing
change-management workflow.

Voice controls and transcripts remain available until **Disconnect Voice**.
The current dynamic dock clearance and compact expandable panels are retained.

## Validation

CI includes API unit tests and a real Frappe document-lifecycle test for field
record protections, plus frontend coverage for both voice engines, shift
context/consent, field checks, revision status, stale responses and live-read
cache behavior. A development-site crew discussion and scan of a freshly
generated workpack remain part of field rollout validation.
