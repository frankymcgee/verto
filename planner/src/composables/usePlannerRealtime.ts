import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Manager } from 'socket.io-client'
import { ALL_PLANNER_SCOPES, createLiveRefreshQueue, type PlannerScope } from '../utils/liveRefreshQueue'

export function plannerSiteName() {
  const embedded = document.querySelector<HTMLMetaElement>('meta[name="frappe-site-name"]')?.content
  return [embedded, window.location.hostname].find((value) => value && /^[\w-][\w.-]*$/.test(value)) || ''
}

export function usePlannerRealtime(options: {
  refresh: (scopes: Set<PlannerScope>) => Promise<void>
  ready: () => boolean
}) {
  const status = ref('Connecting')
  const refreshing = ref(false)
  const lastUpdated = ref<Date | null>(null)
  let socket: ReturnType<Manager['socket']> | undefined
  let subscribed = false
  let stopped = false
  let subscriptionPending = false
  let subscriptionAttempt = 0
  let recoveryTimer: ReturnType<typeof setInterval> | undefined
  let lastRecovery = Date.now()

  const queue = createLiveRefreshQueue({
    canRun: () => navigator.onLine && document.visibilityState === 'visible' && options.ready(),
    async refresh(scopes) {
      refreshing.value = true
      try {
        await options.refresh(scopes)
        lastUpdated.value = new Date()
        if (subscribed) status.value = 'Live'
      } finally {
        refreshing.value = false
      }
    },
    onError() { status.value = 'Refresh failed — retrying' },
  })

  function requestAll() {
    lastRecovery = Date.now()
    queue.request(ALL_PLANNER_SCOPES)
  }

  function subscribe() {
    if (!socket?.connected || subscriptionPending || subscribed || stopped) return
    subscriptionPending = true
    const attempt = ++subscriptionAttempt
    status.value = 'Connecting'
    socket.timeout(8000).emit('verto:planner_subscribe', (error: Error | null, response?: { ok?: boolean }) => {
      if (stopped || attempt !== subscriptionAttempt) return
      subscriptionPending = false
      subscribed = !error && response?.ok === true
      status.value = subscribed ? 'Live' : 'Live unavailable — retrying'
      // Subscription is acknowledged only after joining the room. Refresh then
      // to close the initial-load/reconnect gap, including edits made while away.
      if (subscribed) requestAll()
    })
  }

  function onConnect() { subscribed = false; subscriptionPending = false; subscribe() }
  function onDisconnect() {
    subscribed = false
    subscriptionPending = false
    subscriptionAttempt++
    status.value = navigator.onLine ? 'Reconnecting' : 'Offline'
  }
  function onChange(event: { scope?: PlannerScope }) {
    if (event?.scope && ALL_PLANNER_SCOPES.includes(event.scope)) queue.request([event.scope])
  }
  function recover() {
    if (stopped || !navigator.onLine || document.visibilityState !== 'visible') return
    if (!socket?.connected) socket?.connect()
    else subscribe()
    requestAll()
    queue.resume()
  }

  watch(options.ready, (ready) => { if (ready) queue.resume() })

  onMounted(() => {
    const manager = new Manager(window.location.origin, {
      path: '/socket.io', withCredentials: true, autoConnect: false,
      reconnection: true, reconnectionDelay: 1000, reconnectionDelayMax: 10_000,
    })
    socket = manager.socket(`/${plannerSiteName()}`)
    socket.on('connect', onConnect)
    socket.on('disconnect', onDisconnect)
    socket.on('connect_error', onDisconnect)
    socket.on('verto:planner_changed', onChange)
    socket.connect()
    document.addEventListener('visibilitychange', recover)
    window.addEventListener('online', recover)
    window.addEventListener('offline', onDisconnect)
    window.addEventListener('pageshow', recover)
    recoveryTimer = setInterval(() => {
      if (!navigator.onLine || document.visibilityState !== 'visible') return
      if (!socket?.connected) socket?.connect()
      else subscribe()
      // Quiet recovery only; normal collaboration is driven by committed events.
      if (Date.now() - lastRecovery >= (subscribed ? 5 * 60_000 : 60_000)) requestAll()
    }, 30_000)
  })

  onBeforeUnmount(() => {
    stopped = true
    subscriptionAttempt++
    queue.stop()
    clearInterval(recoveryTimer)
    document.removeEventListener('visibilitychange', recover)
    window.removeEventListener('online', recover)
    window.removeEventListener('offline', onDisconnect)
    window.removeEventListener('pageshow', recover)
    socket?.emit('verto:planner_unsubscribe')
    socket?.removeAllListeners()
    socket?.disconnect()
  })

  return { status, refreshing, lastUpdated, refresh: requestAll }
}
