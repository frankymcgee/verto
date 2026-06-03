import { io, type Socket } from 'socket.io-client'

type RealtimeCallback = (data: any) => void

const callbacks = new Map<string, Set<RealtimeCallback>>()

let socket: Socket | null = null
let hasInitialised = false

function getSiteName() {
  return (
    window.frappe?.boot?.sitename ||
    window.frappe?.boot?.site_name ||
    window.location.hostname
  )
}

function getSocketUrl() {
  return window.location.origin
}

function getSocketPath() {
  return '/socket.io'
}

function makeSocket() {
  const siteName = getSiteName()

  return io(getSocketUrl(), {
    path: getSocketPath(),
    withCredentials: true,
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 500,
    reconnectionDelayMax: 5000,
    auth: {
      site_name: siteName,
    },
    query: {
      site_name: siteName,
    },
  })
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
    console.info('[Verto realtime] connected')
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
      if (!callbacks.has(event)) {
        callbacks.set(event, new Set())
      }

      callbacks.get(event)?.add(callback)

      const activeSocket = ensureSocket()
      activeSocket.on(event, callback)
    },

    off(event: string, callback?: RealtimeCallback) {
      const activeSocket = ensureSocket()

      if (!callback) {
        callbacks.delete(event)
        activeSocket.off(event)
        return
      }

      callbacks.get(event)?.delete(callback)
      activeSocket.off(event, callback)
    },

    emit(event: string, data?: any) {
      const activeSocket = ensureSocket()
      activeSocket.emit(event, data)
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
  }

  ensureSocket()

  return window.frappe.realtime
}

export function getFrappeRealtimeSocket() {
  return ensureSocket()
}