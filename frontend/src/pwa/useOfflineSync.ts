// VERTO_OFFLINE_SYNC_MANAGER_2026_08_24

import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  getOfflineQueueSummary,
  syncOfflineQueue,
  type OfflineQueueSummary,
} from './offlineQueue'
import { primeOfflineData } from './offlineBootstrap'

const LAST_OFFLINE_REFRESH_KEY = 'verto:offline-last-refresh-at'

const isOnline = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
const isSyncing = ref(false)
const isPriming = ref(false)
const lastOfflineRefreshAt = ref(readLastOfflineRefreshAt())
const offlineRefreshError = ref('')
const lastSyncMessage = ref('')
const summary = ref<OfflineQueueSummary>({
  queued: 0,
  syncing: 0,
  failed: 0,
  total: 0,
})

let refreshTimer: number | undefined
let autoSyncTimer: number | undefined
let primeTimer: number | undefined
let watcherCount = 0

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

async function refreshSummary() {
  try {
    summary.value = await getOfflineQueueSummary()
  } catch (err) {
    console.warn('[verto offline sync] Could not read queue summary', err)
  }
}

async function primeNow() {
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
    return true
  } catch (err) {
    offlineRefreshError.value = 'Could not update offline data. Check your connection and try again.'
    console.warn('[verto offline sync] Could not refresh offline dataset', err)
    return false
  } finally {
    isPriming.value = false
  }
}

async function syncNow() {
  if (isSyncing.value) {
    return
  }

  isSyncing.value = true
  lastSyncMessage.value = ''

  try {
    const result = await syncOfflineQueue()

    if (result.skipped) {
      lastSyncMessage.value = 'Offline — queued items will sync when connection returns.'
    } else if (result.failed > 0) {
      lastSyncMessage.value = `${result.synced} synced, ${result.failed} failed.`
    } else if (result.synced > 0) {
      lastSyncMessage.value = `${result.synced} queued item${result.synced === 1 ? '' : 's'} synced.`
      await primeNow()
    } else {
      lastSyncMessage.value = 'Everything is up to date.'
    }
  } catch (err) {
    lastSyncMessage.value = err instanceof Error ? err.message : 'Sync failed.'
  } finally {
    isSyncing.value = false
    await refreshSummary()
  }
}

async function handleOnline() {
  isOnline.value = true
  lastSyncMessage.value = 'Connection restored. Syncing offline work...'
  await primeNow()
  await syncNow()
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

async function initialiseOfflineSync() {
  await refreshSummary()

  if (!isOnline.value) return

  await primeNow()

  if (summary.value.total > 0) {
    await syncNow()
  }
}

function startOfflineSyncWatcher() {
  watcherCount += 1

  if (watcherCount > 1) {
    void refreshSummary()
    return
  }

  void initialiseOfflineSync()

  window.addEventListener('online', handleOnline)
  window.addEventListener('offline', handleOffline)
  window.addEventListener('verto:offline-queue-updated', handleQueueUpdated)
  window.addEventListener('verto:offline-queue-synced', handleQueueUpdated)
  navigator.serviceWorker?.addEventListener('message', handleServiceWorkerMessage)

  refreshTimer = window.setInterval(() => {
    void refreshSummary()
  }, 5000)

  autoSyncTimer = window.setInterval(() => {
    if (navigator.onLine && summary.value.total > 0) {
      void syncNow()
    }
  }, 30000)

  primeTimer = window.setInterval(() => {
    if (navigator.onLine) {
      void primeNow()
    }
  }, 15 * 60 * 1000)
}

function stopOfflineSyncWatcher() {
  watcherCount = Math.max(0, watcherCount - 1)

  if (watcherCount > 0) {
    return
  }

  window.removeEventListener('online', handleOnline)
  window.removeEventListener('offline', handleOffline)
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

    if (summary.value.total > 0) {
      return `${summary.value.total} item${summary.value.total === 1 ? '' : 's'} waiting to sync`
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
