<!-- VERTO_PWA_STAGE2_OFFLINE_SYNC_STATUS_2026_06_10 -->
<template>
  <div
    class="mx-auto w-full max-w-[var(--verto-shell-max-width,28rem)] px-[var(--verto-page-x,0.75rem)] pb-2"
  >
    <div
      role="status"
      aria-live="polite"
      class="flex items-center justify-between gap-3 rounded-xl border px-3 py-2 text-sm shadow-sm"
      :class="bannerClass"
    >
      <div class="min-w-0">
        <p class="truncate font-medium">
          {{ statusLabel }}
        </p>

        <p
          v-if="detailLabel"
          class="mt-0.5 text-xs opacity-80"
        >
          {{ detailLabel }}
        </p>
      </div>

      <button
        v-if="isOnline"
        type="button"
        class="shrink-0 rounded-lg bg-white/80 px-2.5 py-1 text-xs font-semibold text-ink-gray-8 shadow-sm active:scale-95 disabled:opacity-60"
        :disabled="isSyncing || isPriming"
        @click="handleAction"
      >
        {{ actionLabel }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useOfflineSync } from '../pwa/useOfflineSync'

const {
  isOnline,
  isSyncing,
  isPriming,
  lastOfflineRefreshAt,
  offlineRefreshError,
  summary,
  statusLabel,
  lastSyncMessage,
  syncNow,
  primeNow,
} = useOfflineSync()

const formattedRefreshTime = computed(() => {
  if (!lastOfflineRefreshAt.value) return ''

  const date = new Date(lastOfflineRefreshAt.value)

  if (Number.isNaN(date.getTime())) return ''

  return new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
})

const detailLabel = computed(() => {
  if (isPriming.value) {
    return 'Keep the app open until preparation finishes.'
  }

  if (offlineRefreshError.value) {
    const previousRefresh = formattedRefreshTime.value
      ? ` Last successful update: ${formattedRefreshTime.value}.`
      : ''

    return `${offlineRefreshError.value}${previousRefresh}`
  }

  if (!isOnline.value || isSyncing.value) {
    if (lastSyncMessage.value) return lastSyncMessage.value
  }

  if (summary.value.failed > 0) {
    return lastSyncMessage.value || 'Tap Sync now to retry the failed item.'
  }

  if (summary.value.total > 0) {
    return lastSyncMessage.value || 'Saved securely on this device until it can sync.'
  }

  if (formattedRefreshTime.value) {
    return `Updated ${formattedRefreshTime.value}`
  }

  return isOnline.value
    ? 'Refresh now to prepare forms and shifts for offline use.'
    : 'Connect once to prepare offline data on this device.'
})

const actionLabel = computed(() => {
  if (isSyncing.value) return 'Syncing'
  if (isPriming.value) return 'Refreshing'
  return summary.value.total > 0 ? 'Sync now' : 'Refresh'
})

function handleAction() {
  if (summary.value.total > 0) {
    void syncNow()
    return
  }

  void primeNow()
}

const bannerClass = computed(() => {
  if (!isOnline.value) {
    return 'border-amber-200 bg-amber-50 text-amber-900'
  }

  if (summary.value.failed > 0) {
    return 'border-red-200 bg-red-50 text-red-900'
  }

  if (offlineRefreshError.value) {
    return 'border-red-200 bg-red-50 text-red-900'
  }

  if (summary.value.total > 0 || isSyncing.value || isPriming.value) {
    return 'border-blue-200 bg-blue-50 text-blue-900'
  }

  if (lastOfflineRefreshAt.value) {
    return 'border-green-200 bg-green-50 text-green-900'
  }

  return 'border-outline-gray-2 bg-surface-white text-ink-gray-8'
})
</script>
