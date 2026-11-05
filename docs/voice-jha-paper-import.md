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
4. Choose **Discuss each step with PERI** (the default), or **Automatically
   prepare for team leader review**. Confirm the checked reading. This explicitly
   replaces the draft's planned steps and adds the checked hazards/controls.
5. For the guided option, connect voice normally with group microphone/transcription consent. PERI
   confirms the step list, reviews the existing hazards/controls, finds relevant
   incidents for each step, discusses recorded findings/actions and asks the team
   to confirm proposed changes. Critical-control owners and hold points still
   need explicit discussion. Team leader review (Supervisor or above) and crew
   sign-on follow the existing workflow.

## Automatic preparation

The automatic option skips the remaining voice interview and moves the checked
paper JHA directly to **Ready for Team Review**. Select the team leader
(Supervisor or above) and confirm the people who participated in the paper JHA.
New photo readings include legible crew names/roles; correct or add names as
needed. Earlier readings still work, with a manually confirmed team list.
The selected user must be enabled, have a valid email address, and be assigned
to the Work Summary (or be a System Manager) with JHA review access.

After the draft commits, a background job searches the existing incident dataset
for each step using its activity, hazards and controls. Searches run with the
selected team leader's permissions. The review email contains an authenticated
JHA review link, incident references/dates, why they relate to the steps,
excerpts of recorded findings/actions, and missing or unclear paper details for
the reviewer to check. Duplicate incidents are described once; all matched
sources are linked by step, with at most 12 detailed excerpts. Missing data,
unavailable searches and bounded results are labelled explicitly.

Preparation does not create a voice discussion, transcription consent, verified
controls, signatures or approval. Written hold points are retained as source
text; any decisions already confirmed during a partial guided discussion take
precedence. The nominated team leader (or a System Manager with access) still
reviews/signs, followed by personal crew sign-on. The signed-print email remains
the existing separate process after all required signatures.

An already imported, editable paper draft also offers automatic preparation;
disconnect voice before choosing it. Successful retries reuse the same request
and email. The screen shows preparation/delivery status and offers an explicit
retry after failures. The site's existing outgoing Email Account and workers
send the review email immediately after preparation commits; the five-minute
reconciliation job recovers unscheduled work. Sent means SMTP handoff, not
confirmed inbox receipt. Changed/replaced/already reviewed JHAs and revoked
reviewer access cancel unsent requests. New change revisions start in guided
mode and retain the old preparation/audit details on the previous revision.

Photo imports are limited to fresh drafts before voice, confirmed steps, participants
or hazard analysis. Existing discussions, change revisions and reviewed/signed
JHAs cannot be replaced by a photo import. Automatic preparation of an existing
paper draft preserves its current steps/controls. A changed draft/work plan requires a
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
