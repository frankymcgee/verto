# Ask PERI: Raven or Flow

Verto Mobile Settings → Details → PERI Settings includes **Ask PERI Version**.
Existing sites default to **Raven**. Choosing **Flow** embeds the site's native
`/flow` interface in the existing Ask PERI page, with the mobile header and
navigation still available. It does not use the app browser drawer or open a
new window.

## Enable Flow

1. Update/migrate Verto and build its mobile assets using the site's normal
   deployment process. Frappe must include native Flow; the API contract was
   checked against Frappe v16.60.2 source.
2. Set **Ask PERI Version** to **Flow**.
3. Set **PERI Flow Agent** to the exact existing Flow Agent ID, normally `PERI`.
   The agent must exist and be enabled. Save the settings.
4. Give intended users the normal Flow access (including Flow User and the
   permitted agent/model roles). This integration does not assign roles or
   change agent instructions, tools, budgets or approval modes.
5. Reload Verto Mobile and open **Ask PERI**.

The page opens the configured agent, continuing the user's last selected
conversation for that agent where possible. Flow's own conversation list and
new-chat controls remain available. Session recall is scoped to the current
user and configured agent, and ownership is checked on the server.

**Analyse with PERI** on a project opens a fresh conversation with that agent
and sends the same project dashboard request used by the Raven shortcut. It
does not create a Raven channel in Flow mode. If a connection fails while the
analysis is starting, check the displayed conversation before sending again:
the mobile app deliberately does not automatically repeat a paid AI run.

Team **Chat**, voice JHA and automatic photo-analysis workflows retain their
existing integrations. Choosing Raven restores its Ask PERI page; Raven and
Flow histories stay in their respective services and are not migrated.

## Site checks after deployment

- Open Ask PERI as an intended non-administrator user. Confirm the native Flow
  UI loads inside the app and sends a message as PERI, with normal approvals.
- Check conversation switching, attachments, streaming and navigation away
  and back. Check mobile keyboard/composer visibility on iPhone and Android,
  including installed PWA mode.
- Use a project's Analyse with PERI action and verify its prompt appears once.
- Confirm an unauthorised user receives a permission error, then select Raven
  and verify both Ask PERI and ordinary team Chat still work.

Flow is embedded from the same site and uses its existing login cookie. If a
reverse proxy adds `X-Frame-Options: DENY` or CSP `frame-ancestors 'none'`, it must
permit same-origin embedding for `/flow`; do not allow arbitrary external
origins. An expired login returns to the normal sign-in page in the same tab.

## Keyboard and theme

On the Flow route, the mobile shell follows the visible viewport's height and
vertical offset while its outer document stays fixed. Only Flow's own content
scrolls. Phone text controls are at least 16px inside the iframe and its open
shadow roots, including asynchronously mounted editors. Manual pinch zoom is
retained without shrinking the app layout into the magnified viewport.

The avatar menu's **Theme** selector offers **Light**, **Dark** and **Automatic**.
It saves the user's existing `User.desk_theme` through Desk's native theme
endpoint. Mobile reads it with the startup response, synchronises changes
between Mobile tabs for the same user, and checks for Desk changes when the
app regains focus or visibility. Desk uses the same saved preference when it
loads. Automatic follows each device's colour scheme.

Embedded Flow follows the app's active theme without reloading its conversation.
The iframe mirrors the document theme that Flow's own island observes. Mobile
surfaces, text and navigation use Frappe UI's theme colours; signature canvases
and project-specific colours retain their purpose.
