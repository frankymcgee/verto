import {
  cacheApiResponse,
  getCachedApiResponse,
  getCachedShiftForDate,
  getOfflineQueueItems,
  isOfflineSyncAuthError,
  isRetryableOfflineSyncError,
  queueMobileDocumentAction,
  syncOfflineQueueItem,
} from '../pwa/offlineQueue'
import { clearOfflineReadCache } from '../pwa/offlineSecurity'
import { withCsrfHeaders } from './csrf'

const OFFLINE_ACTOR_STORAGE_KEY = 'verto:offline-actor'
let offlineActorVerified = false

function getOfflineActor() {
  try {
    return String(window.localStorage.getItem(OFFLINE_ACTOR_STORAGE_KEY) || '').trim()
  } catch {
    return ''
  }
}

function setOfflineActor(user: string) {
  try {
    window.localStorage.setItem(OFFLINE_ACTOR_STORAGE_KEY, user)
  } catch {
    // Offline writes fail safe below when browser storage is unavailable.
  }
}

function getRedirectPath() {
  const path = window.location.pathname + window.location.search + window.location.hash

  if (!path || path === '/') {
    return '/verto-mobile/'
  }

  return path
}

function isLoginRoute() {
  return window.location.pathname === '/login'
}

function getLoginUrl() {
  const redirectTo = getRedirectPath()

  return `/login?redirect-to=${encodeURIComponent(redirectTo)}`
}

function isHtmlLoginResponse(response: Response, text: string) {
  const contentType = response.headers.get('content-type') || ''

  if (!contentType.includes('text/html')) {
    return false
  }

  const loweredText = text.toLowerCase()

  return (
    loweredText.includes('<html') &&
    (
      loweredText.includes('/login') ||
      loweredText.includes('login') ||
      loweredText.includes('frappe')
    )
  )
}

function extractErrorMessage(data: any, fallback: string) {
  if (!data) {
    return fallback
  }

  if (typeof data === 'string') {
    return data
  }

  return (
    data?._server_messages ||
    data?.exception ||
    data?.exc ||
    data?.message ||
    fallback
  )
}

function parseJsonMaybe(text: string) {
  if (!text) {
    return null
  }

  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

function isAuthFailure(response: Response, data: any, rawText: string) {
  if (response.status === 401) {
    return true
  }

  if (isHtmlLoginResponse(response, rawText)) {
    return true
  }

  const message = String(extractErrorMessage(data, '') || '').toLowerCase()

  return (
    response.status === 403 &&
    (
      message.includes('login required') ||
      message.includes('not permitted in guest mode') ||
      message.includes('session expired') ||
      message.includes('session has expired') ||
      message.includes('not logged in') ||
      message.includes('please login') ||
      message.includes('please log in')
    )
  )
}

function isNetworkFailure(error: unknown) {
  return error instanceof TypeError ||
    String((error as any)?.message || '').toLowerCase().includes('network') ||
    String((error as any)?.message || '').toLowerCase().includes('failed to fetch')
}

async function ensureOfflineActorForWrite() {
  const storedActor = getOfflineActor()

  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return storedActor
  }

  if (offlineActorVerified && storedActor) {
    return storedActor
  }

  try {
    const response = await fetch('/api/method/frappe.auth.get_logged_user', {
      credentials: 'include',
      headers: {
        Accept: 'application/json',
      },
    })
    const rawText = await response.text().catch(() => '')
    const data = parseJsonMaybe(rawText)

    if (isAuthFailure(response, data, rawText)) {
      redirectToLogin()
      throw new Error('Login required')
    }

    if (!response.ok) {
      throw new Error(
        extractErrorMessage(data, `Could not verify the signed-in user (${response.status}).`)
      )
    }

    const currentActor = String(data?.message || '').trim()

    if (!currentActor) {
      throw new Error('Could not verify the signed-in user.')
    }

    if (storedActor && storedActor !== currentActor) {
      await clearOfflineReadCache()
    }

    setOfflineActor(currentActor)
    offlineActorVerified = true
    return currentActor
  } catch (error) {
    if (isNetworkFailure(error) && storedActor) {
      return storedActor
    }

    throw error
  }
}

