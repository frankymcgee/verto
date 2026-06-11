// VERTO_PWA_STAGE2_USE_OFFLINE_SYNC_2026_06_10

import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  getOfflineQueueSummary,
  syncOfflineQueue,
  type OfflineQueueSummary,
} from './offlineQueue'

const isOnline = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
const isSyncing = ref(false)
const lastSyncMessage = ref('')
const summary = ref<OfflineQueueSummary>({
  queued: 0,
  syncing: 0,
  failed: 0,
  total: 0,
})

let refreshTimer: number | undefined
let autoSyncTimer: number | undefined

async function refreshSummary() {
  try {
    summary.value = await getOfflineQueueSummary()
  } catch (err) {
    console.warn('[verto offline sync] Could not read queue summary', err)
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

function handleOnline() {
  isOnline.value = true
  void syncNow()
}

function handleOffline() {
  isOnline.value = false
  lastSyncMessage.value = 'Offline mode active.'
  void refreshSummary()
}

function handleQueueUpdated() {
  void refreshSummary()
}

function startOfflineSyncWatcher() {
  void refreshSummary()

  window.addEventListener('online', handleOnline)
  window.addEventListener('offline', handleOffline)
  window.addEventListener('verto:offline-queue-updated', handleQueueUpdated)
  window.addEventListener('verto:offline-queue-synced', handleQueueUpdated)

  refreshTimer = window.setInterval(() => {
    void refreshSummary()
  }, 5000)

  autoSyncTimer = window.setInterval(() => {
    if (navigator.onLine && summary.value.total > 0) {
      void syncNow()
    }
  }, 30000)
}

function stopOfflineSyncWatcher() {
  window.removeEventListener('online', handleOnline)
  window.removeEventListener('offline', handleOffline)
  window.removeEventListener('verto:offline-queue-updated', handleQueueUpdated)
  window.removeEventListener('verto:offline-queue-synced', handleQueueUpdated)

  if (refreshTimer) {
    window.clearInterval(refreshTimer)
    refreshTimer = undefined
  }

  if (autoSyncTimer) {
    window.clearInterval(autoSyncTimer)
    autoSyncTimer = undefined
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
        ? `${summary.value.total} item${summary.value.total === 1 ? '' : 's'} queued offline`
        : 'Offline'
    }

    if (isSyncing.value) {
      return 'Syncing...'
    }

    if (summary.value.failed > 0) {
      return `${summary.value.failed} item${summary.value.failed === 1 ? '' : 's'} failed to sync`
    }

    if (summary.value.total > 0) {
      return `${summary.value.total} item${summary.value.total === 1 ? '' : 's'} waiting to sync`
    }

    return 'Online'
  })

  return {
    isOnline,
    isSyncing,
    summary,
    hasQueuedItems,
    statusLabel,
    lastSyncMessage,
    refreshSummary,
    syncNow,
  }
}
