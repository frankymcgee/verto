import type { Socket } from 'socket.io-client'

type VertoRealtimeCallback = (data: any) => void

type VertoFrappeRealtimeClient = {
  socket: Socket | null
  on: (event: string, callback: VertoRealtimeCallback) => void
  off: (event: string, callback?: VertoRealtimeCallback) => void
  emit: (event: string, data?: any) => void
  connect: () => void
  disconnect: () => void
  isConnected: () => boolean
}

type VertoFrappeWindowObject = {
  csrf_token?: string
  boot?: {
    sitename?: string
    site_name?: string
  }
  realtime?: VertoFrappeRealtimeClient
}

declare global {
  interface Window {
    frappe?: VertoFrappeWindowObject
    csrf_token?: string
  }
}

export {}