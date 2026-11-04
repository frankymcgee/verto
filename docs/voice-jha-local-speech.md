# Local speech with OpenAI reasoning (Pilot)

This optional engine keeps the existing Verto JHA voice screen, push-to-talk,
PERI speaking animation, live transcript, tools, incident search, active-step
briefings and shift reviews. GPT Realtime and GPT Live remain available. Only
the tenant administrator selects the engine in **Verto Mobile Settings → PERI
Voice JHA**. The default engine is unchanged. A service failure does not start a
different provider automatically.

## Runtime and data flow

- Verto validates the signed-in user, assigned work summary, JHA write access,
  microphone/transcription consent and conversation mode before negotiating.
- The tenant's private speech worker uses Pipecat's Small WebRTC connection to
  keep the same live audio and data connection open between spoken turns.
- `faster-whisper` runs locally with a shared model. Incoming PCM is processed
  during microphone capture to update a replaceable transcript preview. Only a
  final transcript is sent to the reasoning model when push-to-talk is released.
  A short RTP tail is retained to avoid clipping the last word.
- The OpenAI Responses API streams text and selects the existing JHA tools.
  The browser executes each tool through Verto's authenticated endpoint, exactly
  as with GPT Realtime. The worker waits for its result before continuing.
- Chatterbox Nano generates short phrases while the text reply is still being
  generated. Audio is paced over the existing WebRTC output track. The crew can
  interrupt by pressing the microphone; queued old speech is discarded promptly.
  An already-dispatched JHA save is allowed to return and is retained in context.
- Disconnect waits for pending transcription, reasoning and tool results within
  a bounded period. A missing close acknowledgement asks the crew to reconnect
  and check the saved draft rather than claiming an unconfirmed save succeeded.

Audio is processed on your infrastructure. Transcript text, JHA context, tool
definitions and tool results still go to OpenAI. `store=False` is used; OpenAI's
applicable API data policies still apply. There is no ChatGPT subscription-based
integration and no OpenAI audio endpoint in this engine. Text API usage remains
billable. The worker holds conversation state and credentials in memory only;
reconnecting resumes the persisted JHA rather than restoring an audio recording.

This is a streaming speech/text/speech pipeline, so its voice and timing will
differ from GPT Live. Test natural turn-taking, corrections, mining terminology,
background noise, interruption and mobile Safari before production rollout.
Hands-free automatic turn detection is not enabled: push-to-talk is preserved.

## Install the CPU Pilot services

The bench uses Python 3.14. Keep these services in their separate containers;
do not install their packages into the bench. The example targets a Linux host
with Docker Compose. It uses Python 3.12 for the gateway and Python 3.11 for
Chatterbox's pinned dependencies. GPU deployment requires a separate compatible
image and driver configuration; the included images use the CPU.

From the Verto repository root on Pilot:

```bash
cp services/local_voice/.env.example services/local_voice/.env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Edit `.env`: replace the placeholder token with that generated value and set
`VERTO_VOICE_TENANT` to the **exact Frappe site directory name**. Keep the file
private (`chmod 600 services/local_voice/.env`). The same token is used only
between this tenant and these two loopback services. No OpenAI key belongs in
this file: the site supplies its Raven credential directly to its trusted worker
during negotiation, never through the browser.

Place an authorised clean Australian voice reference at
`services/local_voice/voices/peri.wav`. Use a single consenting speaker, at least
six seconds of clear speech (around 10–20 seconds is useful), without music or
background noise. The recording is mounted read-only and ignored by Git and the
Docker build context. Do not copy an OpenAI voice. Audition the result: a reference
voice does not guarantee an identical accent, pronunciation or naturalness.

```bash
docker compose -f services/local_voice/compose.yaml build
docker compose -f services/local_voice/compose.yaml up -d
docker compose -f services/local_voice/compose.yaml ps
curl --fail http://127.0.0.1:8091/health
curl --fail http://127.0.0.1:8090/health
```

The first start downloads model weights into persistent Docker volumes and
warms speech generation before reporting ready. It can take several minutes.
Images pin the inspected Nano-capable Chatterbox source revision because the
current PyPI 0.1.7 release does not include Nano. Logs can be inspected with
`docker compose -f services/local_voice/compose.yaml logs --tail=100`.

The gateway and TTS HTTP APIs bind to **127.0.0.1**, ports 8090 and 8091. Do not
publish them to the Internet or route browser traffic to `/offer`. The browser
uses Verto for SDP exchange; audio uses encrypted WebRTC. Linux host networking
lets the peer advertise host interfaces instead of an unreachable Docker IP.
For another tenant on the same host, use separate instances, tokens, models,
reference mount and loopback ports (override the uvicorn commands and TTS URL).
Set the corresponding tenant's URL to its own gateway port.

## Enable in the tenant

Pull this branch's changes, build Verto assets and run the normal site migration.
Migration adds the optional fields; it does not change the selected voice engine.

1. Keep the existing OpenAI credential in Raven Settings.
2. In **Verto Mobile Settings → PERI Voice JHA**, set the local service URL to
   `http://127.0.0.1:8090` and paste the matching service token into its Password field.
