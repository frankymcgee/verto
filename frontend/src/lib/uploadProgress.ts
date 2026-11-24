import { hasActiveSyncLease, type OfflineQueueItem } from '../pwa/offlineQueue'

export function uploadProgress(item: OfflineQueueItem) {
  const total = Math.max(item.attachment_count || 0, item.attachments?.length || (item.attachment ? 1 : 0))
  const uploaded = Math.min(total, item.uploaded_attachment_count ?? item.uploaded_attachment_ids?.length ?? 0)
  const confirmed = item.status === 'synced'
  const active = hasActiveSyncLease(item)
  let label = 'Saved on this device'
  if (confirmed) label = 'Confirmed by server'
  else if (active && item.sync_stage === 'uploading_attachments') label = `Uploading attachment ${Math.min(uploaded + 1, total)} of ${total}`
  else if (active && item.sync_stage === 'requesting_review') label = 'Finalising upload'
  else if (active) label = 'Saving document'
  else if (item.status === 'failed') label = 'Needs attention'
  else if (item.last_error || item.status === 'syncing') label = 'Waiting to retry'
  else label = 'Waiting to sync'

  const documentSaved = Boolean(item.server_result?.name || item.kind === 'attachment_upload')
  const steps = [
    { label: 'Saved on device', done: true },
    { label: item.kind === 'jha_observation' ? 'Observation saved to server' : 'Document saved to server', done: documentSaved || confirmed },
    ...(total ? [{ label: `${uploaded} of ${total} attachments uploaded`, done: uploaded === total }] : []),
    { label: 'Confirmed by server', done: confirmed },
  ]
  return { label, total, uploaded, confirmed, active, steps }
}

export function retryExplanation(item: OfflineQueueItem, online: boolean) {
  if (item.status === 'synced') return ''
  if (!online) return 'Waiting for a connection to Verto. Your saved work is on this device.'
  if (item.status === 'failed') return item.last_error_retryable
    ? 'Sign in again or check your connection, then retry this upload.'
    : 'This upload needs attention. Check the error below and the original form before retrying.'
  if (item.next_retry_at && item.next_retry_at > Date.now()) {
    return `Automatic retry after ${new Date(item.next_retry_at).toLocaleTimeString()}. You can also sync now.`
  }
  if (item.last_error) return 'The connection was interrupted. This upload will retry automatically.'
  return ''
}
