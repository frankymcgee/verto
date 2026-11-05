# Mobile Frappe UI v1 migration

The mobile frontend uses `file:../frappe-ui`. The submodule is pinned to upstream
release `v1.0.0-beta.64`, commit `f52667b631a1fda169e1823a8c6efe541d5921a0`, matching
the planner's package release. Node 20.19 or newer is required; Node 24 is supported.
Do not independently advance the submodule with `git submodule update --remote`.
The app changes, submodule pointer and frontend lockfile ship together.

## UI changes

- Use FrappeUIProvider, the public stylesheet and Tailwind content preset, and the
  Lucide Vite plugin. Migrate typography, radius and surface tokens.
- Replace removed Card wrappers with native sections; preserve explicit page,
  header and scroll-region layouts without the old nested Card scroll container.
- Project tools, form pickers, personnel, child-row editors, chat threads and
  attachments, form errors, About and install prompts use BottomSheet. MobileSheet
  supplies accessible titles/descriptions and retains full-width sheets at all
  screen sizes, fixed headers and footers, and touch-scrollable content.
- Profile actions use Popover and Button, and notifications use Switch. Keep the
  existing permission, subscription, offline refresh and sync callbacks.
- Link fields use Combobox with scalar IDs, debounced server queries, offline
  cached results, request invalidation, saved-value display and explicit clearing.
  Typing a search query does not overwrite the saved record ID.
- Form tabs use TabButtons; forms continue to use Select, Checkbox, Textarea and
  FormControl. The location progress indicator uses Progress.
- Rich text uses the v1 Editor, EditorContent, EditorFixedMenu and RichTextKit.
  Persist HTML, support disabled fields, and normalise empty documents. Load the
  editor asynchronously only for rich-text fields, including child-table rows.

Signature canvas, calendar rendering, specialised task priority colours, embedded
browser handling, realtime APIs, offline queue/schema, tenant manifest and push
service-worker logic retain their existing implementations. The mobile About
version continues to come from the existing server endpoint and commit-count logic.

## Build and verification

From the repository root:

```sh
git submodule update --init --recursive
cd frontend
yarn install --frozen-lockfile --non-interactive
yarn test:ui
yarn build
```

The root build command performs the submodule and frontend installation steps
automatically. Generated assets and service workers are rebuilt by deployment.

UI regression tests mount real Vue/Frappe UI components with mocked server and
cache requests. They cover online/offline link selection, stale responses, HTML
round trips, read-only controls, child rows, profile actions, dates, tabs and form
submission. Production builds also generate and copy the PWA service worker.

A separate `vue-tsc` diagnostic still reports upstream beta source typing errors
and pre-existing errors in `src/lib/api.ts` and `src/lib/frappeRealtime.ts`; it is
not a passing gate. The Vite production build and UI tests are the verified gates.
The rich-text editor remains a large lazy chunk; ordinary forms do not load it
until a rich-text field renders. No device performance improvement is claimed.

## Dev-server checks before Pilot

On Android Chrome/PWA and iOS Safari/PWA, check:

- Open existing forms and create new forms; change tabs, dates, selects and links.
  Save rich text, signatures, attachments and handover child rows; reopen them.
- Scroll long forms, CCV lists, personnel and chat threads. Confirm sheet headers,
  Close/Save actions and nested selectors remain usable with the keyboard open.
- Tap profile actions and notification controls. Verify the About server version.
- Prepare offline data, disconnect, select cached links and save a form/shift;
  reconnect and confirm each queued operation and attachment syncs once.
- Receive a chat message/push, open its destination, and check existing employee
  profile restrictions on Shifts and Chat navigation.
- Reload an already-installed PWA after deployment and confirm the new asset and
  service-worker version activates. Avoid clearing storage while unsynced work exists.

Live Frappe integration, device scrolling and notification delivery require these
dev-server checks; DOM simulation cannot establish them.

Upstream migration guide: https://github.com/frappe/frappe-ui/blob/v1.0.0-beta.64/docs/content/docs/migration.md