function getMethod(options: RequestInit) {
  return String(options.method || 'GET').toUpperCase()
}

async function serialiseBodyForCache(body: BodyInit | null | undefined) {
  if (!body) return ''

  if (body instanceof FormData) {
    const entries: Array<[string, string]> = []

    body.forEach((value, key) => {
      if (typeof value === 'string') {
        entries.push([key, value])
      }
    })

    entries.sort(([aKey, aValue], [bKey, bValue]) => {
      return `${aKey}:${aValue}`.localeCompare(`${bKey}:${bValue}`)
    })

    return JSON.stringify(entries)
  }

  if (typeof body === 'string') return body

  return ''
}

async function makeCacheKey(url: string, options: RequestInit) {
  const method = getMethod(options)
  const body = await serialiseBodyForCache(options.body)
  return `request:${method}:${url}:${body}`
}

function isCacheableRead(url: string, options: RequestInit) {
  const method = getMethod(options)

  if (method === 'GET') {
    return url.includes('/api/method/verto.api.mobile.') ||
      url.includes('/api/method/frappe.')
  }

  if (method !== 'POST') return false

  return url.includes('get_mobile_doc_for_edit') ||
    url.includes('/api/method/verto.api.fetch_records.fetch_created_records')
}

function isProcessFieldChange(url: string) {
  return url.includes('/api/method/verto.api.mobile.documents.process_field_change')
}

function isPrefillRequest(url: string) {
  return url.includes('/api/method/verto.api.mobile.documents.get_prefill_values')
}

async function getOfflinePrefillFallback<T>(url: string): Promise<T | null> {
  if (!isPrefillRequest(url)) return null

  const parsed = new URL(url, window.location.origin)
  const mobileDoctype = parsed.searchParams.get('mobile_doctype') || ''
  const date = parsed.searchParams.get('date') || ''
  const project = parsed.searchParams.get('project') || ''
  const linkTask = parsed.searchParams.get('link_task') || ''
  const workOrderNumber = parsed.searchParams.get('work_order_number') || ''
  const projectScopeName = parsed.searchParams.get('project_scope_name') || ''
  const parentTaskName = parsed.searchParams.get('parent_task_name') || ''
  const values: Record<string, any> = {}

  const setAliases = (fieldnames: string[], value: string) => {
    if (!value) return

    for (const fieldname of fieldnames) {
      values[fieldname] = value
    }
  }

  // These mirror the server-side get_prefill_values aliases. NewDocument only
  // applies keys that exist in the cached schema, so supplying every supported
  // alias is safe and preserves project/task linkage while offline.
  setAliases(['project', 'custom_project', 'link_project'], project)
  setAliases(['link_task', 'task', 'task_name'], linkTask)
  setAliases([
    'work_summary',
    'parent_task_name',
    'work_scope',
    'scope_of_work',
    'custom_work_summary',
    'custom_work_scope',
  ], parentTaskName)
  setAliases([
    'work_area',
    'project_scope_name',
    'area',
    'scope_name',
    'custom_work_area',
    'custom_project_scope_name',
  ], projectScopeName)
  setAliases(['work_order_number', 'wo_number'], workOrderNumber)
  setAliases(['date', 'attendance_date', 'timesheet_date'], date)

  if (mobileDoctype === 'daily-timesheet' && date) {
    const cached = await getCachedShiftForDate(date)
    const shift = cached?.shift

    if (cached?.user_fullname) {
      values.current_user = cached.user_fullname
    }

    if (shift) {
      values.shift_allocation = shift.name || ''
      values.shift_type = shift.shift_type || ''
      values.custom_project = shift.custom_project || ''
      values.project = shift.custom_project || ''
      values.project_name = shift.custom_project_name || ''
      values.custom_project_name = shift.custom_project_name || ''
      values.client = shift.custom_client || ''
      values.custom_client = shift.custom_client || ''
      values.location = shift.custom_location || ''
      values.custom_location = shift.custom_location || ''
    }
  }

  return {
    message: {
      values,
      offline_cached: true,
    },
  } as T
}

