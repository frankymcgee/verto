# Signed JHA printing emails

## JHA print appearance

Open **Verto Mobile Settings > JHA Print** to set the company name, header
branding text, company logo, font and colours for the **Digital JHA Workpack**.
Leave header branding text blank to use the company name in uppercase on every
page. Upload a PNG, JPEG, WebP or GIF logo; it is embedded in the print so private
uploads also work in background PDFs. The selected font must be installed on
the PDF server, or the browser/PDF renderer uses its standard fallback font.

Heading backgrounds/text, body text, table borders and critical risk colours
have separate colour pickers. Existing sites keep the Mine Site Support,
Arial, orange and yellow defaults until configured. The workpack keeps its A4
landscape page layout and existing content/sign-off fields.

Saving these settings applies to newly generated print previews and PDFs
without another migration. Settings survive app updates. Already downloaded or
emailed PDFs stay as generated. **JHA Print Delivery** also reuses its original
saved PDF when retrying or resending that revision; it does not replace that
historical copy when branding changes. Open a fresh workpack print to see the
current appearance.

## Automatic delivery

Set **JHA Printing Email** on the Project to the office/printing inbox. If it is blank, Verto uses **Default JHA Printing Email** under Automatic JHA Printing in Verto Mobile Settings. Leave both blank to disable automatic delivery for that project. Each setting accepts one plain email address. Delivery uses the site's existing outgoing Email Account, background workers and scheduler.

After human review and the last required participant signature, Verto records a print delivery for that exact JHA revision. It prepares the existing Digital JHA Workpack as a private PDF, including signatures and the revision-check QR, then sends it through Email Queue. The finish screen shows preparation, queued/sending, sent or failed status. “Sent” means the email was sent to the configured inbox; it does not confirm that paper was printed.

There are no email fields or send buttons for the crew to complete as part of sign-on. PDF, Redis or email failures keep the signed JHA intact. The reviewer, a Verto Mobile Manager or a System Manager with access to the JHA can confirm a retry or an additional copy from the finish screen. A failed SMTP retry reuses the existing queue entry; an intentional resend after success creates another email and retains the previous queue reference in delivery history. The saved PDF is reused for that revision.

Automatic delivery occurs once when a JHA transitions to Signed. Refreshing, saving, or migrating the site does not mail historical signed JHAs. A supervisor can explicitly send an existing current, fully signed JHA after configuring an address. Each new change revision requires its own review/sign-on before automatic delivery. Unsent delivery is cancelled if the revision requires reassessment or is replaced; copies already sent cannot be recalled. The printed QR checks the live revision.

Setup is installed by the normal Verto site migration. No SMTP credentials are stored in the printing settings. **JHA Print Delivery** records retain recipient, private PDF, Email Queue reference and resend history separately from the signed JHA. The scheduler reconciles delivery status and recovers preparation jobs that could not be queued. Check Email Queue and Error Log for administrator-level diagnostics.
