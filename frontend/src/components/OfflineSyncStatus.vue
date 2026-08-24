<!-- VERTO_PWA_STAGE2_OFFLINE_SYNC_STATUS_2026_06_10 -->
<template>
  <div
    v-if="shouldShow"
    class="mx-auto w-full max-w-[var(--verto-shell-max-width,28rem)] px-[var(--verto-page-x,0.75rem)] pb-2"
  >
    <div
      role="status"
      aria-live="polite"
      class="rounded-xl border px-3 py-2 text-sm shadow-sm"
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
  showReadyConfirmation,
  lastOfflineRefreshAt,
  offlineRefreshError,
  summary,
  statusLabel,
  lastSyncMessage,
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
    return lastSyncMessage.value || 'Open the profile menu to retry the failed item.'
  }

  if (summary.value.total > 0) {
    return lastSyncMessage.value || 'Saved securely on this device until it can sync.'
  }

  if (showReadyConfirmation.value && formattedRefreshTime.value) {
    return `Updated ${formattedRefreshTime.value}`
  }

  return ''
})

const shouldShow = computed(() => {
  return !isOnline.value ||
    isSyncing.value ||
    isPriming.value ||
    showReadyConfirmation.value ||
    Boolean(offlineRefreshError.value) ||
    summary.value.total > 0 ||
    summary.value.failed > 0
})

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

  if (showReadyConfirmation.value && lastOfflineRefreshAt.value) {
    return 'border-green-200 bg-green-50 text-green-900'
  }

  return 'border-outline-gray-2 bg-surface-white text-ink-gray-8'
})
</script>