async function applyQueuedDocumentUpdates<T>(
  url: string,
  options: RequestInit,
  cached: T
): Promise<T> {
  if (
    !url.includes('get_mobile_doc_for_edit') ||
    !cached ||
    typeof cached !== 'object'
  ) {
    return cached
  }

  const mobileDoctype = getFormValue(options.body, 'mobile_doctype')
  const docname = getFormValue(options.body, 'docname')

  if (!mobileDoctype || !docname) return cached

  const queuedItems = await getOfflineQueueItems()
  const pendingUpdates = queuedItems.filter((item) => {
    return item.kind === 'mobile_document' &&
      item.action_type === 'update' &&
      item.mobile_doctype === mobileDoctype &&
      item.docname === docname &&
      item.status !== 'synced'
  })

  if (!pendingUpdates.length) return cached

  const cachedResponse = cached as any
  const mergedValues = {
    ...(cachedResponse.message?.values || {}),
  }

  for (const item of pendingUpdates) {
    for (const [fieldname, value] of Object.entries(item.values || {})) {
      if (fieldname === '__verto_offline_user') continue
      mergedValues[fieldname] = value
    }
  }

  return {
    ...cachedResponse,
    message: {
      ...(cachedResponse.message || {}),
      values: mergedValues,
      offline_queued: true,
    },
  } as T
}

async function getOfflineReadFallback<T>(url: string, options: RequestInit, cacheKey: string) {
  const cached = await getCachedApiResponse<T>(cacheKey)

  if (cached) {
    return applyQueuedDocumentUpdates(url, options, cached)
  }

  const prefill = await getOfflinePrefillFallback<T>(url)

  if (prefill) {
    return prefill
  }

  if (isProcessFieldChange(url)) {
    return {
      message: {
        values: {},
        messages: [],
        warnings: [],
        offline_cached: true,
      },
    } as T
  }

  return null
}

function getFormValue(body: BodyInit | null | undefined, key: string) {
  if (!(body instanceof FormData)) return ''
  const value = body.get(key)
  return typeof value === 'string' ? value : ''
}

function parseValues(body: BodyInit | null | undefined) {
  const raw = getFormValue(body, 'values')

  if (!raw) return {}

  try {
    return JSON.parse(raw)
  } catch {
    return {}
  }
}

function valuesWithOfflineActor(values: Record<string, any>) {
  const actor = getOfflineActor()

  if (!actor) {
    throw new Error(
      'Offline data is not initialised for this user yet. Reconnect once before submitting forms offline.'
    )
  }

  return {
    ...(values || {}),
    __verto_offline_user: actor,
  }
}

async function queueOfflineWrite<T>(url: string, options: RequestInit): Promise<T | null> {
  if (url.includes('/api/method/verto.api.mobile.documents.create_mobile_doc')) {
    const mobileDoctype = getFormValue(options.body, 'mobile_doctype')
    const values = valuesWithOfflineActor(parseValues(options.body))
    const item = await queueMobileDocumentAction({
      actionType: 'create',
      mobileDoctype,
      values,
    })

    return {
      message: {
        doctype: mobileDoctype,
        name: item.id,
        route: mobileDoctype === 'daily-timesheet' ? '/shifts' : '/forms',
        offline_queued: true,
        offline_operation_id: item.id,
      },
    } as T
  }

  if (url.includes('/api/method/verto.api.mobile.documents.update_mobile_doc')) {
    const mobileDoctype = getFormValue(options.body, 'mobile_doctype')
    const docname = getFormValue(options.body, 'docname')
    const values = valuesWithOfflineActor(parseValues(options.body))
    const item = await queueMobileDocumentAction({
      actionType: 'update',
      mobileDoctype,
      docname,
      values,
    })

    return {
      message: {
        doctype: mobileDoctype,
        name: docname,
        values,
        offline_queued: true,
        offline_operation_id: item.id,
      },
    } as T
  }

  return null
}

