import { createResource } from 'frappe-ui'
import { raiseToast } from './index'

let settings: ReturnType<typeof createResource> | undefined

export function usePlannerSettings() {
  // A cached createResource with auto:true reloads on every call. Construct it
  // once instead so navbar, Apps and view preferences share one request.
  settings ??= createResource({
    url: 'frappe.client.get',
    params: { doctype: 'Verto Mobile Settings', name: 'Verto Mobile Settings' },
    auto: true,
    onError(error: { messages?: string[]; message?: string }) {
      raiseToast('error', error.messages?.[0] || error.message || 'Unable to load Verto Mobile Settings')
    },
  })
  return settings
}
