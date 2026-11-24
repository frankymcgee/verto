# Dependency security review — 24 November 2026

> Follow-up: the seven remaining advisory IDs recorded below are resolved in the
> [dependency and HTML security follow-up](2026-11-24-security-followup.md).
> This document preserves the original PR #114 audit results.

PR #113 was verified through GitHub's API as merged into `version-16` at
2026-11-24 02:20:48 UTC (10:20:48 AWST), merge commit
`32e2779b009df589f24b74fa461f0813a88b8043`, before repository edits. Work uses
`develop`, which already contains the offline fixes. No equivalent open PR was
present at either preflight or the final duplicate check.

## Scope and count limitations

The connector rejects the Dependabot alerts endpoint. The reported **127 alerts
could not be enumerated or reconciled**. Counts below are fresh Yarn Classic
1.22.22 package audit results, not Dependabot alert counts. Each advisory can
appear on several installed dependency paths and in several independent locks.
There were 63 distinct advisory URLs across the four initial application audits;
adding the per-app counts would count shared advisories repeatedly. No alerts
were dismissed or suppressed.

`AGENTS.md`, all four app manifests/locks, `pyproject.toml`, root requirements,
the optional local voice requirements/Dockerfile, build configuration and the
pinned Frappe UI submodule manifest/lock were inspected. Frozen installs and
installed package paths were used to verify the resulting app dependency trees.
The submodule's own `yarn.lock` and devDependencies belong to its independent
upstream development environment. App installs of `file:../frappe-ui` use the
frontend lock and do not install that upstream development toolchain. The
submodule pointer and upstream lock were not changed.

Yarn Classic reports dev counts unreliably here (including zero devDependencies);
exposure below is based on package use, build configuration and import paths,
not that audit field or the manifest section alone.

## Exposure and changes

- **Shipped browser code:** root Excalidraw/Mermaid includes DOMPurify, Nano ID
  and lodash-es; frontend includes DOMPurify, Vue, Socket.IO parser and client
  transports. Root DOMPurify updates to 3.5.0, Nano ID 3 to 3.3.18 and lodash-es
  to 4.18.0. Mobile Vue updates to 3.5.46 and Socket.IO parser to 4.2.7. Other
  application sanitizer copies are also patched.
- **Transport caveat:** `ws` is the Node transport under Engine.IO, normally
  replaced by the browser's native WebSocket in browser builds. Its vulnerable
  installed Node copy is still patched, using a scoped 8.21.0 override.
- **Build/dev/test:** all three apps now use Vite 6.4.6, Vue plugin 5.2.4,
  Vitest 4.1.12 and Happy DOM 21.0.4. This removes vulnerable older Vite/esbuild,
  Vitest/mocker and tinypool paths. Tests use `maxWorkers: 1` in place of removed
  `poolOptions.threads.singleThread`. Inert dialog/print shims only compensate
  for APIs omitted by the newer DOM simulator; production code is unchanged.
- **Build and CSS/PWA tooling:** compatible lock refreshes update PostCSS,
  source-map-js, Nano ID 3, fast-uri, brace-expansion, browserslist,
  baseline-browser-mapping and serialize-javascript. Typography's exact
  selector-parser 6.0.10 pin is scoped to 6.1.5. The service worker's Workbox
  runtime and refresh/queue source logic from #113 are preserved.
- **Scoped overrides:** Excalidraw's exact Nano ID 3 pin, Chevrotain's exact
  lodash-es pin, Typography's parser pin and Engine.IO's `~8.17.1` ws range
  require overrides. These remain on the same major API and are checked by
  tests/builds plus a Mermaid parser smoke check. Yarn's incompatible-range
  warnings for these exact upstream pins are expected. Vite is aligned across
  each app and Vitest to avoid Yarn selecting/linking separate Vite majors.
- **Python runtime:** fresh `pip-audit` resolution of both root requirements
  and the complete pyproject dependency list (including `qrcode[pil]`) found no
  known vulnerabilities. The optional Python 3.12 speech service's six pinned
  direct dependencies plus resolved transitives also produced no findings.
  Python manifests were not changed. These audits resolve packages now; they
  do not establish which versions are already installed on a deployed bench,
  scan native OS libraries, or audit ERPNext/Frappe's separate dependency trees.

## Audit comparison

| App | Distinct advisories before | After | Path findings before | After |
| --- | ---: | ---: | ---: | ---: |
| root | 13 | 5 | 21 | 5 |
| frontend | 58 | 2 | 134 | 5 |
| planner | 31 | 2 | 56 | 2 |
| investigations | 22 | 2 | 43 | 2 |

