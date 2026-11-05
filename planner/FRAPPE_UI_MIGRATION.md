# Planner Frappe UI v1 migration

The planner pins `frappe-ui` to `1.0.0-beta.64`. This is a beta release, not
Frappe UI's stable 0.1.x distribution. Build with Node **20.19.0 or newer**,
Vue 3.5 and Tailwind 3. The mobile frontend has its own dependencies and is
outside this migration.

## Changes

- Frappe UI Dialogs replace the custom overlay layers. A small PlannerDialog
  wrapper supplies an accessible description, while the library manages focus,
  Escape, scrolling and nested overlays.
- Combobox and Select replace native selects and custom link result panels.
  Employee filtering uses MultiSelect's scalar ID array; filter models use scalar
  IDs; DateRangePicker uses its new date tuple. Link requests retain their filters.
- Forms use the new FormControl, TextInput, Textarea and Checkbox components.
  Personnel avatars, roster day toggles, dropdown actions, period tabs and
  task confirmations use library components.
- Lucide icons replace FeatherIcon. Styles use the supported Tailwind preset,
  content export and stylesheet. FrappeUIProvider hosts notifications and
  confirmations; toast calls use the v1 API.
- Calendar rendering, drag/resize behavior and the existing server resource APIs
  are retained. No backend endpoint or document schema changes are required.

## Verification

From `planner/`:

```sh
yarn install --frozen-lockfile --non-interactive
yarn test:ui
yarn build
```

UI tests use real Vue/Frappe UI components with mocked server requests. They
cover task assignment add/remove, project DS/NS defaults, dates, roster modes,
project refresh, location Work Summaries, filters, confirmations and popup
selection. They do not substitute for testing against the deployed Frappe site.

Before rollout, smoke-test pointer and keyboard controls, date entry, long
modal scrolling, popup stacking and permission-restricted users on the target
site. Check both desktop and mobile browsers. This workspace has not verified
live-site or physical-device behavior.

Upstream references:
- https://github.com/frappe/frappe-ui/blob/main/docs/content/docs/migration.md
- https://github.com/frappe/frappe-ui/blob/main/package.json
