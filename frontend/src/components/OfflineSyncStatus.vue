<!-- Render notifications through the root Frappe UI provider, without a layout bar. -->
<template><!-- Sync status remains available in the avatar and Upload queue. --></template>

<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, watch, type WatchStopHandle } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast, type ToastId, type ToastOptions } from 'frappe-ui'
import { useMobileBoot } from '../lib/mobileBoot'
import { formOpen } from '../pwa/formActivity'
import { useOfflineSync } from '../pwa/useOfflineSync'

const router = useRouter()
const route = useRoute()
const { user } = useMobileBoot()
const sync = useOfflineSync()
let toastId: ToastId | undefined
type Notice = { key: string; type: 'info' | 'warning' | 'error' | 'success'; title: string; description: string; progress?: boolean; action?: 'queue' | 'refresh' }
let stop: WatchStopHandle | undefined
let actor = ''
let previousOnline: boolean | undefined
let syncingWork = false
let lastReadyAt = ''
let displayed = ''
let successVisible = false
let closeTimer: number | undefined

const state = computed(() => ({
  user: user.value,
  online: sync.isOnline.value,
  syncing: sync.isSyncing.value,
  priming: sync.isPriming.value,
  ready: sync.showReadyConfirmation.value,
  refreshedAt: sync.lastOfflineRefreshAt.value,
  refreshError: sync.offlineRefreshError.value,
  summary: { ...sync.summary.value },
  message: sync.lastSyncMessage.value,
  result: sync.lastSyncResult?.value,
  formOpen: formOpen.value,
  queueOpen: route.name === 'failed-uploads',
}))

function refreshLabel(value: string) {
  const date = new Date(value)
  return value && !Number.isNaN(date.getTime()) ? new Intl.DateTimeFormat(undefined, {
    day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
  }).format(date) : ''
}

function clearCloseTimer() {
  if (closeTimer !== undefined) window.clearTimeout(closeTimer)
  closeTimer = undefined
}
function closeToast() {
  clearCloseTimer()
  const id = toastId
  toastId = undefined
  if (id !== undefined) toast.dismiss(id)
}

function show(notice: Notice) {
  const key = JSON.stringify(notice)
  if (key === displayed) return
  clearCloseTimer()
  displayed = key
  successVisible = notice.type === 'success'
  let id: ToastId
  const release = () => { if (toastId === id) { clearCloseTimer(); toastId = undefined } }
  const duration = notice.progress || notice.type === 'error' ? Infinity : notice.type === 'success' ? 4000 : 6500
  const options: ToastOptions = {
    id: toastId,
    // A VNode keeps server errors as text, rather than toast's inline HTML.
    description: h('span', notice.description),
    duration,
    onDismiss: release,
    onAutoClose: release,
    classes: { content: 'min-w-0 flex-1', title: 'break-words', description: '[overflow-wrap:anywhere]' },
    closeButton: true,
    dismissible: true,
    icon: notice.progress ? () => h('span', { class: 'lucide-loader-circle size-4 animate-spin', 'aria-hidden': 'true' }) : undefined,
    action: notice.action === 'queue' ? {
      label: 'View uploads',
      onClick: event => {
        if (formOpen.value) { event.preventDefault(); return }
        release()
        void router.push({ name: 'failed-uploads' })
      },
    } : notice.action === 'refresh' ? {
      label: 'Retry',
      onClick: event => {
        event.preventDefault() // Keep the same toast available for the progress update.
        if (!formOpen.value) void sync.primeNow()
      },
    } : undefined,
  }
  id = toast[notice.type](notice.title, options)
  toastId = id
  if (Number.isFinite(duration)) {
    // Updating an indefinite toast can retain its old infinite lifetime in
    // Sonner. Ensure short notices close even after a progress/error state.
    closeTimer = window.setTimeout(() => {
      if (toastId === id && displayed === key) closeToast()
    }, duration)
  }
}

