# PERI Voice JHA engines

Administrators choose **GPT Realtime** or **GPT Live** in **Verto Mobile Settings
→ PERI Voice JHA → Voice Engine**. Develop JHA with PERI has no engine selector;
the server always uses the saved setting, including for cached clients that
send an old engine preference. Both engines use the same Digital JHA, restricted server tools,
ordered step facilitation, critical-risk/mechanism detection, incident lessons,
completeness checks, human review, sign-on and print workflow. A settings change
applies on the next connection and resumes the saved draft.

## Configuration

After updating Verto, run `bench --site <site> migrate`. In **Verto Mobile
Settings → PERI Voice JHA**, configure:

| Setting | Default | Purpose |
| --- | --- | --- |
| Voice Engine | GPT Realtime | Selects the engine for all new sessions; crews cannot override it. |
| Realtime Model / Voice | Existing site values | Existing Realtime configuration is preserved. |
| Live Voice Model | gpt-live-1 | GPT-Live speech conversation. |
| Live Reasoning & Tools Model | gpt-6-luna | Responses backend running the shared JHA workflow and incident tools. |
| Live Backend Reasoning Effort | low | Must be supported by the configured Responses model. |
| Live Voice | quartz | Australian feminine voice. `ripple` is the Australian masculine option. |
| Live Custom Voice ID Override | Empty | Optional authorized OpenAI custom voice. |

OpenAI credentials and project configuration remain in Raven Settings. The
configured project needs access to the selected voice model and, for Live, the
Responses backend model. Model IDs are configurable on the server; the mobile
request cannot override the engine. Realtime custom voice/model overrides remain
independent of Live configuration.

Conversation style, acknowledgement, read-back and question settings apply to
both engines. Realtime transcription, VAD, noise reduction and numeric output
speed settings configure Realtime only. Live handles its own transcripts and
turn-taking. Both use browser microphone noise suppression and push-to-talk.

## Live connection and tools

The server creates a WebRTC session at OpenAI's Live sessions endpoint using
Raven's authenticated client. A typed Live SDK resource is used when available;
the existing SDK's HTTP client is a compatibility path for older Raven pins,
using a typed dictionary response so older SDK parsers can decode the SDP.
Session creation disables retries to avoid creating another billed session
after an ambiguous failure. API keys never appear in the mobile response.

Live has a short speech/delegation prompt. The shared detailed JHA instructions
and tool schemas sit in its Responses backend. Function calls are sequential;
optional tool arguments remain optional. The mobile adapter collects completed
function items from nested Responses events, runs the existing permission-
checked/audited endpoint, submits every result and waits for backend completion
before continuing. Empty completion output arrays do not discard pending calls.

The UI waits for `session.started` before Live commands and uses instruction
appends for greetings. It preserves transcript fragments and timing, grouping
each speaker independently during overlapping speech. The microphone track is
muted except while holding the talk button. Explicit disconnect drains current
tool results and backend continuations, sends `session.close`, then waits for
closure with a bounded timeout. No new tools run after close starts. Timeouts
and unconfirmed closure prompt the crew to reconnect and check the saved draft.
Leaving the page sends a best-effort close and releases local capture.
Neither engine stores raw audio in Verto; Live session recording is disabled
with `store: false`. The shared structured JHA and existing audit remain saved.

## Validation

CI runs the Voice JHA incident and engine tests against a fresh Frappe v16 site,
including custom-field migration and an HTTP-mocked request using Raven's
installed OpenAI SDK. No billed OpenAI session is opened by automated tests.
Tests exercise both typed and legacy SDK request paths. Frontend tests exercise
both configured engines, consent, push-to-talk, transcripts, restricted tool
calls, disconnect and administrator changes on the same draft.

Before enabling Live for field use, test an actual development-site conversation
with the configured OpenAI project. Check Quartz/Ripple pronunciation of site
terms; resume and corrections; hazard/incident prompts and crew-confirmed
controls; every step's hold point; review/sign-on and printed output. The real
INX export and real audio have not been used by automated tests.

Official references:
- [Live WebRTC](https://developers.openai.com/api/docs/guides/voice-webrtc)
- [Delegation and tools](https://developers.openai.com/api/docs/guides/live-delegation)
- [Live voices and session lifecycle](https://developers.openai.com/api/docs/guides/live-conversations)
- [Migration from Realtime](https://developers.openai.com/api/docs/guides/live-migration)
