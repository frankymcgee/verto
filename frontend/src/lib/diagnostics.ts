import type { App } from 'vue'
import { withCsrfHeaders } from './csrf'

const ENDPOINT = '/api/method/verto.api.mobile.diagnostics.log_client_error'
const STORAGE_KEY = 'verto:pending-diagnostics'
const MAX_PENDING = 20
const MAX_TEXT = 8000
const recentErrors = new Map<string, number>()
let flushing = false

export type ClientDiagnostic = {
  message: string
  source?: string
  stack?: string
  page?: string
  details?: Record<string, unknown>
}

function redact(value: string, limit = MAX_TEXT) {
  return String(value || '')
    .replace(/(authorization|api[_-]?key|password|token|secret)(["'\s:=]+)[^\s,"'}]+/gi, '$1$2[REDACTED]')
    .slice(0, limit)
}

function sanitiseDetails(details: Record<string, unknown> = {}) {
  const safe: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(details)) {
    if (/body|content|image|blob|authorization|password|token|secret|api.?key/i.test(key)) {
      continue
    }
    if (typeof value === 'string') safe[key] = redact(value, 2000)
    else if (typeof value === 'number' || typeof value === 'boolean' || value == null) safe[key] = value
    else safe[key] = redact(JSON.stringify(value), 2000)
  }
  return safe
}

function normalise(input: ClientDiagnostic): ClientDiagnostic {
  return {
    message: redact(input.message || 'Unknown client error'),
    source: redact(input.source || 'client', 500),
    stack: redact(input.stack || ''),
    page: redact(input.page || `${window.location.pathname}${window.location.hash}`, 1000),
    details: {
      ...sanitiseDetails(input.details),
      online: navigator.onLine,
      visibility: document.visibilityState,
      viewport: `${window.innerWidth}x${window.innerHeight}`,
    },
  }
}

function readPending(): ClientDiagnostic[] {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(value) ? value.slice(-MAX_PENDING) : []
  } catch {
    return []
  }
}

function savePending(items: ClientDiagnostic[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(-MAX_PENDING)))
  } catch {
    // Diagnostics must never break the application when storage is unavailable.
  }
}

function queueLocally(item: ClientDiagnostic) {
  savePending([...readPending(), item])
}

async function send(item: ClientDiagnostic) {
  const formData = new FormData()
  formData.append('message', item.message)
  formData.append('source', item.source || '')
  formData.append('stack', item.stack || '')
  formData.append('page', item.page || '')
  formData.append('details', JSON.stringify(item.details || {}))

  const response = await fetch(ENDPOINT, {
    method: 'POST',
    credentials: 'include',
    headers: withCsrfHeaders(undefined, 'POST'),
    body: formData,
  })
  if (!response.ok) throw new Error(`Diagnostic upload failed (${response.status})`)
}

export async function flushClientDiagnostics() {
  if (flushing || !navigator.onLine) return
  flushing = true
  try {
    const pending = readPending()
    const unsent: ClientDiagnostic[] = []
    for (const item of pending) {
      try {
        await send(item)
      } catch {
        unsent.push(item)
      }
    }
    savePending(unsent)
  } finally {
    flushing = false
  }
}

export async function reportClientError(input: ClientDiagnostic) {
  const item = normalise(input)
  const fingerprint = `${item.source}:${item.message}:${item.page}`
  const now = Date.now()
  if (now - (recentErrors.get(fingerprint) || 0) < 30_000) return
  recentErrors.set(fingerprint, now)

  if (!navigator.onLine) {
    queueLocally(item)
    return
  }
  try {
    await send(item)
  } catch {
    queueLocally(item)
  }
}

function errorDetails(error: unknown) {
  if (error instanceof Error) {
    return { message: error.message, stack: error.stack || '' }
  }
  return { message: redact(String(error || 'Unknown error')), stack: '' }
}

export function installClientDiagnostics(app: App) {
  app.config.errorHandler = (error, _instance, info) => {
    const value = errorDetails(error)
    void reportClientError({
      ...value,
      source: 'vue',
      details: { component_info: info },
    })
    console.error(error)
  }

  window.addEventListener('error', (event) => {
    void reportClientError({
      message: event.message,
      source: 'window.error',
      stack: event.error?.stack || '',
      details: { filename: event.filename, line: event.lineno, column: event.colno },
    })
  })
  window.addEventListener('unhandledrejection', (event) => {
    const value = errorDetails(event.reason)
    void reportClientError({ ...value, source: 'unhandledrejection' })
  })
  window.addEventListener('online', () => void flushClientDiagnostics())
  void flushClientDiagnostics()
}
