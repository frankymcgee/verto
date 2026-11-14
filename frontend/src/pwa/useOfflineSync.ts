// VERTO_OFFLINE_SYNC_MANAGER_2026_08_24

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useMobileBoot } from '../lib/mobileBoot'
import {
  getOfflineQueueSummary,
  syncOfflineQueue,
  type OfflineQueueSummary,
} from './offlineQueue'
import { primeOfflineData } from './offlineBootstrap'

const LAST_OFFLINE_REFRESH_KEY = 'verto:offline-last-refresh-at'
const { user } = useMobileBoot()

const isOnline = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
const isSyncing = ref(false)
const isPriming = ref(false)
const showReadyConfirmation = ref(false)
const lastOfflineRefreshAt = ref(readLastOfflineRefreshAt())
const offlineRefreshError = ref('')
const lastSyncMessage = ref('')
const emptySummary: OfflineQueueSummary = {
  queued: 0,
  syncing: 0,
  failed: 0,
  total: 0,
}
const summary = ref(emptySummary)

let refreshTimer: number | undefined
let autoSyncTimer: number | undefined
let primeTimer: number | undefined
let readyConfirmationTimer: number | undefined
let watcherCount = 0
let syncPromise: Promise<void> | null = null

watch(user, () => {
  summary.value = emptySummary
  lastSyncMessage.value = ''
  if (watcherCount > 0) void initialiseOfflineSync()
})

function readLastOfflineRefreshAt() {
  if (typeof window === 'undefined') return ''

  try {
    return String(window.localStorage.getItem(LAST_OFFLINE_REFRESH_KEY) || '')
  } catch {
    return ''
  }
}

function saveLastOfflineRefreshAt(value: string) {
  lastOfflineRefreshAt.value = value

  try {
    window.localStorage.setItem(LAST_OFFLINE_REFRESH_KEY, value)
  } catch {
    // The current session can still display the successful refresh time.
  }
}

function brieflyShowReadyConfirmation() {
  showReadyConfirmation.value = true

  if (readyConfirmationTimer) {
    window.clearTimeout(readyConfirmationTimer)
  }

  readyConfirmationTimer = window.setTimeout(() => {
    showReadyConfirmation.value = false
    readyConfirmationTimer = undefined
  }, 5000)
}

async function refreshSummary() {
  const actor = user.value
  try {
    const counts = await getOfflineQueueSummary(actor)
    if (user.value === actor) summary.value = counts
  } catch (err) {
    console.warn('[verto offline sync] Could not read queue summary', err)
  }
}

async function primeNow(options: { showConfirmation?: boolean } = {}) {
  if (!isOnline.value || isPriming.value) {
    return false
  }

  isPriming.value = true
  offlineRefreshError.value = ''

  try {
    const bootstrap = await primeOfflineData()

    if (!bootstrap) {
      return false
    }

    saveLastOfflineRefreshAt(new Date().toISOString())

    if (options.showConfirmation !== false) {
      brieflyShowReadyConfirmation()
    }

    return true
  } catch (err) {
    offlineRefreshError.value = 'Could not update offline data. Check your connection and try again.'
    console.warn('[verto offline sync] Could not refresh offline dataset', err)
    return false
  } finally {
    isPriming.value = false
  }
}

function syncNow(options: { refreshOffline?: boolean } = {}) {
  if (syncPromise) return syncPromise
  syncPromise = performSync(options).finally(() => { syncPromise = null })
  return syncPromise
}

async function performSync(options: { refreshOffline?: boolean }) {
  const actor = user.value
  isSyncing.value = true
  lastSyncMessage.value = ''

  try {
    const result = await syncOfflineQueue(actor)
    if (user.value !== actor) return

    if (result.skipped) {
      lastSyncMessage.value = 'Offline — queued items will sync when connection returns.'
    } else if (result.failed > 0) {
      lastSyncMessage.value = `${result.synced} synced, ${result.failed} failed.`
    } else if (result.synced > 0) {
      lastSyncMessage.value = `${result.synced} queued item${result.synced === 1 ? '' : 's'} synced.`
      if (options.refreshOffline !== false) await primeNow()
    }
  } catch (err) {
    if (user.value === actor) lastSyncMessage.value = err instanceof Error ? err.message : 'Sync failed.'
  } finally {
    isSyncing.value = false
    await refreshSummary()
  }
}

async function resumeQueuedWork() {
  isOnline.value = navigator.onLine
  await refreshSummary()
  if (isOnline.value && (summary.value.queued > 0 || summary.value.failed > 0)) {
    await syncNow({ refreshOffline: false })
  }
}

