<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Dialog } from 'frappe-ui'
import { DialogDescription } from 'reka-ui'
import { useMobileBoot } from '../lib/mobileBoot'
import { useOfflineSync } from '../pwa/useOfflineSync'
import { uploadProgress, retryExplanation } from '../lib/uploadProgress'
import {
  discardFailedOfflineQueueItem,
  getVisibleOfflineQueueItems,
  hasActiveSyncLease,
  syncOfflineQueueItem,
  type OfflineQueueItem,
} from '../pwa/offlineQueue'

const router = useRouter()
const { user } = useMobileBoot()
const { isOnline, refreshSummary } = useOfflineSync()
const items = ref<OfflineQueueItem[]>([])
const loading = ref(true)
const error = ref('')
const notice = ref('')
const busyId = ref('')
const removal = ref<OfflineQueueItem | null>(null)
const confirmOpen = ref(false)
let refreshTimer: number | undefined
let listRequest = 0

function title(item: OfflineQueueItem) {
  if (item.kind === 'jha_observation') return 'JHA observation'
  return String(item.server_result?.doctype || item.target_doctype || item.mobile_doctype || item.type)
    .split(/[-_]/)
    .map(word => word.toLowerCase() === 'batb' ? 'BATB' : word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function reference(item: OfflineQueueItem) {
  return item.server_result?.name || item.docname || item.target_name || item.values?.jha_name || ''
}

function savedDocument(item: OfflineQueueItem) {
  return Boolean(item.server_result?.name || item.docname || item.target_name)
}

function savedAt(item: OfflineQueueItem) {
  const date = new Date(item.created_at)
  return Number.isNaN(date.getTime()) ? item.created_at : date.toLocaleString()
}

function uploadStatus(item: OfflineQueueItem) {
  return uploadProgress(item).label
}

async function refreshList() {
  const request = ++listRequest
  try {
    const rows = await getVisibleOfflineQueueItems(user.value)
    if (request === listRequest) items.value = rows
  } catch {
    if (request === listRequest) {
      error.value = 'Could not read the upload queue on this device. Try refreshing the list.'
    }
  } finally {
    if (request === listRequest) loading.value = false
  }
}

watch(user, () => {
  items.value = []
  error.value = ''
  notice.value = ''
  loading.value = true
  void refreshList()
})

async function refresh() {
  error.value = ''
  await refreshList()
}

async function retry(item: OfflineQueueItem) {
  if (busyId.value || !isOnline.value || hasActiveSyncLease(item)) return
  const actor = user.value
  busyId.value = item.id
  error.value = ''
  notice.value = ''
  try {
    await syncOfflineQueueItem(item.id, { user: actor })
    await refreshList()
    if (actor === user.value) {
      const remaining = items.value.find(current => current.id === item.id && current.status !== 'synced')
      notice.value = remaining ? `${title(item)} still has work in the queue. Follow its progress above.`
        : `${title(item)} uploaded successfully and was confirmed by the server.`
    }
  } catch (err) {
    if (actor === user.value) error.value = err instanceof Error ? err.message : 'The upload failed. Your saved work is still on this device.'
  } finally {
    busyId.value = ''
    await refreshList()
    await refreshSummary()
  }
}

function askToRemove(item: OfflineQueueItem) {
  removal.value = item
  confirmOpen.value = true
}

async function remove() {
  const item = removal.value
  if (!item || busyId.value) return
  busyId.value = item.id
  error.value = ''
  notice.value = ''
  try {
    await discardFailedOfflineQueueItem(item.id, user.value)
    notice.value = `${title(item)} removed from the upload queue.`
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not remove this upload. Try again.'
  } finally {
    confirmOpen.value = false
    removal.value = null
    busyId.value = ''
    await refreshList()
    await refreshSummary()
  }
}

function handleQueueUpdated() { void refreshList() }
function handleServiceWorkerMessage(event: MessageEvent) {
  if (event.data?.type === 'VERTO_OFFLINE_QUEUE_UPDATED') handleQueueUpdated()
}

onMounted(() => {
  void refreshList()
  window.addEventListener('verto:offline-queue-updated', handleQueueUpdated)
  window.addEventListener('verto:offline-queue-synced', handleQueueUpdated)
  window.addEventListener('focus', handleQueueUpdated)
  navigator.serviceWorker?.addEventListener('message', handleServiceWorkerMessage)
  refreshTimer = window.setInterval(handleQueueUpdated, 5000)
})

onBeforeUnmount(() => {
  window.removeEventListener('verto:offline-queue-updated', handleQueueUpdated)
  window.removeEventListener('verto:offline-queue-synced', handleQueueUpdated)
  window.removeEventListener('focus', handleQueueUpdated)
  navigator.serviceWorker?.removeEventListener('message', handleServiceWorkerMessage)
  window.clearInterval(refreshTimer)
})
</script>

<template>
  <section class="mx-auto max-w-3xl space-y-4 px-[var(--verto-page-x,0.75rem)] py-[var(--verto-page-y,0.75rem)] pb-8" :aria-busy="loading">
    <div class="flex items-center justify-between gap-3">
      <h1 class="text-xl-semibold text-ink-gray-9">Upload queue</h1>
      <Button variant="subtle" :disabled="Boolean(busyId)" @click="refresh">Refresh list</Button>
    </div>
    <p v-if="!isOnline" class="text-sm text-ink-gray-6">Connect to retry uploads. You can remove failed uploads while offline.</p>
    <p v-if="error" role="alert" class="whitespace-pre-wrap break-words text-sm text-red-700">{{ error }}</p>
    <p v-if="notice" role="status" class="text-sm text-ink-gray-7">{{ notice }}</p>
    <p class="text-xs text-ink-gray-5">Uploads are confirmed only after Verto accepts the document and all attachments. Up to 20 confirmations from the last 24 hours are shown.</p>
    <p v-if="loading" role="status" class="py-6 text-sm text-ink-gray-6">Loading uploads…</p>
    <p v-else-if="!items.length && !error" class="rounded-7 border border-outline-gray-1 bg-surface-base p-4 text-sm text-ink-gray-6">No pending uploads for your account on this device.</p>

    <article v-for="item in items" :key="item.id" class="space-y-3 rounded-7 border border-outline-gray-1 bg-surface-base p-4">
      <div>
        <div class="flex items-start justify-between gap-2">
          <h2 class="min-w-0 break-words text-base-semibold text-ink-gray-9">{{ title(item) }}</h2>
          <span class="shrink-0 rounded-5 px-2 py-1 text-xs-medium"
            :class="item.status === 'synced' ? 'bg-green-50 text-green-800' : item.status === 'failed' && !hasActiveSyncLease(item) ? 'bg-red-50 text-red-800' : 'bg-surface-gray-2 text-ink-gray-7'">
            {{ uploadStatus(item) }}
          </span>
        </div>
        <p v-if="reference(item)" class="break-words text-sm text-ink-gray-7">{{ reference(item) }}</p>
        <p class="mt-1 text-xs text-ink-gray-5">Saved {{ savedAt(item) }} · {{ item.attempts || 0 }} upload attempts</p>
      </div>
      <ol class="grid gap-1 text-sm text-ink-gray-6" aria-label="Upload stages">
        <li v-for="step in uploadProgress(item).steps" :key="step.label" :class="step.done ? 'text-ink-gray-8' : ''">
          <span aria-hidden="true">{{ step.done ? '✓' : '○' }}</span> {{ step.label }}<span class="sr-only">{{ step.done ? ': complete' : ': pending' }}</span>
        </li>
      </ol>
      <div v-if="uploadProgress(item).total" class="space-y-1">
        <progress class="h-2 w-full accent-blue-600" :value="uploadProgress(item).uploaded" :max="uploadProgress(item).total" aria-label="Attachments accepted by server" />
        <p v-if="item.active_attachment_name && hasActiveSyncLease(item)" class="break-words text-xs text-ink-gray-5">{{ item.active_attachment_name }}</p>
      </div>
      <p v-if="retryExplanation(item, isOnline)" class="text-sm text-ink-gray-6">{{ retryExplanation(item, isOnline) }}</p>
      <p v-if="item.last_error && !hasActiveSyncLease(item) && item.status !== 'synced'"
        class="whitespace-pre-wrap break-words rounded-6 bg-red-50 p-3 text-sm text-red-800">{{ item.last_error || 'No error details were recorded.' }}</p>
      <p v-if="item.status === 'synced' && item.confirmed_at" class="text-xs text-ink-gray-5">Confirmed {{ new Date(item.confirmed_at).toLocaleString() }}</p>
      <p v-else-if="item.server_result?.name" class="text-sm text-ink-gray-6">The document was saved to the server. Photos or other work may still be waiting to upload.</p>
      <p v-else-if="savedDocument(item)" class="text-sm text-ink-gray-6">This upload contains pending changes or photos for an existing document.</p>
      <div v-if="item.status !== 'synced'" class="flex flex-wrap gap-2">
        <Button variant="subtle" :disabled="!isOnline || Boolean(busyId) || hasActiveSyncLease(item)" @click="retry(item)">
          {{ item.status === 'queued' ? 'Sync now' : 'Retry upload' }}
        </Button>
        <Button v-if="item.status === 'failed' && !hasActiveSyncLease(item)" variant="subtle" theme="red" :disabled="Boolean(busyId)" @click="askToRemove(item)">Remove upload</Button>
      </div>
    </article>
    <Button variant="ghost" @click="router.push('/')">Home</Button>
  </section>

  <Dialog v-model:open="confirmOpen" title="Remove failed upload?" size="sm" :dismissible="!busyId" :show-close-button="!busyId">
    <template #default>
      <DialogDescription as-child>
        <div v-if="removal" class="space-y-3 text-sm text-ink-gray-7">
          <p class="font-medium">{{ title(removal) }}<span v-if="reference(removal)"> · {{ reference(removal) }}</span></p>
          <p>This permanently removes the saved upload and any pending photos from this device. Any work that has not reached the server will be lost. This cannot be undone.</p>
          <p v-if="savedDocument(removal)">The existing server document and any photos already uploaded will be kept.</p>
          <p v-else>The server may have received an earlier attempt. Check Forms before submitting a replacement.</p>
        </div>
      </DialogDescription>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button variant="subtle" :disabled="Boolean(busyId)" @click="confirmOpen = false">Cancel</Button>
        <Button variant="solid" theme="red" :loading="Boolean(busyId)" :disabled="Boolean(busyId)" @click="remove">Remove permanently</Button>
      </div>
    </template>
  </Dialog>
</template>
