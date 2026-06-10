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
const RAVEN_NATIVE_EVENTS = new Set([
  'message_created',
  'message_edited',
  'message_deleted',
  'message_reacted',
  'message_saved',
  'raven:unread_channel_count_updated',
  'thread_reply',
  'ai_event',
  'ai_event_clear',
])

export function useRavenRealtime(options: RavenRealtimeOptions) {
  const ready = ref(false)
  const status = ref('Connecting')
  const lastEvent = ref('')

  const subscribedDocs = new Set<string>()
  const subscribedDoctypes = new Set<string>()
  const boundTargets = new WeakSet<object>()

  let cleanupFns: Array<() => void> = []
  let resubscribeTimers: number[] = []

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

  function getEventTargets() {
    const realtime = getRealtime()
    return uniqueObjects([realtime, ...getSocketCandidates()]).filter((target) => {
      return typeof target?.on === 'function'
    })
  }

  function emitToAll(event: string, ...args: any[]) {
    const realtime = getRealtime()
    let emitted = false

    if (typeof realtime?.emit === 'function') {
      try {
        realtime.emit(event, ...args)
        emitted = true
      } catch (err) {
        console.warn('[verto raven realtime] realtime emit failed', event, err)
      }
    }

    for (const socket of getSocketCandidates()) {
      if (socket === realtime) continue

      try {
        socket.emit?.(event, ...args)
        emitted = true
      } catch (err) {
        console.warn('[verto raven realtime] socket emit failed', event, err)
      }
    }

    return emitted
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

  function bindAnyListeners() {
    for (const socket of getSocketCandidates()) {
      if (boundTargets.has(socket)) continue
      boundTargets.add(socket)

      if (typeof socket.onAny === 'function') {
        const anyHandler = (eventName: string, payload: any) => {
          if (!RAVEN_NATIVE_EVENTS.has(eventName)) return

          console.log('[verto raven realtime] raw socket event', eventName, payload)
          lastEvent.value = eventName
          dispatchRavenEvent(eventName, payload)
        }

        socket.onAny(anyHandler)
        cleanupFns.push(() => {
          try {
            socket.offAny?.(anyHandler)
          } catch {
            // ignored
          }
        })
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
    emitToAll('doctype_subscribe', value)

    console.log('[verto raven realtime] subscribed doctype room', {
      doctype: value,
      usedMethod,
      sockets: getSocketCandidates().length,
    })
  }

  function unsubscribeDoctypeRoom(doctype: string) {
    const value = String(doctype || '').trim()
    if (!value) return

    subscribedDoctypes.delete(value)

    callRealtimeMethod('doctype_unsubscribe', value)
    emitToAll('doctype_unsubscribe', value)
  }

  function subscribeChannelDoc(channelId?: string) {
    const channel = String(channelId || '').trim()
    if (!channel) return

    subscribedDocs.add(channel)

    const usedSubscribeMethod = callRealtimeMethod('doc_subscribe', RAVEN_CHANNEL_DOCTYPE, channel)
    const usedOpenMethod = callRealtimeMethod('doc_open', RAVEN_CHANNEL_DOCTYPE, channel)

    emitToAll('doc_subscribe', RAVEN_CHANNEL_DOCTYPE, channel)
    emitToAll('doc_open', RAVEN_CHANNEL_DOCTYPE, channel)

    console.log('[verto raven realtime] subscribed channel doc', {
      doctype: RAVEN_CHANNEL_DOCTYPE,
      channel,
      usedSubscribeMethod,
      usedOpenMethod,
      sockets: getSocketCandidates().length,
    })
  }

  function unsubscribeChannelDoc(channelId?: string) {
    const channel = String(channelId || '').trim()
    if (!channel) return

    subscribedDocs.delete(channel)

    callRealtimeMethod('doc_unsubscribe', RAVEN_CHANNEL_DOCTYPE, channel)
    callRealtimeMethod('doc_close', RAVEN_CHANNEL_DOCTYPE, channel)

    emitToAll('doc_unsubscribe', RAVEN_CHANNEL_DOCTYPE, channel)
    emitToAll('doc_close', RAVEN_CHANNEL_DOCTYPE, channel)
  }

  function clearResubscribeTimers() {
    for (const timer of resubscribeTimers) {
      window.clearTimeout(timer)
    }

    resubscribeTimers = []
  }

  function scheduleResubscribeBursts() {
    clearResubscribeTimers()

    for (const delay of [0, 250, 1000, 3000]) {
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
    status.value = 'Live'
    console.log('[verto raven realtime] connected', {
      sockets: getSocketCandidates().length,
      activeChannel: options.channelId.value,
      activeThread: options.threadChannelId?.value,
    })

    bindAnyListeners()
    scheduleResubscribeBursts()
  }

  function handleDisconnect() {
    ready.value = false
    status.value = 'Offline'
    console.log('[verto raven realtime] disconnected')
  }

  function handleReconnect() {
    ready.value = true
    status.value = 'Live'
    console.log('[verto raven realtime] reconnected')
    bindAnyListeners()
    scheduleResubscribeBursts()
  }

  function handleMessageCreated(event: any) {
    const eventChannel = getEventChannel(event)
    console.log('[verto raven realtime] message_created', { eventChannel, event })
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
    console.log('[verto raven realtime] message_edited', { eventChannel, event })
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
    console.log('[verto raven realtime] message_deleted', { eventChannel, event })
    lastEvent.value = 'message_deleted'

    if (!isActiveChannel(eventChannel)) return
    options.onMessageDeleted?.(event?.message_id || event?.name || '', event)
  }

  function handleMessageReacted(event: any) {
    const eventChannel = getEventChannel(event)
    console.log('[verto raven realtime] message_reacted', { eventChannel, event })
    lastEvent.value = 'message_reacted'

    if (eventChannel && !isActiveChannel(eventChannel)) return
    options.onMessageReacted?.(event?.message_id || '', event?.reactions, event)
  }

  function handleMessageSaved(event: any) {
    const eventChannel = getEventChannel(event)
    console.log('[verto raven realtime] message_saved', { eventChannel, event })
    lastEvent.value = 'message_saved'

    if (eventChannel && !isActiveChannel(eventChannel)) return
    options.onMessageSaved?.(event?.message_id || '', event?.liked_by || '', event)
  }

  function handleChannelUpdated(event: any) {
    const eventChannel = getEventChannel(event)
    console.log('[verto raven realtime] raven channel update', { eventChannel, event })
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
    console.log('[verto raven realtime] thread_reply', { eventChannel, event })
    lastEvent.value = 'thread_reply'

    if (!eventChannel) return
    options.onThreadReply?.(eventChannel, event)
  }

  function dispatchRavenEvent(eventName: string, event: any) {
    switch (eventName) {
      case 'message_created':
        handleMessageCreated(event)
        break
      case 'message_edited':
        handleMessageEdited(event)
        break
      case 'message_deleted':
        handleMessageDeleted(event)
        break
      case 'message_reacted':
        handleMessageReacted(event)
        break
      case 'message_saved':
        handleMessageSaved(event)
        break
      case 'raven:unread_channel_count_updated':
        handleChannelUpdated(event)
        break
      case 'thread_reply':
        handleThreadReply(event)
        break
      case 'ai_event':
        options.onAiEvent?.(event)
        break
      case 'ai_event_clear':
        options.onAiEventClear?.(event)
        break
      default:
        break
    }
  }

  function bindEvents() {
    cleanupFns.forEach((fn) => fn())
    cleanupFns = []
    onAll('message_created', handleMessageCreated)
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
        socket.on?.('disconnect', handleDisconnect)
        socket.io?.on?.('reconnect', handleReconnect)
        cleanupFns.push(() => socket.off?.('connect', handleConnect))
        cleanupFns.push(() => socket.off?.('disconnect', handleDisconnect))
        cleanupFns.push(() => socket.io?.off?.('reconnect', handleReconnect))
      } catch (err) {
        console.warn('[verto raven realtime] connection bind failed', err)
      }
    }

    bindAnyListeners()
  }

  function start() {
    const realtime = getRealtime()
    const sockets = getSocketCandidates()

    if (!realtime && sockets.length === 0) {
      ready.value = false
      status.value = 'Live unavailable'
      console.warn('[verto raven realtime] no realtime object or socket candidates found')
      return
    }

    bindEvents()

    if (typeof realtime?.connect === 'function') {
      try {
        realtime.connect()
      } catch (err) {
        console.warn('[verto raven realtime] realtime connect failed', err)
      }
    }

    ready.value = true
    status.value = 'Live'
    console.log('[verto raven realtime] started', {
      sockets: sockets.length,
      activeChannel: options.channelId.value,
      activeThread: options.threadChannelId?.value,
      hasRealtimeEmit: typeof realtime?.emit === 'function',
      hasRealtimeOn: typeof realtime?.on === 'function',
    })

    scheduleResubscribeBursts()
  }

  function stop() {
    clearResubscribeTimers()
    cleanupFns.forEach((fn) => fn())
    cleanupFns = []

    for (const channel of [...subscribedDocs]) {
      unsubscribeChannelDoc(channel)
    }

    for (const doctype of [...subscribedDoctypes]) {
      unsubscribeDoctypeRoom(doctype)
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
    subscribeChannelDoc,
    unsubscribeChannelDoc,
    resubscribeAll,
  }
}
