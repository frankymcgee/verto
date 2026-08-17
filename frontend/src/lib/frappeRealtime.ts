import { Manager, type Socket } from 'socket.io-client'

type RealtimeCallback = (data: any) => void

const callbacks = new Map<string, Set<RealtimeCallback>>()

let socket: Socket | null = null
let hasInitialised = false

function normaliseSiteName(value?: string) {
  return String(value || '').trim().replace(/^\/+|\/+$/g, '')
}

function getSiteName() {
  const embeddedSiteName = document
    .querySelector<HTMLMetaElement>('meta[name="frappe-site-name"]')
    ?.content

  return normaliseSiteName(
    window.frappe?.boot?.sitename ||
    window.frappe?.boot?.site_name ||
    embeddedSiteName ||
    window.location.hostname
  )
}

function getSocketNamespace(siteName: string) {
  return `/${siteName}`
}

function getSocketPath() {
  return '/socket.io'
}

function makeSocket() {
  const siteName = getSiteName()
  const manager = new Manager(window.location.origin, {
    path: getSocketPath(),
    withCredentials: true,
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 500,
    reconnectionDelayMax: 5000,
  })

  return manager.socket(getSocketNamespace(siteName))
}

function attachStoredListeners() {
  if (!socket) return

  for (const [event, eventCallbacks] of callbacks.entries()) {
    for (const callback of eventCallbacks) {
      socket.on(event, callback)
    }
  }
}

function ensureSocket() {
  if (socket) {
    return socket
  }

  socket = makeSocket()

  socket.on('connect', () => {
    console.info('[Verto realtime] connected', {
      namespace: socket?.nsp,
      transport: socket?.io.engine.transport.name,
    })
  })

  socket.on('connect_error', (error) => {
    console.warn('[Verto realtime] connect_error:', error.message)
  })

  socket.on('disconnect', (reason) => {
    console.warn('[Verto realtime] disconnected:', reason)
  })

  attachStoredListeners()

  return socket
}

export function setupFrappeRealtime() {
  if (hasInitialised) {
    return window.frappe?.realtime
  }

  hasInitialised = true

  window.frappe = window.frappe || {}

  window.frappe.realtime = {
    get socket() {
      return socket
    },

    on(event: string, callback: RealtimeCallback) {
      const activeSocket = ensureSocket()

      if (!callbacks.has(event)) {
        callbacks.set(event, new Set())
      }

      callbacks.get(event)?.add(callback)
      activeSocket.on(event, callback)
    },

    off(event: string, callback?: RealtimeCallback) {
      if (!callback) {
        callbacks.delete(event)
        socket?.off(event)
        return
      }

      callbacks.get(event)?.delete(callback)
      socket?.off(event, callback)
    },

    emit(event: string, ...args: any[]) {
      const activeSocket = ensureSocket()
      activeSocket.emit(event, ...args)
    },

    connect() {
      const activeSocket = ensureSocket()

      if (!activeSocket.connected) {
        activeSocket.connect()
      }
    },

    disconnect() {
      socket?.disconnect()
    },

    isConnected() {
      return Boolean(socket?.connected)
    },

    ping(timeoutMs = 5000) {
      const activeSocket = ensureSocket()

      if (!activeSocket.connected) {
        return Promise.resolve(false)
      }

      return new Promise<boolean>((resolve) => {
        let settled = false
        let timer = 0

        const finish = (healthy: boolean) => {
          if (settled) return
          settled = true
          window.clearTimeout(timer)
          activeSocket.off('pong', handlePong)
          resolve(healthy)
        }

        const handlePong = () => finish(true)

        activeSocket.once('pong', handlePong)
        timer = window.setTimeout(() => finish(false), timeoutMs)
        activeSocket.emit('ping')
      })
    },
  }

  return window.frappe.realtime
}

export function getFrappeRealtimeSocket() {
  return ensureSocket()
}
