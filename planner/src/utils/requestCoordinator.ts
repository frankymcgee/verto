import { frappeRequest } from 'frappe-ui'
import { createReadCoordinator, stableKey } from '../../../shared/requestCoordinator'
import { createReadBatcher } from './readBatcher'

const reads = createReadCoordinator(4)
const batches = createReadBatcher(requests => reads.run(null, () => frappeRequest({
  url: 'verto.api.planner_data.get_planner_data', method: 'POST', params: { requests },
})))
const batchMethods = new Set([
  'verto.api.planner.get_events', 'verto.api.planner.get_year_events',
  'verto.api.planner.get_available_employees',
])
function invalidate() { reads.invalidate(); batches.invalidate() }
const coordinatedMethods = new Set([
  'verto.api.planner_data.get_bootstrap',
  'frappe.client.get', 'frappe.client.get_list', 'frappe.client.get_value',
  'frappe.desk.reportview.get_list', 'frappe.desk.search.search_link',
  'frappe.apps.get_apps',
  'verto.api.planner.get_events', 'verto.api.planner.get_year_events',
  'verto.api.planner.get_available_employees',
  'verto.api.planner.get_project_planner_details', 'verto.api.planner.get_task_assignment_users',
])

export function plannerRequest(options: any) {
  const method = String(options.url || '').replace(/^\/api\/method\//, '')
  const batchable = batchMethods.has(method) || (method === 'frappe.client.get_list'
    && ['Employee', 'Project'].includes(options.params?.doctype))
  if (batchable && !options.headers && !options.credentials
    && (!options.method || ['GET', 'POST'].includes(options.method.toUpperCase()))) {
    return batches.read(method, options.params, options.signal)
  }
  if (!coordinatedMethods.has(method)) {
    invalidate()
    return frappeRequest(options).finally(invalidate)
  }
  // Snapshot reactive filters before a request waits in the queue.
  const params = options.params == null ? options.params : JSON.parse(JSON.stringify(options.params))
  const key = options.signal ? null : stableKey({ url: options.url, method: options.method, params, headers: options.headers })
  return reads.run(key, () => {
    options.signal?.throwIfAborted()
    return frappeRequest({ ...options, params })
  })
}
