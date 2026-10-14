# JHA workpack and job-learning workflows

This completes priorities 4–8: permit/isolation links, annotated step photos, downloaded signed copies and queued observations, approved reusable job templates, and reviewed closeout lessons.

## Supporting records and photos

Open **Permits, isolations and step photos** in the JHA. Select a recorded work step and add a Permit, Isolation, Document or Photo. Enter the actual external record number, the scope/description, an optional private attachment and the expiry in site date/time. An EHS Permit can also be linked by its existing record name; the server checks read access and tracks changes to that source.

Pending and Confirmed describe the person's check of the reference. The display separately identifies expired, not-yet-valid, withdrawn or changed EHS permits. These records do not issue permits or authorise work. Outstanding permit/isolation references prevent an unchanged start-of-shift confirmation.

**Update Supporting Record** appends a replacement and retains the earlier record. Changing a permit/isolation number, linked permit, file or expiry, or withdrawing it, requires JHA change review. Confirming an unchanged reference leaves signed content intact. The **changed work / missing control** checkbox also marks a reviewed JHA Review Required. **Review Reported Changes with PERI** carries the recorded description into the existing separate change-revision process; the crew still confirms placement and reassesses affected steps.

Photos accept JPG, PNG and WebP up to 10 MB / 40 megapixels. Enter a description, upload the photo and add labelled markers by tapping the image. Up to 20 relative-coordinate markers are stored alongside the original private file. Photo files must be readable attachments on that exact JHA. The change review can show photos from earlier revisions with their original revision and step numbers.

Printed workpacks append supporting-record pages in groups of four. They include permit references, recorded state/expiry, recorder/time and annotated photo previews. Long descriptions and marker notes are labelled excerpts; the cover QR opens the full authenticated records. Earlier signed JHA content and signatures are retained.

## Offline signed copies

On a current Signed JHA, expand **Offline JHA copy** and select **Save Signed Copy for Offline**. The device saves the signed revision, job steps, hazards/controls, review and sign-on, supporting-record descriptions and available photo blobs. The copy shows its revision and server download time. Photos are capped at 30 MB per copy; missing images are explicitly identified.

**Offline JHAs** is available from Forms and the JHA page. Copies are scoped to the downloading account. Logout removes the offline identity and clears read caches. Account changes also clear read caches; observations remain owned by their original recorder in the durable sync queue.

The saved-copy observation form records a whole-job or step-specific text observation against the downloaded revision. It shows Pending Sync until the server accepts it. The global offline sync manager retries when connectivity returns. Every replay rechecks login, the original actor, JHA write access, Work Summary assignment and revision. Stable request IDs prevent duplicates. Server receipt time and client-observed time are recorded separately.

An observation from an older revision remains on that revision and is shown in the current workpack's earlier-observation history. A reported work change flags the current reviewed/signed replacement for reassessment too; it does not silently rewrite or rebase signed content. Changed-work observations received since the last sign-on can be carried into the next change interview. Follow site hold/escalation arrangements while offline because the server has not received an unsynced observation.

The QR page continues to check status live. A failed/offline check clears its live status; the downloaded copy is presented separately as historical reference. Voice connection, sign-on, template selection and live field confirmations require connectivity.

## Reusable job templates

From a current Signed JHA, choose **Propose Reusable Template**. The proposal snapshots allowlisted step/control guidance. It omits participant records, signatures, control owners, verification results and live permit/evidence records.

The JHA's human reviewer or a System Manager can approve/reject a proposal with review notes. Approved templates are available for new drafts in the same project. Before confirming a new draft's step list, select **Use Job Template**, read its proposed steps/controls and record what differs on today's job. PERI receives the selected guidance and differences in both voice engines and in refreshed saved-state responses. It checks applicability during the normal step discussion and records only crew-confirmed content. The existing ordered interview and human review/sign-on still apply.

Template content is immutable. A reviewer can retire an approved template; retired guidance cannot be newly selected and is removed from the guidance supplied to a resumed session. A replacement proposal can be approved separately.

## Closeout and future learning

**Record Job Closeout** asks about work deviations, controls that worked/need improvement, follow-up actions and owners, and a proposed future lesson. The submission is a separate Pending Review record for the JHA revision. It retains the signed workpack and does not close Tasks, permits, or follow-up actions.

The JHA reviewer or a System Manager reviews the record. They can approve/reject it and optionally enter a concise, de-identified **Reviewed guidance for future jobs**. Only this explicitly approved text is supplied as a future lesson. The raw crew narrative and unreviewed proposal do not enter future PERI guidance. Guidance is scoped to the same project and matched to the job's activity terms, with a bounded maximum of five lessons. PERI cites the source record, treats it as historical guidance and checks suitability with the crew.

## Persistence and rollout

Three standalone DocTypes hold these records: JHA Step Resource, JHA Job Template and JHA Job Closeout. Document hooks enforce append-only resources and immutable source content for learning reviews, even when ordinary permission checks are bypassed. Read access follows the JHA's Work Summary assignment; approved templates have project-scoped read access for assigned project personnel. No voice tool approves a template or lesson.

Run the normal Verto migration and asset build. Migration creates the DocTypes and updates the workpack print format. Regenerate existing PDFs to include supporting-record pages. Validate the upload/marker workflow, an offline/reconnect observation, template review/reuse and a closeout review on development before field rollout.

CI runs the existing JHA regressions plus 17 new backend unit tests, three Frappe document-lifecycle integration tests and 18 UI/offline regressions. PDF QA includes a nine-record workpack spanning three supporting-record pages with annotated image previews and continuous page numbering.
