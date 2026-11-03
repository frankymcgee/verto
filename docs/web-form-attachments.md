# Multiple attachments in browser Web Forms

Enable an **Add attachments** button on an individual ERPNext Web Form by adding
a short script under **Scripting / Style → Client Script**. Visitors can select
several photos or documents, preview images and remove selections before
submitting. This is the standard browser Web Form and does not require Verto
Mobile, an installed app or a user login.

## Add to a Web Form

Deploy this Verto update first using the site's normal update process. Rebuild
assets, clear the site's cache and restart web/worker processes to load the
server hook. For a conventional bench installation:

```sh
bench --site your-site migrate
bench build --app verto
bench --site your-site clear-cache
bench restart
```

In the desired **Web Form → Scripting / Style → Client Script**, add this snippet
alongside any existing script:

```js
frappe.require('/assets/verto/js/web_form_attachments.js').then(() => {
    verto.web_form_attachments.setup();
});
```

An exact copy is stored at `docs/snippets/web-form-attachments-client.js`.
Save the Web Form and reload its browser page. The uploader appears below the
form fields and above the submit controls for **new responses**. The same snippet
works on Field Interaction and other Web Form DocTypes. Each form is enabled
individually; forms without the snippet have no extra uploader. It does not
replace an existing `after_load` handler.

No DocType attachment fields, child tables or additional HTML fields are needed.
Existing single-file attachment fields continue to work. To disable the new
picker on one form, remove the snippet from that form and reload it.

## Guest uploads

For visitors who are not logged in:

1. In **System Settings → Files**, enable **Allow Guests to Upload Files**.
2. If **Allowed Doctypes for Guest Uploads** contains entries, add each form's
   target DocType on its own line, such as `Field Interaction` or
   `Workplace Inspection`, while retaining other allowed DocTypes.
3. Publish the Web Form and leave **Login Required** unchecked.

The server derives the target DocType from the saved Web Form. Pasting a script
does not override the site's guest upload permissions or Web Form access checks.

Test in an incognito window: select two files, remove one, add another and submit.
Staff can open the resulting record in Desk and check its **Attachments** list.

## Styling

Use the Web Form's **Custom CSS** / style field to style this picker. For example:

```css
.verto-web-form-attachments {
    border-top: 1px solid var(--border-color, #d1d5db);
    padding-top: 20px;
}
```

The picker uses the site's existing button and text styles. File names are
rendered as text, rather than inserted as HTML.

## Limits and saving

- Maximum **10 files**, **10 MB per file**, **25 MB in total** per response.
- Stricter site **Max File Size**, Web Form **Max Attachment Size**, target
  DocType **Max Attachments** and **Allowed File Extensions** settings apply.
- Supported extensions: JPG, JPEG, PNG, GIF, PDF, TXT, CSV, DOC, DOCX, XLS, XLSX,
  ODT and ODS. The site can restrict this list further.

The browser reads its limits from the server, which validates them again on
submission. If no supported extensions are allowed, the picker is disabled and
the rest of the form can still be submitted.

Files stay in the browser until the visitor submits. They are then saved as
private Frappe **File** attachments to the newly created record in the same
transaction as the standard Web Form submission. Frappe's normal publication,
login/request-key, mandatory field, permission and rate-limit checks remain in
place. A File validation error fails the submission; the browser retains its
selection so the visitor can correct the problem and retry.

This flow only accepts file content alongside a **new** response. Existing record
names, existing File URLs and the shared Guest owner do not authorize attaching
to another response. Staff with read permission on the record can access its
private attachments. Attachment URLs are not added to the guest success response.

Files are sent with the form in one request. The web server/reverse proxy must
allow the encoded request body; base64 adds roughly one third to file sizes before
JSON/form encoding overhead. A lower server request limit can reject a submission
even when individual files fit the picker limits.

## Verification

```sh
python -m unittest discover -s tests -p test_web_form_attachments.py
node --test tests/web-form-attachments.test.mjs
bench --site test_site run-tests --app verto --module verto.api.test_web_form_attachments --skip-before-tests
```

The standalone suites cover explicit Client Script activation, reuse across
DocTypes, payload boundaries, permission gates, file selection/removal, previews,
pending reads and retries. The bench suite exercises real public Web Form
submissions for Field Interaction and Note, private file linkage, guest read/
append denial and normal submissions without files.
