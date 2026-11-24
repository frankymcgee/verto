# Handover drafts, upload progress and photo annotation

## PERI handover drafts

Open **Safety Handover** or **Lead Safety Handover**, then add or edit an unsigned
**Handover Information** row. **Draft with PERI** appears above the row fields.

1. Set the row's Date & Time. The suggested record period ends at that time and
   starts 12 hours earlier. Adjust **Records from / Records to** for the actual
   shift; both are interpreted in the site's timezone and can cross midnight.
2. Select **Prepare handover draft**. This is an online operation using the PERI
   Raven Bot already selected in Verto Mobile Settings (`peri_bot_name`, with
   `ai_photo_analysis_bot` as the existing fallback) and Raven's OpenAI credentials.
   No additional Flow tool registration is required.
3. Review the suggested sections, source links and source-coverage notes. Source
   records use the requesting user's Frappe permissions. Date-only incidents can
   include other shifts; forms without event timestamps use submission time.
4. Select **Use draft in row**. Existing narrative text is kept by default. The
   replacement checkbox explicitly permits replacing text in suggested fields.
   Review incident counts, the shift safety summary, names and sign-off yourself,
   then use the normal **Save Row** action.

The draft request does not create or save handovers, sign rows, change actions or
run the bot's other tools. It uses bounded samples of supported project safety
forms, incident records, digital JHAs and investigations. Current investigation
actions are labelled with their recorded status; previous handover actions are
unverified carry-over. A sample or an empty result is not evidence of zero
incidents or a safe shift. Section/area is context, not a query filter.

Each specific finding includes a source ID. On applying the draft to a rich-text
field, recognised source IDs become links to the original records. Dates and
source links remain available for checking. Signed rows do not offer this helper;
start a new unsigned handover row for the next shift.

## Upload queue

Use **Upload queue** from the profile menu. Pending items show:

- the device save and server document acknowledgement separately;
- accepted attachment counts and the active filename during transfer;
- connection, retry or validation information and individual retry controls;
- final confirmation after the document, attachments and photo-review request
  have been accepted. This does not mean the asynchronous PERI review has finished.

Progress counts completed server requests, not estimated byte percentages. Retries
reuse operation/attachment receipts and resume after accepted attachments. Recent
confirmations are shown for the current account on this device (up to 20 from the
last 24 hours); uploaded blobs are released. These records do not increase pending
counts or get replayed by automatic sync. Existing pending records remain usable.
Photo bytes are persisted before opening the IndexedDB transaction, avoiding
WebKit's native Blob/File storage failure. Existing Blob-based queue entries are
still readable and retain their original operation and attachment identifiers.

## Photo annotation

New and edited mobile forms share an attachment picker. Additional selections
append to the current list. For a supported photo, select **Annotate**, choose
**Arrow**, **Circle** or **Note**, then drag or tap the photo. Notes are entered in
the note field before placing them. Colour, Undo and Clear marks are available.

**Add annotated copy** adds a separately named JPEG alongside the unchanged
original. The copy contains an identifying footer and is bounded to 2560 pixels
on the longest image edge. Both files use the normal durable form upload queue,
including when the form is saved offline. Drawing/export require no network once
the editor has loaded (the installed PWA precaches its editor assets). Cancelling
keeps the attachment selection unchanged. Images the browser cannot decode, such
as unsupported HEIC variants, can still be attached as originals.

The investigation evidence register has **Annotate photo** beside its attachment
button. It uploads the original into the selected evidence entry and creates a
separate **Unverified** entry for the annotated copy, referencing the source entry
and original attachment. Review and save the investigation to retain the evidence
references. Existing report generation includes both entries and attachments.
The investigation app continues to use its normal online private-file uploads.

PERI photo review treats added marks and notes as annotations and compares them
with the original evidence. A copy and original do not provide independent
confirmation of a condition.

## Deployment and validation

Update the app, rebuild mobile and investigation assets, and restart through the
normal deployment process. No new DocTypes, custom fields or credentials are
required. Installed PWA updates continue to wait until users leave active forms.

Automated checks cover permission boundaries, overnight periods, missing/truncated
source coverage, inference failure, explicit draft application, original/copy
retention, partial attachment retries, recent confirmations and investigation
evidence linkage. `frontend/tests/field-tools.e2e.py` exercises the production
mobile build with local API fixtures, real canvas rendering/JPEG export, Chromium
touch input at phone size, desktop pointer input and the handover save flow.
CI runs this script in Chromium and WebKit. Live model/site behaviour and physical
iPhone/Android checks remain deployment validation.
