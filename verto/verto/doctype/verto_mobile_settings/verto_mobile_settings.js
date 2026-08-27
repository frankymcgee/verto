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
      __('Check Safety Cross Status'),
      () => show_safety_cross_status(frm),
      __('Insights')
    )

    frm.add_custom_button(
      __('Install / Update & Rebuild'),
      () => deploy_safety_cross(frm),
      __('Insights')
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

function safety_cross_indicator(state) {
  if (['installed', 'completed'].includes(state)) return 'green'
  if (['available', 'queued', 'running'].includes(state)) return 'blue'
  if (['diagonal_upgrade_available', 'responsive_upgrade_available'].includes(state)) {
    return 'orange'
  }
  if (['incompatible', 'unavailable', 'failed'].includes(state)) return 'red'
  return 'gray'
}

function safety_cross_label(state) {
  const labels = {
    installed: __('Installed'),
    available: __('Available'),
    diagonal_upgrade_available: __('Upgrade Available'),
    responsive_upgrade_available: __('Upgrade Available'),
    incompatible: __('Incompatible'),
    unavailable: __('Unavailable'),
    not_installed: __('Insights Not Installed'),
    idle: __('Idle'),
    queued: __('Queued'),
    running: __('Running'),
    completed: __('Completed'),
    failed: __('Failed'),
  }
  return labels[state] || state || __('Unknown')
}

function escaped_lines(value) {
  return frappe.utils.escape_html(value || '').replace(/\n/g, '<br>')
}

function safety_cross_status_html(status) {
  const deployment = status.deployment || {}
  const sourceState = status.state || 'unknown'
  const deploymentState = deployment.state || 'idle'
  const release = status.installed_insights_release || ''
  const commit = status.installed_insights_commit || ''
  const patchVersion = status.patch_version || deployment.patch_version || ''
  const sourceDetails = status.details || status.next_step || ''
  const deploymentError = deployment.error || ''

  return `
    <div>
      <p class="mb-2">
        <span class="indicator-pill ${safety_cross_indicator(sourceState)}">
          ${frappe.utils.escape_html(safety_cross_label(sourceState))}
        </span>
        <strong>${__('Safety Cross Source')}</strong>
      </p>
      <p>${escaped_lines(status.message || '')}</p>
      ${sourceDetails ? `<p class="text-muted">${escaped_lines(sourceDetails)}</p>` : ''}

      <hr>
      <p class="mb-2">
        <span class="indicator-pill ${safety_cross_indicator(deploymentState)}">
          ${frappe.utils.escape_html(safety_cross_label(deploymentState))}
        </span>
        <strong>${__('Latest Deployment')}</strong>
      </p>
      <p>${escaped_lines(deployment.message || '')}</p>
      ${deployment.updated_on ? `<p class="text-muted">${__('Updated')}: ${frappe.utils.escape_html(deployment.updated_on)}</p>` : ''}
      ${deploymentError ? `<p class="text-danger">${escaped_lines(deploymentError)}</p>` : ''}

      <hr>
      <p class="text-muted mb-1">
        ${__('Installed Insights')}: ${frappe.utils.escape_html(release || __('Unknown'))}
        ${commit ? ` (${frappe.utils.escape_html(commit)})` : ''}
      </p>
      ${patchVersion ? `<p class="text-muted mb-1">${__('Safety Cross Patch')}: ${frappe.utils.escape_html(patchVersion)}</p>` : ''}
      <p class="text-muted mb-0">
        ${__('This integration modifies and rebuilds the shared Insights app for every site on this Bench.')}
      </p>
    </div>
  `
}

function show_safety_cross_status(frm) {
  frappe.call({
    method: 'verto.insights_safety_cross.actions.get_status',
    freeze: true,
    freeze_message: __('Checking Safety Cross status...'),
    callback(response) {
      const status = response.message || {}
      frappe.msgprint({
        title: __('Verto Safety Cross'),
        indicator: safety_cross_indicator(status.state),
        message: safety_cross_status_html(status),
      })

      const deploymentState = (status.deployment || {}).state
      if (['queued', 'running'].includes(deploymentState)) {
        start_safety_cross_poll(frm)
      }
    },
  })
}

function deploy_safety_cross(frm) {
  frappe.confirm(
    __(
      'This will patch and rebuild the shared Insights frontend for every site on this Bench. The build runs in the background and may take several minutes. Continue?'
    ),
    () => {
      frappe.call({
        method: 'verto.insights_safety_cross.actions.queue_install_and_rebuild',
        freeze: true,
        freeze_message: __('Queuing Safety Cross deployment...'),
        callback(response) {
          const result = response.message || {}
          const status = result.status || {}
          frappe.msgprint({
            title: result.already_running
              ? __('Safety Cross Deployment Already Running')
              : __('Safety Cross Deployment Queued'),
            indicator: 'blue',
            message: `
              <p>${
                result.already_running
                  ? __('An existing Safety Cross deployment is already queued or running.')
                  : __('The Safety Cross patch and Insights rebuild were queued on the long worker.')
              }</p>
              <p class="text-muted">
                ${__('You can continue using Desk. This page will notify you when the deployment finishes.')}
              </p>
              ${safety_cross_status_html(status)}
            `,
          })
          start_safety_cross_poll(frm)
        },
      })
    }
  )
}

function start_safety_cross_poll(frm) {
  if (frm.__verto_safety_cross_polling) return

  frm.__verto_safety_cross_polling = true
  let attempts = 0
  const maxAttempts = 120

  const poll = () => {
    window.setTimeout(() => {
      frappe.call({
        method: 'verto.insights_safety_cross.actions.get_status',
        callback(response) {
          const status = response.message || {}
          const deployment = status.deployment || {}
          const state = deployment.state || 'idle'

          if (['completed', 'failed'].includes(state)) {
            frm.__verto_safety_cross_polling = false
            frappe.msgprint({
              title:
                state === 'completed'
                  ? __('Safety Cross Deployment Complete')
                  : __('Safety Cross Deployment Failed'),
              indicator: safety_cross_indicator(state),
              message: safety_cross_status_html(status),
            })
            return
          }

          attempts += 1
          if (attempts < maxAttempts && ['queued', 'running'].includes(state)) {
            poll()
          } else {
            frm.__verto_safety_cross_polling = false
          }
        },
        error() {
          attempts += 1
          if (attempts < maxAttempts) {
            poll()
          } else {
            frm.__verto_safety_cross_polling = false
          }
        },
      })
    }, 5000)
  }

  poll()
}
