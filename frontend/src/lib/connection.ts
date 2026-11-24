import { ref } from 'vue'

// Wi-Fi/mobile service being connected does not mean the Verto server is reachable.
export const serverReachable = ref(typeof navigator === 'undefined' || navigator.onLine)
let retryAfter = 0
let failures = 0
let lastConfirmedAt = 0
let probe: Promise<boolean> | null = null

export class ConnectionUnavailableError extends TypeError {
  constructor(message = 'Connection unavailable. Your saved work will retry when Verto is reachable.') {
    super(message)
    this.name = 'ConnectionUnavailableError'
  }
}

export function connectionLost() {
  serverReachable.value = false
  retryAfter = Date.now() + Math.min(5000 * 2 ** Math.min(failures++, 4), 60_000)
}

function connectionConfirmed() {
  serverReachable.value = true
  lastConfirmedAt = Date.now()
  retryAfter = 0
  failures = 0
}

// Keep the deadline active while reading the body too: weak connections can stall
// after headers arrive. Never follow a redirect to a captive Wi-Fi sign-in page.
export async function fetchServerJson(
  url: string,
  options: RequestInit = {},
  timeoutMs = 15_000,
): Promise<{ response: Response; data: any }> {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    throw new ConnectionUnavailableError()
  }
  const controller = new AbortController()
  let disconnected = false
  const abort = () => controller.abort()
  const disconnect = () => { disconnected = true; abort() }
  const timeout = setTimeout(abort, timeoutMs)
  options.signal?.addEventListener('abort', abort, { once: true })
  if (options.signal?.aborted) abort()
  window.addEventListener('offline', disconnect, { once: true })
  try {
    const response = await fetch(url, {
      cache: 'no-store', ...options, credentials: 'include', redirect: 'manual', signal: controller.signal,
    })
    if (response.type === 'opaqueredirect' || response.redirected || (response.status >= 300 && response.status < 400)) {
      throw new ConnectionUnavailableError('Verto could not be reached. Complete the Wi-Fi sign-in if required; your work is kept on this device.')
    }
    const text = await response.text()
    let data: any
    try { data = JSON.parse(text) } catch {
      // Reverse proxies can reject an oversized file before Frappe emits JSON.
      if (response.status === 413) data = { message: 'The upload exceeds the server size limit.' }
      else throw new ConnectionUnavailableError()
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new ConnectionUnavailableError()
    if (response.status >= 500 || [408, 425, 429].includes(response.status)) {
      throw new ConnectionUnavailableError('The server is temporarily unavailable. Your saved work will retry automatically.')
    }
    connectionConfirmed()
    return { response, data }
  } catch (error) {
    if (options.signal?.aborted) throw error
    connectionLost()
    if (controller.signal.aborted) {
      throw new ConnectionUnavailableError(disconnected
        ? 'Connection interrupted. Your saved work will retry automatically.'
        : 'The server took too long to respond. Your saved work will retry automatically.')
    }
    if (error instanceof ConnectionUnavailableError) throw error
    throw new ConnectionUnavailableError()
  } finally {
    clearTimeout(timeout)
    options.signal?.removeEventListener('abort', abort)
    window.removeEventListener('offline', disconnect)
  }
}

export function checkServerConnection(force = false): Promise<boolean> {
  if (!navigator.onLine) {
    serverReachable.value = false
    return Promise.resolve(false)
  }
  if (probe) return probe
  if (!force && Date.now() < retryAfter) return Promise.resolve(false)
  if (!force && serverReachable.value && lastConfirmedAt && Date.now() - lastConfirmedAt < 10_000) {
    return Promise.resolve(true)
  }
  probe = fetchServerJson('/api/method/frappe.ping', {}, 8000)
    .then(({ response, data }) => {
      if (!response.ok || data.message !== 'pong') {
        connectionLost()
        return false
      }
      return true
    })
    .catch(() => false)
    .finally(() => { probe = null })
  return probe
}