## Remaining work (not dismissed)

| Installed path | Remaining issue | Required follow-up |
| --- | --- | --- |
| Root `@excalidraw/excalidraw > @excalidraw/mermaid-to-excalidraw > nanoid@4.0.2` | Four advisories: GHSA-mwcw-c2x4-8c55, GHSA-28wg-ghj8-5hjv, GHSA-2v37-7h3g-55p8, GHSA-xwg4-73v4-xw9w; patched Nano ID 5 versions are outside the exact 4.0.2 pin | Upstream converter update or tested Nano ID 5 migration, including diagram conversion and ID generation compatibility |
| Root `… > mermaid > katex@0.16.47` | GHSA-238p-pmpm-9mq7; trust restriction bypass when prototype pollution already exists; patched in 0.18.2 | Mermaid upgrade supporting KaTeX 0.18 or separately validated math rendering migration |
| All app test trees `@vue/test-utils > js-beautify > glob@10.5.0`, plus frontend `vite-plugin-pwa > workbox-build > glob@11.1.0` | GHSA-3g3m-2fjr-6pw4; audit requires glob 14.0.2 | Upstream js-beautify/Workbox releases or compatible glob major migrations |
| All app test trees `… > editorconfig > minimatch@9.0.9`, plus frontend `vue-tsc > @vue/language-core > minimatch@9.0.9` and Workbox's glob > minimatch 10 | GHSA-g3hv-75wg-m249; audit requires minimatch 11.0.1 | Parent toolchain updates or tested minimatch major migrations |

Runtime whiteboard issues remain material; the tool-only findings also remain
open. Blanket cross-major overrides were not applied just to clear the audit.
Advisory-specific paths, affected versions, patched ranges and severities are in
[the evidence file](2026-11-24-audit-evidence.json).

## Validation

- Four frozen-lockfile app installs passed using Node 24.22.3 and Yarn 1.22.22.
- Mobile: 399 tests in 37 files, including connection resilience, queue retries,
  cached shell and refresh safety from #113; production build and injected PWA
  service-worker build passed.
- Planner: 109 tests in 11 files and production build passed.
- Investigations: 37 tests in four files and production build passed.
- Whiteboard: eight page-state tests, minified production-mode esbuild bundle,
  and Mermaid flowchart parser smoke check passed. This is not a full Frappe
  Bench asset build or interactive whiteboard/math-rendering acceptance test.
- Backend offline sync: 22 tests passed; CI configuration: 10 tests passed;
  Desk Gantt/geolocation/attachment picker: 24 Node tests passed; local voice
  bridge: five tests passed.
- Optional voice protocol suite was attempted; its WebRTC module cannot import
  `aiortc` in this environment (nine other tests passed). No speech dependencies
  were changed. The optional service remains subject to its isolated CI job.
- Full Frappe integration/fresh-install checks require the prepared Bench/CI
  stack and were not run locally. Physical-device/captive-Wi-Fi checks and
  deployed-package auditing remain outside this checkout's validation.

## Advisory reconciliation

“Fixed” means the advisory is absent from all four resulting app package audits;
where a shared advisory remains in another path it stays listed as remaining.

