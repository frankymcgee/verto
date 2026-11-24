# Remaining dependency and HTML security fixes — 24 November 2026

This follows merged PR #114 (`51926fe`) on `develop` and increments Verto to
**16.3.151**. It is proposed in a new PR targeting `version-16`; it does not merge
or deploy anything. The mobile About screen's commit-count handling is unchanged.

## Dependency migrations

| Installed caller | Override | Compatibility checks |
| --- | --- | --- |
| `@excalidraw/mermaid-to-excalidraw > nanoid@4.0.2` | Nano ID **5.1.16** | Real ESM import, custom-length/unique IDs, Chromium diagram conversion with generated group/file IDs |
| `mermaid > katex@0.16.47` | KaTeX **0.18.2** | Public render API with trust disabled, Mermaid math rendering and whiteboard conversion in Chromium |
| All three apps: `editorconfig > minimatch@9.0.9`; frontend: `@vue/language-core > minimatch@9.0.9` | minimatch **11.0.1** | EditorConfig glob sections, Vue attribute-pattern matching, UI suites and builds |
| All three apps: `js-beautify > glob@10.5.0`; frontend: `workbox-build > glob@11.1.0` | glob **14.0.2** (also resolves the vulnerable minimatch 10 path) | Real js-beautify/EditorConfig callers, ignored-file and brace matching, all builds including PWA precaching |

These overrides deliberately cross upstream dependency ranges and are scoped to
callers checked above. Nano ID 3 consumers retain their patched 3.x versions and
CommonJS API; globally replacing every Nano ID dependency with its ESM-only major
would unnecessarily affect different callers. No upstream package files or
submodule pointers were edited. These scoped overrides should be removed when
upstream manifests support the secure versions directly.

KaTeX 0.18 renames several internal CSS classes. The app has no custom selectors
for those internals and does not use its changed private `__defineFunction` API.
The migration uses its public rendering interface and tests Mermaid's math path.
See the [official KaTeX migration guide](https://katex.org/docs/migration.html).

### Fresh package audit results

| Application lockfile | Distinct advisory IDs before | After |
| --- | ---: | ---: |
| Root | 5 | 0 |
| Mobile frontend | 2 | 0 |
| Planner | 2 | 0 |
| Investigations | 2 | 0 |

There were **seven distinct advisory IDs** across the previous four app audits;
all are now absent from fresh Yarn package audits. The two tooling IDs repeated
across locks and installed paths, so these per-app counts must not be added as
unique alerts. The resolved advisory IDs are:

- Nano ID: [GHSA-mwcw-c2x4-8c55](https://github.com/advisories/GHSA-mwcw-c2x4-8c55), [GHSA-28wg-ghj8-5hjv](https://github.com/advisories/GHSA-28wg-ghj8-5hjv), [GHSA-2v37-7h3g-55p8](https://github.com/advisories/GHSA-2v37-7h3g-55p8), [GHSA-xwg4-73v4-xw9w](https://github.com/advisories/GHSA-xwg4-73v4-xw9w).
- KaTeX: [GHSA-238p-pmpm-9mq7](https://github.com/advisories/GHSA-238p-pmpm-9mq7).
- minimatch: [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249).
- glob: [GHSA-3g3m-2fjr-6pw4](https://github.com/advisories/GHSA-3g3m-2fjr-6pw4).

[Audit evidence](2026-11-24-followup-audit-evidence.json) records the prior paths,
patched ranges, fresh audit summaries and actual resolved override versions.
The GitHub connector cannot read Dependabot alerts. Zero package audit findings
is not a claim that the repository's Dependabot count is zero or reconciled with
the reported 127 alerts. No alerts were dismissed. Python dependencies are
unchanged from the earlier review. The upstream Frappe UI development lock is
not installed as a separate toolchain by these four application installs.

## Four reported scanning findings

The connector also rejects the code-scanning alerts endpoint, so this mapping
uses the supplied screenshot's finding IDs and the matching current source.
Actual CodeQL alert closure requires GitHub's next scan; it has not been
asserted or achieved by dismissing findings.

| Finding | Location | Source fix |
| --- | --- | --- |
| #4 — incomplete multi-character sanitization | `verto/public/js/mobile_install_prompt.js` | Instructions are authored as plain text. The alert receives text directly; the Frappe modal receives markup serialized from a text node. Removed regex tag stripping entirely. |
| #3 — incomplete multi-character sanitization | `planner/src/components/YearViewTable.vue` | Replaced HTML/tag regex conversion with a DOMPurify-sanitized fragment and a DOM text walk that preserves paragraph/list/line breaks. The result stays in Vue interpolation/text nodes. |
| #2 — double escaping or unescaping | Same annual planner helper | Removed chained entity replacements and the non-DOM regex fallback. The HTML parser decodes entities once; extracted text is never reparsed as HTML or decoded again. |
| #1 — DOM text reinterpreted as HTML | `frontend/src/pages/Chat.vue` | Removed textarea/element `innerHTML` tricks for entity decoding and escaping. The `entities` library handles string decoding and escaping (including quotes used in attributes); DOMPurify still sanitizes the final formatted message before `v-html`. |

The app already uses DOMPurify. Adding the separate `sanitize-html` parser is
unnecessary for these browser paths: the install dialog needs text, the planner
needs sanitized text extraction, and chat already has a final HTML sanitizer.
Planner now declares DOMPurify directly. Chat declares `entities` directly;
entity decoding is not treated as sanitization. The existing bounded legacy
Raven decoding remains supported, but decoded markup only reaches the DOM after
final sanitization. The helpers are extracted so browser tests exercise the
same functions used by the components.

Relevant primary guidance:
[CodeQL incomplete sanitization](https://codeql.github.com/codeql-query-help/javascript/js-incomplete-multi-character-sanitization/),
[double escaping](https://codeql.github.com/codeql-query-help/javascript/js-double-escaping/),
[DOM text reinterpretation](https://codeql.github.com/codeql-query-help/javascript/js-xss-through-dom/),
[DOMPurify](https://github.com/cure53/DOMPurify), and
[entities](https://github.com/fb55/entities).

## Validation

- Frozen installs for all four application locks passed under Node 24.22.3 and
  Yarn 1.22.22; all four fresh package audits report no known vulnerabilities.
- Mobile **399**, planner **109**, investigations **37** UI tests passed.
  All three production builds passed, including mobile PWA injectManifest.
- **Seven Chromium tests** use the real DOMPurify library: malformed/nested tags,
  active content, encoded/double-encoded entities, escaped quotes in attributes,
  dialog versus alert output, Nano ID-backed diagram conversion, and KaTeX /
  Mermaid math. These do not rely on the UI unit suite's sanitizer mock.
- **Five Node dependency compatibility tests** exercise real EditorConfig,
  js-beautify, Vue minimatch calls and the converter's Nano ID ESM dependency.
- **22 backend offline-sync**, **eight whiteboard page-state**, **24 Desk JS**,
  and **10 CI configuration** tests passed. The minified whiteboard bundle built.
- The Chromium security checks and dependency compatibility checks are added to
  PR/manual CI after the existing isolated browser installation. CI also builds
  planner/investigations and runs the investigations suite for this path.

Full Bench integration/fresh-install validation and physical-device testing are
not claimed locally. GitHub CI and CodeQL results for the new PR must be checked
before merging. No deployment or alert dismissal is part of this change.
