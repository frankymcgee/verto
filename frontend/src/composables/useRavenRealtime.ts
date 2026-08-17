// VERTO_RAVEN_NATIVE_REALTIME_SOCKET_BRIDGE_FIX_2026_06_10
import { onBeforeUnmount, ref, type Ref, watch } from 'vue'
import type { RavenMessage } from '../lib/ravenClient'
import { normaliseRavenMessage } from '../lib/ravenClient'

type RavenRealtimeOptions = {
  channelId: Ref<string>
  threadChannelId?: Ref<string>
  currentUser?: Ref<string>
  onMessageCreated?: (message: RavenMessage, event: any) => void
  onMessageEdited?: (messageId: string, patch: Partial<RavenMessage>, event: any) => void
  onMessageDeleted?: (messageId: string, event: any) => void
  onMessageReacted?: (messageId: string, reactions: any, event: any) => void
  onMessageSaved?: (messageId: string, likedBy: string, event: any) => void
  onChannelUpdated?: (channelId: string, event: any) => void
  onThreadReply?: (channelId: string, event: any) => void
  onAiEvent?: (event: any) => void
  onAiEventClear?: (event: any) => void
}

declare global {
  interface Window {
    frappe?: any
    socketio?: any
  }
}

const RAVEN_GLOBAL_DOCTYPE_ROOM = 'Raven User'
const RAVEN_CHANNEL_DOCTYPE = 'Raven Channel'
const VERTO_RAVEN_BRIDGE_EVENT = 'verto:raven_message_event'

