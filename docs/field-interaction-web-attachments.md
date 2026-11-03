# Field Interaction Web Form attachments

The public ERPNext **Web Form** for **Field Interaction** has an **Add attachments**
button in the browser. Visitors can select several photos or documents, review
image previews and remove individual selections before submitting. This does not
require Verto Mobile, an installed app or a user login.

The picker is added automatically to new Field Interaction Web Form responses,
including site-created Web Forms with their own client script. No additional
DocType fields, child tables or Web Form script changes are required. Existing
single attachment fields remain available.

## Enable and deploy

1. In **System Settings → Files**, enable **Allow Guests to Upload Files**.
2. If **Allowed Doctypes for Guest Uploads** contains any entries, include
   `Field Interaction` on its own line and retain the other allowed DocTypes.
3. Publish the Field Interaction Web Form and leave **Login Required** unchecked.
4. Deploy the Verto update using the site's normal update process. Build assets,
   clear the site's cache and restart workers/web processes so they load the new
   hook. For a conventional bench installation:

   ```sh
   bench --site your-site migrate
   bench build --app verto
   bench --site your-site clear-cache
   bench restart
   ```

Open the existing public Web Form in a fresh browser tab. No route change or
additional setup in Verto Mobile is needed. Test once in an incognito window:
select two files, remove one, add another and submit. Open the resulting Field
Interaction in Desk and check its **Attachments** list.

## Upload limits

- Maximum **10 files**, **10 MB per file**, **25 MB in total** per response.
- Stricter **Max File Size**, Web Form **Max Attachment Size**, DocType
  **Max Attachments** and **Allowed File Extensions** settings still apply.
- Supported extensions: JPG, JPEG, PNG, GIF, PDF, TXT, CSV, DOC, DOCX, XLS, XLSX,
  ODT and ODS. The site can restrict this list further.

The browser obtains its limits from the server. The same limits are checked again
when the response is submitted. If the site allows none of these extensions,
the picker is disabled and the rest of the form can still be submitted.

Files are sent with the form in one request. The web server/reverse proxy must
allow the encoded request body; base64 encoding adds roughly one third to file
sizes before JSON/form encoding overhead. A lower server request limit can still
reject a submission even when its individual files fit the picker limits.

## Saving and privacy

Files stay in the browser until the visitor submits. They are saved as private
Frappe **File** attachments against the newly created Field Interaction, visible
to staff who have permission to read that record. The existing `photo` field is
not used as a list of URLs.

The server delegates to Frappe's normal Web Form submission code for publication,
login/request-key checks, mandatory fields, permissions and rate limits. It then
creates the files in that same database transaction using Frappe's File document
validation and rollback cleanup. A file error fails the submission; no separate
post-submission guest upload is used. The browser retains its selections after a
validation failure so the visitor can correct the form and try again.

This flow only accepts file content alongside a **new** response. Existing record
names, existing File URLs and the shared Guest owner do not authorize attaching
files to another response. The response contains the normal submitted document;
attachment URLs are not added to the guest success response.

## Verification

```sh
python -m unittest discover -s tests -p test_web_form_attachments.py
node --test tests/web-form-attachments.test.mjs
bench --site test_site run-tests --app verto --module verto.api.test_web_form_attachments --skip-before-tests
```

The first two suites cover payload boundaries, permission gates, queue/removal,
previews, reads in progress, retries and unchanged submission handling. The bench
suite covers actual public Web Form creation, private file linkage and guest
read/append denial against Frappe's database and File implementation.