async function initialiseOfflineSync() {
  const actor = user.value
  await resumeQueuedWork()
  if (isOnline.value && actor && actor !== 'Guest' && actor === user.value) {
    await primeNow()
  }
}

function handleForeground() {
  if (document.visibilityState === 'visible') void resumeQueuedWork()
}

function handleOffline() {
  isOnline.value = false
  lastSyncMessage.value = 'Offline mode active. Forms and cached shifts remain available.'
  void refreshSummary()
}

function handleQueueUpdated() {
  void refreshSummary()
}

function handleServiceWorkerMessage(event: MessageEvent) {
  if (event.data?.type === 'VERTO_OFFLINE_QUEUE_UPDATED') {
    void refreshSummary()
  }
}

function startOfflineSyncWatcher() {
  watcherCount += 1

  if (watcherCount > 1) {
    void refreshSummary()
    return
  }

  void initialiseOfflineSync()

  window.addEventListener('online', initialiseOfflineSync)
  window.addEventListener('offline', handleOffline)
  window.addEventListener('pageshow', handleForeground)
  document.addEventListener('visibilitychange', handleForeground)
  window.addEventListener('verto:offline-queue-updated', handleQueueUpdated)
  window.addEventListener('verto:offline-queue-synced', handleQueueUpdated)
  navigator.serviceWorker?.addEventListener('message', handleServiceWorkerMessage)

  refreshTimer = window.setInterval(() => {
    void refreshSummary()
  }, 5000)

  autoSyncTimer = window.setInterval(() => {
    if (navigator.onLine && (summary.value.queued > 0 || summary.value.failed > 0)) {
      void syncNow()
    }
  }, 30000)

  primeTimer = window.setInterval(() => {
    if (navigator.onLine && user.value && user.value !== 'Guest' && document.visibilityState === 'visible' && !isSyncing.value) {
      void primeNow({ showConfirmation: false })
    }
  }, 15 * 60 * 1000)
}

function stopOfflineSyncWatcher() {
  watcherCount = Math.max(0, watcherCount - 1)

  if (watcherCount > 0) {
    return
  }

  window.removeEventListener('online', initialiseOfflineSync)
  window.removeEventListener('offline', handleOffline)
  window.removeEventListener('pageshow', handleForeground)
  document.removeEventListener('visibilitychange', handleForeground)
  window.removeEventListener('verto:offline-queue-updated', handleQueueUpdated)
  window.removeEventListener('verto:offline-queue-synced', handleQueueUpdated)
  navigator.serviceWorker?.removeEventListener('message', handleServiceWorkerMessage)

  if (refreshTimer) {
    window.clearInterval(refreshTimer)
    refreshTimer = undefined
  }

  if (autoSyncTimer) {
    window.clearInterval(autoSyncTimer)
    autoSyncTimer = undefined
  }

  if (primeTimer) {
    window.clearInterval(primeTimer)
    primeTimer = undefined
  }
}

export function useOfflineSync() {
  onMounted(() => {
    startOfflineSyncWatcher()
  })

  onBeforeUnmount(() => {
    stopOfflineSyncWatcher()
  })

  const hasQueuedItems = computed(() => summary.value.total > 0)
  const statusLabel = computed(() => {
    if (!isOnline.value) {
      return summary.value.total > 0
        ? `${summary.value.total} item${summary.value.total === 1 ? '' : 's'} saved offline`
        : 'Offline mode'
    }

    if (isSyncing.value) {
      return 'Syncing offline work...'
    }

    if (summary.value.failed > 0) {
      return `${summary.value.failed} item${summary.value.failed === 1 ? '' : 's'} failed to sync`
    }

    if (summary.value.queued > 0) {
      return `${summary.value.queued} item${summary.value.queued === 1 ? '' : 's'} waiting to sync`
    }

    if (summary.value.syncing > 0) {
      return 'Syncing offline work...'
    }

    if (isPriming.value) {
      return lastOfflineRefreshAt.value
        ? 'Refreshing offline data...'
        : 'Preparing offline data...'
    }

    if (offlineRefreshError.value) {
      return 'Offline data refresh failed'
    }

    return lastOfflineRefreshAt.value
      ? 'Offline data ready'
      : 'Offline data not prepared'
  })

  return {
    isOnline,
    isSyncing,
    isPriming,
    showReadyConfirmation,
    lastOfflineRefreshAt,
    offlineRefreshError,
    summary,
    hasQueuedItems,
    statusLabel,
    lastSyncMessage,
    refreshSummary,
    syncNow,
    primeNow,
  }
}