export function useRavenRealtime(options: RavenRealtimeOptions) {
  const ready = ref(false)
  const status = ref('Connecting')
  const lastEvent = ref('')

  const subscribedDocs = new Set<string>()
  const subscribedDoctypes = new Set<string>()
  let cleanupFns: Array<() => void> = []
  let resubscribeTimers: number[] = []
  let healthCheckInFlight: Promise<boolean> | null = null
  let running = false

  function getRealtime() {
    return window.frappe?.realtime || null
  }

  function uniqueObjects(items: any[]) {
    const seen = new Set<any>()
    return items.filter((item) => {
      if (!item || seen.has(item)) return false
      seen.add(item)
      return true
    })
  }

  function getSocketCandidates() {
    const realtime = getRealtime()
    const candidates = [
      realtime?.socket,
      realtime?.socketio,
      realtime?._socket,
      realtime?.io?.socket,
      window.frappe?.socketio,
      window.frappe?.socket,
      window.socketio,
    ]

    return uniqueObjects(candidates).filter((socket) => {
      return typeof socket?.emit === 'function' || typeof socket?.on === 'function'
    })
  }

  function isConnected() {
    const realtime = getRealtime()

    return Boolean(
      realtime?.isConnected?.()
      || getSocketCandidates().some((socket) => socket?.connected)
    )
  }

  function ensureConnected() {
    const realtime = getRealtime()

    if (!realtime) {
      ready.value = false
      status.value = 'Live unavailable'
      return false
    }

    if (isConnected()) {
      ready.value = true
      status.value = 'Live'
      return true
    }

    ready.value = false
    status.value = 'Connecting'

    try {
      realtime.connect?.()
    } catch (err) {
      status.value = 'Offline'
      console.warn('[verto raven realtime] realtime connect failed', err)
    }

    return isConnected()
  }

  async function ensureHealthy() {
    if (healthCheckInFlight) {
      return healthCheckInFlight
    }

    const realtime = getRealtime()

    if (!realtime || !isConnected()) {
      ensureConnected()
      return false
    }

    if (typeof realtime.ping !== 'function') {
      ready.value = true
      status.value = 'Live'
      return true
    }

    status.value = 'Checking live'

    healthCheckInFlight = Promise.resolve(realtime.ping(5000))
      .then((healthy) => {
        if (!running) return false

        if (healthy) {
          ready.value = true
          status.value = 'Live'
          return true
        }

        ready.value = false
        status.value = 'Reconnecting'

        try {
          realtime.disconnect?.()
          realtime.connect?.()
        } catch (err) {
          status.value = 'Offline'
          console.warn('[verto raven realtime] health reconnect failed', err)
        }

        return false
      })
      .catch((err) => {
        if (running) {
          ready.value = false
          status.value = 'Offline'
        }

        console.warn('[verto raven realtime] health check failed', err)
        return false
      })
      .finally(() => {
        healthCheckInFlight = null
      })

    return healthCheckInFlight
  }

  function getEventTargets() {
    const realtime = getRealtime()

    if (typeof realtime?.on === 'function') {
      return [realtime]
    }

    return getSocketCandidates()
      .filter((target) => typeof target?.on === 'function')
      .slice(0, 1)
  }

  function emitToAll(event: string, ...args: any[]) {
    const realtime = getRealtime()

    if (typeof realtime?.emit === 'function') {
      try {
        realtime.emit(event, ...args)
        return true
      } catch (err) {
        console.warn('[verto raven realtime] realtime emit failed', event, err)
      }
    }

    const socket = getSocketCandidates()[0]

    if (!socket) {
      return false
    }

    try {
      socket.emit?.(event, ...args)
      return true
    } catch (err) {
      console.warn('[verto raven realtime] socket emit failed', event, err)
      return false
    }
  }

  function callRealtimeMethod(method: string, ...args: any[]) {
    const realtime = getRealtime()

    if (typeof realtime?.[method] === 'function') {
      try {
        realtime[method](...args)
        return true
      } catch (err) {
        console.warn('[verto raven realtime] realtime method failed', method, err)
      }
    }

    return false
  }

  function onAll(event: string, handler: (payload: any) => void) {
    for (const target of getEventTargets()) {
      try {
        target.on(event, handler)
        cleanupFns.push(() => {
          try {
            target.off?.(event, handler)
          } catch {
            // ignored
          }
        })
      } catch (err) {
        console.warn('[verto raven realtime] event bind failed', event, err)
      }
    }
  }

  function getEventChannel(event: any) {
    return String(
      event?.channel_id ||
        event?.message_details?.channel_id ||
        event?.message?.channel_id ||
        event?.doc?.channel_id ||
        event?.channel ||
        ''
    ).trim()
  }

  function isActiveChannel(eventChannel: string) {
    if (!eventChannel) return false

    return [options.channelId.value, options.threadChannelId?.value]
      .filter(Boolean)
      .map((value) => String(value))
      .includes(eventChannel)
  }

  function subscribeDoctypeRoom(doctype: string) {
    const value = String(doctype || '').trim()
    if (!value) return

    subscribedDoctypes.add(value)

    const usedMethod = callRealtimeMethod('doctype_subscribe', value)

    if (!usedMethod) {
      emitToAll('doctype_subscribe', value)
    }

  }

  function unsubscribeDoctypeRoom(doctype: string) {
    const value = String(doctype || '').trim()
    if (!value) return

    subscribedDoctypes.delete(value)

    const usedMethod = callRealtimeMethod('doctype_unsubscribe', value)

    if (!usedMethod) {
      emitToAll('doctype_unsubscribe', value)
    }
  }

  function subscribeChannelDoc(channelId?: string) {
    const channel = String(channelId || '').trim()
    if (!channel) return

    subscribedDocs.add(channel)

    const usedSubscribeMethod = callRealtimeMethod('doc_subscribe', RAVEN_CHANNEL_DOCTYPE, channel)
    const usedOpenMethod = callRealtimeMethod('doc_open', RAVEN_CHANNEL_DOCTYPE, channel)

    if (!usedSubscribeMethod) {
      emitToAll('doc_subscribe', RAVEN_CHANNEL_DOCTYPE, channel)
    }

    if (!usedOpenMethod) {
      emitToAll('doc_open', RAVEN_CHANNEL_DOCTYPE, channel)
    }

  }

  function unsubscribeChannelDoc(channelId?: string) {
    const channel = String(channelId || '').trim()
    if (!channel) return

    subscribedDocs.delete(channel)

    const usedUnsubscribeMethod = callRealtimeMethod(
      'doc_unsubscribe',
      RAVEN_CHANNEL_DOCTYPE,
      channel
    )
    const usedCloseMethod = callRealtimeMethod(
      'doc_close',
      RAVEN_CHANNEL_DOCTYPE,
      channel
    )

    if (!usedUnsubscribeMethod) {
      emitToAll('doc_unsubscribe', RAVEN_CHANNEL_DOCTYPE, channel)
    }

    if (!usedCloseMethod) {
      emitToAll('doc_close', RAVEN_CHANNEL_DOCTYPE, channel)
    }
  }

  function clearResubscribeTimers() {
    for (const timer of resubscribeTimers) {
      window.clearTimeout(timer)
    }

    resubscribeTimers = []
  }

  function scheduleResubscribeBursts() {
    clearResubscribeTimers()

    for (const delay of [0, 1000]) {
      const timer = window.setTimeout(() => {
        resubscribeAll()
      }, delay)

      resubscribeTimers.push(timer)
    }
  }

  function resubscribeAll() {
    subscribeDoctypeRoom(RAVEN_GLOBAL_DOCTYPE_ROOM)
    subscribeDoctypeRoom(RAVEN_CHANNEL_DOCTYPE)
    subscribeChannelDoc(options.channelId.value)
    subscribeChannelDoc(options.threadChannelId?.value)
  }

  function handleConnect() {
    ready.value = true
    status.value = 'Checking live'

    scheduleResubscribeBursts()
    void ensureHealthy()
  }

  function handleDisconnect() {
    ready.value = false
    status.value = 'Offline'
  }

  function handleConnectError() {
    ready.value = false
    status.value = 'Offline'
  }

  function handleReconnect() {
    ready.value = true
    status.value = 'Checking live'
    scheduleResubscribeBursts()
    void ensureHealthy()
  }

  function handleMessageCreated(event: any) {
    const eventChannel = getEventChannel(event)
    lastEvent.value = 'message_created'

    if (!isActiveChannel(eventChannel)) return

    const message = event?.message_details || event?.message || event?.doc

    if (message) {
      options.onMessageCreated?.(normaliseRavenMessage(message), event)
      return
    }

    options.onChannelUpdated?.(eventChannel, event)
  }

  function handleMessageEdited(event: any) {
    const eventChannel = getEventChannel(event)
    lastEvent.value = 'message_edited'

    if (!isActiveChannel(eventChannel)) return

    options.onMessageEdited?.(
      event?.message_id || event?.message_details?.name || '',
      event?.message_details || {},
      event
    )
  }

  function handleMessageDeleted(event: any) {
    const eventChannel = getEventChannel(event)
    lastEvent.value = 'message_deleted'

    if (!isActiveChannel(eventChannel)) return
    options.onMessageDeleted?.(event?.message_id || event?.name || '', event)
  }

  function handleMessageReacted(event: any) {
    const eventChannel = getEventChannel(event)
    lastEvent.value = 'message_reacted'

    if (eventChannel && !isActiveChannel(eventChannel)) return
    options.onMessageReacted?.(event?.message_id || '', event?.reactions, event)
  }

  function handleMessageSaved(event: any) {
    const eventChannel = getEventChannel(event)
    lastEvent.value = 'message_saved'

    if (eventChannel && !isActiveChannel(eventChannel)) return
    options.onMessageSaved?.(event?.message_id || '', event?.liked_by || '', event)
  }

  function handleChannelUpdated(event: any) {
    const eventChannel = getEventChannel(event)
    lastEvent.value = 'raven:unread_channel_count_updated'

    if (!eventChannel) return

    if (event?.is_thread) {
      options.onThreadReply?.(eventChannel, event)
      return
    }

    if (eventChannel === options.channelId.value || eventChannel === options.threadChannelId?.value) {
      options.onChannelUpdated?.(eventChannel, event)
    }
  }

  function handleThreadReply(event: any) {
    const eventChannel = getEventChannel(event)
    lastEvent.value = 'thread_reply'

    if (!eventChannel) return
    options.onThreadReply?.(eventChannel, event)
  }

  function handleVertoBridgeEvent(event: any) {
    const eventChannel = getEventChannel(event)

    if (!isActiveChannel(eventChannel)) {
      return
    }

    lastEvent.value = VERTO_RAVEN_BRIDGE_EVENT

    if (String(event?.action || '').toLowerCase() === 'delete') {
      options.onMessageDeleted?.(
        event?.message_id || event?.name || '',
        event
      )
      return
    }

    if (event?.message) {
      options.onMessageCreated?.(
        normaliseRavenMessage(event.message),
        event
      )
      return
    }

    options.onChannelUpdated?.(eventChannel, event)
  }

  function bindEvents() {
    cleanupFns.forEach((fn) => fn())
    cleanupFns = []
    onAll('message_created', handleMessageCreated)
    onAll(VERTO_RAVEN_BRIDGE_EVENT, handleVertoBridgeEvent)
    onAll('message_edited', handleMessageEdited)
    onAll('message_deleted', handleMessageDeleted)
    onAll('message_reacted', handleMessageReacted)
    onAll('message_saved', handleMessageSaved)
    onAll('raven:unread_channel_count_updated', handleChannelUpdated)
    onAll('thread_reply', handleThreadReply)
    onAll('ai_event', (event) => {
      lastEvent.value = 'ai_event'
      options.onAiEvent?.(event)
    })
    onAll('ai_event_clear', (event) => {
      lastEvent.value = 'ai_event_clear'
      options.onAiEventClear?.(event)
    })

    for (const socket of getSocketCandidates()) {
      try {
        socket.on?.('connect', handleConnect)
        socket.on?.('connect_error', handleConnectError)
        socket.on?.('disconnect', handleDisconnect)
        socket.io?.on?.('reconnect', handleReconnect)
        cleanupFns.push(() => socket.off?.('connect', handleConnect))
        cleanupFns.push(() => socket.off?.('connect_error', handleConnectError))
        cleanupFns.push(() => socket.off?.('disconnect', handleDisconnect))
        cleanupFns.push(() => socket.io?.off?.('reconnect', handleReconnect))
      } catch (err) {
        console.warn('[verto raven realtime] connection bind failed', err)
      }
    }

  }

  function start() {
    running = true
    const realtime = getRealtime()
    const sockets = getSocketCandidates()

    if (!realtime && sockets.length === 0) {
      ready.value = false
      status.value = 'Live unavailable'
      console.warn('[verto raven realtime] no realtime object or socket candidates found')
      return
    }

    bindEvents()
    if (ensureConnected()) {
      void ensureHealthy()
    }
    scheduleResubscribeBursts()
  }

  function stop() {
    running = false
    clearResubscribeTimers()
    cleanupFns.forEach((fn) => fn())
    cleanupFns = []

    for (const channel of [...subscribedDocs]) {
      unsubscribeChannelDoc(channel)
    }

    for (const doctype of [...subscribedDoctypes]) {
      unsubscribeDoctypeRoom(doctype)
    }

    try {
      getRealtime()?.disconnect?.()
    } catch (err) {
      console.warn('[verto raven realtime] disconnect failed', err)
    }

    ready.value = false
    status.value = 'Stopped'
  }

  watch(
    () => options.channelId.value,
    (newChannel, oldChannel) => {
      if (oldChannel) unsubscribeChannelDoc(oldChannel)
      if (newChannel) {
        subscribeChannelDoc(newChannel)
        scheduleResubscribeBursts()
      }
    }
  )

  if (options.threadChannelId) {
    watch(
      () => options.threadChannelId?.value,
      (newChannel, oldChannel) => {
        if (oldChannel) unsubscribeChannelDoc(oldChannel)
        if (newChannel) {
          subscribeChannelDoc(newChannel)
          scheduleResubscribeBursts()
        }
      }
    )
  }

  onBeforeUnmount(stop)

  return {
    ready,
    status,
    lastEvent,
    start,
    stop,
    isConnected,
    ensureConnected,
    ensureHealthy,
    subscribeChannelDoc,
    unsubscribeChannelDoc,
    resubscribeAll,
  }
}
