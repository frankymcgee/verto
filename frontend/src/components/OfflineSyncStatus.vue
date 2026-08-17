<!-- VERTO_PWA_STAGE2_OFFLINE_SYNC_STATUS_2026_06_10 -->
<template>
  <div
    v-if="shouldShow"
    class="mx-auto w-full max-w-[var(--verto-shell-max-width,28rem)] px-[var(--verto-page-x,0.75rem)] pb-2"
  >
    <div
      class="flex items-center justify-between gap-3 rounded-xl border px-3 py-2 text-sm shadow-sm"
      :class="bannerClass"
    >
      <div class="min-w-0">
        <p class="truncate font-medium">
          {{ statusLabel }}
        </p>

        <p
          v-if="lastSyncMessage"
          class="mt-0.5 truncate text-xs opacity-80"
        >
          {{ lastSyncMessage }}
        </p>
      </div>

      <button
        v-if="isOnline && summary.total > 0"
        type="button"
        class="shrink-0 rounded-lg bg-white/80 px-2.5 py-1 text-xs font-semibold text-ink-gray-8 shadow-sm active:scale-95 disabled:opacity-60"
        :disabled="isSyncing"
        @click="syncNow"
      >
        {{ isSyncing ? 'Syncing' : 'Sync now' }}
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
  summary,
  statusLabel,
  lastSyncMessage,
  syncNow,
} = useOfflineSync()

const shouldShow = computed(() => {
  return !isOnline.value || summary.value.total > 0 || summary.value.failed > 0 || isSyncing.value
})

const bannerClass = computed(() => {
  if (!isOnline.value) {
    return 'border-amber-200 bg-amber-50 text-amber-900'
  }

  if (summary.value.failed > 0) {
    return 'border-red-200 bg-red-50 text-red-900'
  }

  if (summary.value.total > 0 || isSyncing.value) {
    return 'border-blue-200 bg-blue-50 text-blue-900'
  }

  return 'border-outline-gray-1 bg-surface-white text-ink-gray-8'
})
</script>