| Advisory | Package | Affected lockfiles before | Remaining lockfiles |
| --- | --- | --- | --- |
| [GHSA-238p-pmpm-9mq7](https://github.com/advisories/GHSA-238p-pmpm-9mq7) | katex | root | root |
| [GHSA-28wg-ghj8-5hjv](https://github.com/advisories/GHSA-28wg-ghj8-5hjv) | nanoid | root, frontend | root |
| [GHSA-2m8v-j782-fhvr](https://github.com/advisories/GHSA-2m8v-j782-fhvr) | socket.io-parser | frontend | Fixed |
| [GHSA-2v37-7h3g-55p8](https://github.com/advisories/GHSA-2v37-7h3g-55p8) | nanoid | root, frontend | root |
| [GHSA-333x-w4r6-6crp](https://github.com/advisories/GHSA-333x-w4r6-6crp) | fast-uri | frontend | Fixed |
| [GHSA-3g3m-2fjr-6pw4](https://github.com/advisories/GHSA-3g3m-2fjr-6pw4) | glob | frontend, planner, investigations | frontend, planner, investigations |
| [GHSA-3jxr-9vmj-r5cp](https://github.com/advisories/GHSA-3jxr-9vmj-r5cp) | brace-expansion | frontend | Fixed |
| [GHSA-4c8g-83qw-93j6](https://github.com/advisories/GHSA-4c8g-83qw-93j6) | fast-uri | frontend | Fixed |
| [GHSA-4w7w-66w2-5vf9](https://github.com/advisories/GHSA-4w7w-66w2-5vf9) | vite | frontend, planner, investigations | Fixed |
| [GHSA-587h-7wmj-h5pm](https://github.com/advisories/GHSA-587h-7wmj-h5pm) | vite | frontend, planner, investigations | Fixed |
| [GHSA-58qx-3vcg-4xpx](https://github.com/advisories/GHSA-58qx-3vcg-4xpx) | ws | frontend | Fixed |
| [GHSA-5fpq-26gf-qwcr](https://github.com/advisories/GHSA-5fpq-26gf-qwcr) | happy-dom | frontend, planner, investigations | Fixed |
| [GHSA-5gmw-xhrv-c9v3](https://github.com/advisories/GHSA-5gmw-xhrv-c9v3) | tinypool | frontend, planner, investigations | Fixed |
| [GHSA-5xrq-8626-4rwp](https://github.com/advisories/GHSA-5xrq-8626-4rwp) | vitest | frontend, planner, investigations | Fixed |
| [GHSA-6688-9rhm-gjv2](https://github.com/advisories/GHSA-6688-9rhm-gjv2) | dompurify | root, frontend, planner | Fixed |
| [GHSA-67mh-4wv8-2f99](https://github.com/advisories/GHSA-67mh-4wv8-2f99) | esbuild | frontend, planner, investigations | Fixed |
| [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q) | source-map-js | root, frontend, planner | Fixed |
| [GHSA-698v-4r3x-3vcv](https://github.com/advisories/GHSA-698v-4r3x-3vcv) | vite | frontend, planner, investigations | Fixed |
| [GHSA-6j4f-fj2g-mc7p](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p) | brace-expansion | frontend, planner | Fixed |
| [GHSA-6q6h-j7hj-3r64](https://github.com/advisories/GHSA-6q6h-j7hj-3r64) | happy-dom | frontend, planner, investigations | Fixed |
| [GHSA-73wf-gq98-2v4g](https://github.com/advisories/GHSA-73wf-gq98-2v4g) | browserslist | frontend | Fixed |
| [GHSA-7p8r-x3mc-p8w7](https://github.com/advisories/GHSA-7p8r-x3mc-p8w7) | fast-uri | frontend | Fixed |
| [GHSA-82fw-gwwq-j7x9](https://github.com/advisories/GHSA-82fw-gwwq-j7x9) | vitest | frontend, planner, investigations | Fixed |
| [GHSA-834v-8h66-3h79](https://github.com/advisories/GHSA-834v-8h66-3h79) | happy-dom | frontend, planner, investigations | Fixed |
| [GHSA-85c8-ppgw-ccpr](https://github.com/advisories/GHSA-85c8-ppgw-ccpr) | tinypool | frontend, planner, investigations | Fixed |
| [GHSA-96hv-2xvq-fx4p](https://github.com/advisories/GHSA-96hv-2xvq-fx4p) | ws | frontend | Fixed |
| [GHSA-9jrq-w75r-8gcw](https://github.com/advisories/GHSA-9jrq-w75r-8gcw) | vite | frontend, planner, investigations | Fixed |
| [GHSA-c6gr-qvv4-5v3f](https://github.com/advisories/GHSA-c6gr-qvv4-5v3f) | dompurify | root, frontend, planner | Fixed |
| [GHSA-c83g-rgw3-j3cx](https://github.com/advisories/GHSA-c83g-rgw3-j3cx) | browserslist | frontend | Fixed |
| [GHSA-c8p4-j97h-3vg8](https://github.com/advisories/GHSA-c8p4-j97h-3vg8) | happy-dom | frontend, planner, investigations | Fixed |
| [GHSA-cg2g-xh64-v4q7](https://github.com/advisories/GHSA-cg2g-xh64-v4q7) | dompurify | root, frontend, planner | Fixed |
| [GHSA-f65p-4m7j-42xc](https://github.com/advisories/GHSA-f65p-4m7j-42xc) | fast-uri | frontend | Fixed |
| [GHSA-fph4-wmhf-6fwf](https://github.com/advisories/GHSA-fph4-wmhf-6fwf) | fast-uri | frontend | Fixed |
| [GHSA-fx2h-pf6j-xcff](https://github.com/advisories/GHSA-fx2h-pf6j-xcff) | vite | frontend, planner, investigations | Fixed |
| [GHSA-fxqj-rqcc-2cmp](https://github.com/advisories/GHSA-fxqj-rqcc-2cmp) | postcss | frontend | Fixed |
| [GHSA-g2v6-rqmx-r4w6](https://github.com/advisories/GHSA-g2v6-rqmx-r4w6) | @vue/server-renderer | frontend | Fixed |
| [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249) | minimatch | frontend, planner, investigations | frontend, planner, investigations |
| [GHSA-hrr3-gc8f-f4qj](https://github.com/advisories/GHSA-hrr3-gc8f-f4qj) | fast-uri | frontend | Fixed |
| [GHSA-jqff-g426-hqxp](https://github.com/advisories/GHSA-jqff-g426-hqxp) | fast-uri | frontend | Fixed |
| [GHSA-m5mm-p8h7-m29v](https://github.com/advisories/GHSA-m5mm-p8h7-m29v) | serialize-javascript | frontend | Fixed |
| [GHSA-mh99-v99m-4gvg](https://github.com/advisories/GHSA-mh99-v99m-4gvg) | brace-expansion | frontend | Fixed |
| [GHSA-mrv2-3pqr-j5jr](https://github.com/advisories/GHSA-mrv2-3pqr-j5jr) | dompurify | root, frontend, planner | Fixed |
| [GHSA-mwcw-c2x4-8c55](https://github.com/advisories/GHSA-mwcw-c2x4-8c55) | nanoid | root | root |
| [GHSA-p98j-92pf-mc4p](https://github.com/advisories/GHSA-p98j-92pf-mc4p) | dompurify | root, frontend, planner | Fixed |
| [GHSA-q2hr-2g5m-vwhr](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr) | brace-expansion | frontend, planner | Fixed |
| [GHSA-qhr7-859c-m2p7](https://github.com/advisories/GHSA-qhr7-859c-m2p7) | brace-expansion | frontend, planner | Fixed |
| [GHSA-qw65-cvwx-89v3](https://github.com/advisories/GHSA-qw65-cvwx-89v3) | fast-uri | frontend | Fixed |
| [GHSA-qxg6-89mg-rqv8](https://github.com/advisories/GHSA-qxg6-89mg-rqv8) | @vitest/mocker | frontend, planner, investigations | Fixed |
| [GHSA-r28c-9q8g-f849](https://github.com/advisories/GHSA-r28c-9q8g-f849) | postcss | frontend | Fixed |
| [GHSA-r5fr-rjxr-66jc](https://github.com/advisories/GHSA-r5fr-rjxr-66jc) | lodash-es | root | Fixed |
| [GHSA-r825-w8mm-5pxw](https://github.com/advisories/GHSA-r825-w8mm-5pxw) | vite | frontend, planner, investigations | Fixed |
| [GHSA-rgw5-rvv9-x895](https://github.com/advisories/GHSA-rgw5-rvv9-x895) | brace-expansion | frontend | Fixed |
| [GHSA-rj75-hqrm-r3gf](https://github.com/advisories/GHSA-rj75-hqrm-r3gf) | postcss-selector-parser | frontend, planner, investigations | Fixed |
| [GHSA-rq7h-c2jc-7f22](https://github.com/advisories/GHSA-rq7h-c2jc-7f22) | vite | frontend, planner, investigations | Fixed |
| [GHSA-v2hh-gcrm-f6hx](https://github.com/advisories/GHSA-v2hh-gcrm-f6hx) | fast-uri | frontend | Fixed |
| [GHSA-v6wh-96g9-6wx3](https://github.com/advisories/GHSA-v6wh-96g9-6wx3) | vite | frontend, planner, investigations | Fixed |
| [GHSA-w4gp-fjgq-3q4g](https://github.com/advisories/GHSA-w4gp-fjgq-3q4g) | happy-dom | frontend, planner, investigations | Fixed |
| [GHSA-w5vr-8v7q-w6rv](https://github.com/advisories/GHSA-w5vr-8v7q-w6rv) | baseline-browser-mapping | frontend | Fixed |
| [GHSA-w74x-v6f9-j3xg](https://github.com/advisories/GHSA-w74x-v6f9-j3xg) | fast-uri | frontend | Fixed |
| [GHSA-w9m9-85wc-3x92](https://github.com/advisories/GHSA-w9m9-85wc-3x92) | postcss-selector-parser | frontend | Fixed |
| [GHSA-xhq7-xmqj-769h](https://github.com/advisories/GHSA-xhq7-xmqj-769h) | fast-uri | frontend | Fixed |
| [GHSA-xwg4-73v4-xw9w](https://github.com/advisories/GHSA-xwg4-73v4-xw9w) | nanoid | root | root |
| [GHSA-xxjr-mmjv-4gpg](https://github.com/advisories/GHSA-xxjr-mmjv-4gpg) | lodash-es | root | Fixed |
