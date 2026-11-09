# Project walkie talkie

Walkie talkie is a live, half-duplex project radio in Verto Mobile. Each standalone
**Verto Walkie Talkie** record is a channel with a required Project link. Several
channels can belong to one project. Audio is carried by LiveKit; Verto does not
record audio, create chat messages, or send audio to PERI.

## Setup

1. Update the app, run `bench --site <site> migrate`, rebuild Verto assets and restart
   the usual bench services.
2. Open **Verto Walkie Talkie Settings** as a System Manager. Enter the LiveKit
   Cloud URL (`wss://…`), API key and API secret, then enable Walkie Talkie. The
   secret is a Password field and stays on the server. The default maximum
   transmission is 60 seconds, configurable between 5 and 120 seconds.
3. Create a **Verto Walkie Talkie** record, enter a channel name, link its Project
   and leave Enabled checked. Optionally link an existing Raven Channel to require
   that channel's membership too. This does not change Raven messages or members.
4. In **Verto Mobile Settings → Project Tools**, add an enabled row with Tool set
   to **Walkie Talkie**. It is an available selection and is not automatically
   added to existing menus.
5. Project Tools opens the mobile page for the selected project. Choose a channel,
   tap **Join channel**, and hold **Hold to talk**. Release to stop. Desktop users
   can hold Space or Enter while the talk button has focus. If the browser blocks
   playback, tap **Enable audio**.

## Access and behaviour

System Managers manage channels and credentials. Other authenticated users can
join when they appear in Project's Users table or are assigned to a non-cancelled
Task/Work Summary in that project. If a Raven Channel is linked, exact Raven
Channel Member membership is also required. These rules apply to direct API calls,
channel lists and Desk reads, not just the mobile menu. Only administrators can
create, edit or delete channels. Disabled channels cannot be joined.

Joining subscribes to live audio without opening the microphone. Holding the
button requests an atomic, site-scoped Redis floor lease. The server grants
LiveKit microphone-publishing permission only to the current speaker. Releasing
stops microphone capture immediately and revokes publishing. Before another
speaker can claim an expired lease, the old participant's publish permission is
revoked. Failure to revoke prevents a new grant. No room-admin credential is sent
to the browser. The initial join token is valid for five minutes and is listen-only.

One heartbeat runs every three seconds per connected radio page. It checks access,
reports the current speaker and renews the speaker's ten-second lease up to the
maximum transmission deadline. An eight-second browser watchdog stops the radio
if heartbeats hang; rejected heartbeats disconnect immediately. Expired leases are
revoked by the next channel heartbeat or floor request. With no requests at all,
there is no independent server timer; the browser closes capture on its own
watchdog and maximum timer.

The PWA must remain open and in the foreground. Hiding the page, locking the phone,
navigating away or going offline disconnects it. It does not provide native radio
background operation or offline voice-message delivery. Users must join again
after a disconnect. Microphone permission is requested on the first talk attempt;
if the permission prompt interrupts the hold, press again after granting access.

## Validation

Run the isolated backend concurrency/permission tests and the mobile tests:

```sh
python -m unittest discover -s tests -p 'test_walkie_talkie.py' -v
cd frontend
yarn test:ui tests/walkie-talkie.test.js tests/qr-scanner.test.js
yarn build
```

The full frontend type check currently reports existing Frappe UI and realtime/router
diagnostics on the base branch. This change adds no new type-check diagnostics.

For live acceptance, use two authorised users on two devices with the same project
channel. Confirm mutual audio, one-speaker contention, immediate silence on release,
channel separation, permission denial, transmission cutoff and background cleanup.
This requires the site's own LiveKit credentials and cannot be verified with mocks.

Protocol references:
[tokens and grants](https://docs.livekit.io/frontends/reference/tokens-grants/),
[RoomService APIs](https://docs.livekit.io/reference/server/server-apis/), and the
[JavaScript SDK](https://docs.livekit.io/reference/client-sdk-js/).