function isMobileDocumentWrite(url: string, options: RequestInit) {
  if (getMethod(options) !== 'POST') return false

  return url.includes('/api/method/verto.api.mobile.documents.create_mobile_doc') ||
    url.includes('/api/method/verto.api.mobile.documents.update_mobile_doc')
}

async function submitDurableMobileDocumentWrite<T>(url: string, options: RequestInit) {
  await ensureOfflineActorForWrite()

  const queuedResponse = await queueOfflineWrite<T>(url, options)

  if (!queuedResponse) {
    throw new Error('This document action cannot be saved offline.')
  }

  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return queuedResponse
  }

  const operationId = String((queuedResponse as any)?.message?.offline_operation_id || '')

  try {
    const result = await syncOfflineQueueItem(operationId, {
      deleteOnPermanentFailure: true,
    })

    return {
      message: result,
    } as T
  } catch (error) {
    if (isOfflineSyncAuthError(error)) {
      redirectToLogin()
      throw new Error('Login required')
    }

    // An ambiguous network/server outage keeps the operation in IndexedDB and
    // returns the normal queued response. The idempotency receipt makes a later
    // replay safe even if the server accepted the first attempt.
    if (isRetryableOfflineSyncError(error)) {
      return queuedResponse
    }

    throw error
  }
}

export function redirectToLogin() {
  if (isLoginRoute()) {
    return
  }

  window.location.href = getLoginUrl()
}

export async function apiRequest<T>(url: string, options: RequestInit = {}): Promise<T> {
  const cacheableRead = isCacheableRead(url, options)
  const cacheKey = cacheableRead ? await makeCacheKey(url, options) : ''
  const method = getMethod(options)

  if (isMobileDocumentWrite(url, options)) {
    return submitDurableMobileDocumentWrite<T>(url, options)
  }

  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    if (method !== 'GET') {
      const queued = await queueOfflineWrite<T>(url, options)

      if (queued) return queued
    }

    if (cacheableRead || isProcessFieldChange(url) || isPrefillRequest(url)) {
      const fallback = await getOfflineReadFallback<T>(url, options, cacheKey)

      if (fallback) return fallback
    }
  }

  try {
    const headers = withCsrfHeaders(options.headers, method)

    if (!headers.has('Accept')) {
      headers.set('Accept', 'application/json')
    }

    const response = await fetch(url, {
      ...options,
      credentials: 'include',
      headers,
    })

    const rawText = await response.text().catch(() => '')
    const data = parseJsonMaybe(rawText)

    if (isAuthFailure(response, data, rawText)) {
      redirectToLogin()
      throw new Error('Login required')
    }

    if (!response.ok) {
      throw new Error(
        extractErrorMessage(data, `Request failed with status ${response.status}`)
      )
    }

    const result = (data ?? rawText) as T

    if (cacheableRead && cacheKey) {
      void cacheApiResponse(cacheKey, result, 'api-request')
    }

    return result
  } catch (error) {
    if (!isNetworkFailure(error)) {
      throw error
    }

    if (method !== 'GET') {
      const queued = await queueOfflineWrite<T>(url, options)

      if (queued) return queued
    }

    if (cacheableRead || isProcessFieldChange(url) || isPrefillRequest(url)) {
      const fallback = await getOfflineReadFallback<T>(url, options, cacheKey)

      if (fallback) return fallback
    }

    throw new Error('Offline — this data has not been cached on this device yet.')
  }
}
