// Copyright (c) 2026, Webwire and contributors
// For license information, please see license.txt

frappe.ui.form.on('Verto Mobile Settings', {
  refresh(frm) {
    frm.add_custom_button(
      __('Generate PWA Manifest'),
      () => generate_pwa_manifest(frm),
      __('PWA')
    )

    frm.add_custom_button(
      __('Regenerate VAPID Keys'),
      () => regenerate_vapid_keys(frm),
      __('Push Notifications')
    )

    frm.add_custom_button(
      __('Run System Health Check'),
      () => run_system_health_check(),
      __('Setup')
    )

    frm.add_custom_button(
      __('Repair Verto Setup'),
      () => repair_verto_setup(frm),
      __('Setup')
    )

    frm.add_custom_button(
      __('Enable Scheduler'),
      () => enable_scheduler(),
      __('Setup')
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

function regenerate_vapid_keys(frm) {
  frappe.confirm(
    __('Regenerating VAPID keys will invalidate existing browser push subscriptions. Users will need to enable push notifications again. Continue?'),
    () => {
      frappe.call({
        method: 'verto.runtime_config.generate_vapid_keys',
        args: { force: 1 },
        freeze: true,
        freeze_message: __('Generating VAPID keys...'),
        callback(response) {
          const message = response.message || {}
          frappe.msgprint({
            title: __('VAPID Keys Generated'),
            indicator: 'green',
            message: `
              <p>${__('Push notification keys are now managed by Verto Mobile Settings.')}</p>
              <p><strong>${__('Public Key')}:</strong><br>${frappe.utils.escape_html(message.public_key || '')}</p>
            `,
          })
          frm.reload_doc()
        },
      })
    }
  )
}

function health_html(health) {
  const checks = health.checks || []
  const rows = checks.map((item) => {
    const indicator = item.ok ? 'green' : 'red'
    const status = item.ok ? __('OK') : __('Needs Attention')
    return `
      <div class="mb-3">
        <div>
          <span class="indicator-pill ${indicator}">${frappe.utils.escape_html(status)}</span>
          <strong>${frappe.utils.escape_html(item.label || '')}</strong>
        </div>
        <div class="text-muted mt-1">${frappe.utils.escape_html(item.detail || '')}</div>
      </div>
    `
  })

  return `
    <div>
      <p><strong>${health.healthy ? __('Verto setup is healthy.') : __('Some Verto setup items need attention.')}</strong></p>
      ${rows.join('')}
    </div>
  `
}

function run_system_health_check() {
  frappe.call({
    method: 'verto.health.get_system_health',
    freeze: true,
    freeze_message: __('Checking Verto setup...'),
    callback(response) {
      const health = response.message || {}
      frappe.msgprint({
        title: __('Verto System Health'),
        indicator: health.healthy ? 'green' : 'orange',
        message: health_html(health),
      })
    },
  })
}

async function repair_verto_setup(frm) {
  if (frm.is_dirty()) {
    await frm.save()
  }

  frappe.call({
    method: 'verto.health.repair_setup',
    freeze: true,
    freeze_message: __('Repairing Verto setup...'),
    callback(response) {
      const result = response.message || {}
      const health = result.health || {}
      frappe.msgprint({
        title: __('Verto Setup Repair Complete'),
        indicator: health.healthy ? 'green' : 'orange',
        message: health_html(health),
      })
      frm.reload_doc()
    },
  })
}

function enable_scheduler() {
  frappe.confirm(
    __('Enable the Frappe scheduler for this site? This allows Verto reminders, qualification checks and scheduled timesheet tasks to run.'),
    () => {
      frappe.call({
        method: 'verto.health.enable_site_scheduler',
        freeze: true,
        freeze_message: __('Enabling scheduler...'),
        callback(response) {
          const health = response.message || {}
          frappe.msgprint({
            title: __('Scheduler Updated'),
            indicator: health.healthy ? 'green' : 'orange',
            message: health_html(health),
          })
        },
      })
    }
  )
}
