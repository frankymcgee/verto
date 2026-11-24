# Frappe UI 1.2 migration — 24 November 2026

The latest stable npm release and GitHub release both identify **1.2.0**,
published 11 November 2026. Verto pins upstream tag `v1.2.0` at commit
`a9e454c1f82fd189f63031a97c05c94466046e0a`; it does not track unreleased `main`.
Verto's version is incremented to **16.3.153** with this change.

## Documentation reviewed

- [Release v1.2.0](https://github.com/frappe/frappe-ui/releases/tag/v1.2.0)
- [Current installation guide](https://ui.frappe.io/docs/getting-started)
- [v1 changelog](https://ui.frappe.io/docs/changelog/v1)
- [Migration guide](https://ui.frappe.io/docs/migration)
- The migration guide, API contracts and codemods shipped in the pinned tag.

The older code was already largely using the v1 API. The guide's v0 migration
is therefore a checklist, not a reason to repeat every transformation.

## Dependency alignment

| App | Previously | Now |
| --- | --- | --- |
| Mobile frontend | Local submodule at `1.0.0-beta.64`, `f52667b` | Local pinned submodule at `1.2.0`, `a9e454c` |
| Planner | npm `1.0.0-beta.64` | Same `file:../frappe-ui` submodule |
| Investigations | npm `1.0.2` | Same `file:../frappe-ui` submodule |

All three application lockfiles are refreshed and frozen installs verified.
Planner CI now checks out submodules recursively too. The existing CI dependency
image key includes the gitlink and all app manifests/locks, so a new SDK cannot
reuse an image containing the older installed dependencies.

The documented requirements are met by the existing Node 24, Vue 3.5, Vue Router
4 and Tailwind 3 toolchains. Tailwind 4 is not supported by Frappe UI 1.2 and is
not introduced. Optional CodeEditor/VitePress peers are not needed by these
apps; the public Editor path is already used.

## Application changes and compatibility review

| Area | Required handling in Verto |
| --- | --- |
| Icons | Migrate planner `Icon` calls from legacy `name` to documented `icon`, including bound values. Existing Lucide-prefixed names and the dedicated Vite icon resolver are retained. |
| Radius tokens | Replace nine remaining bare/legacy `rounded`, `rounded-sm`, `rounded-lg` and `rounded-xl` uses with numbered `rounded-4`, `rounded-1`, `rounded-6` and `rounded-7`. |
| Typography and colors | Already on Espresso v2. Run only the radius pass: reapplying the typography/ink migration would shrink or shift intentional existing styles a second time. |
| Base CSS | Import `frappe-ui/style.css` once per app. Remove the duplicate `@tailwind` directives from mobile; investigations now imports the base stylesheet instead of maintaining separate Tailwind directives. This includes Inter fonts and the SDK's base behavior. Planner already imports this stylesheet correctly. |
| Date ranges | Type the availability model as the exported `DateRangeValue`: a two-date tuple or `[]`. Keep the server-facing `{from, to}` mapping and clearing behavior. |
| Date entry | Regression-check `DD-MM-YYYY` parsing with `3-11-2026`, `3/11/26` and `03.11.2026`, and focus/blur preserving a saved timestamp's hidden seconds. Mobile's read-only date/time triggers and 15-minute options remain intentional. |
| Dialogs, popovers and selection | Existing `FrappeUIProvider`, `v-model:open`, trigger/content slots and scalar selection values already use the current APIs. Tests include clearing selections with `null` and clearing the date tuple with `[]`. |
| Editor | Already composes `Editor`, `EditorContent`, `EditorFixedMenu` and `RichTextKit` from `frappe-ui/editor`. No old `TextEditor` imports are used by the built apps. Family CSS is automatically included. Existing HTML round trips/read-only tests pass. |
| Uploads | Verto's direct Frappe multipart requests still use the HTTP API's `is_private` field. The guide removes a FileUploader component option, not this server field; private attachments are not changed to public. |
| Resources and HTTP | The existing `createResource`/resource plugin API remains supported in v1. Keep the planner's configured request coordinator and Verto's own offline-aware mobile transport. No forced conversion to `useDoc` or new sockets is needed. |
| Toasts | Planner already uses `toast.success`/`toast.error`; no legacy object-form calls need migration. |
| Navigation/security | Built app links use supported relative/HTTP destinations. No app-specific protocol handlers need conversion. The 1.2 editor security fixes are included. |
| Truncation | v1.2 clips `truncate` horizontally so descenders remain visible. Existing labels do not require a vertical-clipping compatibility override. Phone/desktop shell dimensions are checked in Chromium. |

Upstream dry-run codemods were checked for packaging, destinations, overlays,
navigation, shortcuts, base props, list, editor and data setup. Only the base-prop
and remaining radius changes were needed. Rechecking those passes reports no
remaining changes. No upstream submodule files were modified.

The isolated `roster/src/components/YearViewTable.vue` is not an installed app:
there is no package/build entry and none of the Verto build scripts or routes
reference it. Its old Autocomplete code is not part of the three shipped bundles.

## Browser CI improvement

`Mobile form row saves and offline updates` now contains the quick unit/offline
checks only. Browser checks run independently in **Browser layout and security**
on a pinned Ubuntu 24.04 runner, using:

```
mcr.microsoft.com/playwright/python:v1.62.0-noble@sha256:aa81288e738725378becba5b3e06cb0f3a7f012a610e87e8d767a090ea3f740d
```

The registry tag/digest was verified. It includes Chromium, WebKit and their
Linux libraries. The job installs the matching Python client `playwright==1.62.0`
in a virtual environment created with the image's bundled `virtualenv` module
(the image does not include the system `ensurepip` needed by `python -m venv`);
there is no `playwright install --with-deps` or apt
installation on each run. The image and client must be updated together.

The browser job keeps the phone/desktop and iOS-standalone viewport model,
Chromium/WebKit coverage, HTML security checks, dependency compatibility checks,
planner/investigations builds, investigations tests and screenshot artifact.
It has a 15-minute timeout and caches Yarn inputs for all four locks. The mobile
job does not depend on it. Actual cold image-pull time still depends on GitHub's
runner/network; no unmeasured speedup is claimed.

For local checks the layout script accepts `--browser chromium` and an explicit
`CHROMIUM_BINARY`. With no arguments CI still tests both Chromium and WebKit.

## Validation and limits

- **549 UI tests:** 399 mobile, 113 planner, 37 investigations.
- All three production builds, including mobile PWA injectManifest.
- Four frozen app installs and fresh package audits: **zero known findings**
  in all four application locks. Prior scoped security overrides are preserved.
- Seven real Chromium HTML security/whiteboard dependency checks.
- Five Chromium shell scenarios: phone/desktop, viewport shortfall, modelled
  installed iOS viewport behavior, plus keyboard opening/closing checks.
- Five dependency caller checks, 22 backend offline-sync tests, and 10 CI
  configuration regressions.
- Browser workflow YAML and shell structure reviewed; official image digest
  verified. Docker and WebKit are unavailable locally, so actual container
  execution and WebKit layout validation remain GitHub CI checks.
- Full Frappe integration/fresh-install verification belongs to the prepared
  Bench CI jobs, not the isolated local frontend tests. The SDK update changes
  the reusable dependency-image key and may require a one-time rebuild.

This follow-up was prepared on a separate branch so PR #115's running workflow
was not cancelled or replaced. Nothing is merged or deployed by this change.