3. Set **Local Speech Reasoning Model** and **Local Speech Reasoning Effort** to
   a Responses model/effort available to your OpenAI project. The initial model
   default is the same `gpt-6-luna` used by the existing Live backend.
4. Choose **Local Speech + OpenAI Reasoning** as **Voice Engine**. Save and reload
   the mobile page before testing, particularly after changing ICE settings.
5. Start with one consenting test crew. Connect, speak, interrupt a reply, correct
   a step and check the saved JHA. Test incident lookup, shift review and active-step
   changes as well as ordinary development.

To use a cloud voice engine again, select **GPT Realtime** or **GPT Live** and
reconnect. Calls already in progress keep their engine until disconnected.

## Connectivity and tenant boundaries

Test from an actual phone on mobile data, not only Pilot's LAN. WebRTC needs a
reachable UDP media path. Configure STUN/TURN if NAT or host firewalls block it;
a reverse proxy carrying only HTTPS requests does not relay WebRTC audio.
Self-hosted coturn can provide the relay. Put the required standard browser
`RTCIceServer` objects in **Local Speech ICE Servers**, for example:

```json
[
  {"urls": "stun:turn.example.com:3478"},
  {"urls": "turns:turn.example.com:5349", "username": "voice-user", "credential": "turn-credential"}
]
```

These connection credentials are intentionally sent to the browser and the
worker. Never put an OpenAI key or the private service token in that field.
Configure the relay's firewall and credential lifetime for the deployment.
Use HTTPS for a speech worker on another host. The worker rejects other tenant
names, unauthenticated offers and requests exceeding its session capacity.
Service token holders are trusted to create sessions: use one token/service pair
per tenant rather than sharing it among resellers' customers.

## Capacity and validation

The initial session cap is **four**, a conservative configuration limit, not a
measured capacity claim. Each connected peer reserves a slot. Live partial
transcription performs repeated in-memory passes over the current utterance;
long utterances cost more than short turns. Individual microphone turns are
bounded to two minutes. Models are shared within the tenant, with bounded ASR
concurrency and serial TTS generation; actual throughput depends on hardware.
The browser sends a heartbeat while the connection is open; abandoned peers
expire rather than retaining credentials and slots indefinitely.

Before promising 20–30 simultaneous users, measure at 1, 5, 10, 20 and 30 users:
time from release to first reply audio, interruption delay, transcript corrections,
tool correctness, queued speech, CPU/RAM and ERPNext response times. Compare with
your cloud engines using the same JHA scenarios. Benchmark with real model
weights: mocked protocol tests are not performance or accent validation.

The standalone tests do not call OpenAI or download model weights:

```bash
python3.12 -m venv /tmp/verto-voice-tests
/tmp/verto-voice-tests/bin/pip install -r services/local_voice/requirements.txt
/tmp/verto-voice-tests/bin/python -m unittest discover -s services/local_voice/tests -v
```

Those tests cover phrase streaming before response completion, ordered tools,
interruption, partial/final transcription, tenant/token rejection and repeated
turns over a real local WebRTC connection with fake speech/Responses providers.
