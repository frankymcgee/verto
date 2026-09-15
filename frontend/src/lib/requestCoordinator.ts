import { createReadCoordinator, stableKey } from '../../../shared/requestCoordinator'

const reads = createReadCoordinator(4)
// Frappe also exposes writes through GET (notably get_or_create_*), so HTTP
// method and names alone are insufficient to decide whether a call is a read.
const coordinatedMethods = new Set([
  'verto.api.mobile.about.get_about_info',
  'verto.api.mobile.boot.get_mobile_boot',
  'verto.api.mobile.navigation.get_navigation_access',
  'verto.api.mobile.home.get_home_summary',
  'verto.api.mobile.documents.get_form_schema',
  'verto.api.mobile.documents.get_mobile_doc_for_edit',
  'verto.api.mobile.documents.search_link',
  'verto.api.mobile.shifts.get_shift_calendar',
  'verto.api.mobile.offline.get_offline_bootstrap',
  'verto.api.mobile.project_personnel.get_project_personnel',
  'verto.api.mobile.push_notifications.get_push_config',
  'verto.api.fetch_records.fetch_created_records',
  'verto.api.mobile.raven.get_thread_counts',
  'raven.api.chat_stream.get_messages',
  'raven.api.chat_stream.get_newer_messages',
  'raven.api.chat_stream.get_older_messages',
  'raven.api.document_link.get_preview_data',
])

export function coordinateApiRead<T>(url: string, options: RequestInit, operation: () => Promise<T>) {
  const parsed = new URL(url, window.location.origin)
  const method = String(options.method || 'GET').toUpperCase()
  if (parsed.origin !== window.location.origin || !['GET', 'POST'].includes(method)
    || !coordinatedMethods.has(parsed.pathname.replace(/^\/api\/method\//, ''))) {
    reads.invalidate()
    return operation().finally(reads.invalidate)
  }

  // Cached forms must remain available immediately when the connection drops,
  // even if previous online requests have not timed out yet.
  if (!navigator.onLine) return operation()

  let body: unknown = options.body || ''
  if (body instanceof FormData || body instanceof URLSearchParams) {
    const entries = Array.from(body.entries())
    if (entries.some(([, value]) => typeof value !== 'string')) return operation()
    body = entries.sort(([a], [b]) => a.localeCompare(b))
  } else if (typeof body !== 'string') {
    return operation()
  }

  // Independently cancellable requests keep their own transport. They still
  // count towards the limit and an aborted queued request never reaches fetch.
  const key = options.signal ? null : stableKey({
    url: parsed.href, method, body,
    headers: Array.from(new Headers(options.headers).entries()).sort(),
    cache: options.cache, credentials: options.credentials,
  })
  return reads.run(key, () => {
    options.signal?.throwIfAborted()
    return operation()
  })
}
