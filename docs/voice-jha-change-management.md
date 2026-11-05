# PERI voice panel and JHA changes

The connected voice panel stays at the top of the scrolling work area. The
push-to-talk microphone remains centred, beside PERI's configured mobile avatar.
The avatar and voice bars show received speech activity; a separate thinking
state shows that PERI is working. The meter reads only the received call audio
and releases its audio resources when the call ends. It does not open another
microphone or record audio. Reduced-motion preferences disable the thinking
animation.

The current step and latest PERI speech remain in the panel. Recorded JHA data,
step progress, incident details and the full conversation can be expanded when
needed. Review, printing and downloading do not end the call.

## Request a change

1. Open the reviewed or signed JHA from its assigned Work Summary.
2. Select **Request a JHA Change**. If the old call is connected, it finishes
   before a new call starts. Confirm microphone/transcription consent if needed.
3. Tell PERI what changed or needs adding. Confirm which existing step it belongs
   to, or the position of a new step. Participant changes are also supported.
4. Reassess the affected steps, including controls, critical controls/owners and
   the hold-point decision. Other steps retain their recorded content.
5. Confirm PERI's change read-back and the development team for this revision.
6. Complete fresh human review and participant sign-on. PERI cannot sign or
   authorise work. **Disconnect Voice** ends the call when the crew is finished.

## Revision records

Change management creates a separate JHA with an incremented revision and a link
to its predecessor. The previous content and signatures remain on that original
record. Its status becomes **Review Required - Work Changed**, preventing its
mobile print action while the change is assessed. Repeated requests resume the
same change revision rather than making duplicate drafts.

The new revision starts unsigned. When its human sign-on is complete, the
predecessor becomes **Superseded**. Review and voice-tool audit entries record
the revision links, requester, confirmed scope and edits. New steps renumber
later steps, hazard links and incident references together. PERI cannot edit
steps outside the confirmed change scope or mutate the previous reviewed JHA.

## Update and checks

Run the normal Verto migration and asset build after updating. The migration
adds revision links, change stage/summary, requester and affected-step fields to
Digital Job Hazard Analysis. PERI's avatar uses the existing mobile bot-image
configuration, with an initial fallback if the image is missing.

CI covers both voice engines, review/print continuity, panel activity and audio
cleanup, call handoff to a change revision, scoped server changes, insertion
replay, fresh review requirements, and real-document revision creation and
protection. Actual speech, avatar configuration and printed workpacks still
need a development-site conversation before field rollout.
