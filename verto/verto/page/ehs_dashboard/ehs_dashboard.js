
frappe.pages['ehs-dashboard'].on_page_load = function(wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: 'EHS Dashboard',
    single_column: true
  });
  const body = $(`<div class="p-4 space-y-4">
    <div class="grid" style="grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px;">
      <div class="frappe-card p-4"><div class="text-sm text-muted">Incidents (This Month)</div><div id="incidents_mtd" class="text-2xl font-bold">-</div></div>
      <div class="frappe-card p-4"><div class="text-sm text-muted">Open Actions</div><div id="open_actions" class="text-2xl font-bold">-</div></div>
      <div class="frappe-card p-4"><div class="text-sm text-muted">LTIs (YTD)</div><div id="ltis_ytd" class="text-2xl font-bold">-</div></div>
      <div class="frappe-card p-4"><div class="text-sm text-muted">Training Expiring (30d)</div><div id="training_exp" class="text-2xl font-bold">-</div></div>
    </div>
  </div>`);
  page.body.append(body);

  const today = frappe.datetime.get_today();
  const monthStart = frappe.datetime.month_start(today);

  frappe.call('frappe.client.get_count', {
    doctype: 'EHS Incident',
    filters: { 'incident_datetime': ['>=', monthStart] }
  }).then(r => document.getElementById('incidents_mtd').innerText = r.message || 0);

  frappe.call('frappe.client.get_count', {
    doctype: 'EHS Action',
    filters: { 'action_status': ['!=', 'Done'] }
  }).then(r => document.getElementById('open_actions').innerText = r.message || 0);

  const yearStart = frappe.datetime.year_start(today);
  frappe.call('frappe.client.get_count', {
    doctype: 'EHS Incident',
    filters: { 'classification': 'LTI', 'incident_datetime': ['>=', yearStart] }
  }).then(r => document.getElementById('ltis_ytd').innerText = r.message || 0);

  const in30 = frappe.datetime.add_days(today, 30);
  frappe.call('frappe.client.get_count', {
    doctype: 'EHS Training Record',
    filters: { 'expires_on': ['between', [today, in30]] }
  }).then(r => document.getElementById('training_exp').innerText = r.message || 0);
};
