# Mobile submission checklist

New and editable mobile documents show a **Submission checklist** above Submit or
Save Changes. It gives a live count of missing required items. Tap **Review** to
see the field label, tab/section and, for table entries, the row number. Tapping an
item selects its tab and focuses the field, opens the existing row, or opens Add
row for an empty required table. A required signature links to its signing area.

Submitting an incomplete form expands and focuses the checklist without clearing
values or selected attachments. Row editors have the same checklist; an incomplete
row stays open. Checks run before writes and offline queueing. Once the items are
complete, the existing save flow runs, including daily-timesheet hours confirmation.
No additional confirmation is shown for a valid form.

## Rules

- Use the same `depends_on`, section visibility, `mandatory_depends_on` and
  `read_only_depends_on` evaluation as the form renderer.
- Validate visible, editable fields. Hidden sections and read-only values supplied
  by the server do not create tasks the user cannot complete.
- A required table needs a row. Existing rows in optional tables still need their
  own required fields. Conditional child requirements use that row's values.
- Numeric zero is a valid answer. A required checkbox needs to be ticked; a
  required rating needs a selection. Whitespace and empty rich-text markup do not
  count as answers.
- Forms aggregate native input validity, such as malformed email addresses or
  an unfinished date/time selection, into the checklist instead of letting the
  browser stop on a field in an inactive tab.
- The checklist covers available mobile schema requirements and input validity.
  Server permission, link, business-rule and concurrency checks remain authoritative;
  their existing error handling and offline retry behaviour are unchanged.

## Saving rows on existing documents

Save Row normally persists the row, current parent changes and selected
attachments together. If another form requirement prevents that save, the editor
stays open and offers **Keep row and review form**. This explicit action places the
latest row entries into the current form, closes the row editor and opens the main
checklist. It does not write to the server or queue an incomplete document.

Complete the remaining items and use Save Changes to persist everything. Notes,
selected attachments, existing row identity and the pending operation ID are
retained. These row changes stay in the current open form until it is saved.

## Implementation and checks

- `frontend/src/lib/submissionChecklist.ts`: shared schema requirements, native
  input validity, field targets and the blocked-parent row-save signal.
- `frontend/src/lib/useSubmissionChecklist.ts`: live issues, validation and
  tab/row navigation without writes.
- `frontend/src/components/SubmissionChecklist.vue`: accessible summary and list.
- `NewDocument.vue`, `EditDocument.vue` and `ChildTableField.vue`: save gates and
  exact field/row targets.
- `frontend/tests/submission-checklist.test.js`: conditions, zero/rating/checkbox
  values, row navigation, safe staging, native email validation and attachments.
- `frontend/tests/submission-checklist.e2e.py`: production-build Chromium/WebKit
  checks for new/edit forms at 320px, 440px and desktop widths, including real
  signatures, cross-tab navigation, native validity and one complete submission.

Run `yarn --cwd frontend test:ui` and `yarn --cwd frontend build`. After building,
run `python frontend/tests/submission-checklist.e2e.py`; use `--browser chromium`
to select an installed engine. Both engines run in CI.
