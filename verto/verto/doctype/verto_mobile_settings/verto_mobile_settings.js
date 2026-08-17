// Copyright (c) 2026, Webwire and contributors
// For license information, please see license.txt

frappe.ui.form.on('Verto Mobile Settings', {
  refresh(frm) {
    frm.add_custom_button(
      __('Generate PWA Manifest'),
      () => generate_pwa_manifest(frm),
      __('PWA')
    )
  },
})

async function generate_pwa_manifest(frm) {
  if (frm.is_dirty()) {
    await frm.save()
  }

  frappe.call({
    method: 'verto.api.mobile.pwa_manifest.generate_manifest_from_settings',
    freeze: true,
    freeze_message: __('Generating PWA manifest...'),
    callback(response) {
      const message = response.message || {}
      const manifestUrl = message.manifest_url || ''
      const assetManifestUrl = message.asset_manifest_url || ''

      const links = []

      if (manifestUrl) {
        links.push(`
          <p>
            <a href="${frappe.utils.escape_html(manifestUrl)}" target="_blank" rel="noopener noreferrer">
              ${frappe.utils.escape_html(manifestUrl)}
            </a>
          </p>
        `)
      }

      if (assetManifestUrl) {
        links.push(`
          <p>
            <a href="${frappe.utils.escape_html(assetManifestUrl)}" target="_blank" rel="noopener noreferrer">
              ${frappe.utils.escape_html(assetManifestUrl)}
            </a>
          </p>
        `)
      }

      frappe.msgprint({
        title: __('PWA Manifest Generated'),
        indicator: 'green',
        message: `
          <p>${__('The PWA manifest has been generated from Verto Mobile Settings.')}</p>
          ${links.join('')}
          <p class="text-muted">
            ${__('Clear browser/site data on test devices if the old PWA name or icon is still cached.')}
          </p>
        `,
      })

      frm.reload_doc()
    },
    error() {
      frappe.msgprint({
        title: __('Could not generate manifest'),
        indicator: 'red',
        message: __('Check the server error log for details.'),
      })
    },
  })
}
