# Paper JHA photos

Teams can start a Digital JHA from photographs of an existing written JHA.
Open the assigned Work Summary's JHA, create/resume a fresh draft and open
**Use a paper JHA** before connecting voice.

1. Photograph or select the pages. Include the whole page in focus, in good light.
   Reorder/remove pages before reading. Supported inputs are JPG, PNG and WebP:
   at most 10 pages, 10 MB and 40 megapixels per page, 30 MB total.
2. Select **Read pages with PERI**. The existing PERI Raven Bot model/credentials
   read all pages together, without conversational tools. The model must support
   images. The selected voice engine remains managed in Verto Mobile Settings.
3. Compare the reading to every original page. Correct steps, hazard/control
   associations and written owners/hold points; add or remove missing/incorrect
   rows. PERI retains uncertainty notes for clarification. Blank controls can be
   discussed later; unreadable step/hazard names must be corrected or removed.
4. Confirm the checked reading and select **Use checked JHA**. This explicitly
   replaces the draft's planned steps and adds the checked hazards/controls.
5. Connect voice normally with group microphone/transcription consent. PERI
   confirms the step list, reviews the existing hazards/controls, finds relevant
   incidents for each step, discusses recorded findings/actions and asks the team
   to confirm proposed changes. Critical-control owners and hold points still
   need explicit discussion. Team leader review (Supervisor or above) and crew
   sign-on follow the existing workflow.

Imports are limited to fresh drafts before voice, confirmed steps, participants
or hazard analysis. Existing discussions, change revisions and reviewed/signed
JHAs cannot be replaced by a photo import. A changed draft/work plan requires a
new reading. Importing does not confirm steps, complete discussion, verify field
controls, copy signatures, record consent or approve/authorise work.

Original photos are private File attachments on the exact JHA. A **JHA Photo
Import** record retains page order/hashes, original extraction, checked text,
model, actor and timestamps. Reading does not change the JHA. Successful reads
and confirmations are replay safe; retries do not create duplicate imported
steps. Source records are immutable after import and access follows the linked
Work Summary assignment. A new change revision retains its link to the previous
JHA, where the original paper source remains available.

Deploy with the normal Verto update, including `bench --site <site> migrate`
and `bench build --app verto`. Migration adds the source DocType/field and origin
options automatically. No manual custom fields or voice-engine selection are
needed. No live model calls are made by the automated tests.