function update(current: typeof state.value) {
  if (current.user !== actor) {
    closeToast()
    actor = current.user
    previousOnline = undefined
    syncingWork = false
    displayed = lastReadyAt = ''
    successVisible = false
  }
  if (!actor || actor === 'Guest') return
  // The queue owns its detailed status and retry controls; a floating copy
  // would cover the very controls the user needs to resolve an upload.
  if (current.queueOpen) {
    closeToast()
    displayed = ''
    successVisible = syncingWork = false
    previousOnline = current.online
    return
  }
  const queueAction = !current.formOpen ? 'queue' as const : undefined
  const queueHelp = current.formOpen ? ' Finish this form, then open Upload queue from your profile.' : ''
  const restored = previousOnline === false && current.online
  previousOnline = current.online
  if (current.syncing && (current.summary.total > 0 || (current.result?.synced || 0) > 0)) syncingWork = true
  const completed = syncingWork && !current.syncing
  if (!current.syncing) syncingWork = false

  if (!current.online) {
    show({ key: `offline:${current.summary.total}`, type: 'warning', title: 'Offline mode',
      description: current.summary.total > 0
        ? `${current.summary.total} item${current.summary.total === 1 ? '' : 's'} saved on this device. Sync resumes when Verto is reachable.${queueHelp}`
        : 'Verto cannot be reached. Any queued work stays on this device.',
      action: current.summary.total > 0 ? queueAction : undefined })
  } else if ((current.syncing && syncingWork) || current.summary.syncing > 0) {
    show({ key: 'syncing', type: 'info', title: 'Syncing saved work…', progress: true,
      description: current.syncing && current.message ? current.message : 'Your saved work is uploading. You can keep using Verto.', action: queueAction })
  } else if (current.summary.failed > 0) {
    show({ key: `failed:${current.summary.failed}`, type: 'error', title: `${current.summary.failed} upload${current.summary.failed === 1 ? '' : 's'} need${current.summary.failed === 1 ? 's' : ''} attention`,
      description: 'Your saved work remains in Upload queue for review and retry.' + queueHelp, action: queueAction })
  } else if (current.result?.error && current.summary.total > 0) {
    show({ key: 'sync-error', type: 'error', title: 'Could not finish syncing', description: current.result.error + queueHelp, action: queueAction })
  } else if (current.refreshError) {
    const lastUpdate = refreshLabel(current.refreshedAt)
    show({ key: 'refresh-error', type: 'error', title: 'Offline data refresh failed',
      description: current.refreshError + (lastUpdate ? ` Last successful update: ${lastUpdate}.` : ''),
      action: !current.formOpen ? 'refresh' : undefined })
  } else if (current.priming) {
    show({ key: 'preparing', type: 'info', title: current.refreshedAt ? 'Refreshing offline data…' : 'Preparing offline data…',
      description: 'Keep Verto open while offline data is prepared.', progress: true })
  } else if (current.summary.total > 0) {
    show({ key: `queued:${current.summary.total}`, type: 'info', title: `${current.summary.total} item${current.summary.total === 1 ? '' : 's'} waiting to sync`,
      description: 'Saved work will upload automatically when the connection is ready.' + queueHelp, action: queueAction })
  } else if (completed && (current.result?.synced || 0) > 0 && !current.result?.skipped) {
    lastReadyAt = current.refreshedAt
    show({ key: 'synced', type: 'success', title: 'Saved work synced', description: current.message || 'Your saved work was confirmed by the server.' })
  } else if (current.ready && current.refreshedAt && lastReadyAt !== current.refreshedAt) {
    lastReadyAt = current.refreshedAt
    show({ key: `ready:${lastReadyAt}`, type: 'success', title: 'Offline data ready', description: `Updated ${refreshLabel(current.refreshedAt)}` })
  } else if (restored) {
    show({ key: 'online', type: 'success', title: 'Connection restored', description: 'Verto is reachable again.' })
  } else if (!successVisible && displayed) {
    closeToast()
    displayed = ''
  }
}

onMounted(() => { stop = watch(state, update, { immediate: true, deep: true, flush: 'post' }) })
onBeforeUnmount(() => { stop?.(); closeToast() })
</script>
