import {
  cacheApiResponse,
  getCachedApiResponse,
  getCachedShiftForDate,
  queueMobileDocumentAction,
} from '../pwa/offlineQueue'
import { getOfflineActor } from '../pwa/offlineBootstrap'

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

  return url.includes('get_mobile_doc_for_edit')
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
  const values: Record<string, any> = {}

  if (date) {
    values.date = date
  }

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

async function getOfflineReadFallback<T>(url: string, options: RequestInit, cacheKey: string) {
  const cached = await getCachedApiResponse<T>(cacheKey)

  if (cached) {
    return cached
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
    const response = await fetch(url, {
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...(options.headers || {}),
      },
      ...options,
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
