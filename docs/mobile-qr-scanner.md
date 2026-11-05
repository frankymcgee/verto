# Scan documents and forms inside Verto

Open **Home → Project Tools → Scan QR code**, allow camera access, and point the rear camera at the printed code. The scanner opens the document within Verto and stops the camera as soon as it reads a code. Close the scanner to return Home. Camera access also stops when the app goes into the background; use **Scan again** to restart it.

Supported codes contain a link on the same website as the installed Verto app:

- Existing mobile JHA links, including their printed revision number.
- Mobile document and new-form links, including form prefill parameters.
- Standard Frappe Desk document links and document print links. Enabled mobile forms open in their mobile screen; other readable documents open in Verto's document drawer.
- Public or private PDF links on the same site, opened in the document drawer with the existing file access checks.

QR scanning does not grant document permissions, submit a form, sign a JHA, or execute a print action. Links to other sites, executable URLs, API calls, and unsupported paths are rejected. Users can retry after a permission or camera error. Desk-link resolution requires a network connection; mobile destinations retain their existing offline behaviour.

The camera needs HTTPS and browser camera permission. The preview plays inline on iPhone, and decoding uses a bundled JavaScript reader rather than requiring the native BarcodeDetector API. Camera frames are processed on the device and are not uploaded.

The scanner appears in default Project Tools and existing customised menus. Administrators can add a **Scan QR** row to **Verto Mobile Settings → Project Tools** to customise its label or explicitly disable it. Existing menu entries and labels are preserved. Apply the normal site migration to update the available tool choices.

Physical iPhone and Android camera testing is still needed after deployment; automated tests simulate camera access and independently decode a real QR image.
