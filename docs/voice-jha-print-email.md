# Signed JHA printing emails

## JHA print appearance

Open **Verto Mobile Settings > JHA Print** to set the company name, header
branding text, company logo, font and colours for the **Digital JHA Workpack**.
The logo appears in the top right corner of every page. If no logo is set,
header branding text appears there instead; leave that text blank to use the
company name in uppercase. The revision-check QR sits below the logo or text
on every page. Critical risks and controls print in full, with additional
critical risk pages when more than two are recorded. Upload a PNG, JPEG, WebP or GIF logo; it is embedded in the print so private
uploads also work in background PDFs. The selected font must be installed on
the PDF server, or the browser/PDF renderer uses its standard fallback font.

Heading backgrounds/text, body text, table borders and critical risk colours
have separate colour pickers. Existing sites keep the Mine Site Support,
Arial, orange and yellow defaults until configured. The workpack keeps its A4
landscape page layout and existing content/sign-off fields.

Saving these settings applies to newly generated print previews and PDFs
without another migration. Settings survive app updates. Already downloaded or
emailed PDFs stay as generated. Each newly confirmed **Send print copy** or
**Resend print copy** request generates a fresh signed PDF using the current
Digital JHA Workpack format and branding settings. Earlier PDFs and emails
remain in the delivery history, including their File and Email Queue references.

## Automatic delivery

Set **JHA Printing Email** on the Project to the office/printing inbox. If it is blank, Verto uses **Default JHA Printing Email** under Automatic JHA Printing in Verto Mobile Settings. Leave both blank to disable automatic delivery for that project. Each setting accepts one plain email address. Delivery uses the site's existing outgoing Email Account, background workers and scheduler.

After review by the team leader (Supervisor or above) and the last required participant signature, Verto records a print delivery for that exact JHA revision. It prepares the existing Digital JHA Workpack as a private PDF, including signatures and the revision-check QR, then attempts SMTP delivery immediately after the PDF and email record have committed. It does not wait for the scheduled Email Queue flush. The Email Queue entry remains as the delivery/audit record. The finish screen shows preparation, queued/sending, sent or failed status. “Sent” means the email was sent to the configured inbox; it does not confirm that paper was printed.

There are no email fields or send buttons for the crew to complete as part of sign-on. PDF, Redis or email failures keep the signed JHA intact. The reviewer, a Verto Mobile Manager or a System Manager with access to the JHA can confirm a retry or an additional copy from the finish screen. Each new manual request creates a fresh PDF and email, including retries after SMTP failure. Any replaced unsent queue entry is stopped so its older attachment cannot be dispatched automatically. Repeating the same request after a connection failure reuses that request without creating another email. Automatic recovery also keeps the PDF already prepared for the current request.

Automatic delivery occurs once when a JHA transitions to Signed. Refreshing, saving, or migrating the site does not mail historical signed JHAs. A supervisor can explicitly send an existing current, fully signed JHA after configuring an address. Each new change revision requires its own review/sign-on before automatic delivery. Unsent delivery is cancelled if the revision requires reassessment or is replaced; copies already sent cannot be recalled. The printed QR checks the live revision.

Setup is installed by the normal Verto site migration. No SMTP credentials are stored in the printing settings. **JHA Print Delivery** records retain recipient, private PDF, Email Queue reference and resend history separately from the signed JHA. SMTP failures remain visible as Failed, with the failed email/PDF retained in history when a fresh copy is requested. Email suspension and muted-email settings are respected. The scheduler reconciles delivery status, recovers preparation jobs that could not be queued and dispatches older unsent JHA printing emails. The site still needs its background workers and outgoing Email Account available; Sent confirms SMTP handoff, not inbox receipt or paper printing. Check Email Queue and Error Log for administrator-level diagnostics. Email Queue's own Send Now action retries its saved attachment; use the JHA finish screen to generate a copy with the latest print format.

The mobile review screens and PERI instructions identify the reviewer as the
**team leader (Supervisor or above)**. The review confirmation includes this
declaration. Existing API names and review audit events are retained for
compatibility; this wording does not map free-text crew roles to ERPNext roles.
