import { apiRequest } from '../lib/api'
import { cacheApiResponse, getCachedApiResponse, getOfflineQueueItems, queueJhaObservation, syncOfflineQueueItem } from './offlineQueue'

export type OfflineJhaCopy = {
  user: string
  saved_at: string
  jha: Record<string, any>
  review: Record<string, any>
  resources: any[]
  notice: string
  photos: Record<string, Blob>
  media_missing: number
}

export function jhaOfflineActor() {
  return String(window.localStorage.getItem('verto:offline-actor') || '').trim()
}
const key = (actor: string, name: string) => `jha-copy:${actor}:${name}`

export async function readOfflineJha(name: string) {
  const actor = jhaOfflineActor()
  if (!actor || actor === 'Guest') return null
  const copy = await getCachedApiResponse<OfflineJhaCopy>(key(actor, name))
  return copy?.user === actor && copy.jha.name === name ? copy : null
}

export async function downloadOfflineJha(name: string) {
  if (!navigator.onLine) throw new Error('Connect to download a signed JHA copy.')
  const { message } = await apiRequest<{ message: OfflineJhaCopy }>(
    `/api/method/verto.api.mobile.voice_jha_workpack.download_jha_offline?jha_name=${encodeURIComponent(name)}`, { cache: 'no-store' })
  const actor = jhaOfflineActor()
  if (!actor || actor !== message.user) throw new Error('Refresh your signed-in session before downloading offline data.')
  const copy: OfflineJhaCopy = { ...message, photos: {}, media_missing: 0 }
  let size = 0
  const urls = [...new Set(copy.resources.filter(row => row.kind === 'Photo' && !row.historical && row.evidence).map(row => row.evidence))]
  for (const url of urls) {
    try {
      if (!String(url).startsWith('/private/files/') || size >= 30 * 1024 * 1024) throw new Error('Photo limit')
      const response = await fetch(url, { credentials: 'include', cache: 'no-store' })
      if (!response.ok || !response.headers.get('content-type')?.startsWith('image/')) throw new Error('Photo unavailable')
      const blob = await response.blob()
      if (blob.size > 10 * 1024 * 1024 || size + blob.size > 30 * 1024 * 1024) throw new Error('Photo limit')
      copy.photos[url] = blob; size += blob.size
    } catch { copy.media_missing++ }
  }
  // Do not save into a different account if the user switched during downloads.
  if (jhaOfflineActor() !== actor) throw new Error('The signed-in account changed. Download again.')
  await cacheApiResponse(key(actor, name), copy, 'jha-signed-copies')
  return copy
}

export async function pendingJhaObservations(name: string) {
  const actor = jhaOfflineActor()
  return (await getOfflineQueueItems()).filter(row => row.kind === 'jha_observation'
    && row.values?.jha_name === name && row.values?.actor === actor)
}

export async function saveJhaObservation(copy: OfflineJhaCopy, notes: string, stepRow: string, changed: boolean, requestId: string) {
  const actor = jhaOfflineActor()
  if (!actor || copy.user !== actor) throw new Error('Sign in as the person who downloaded this copy.')
  const values = { jha_name: copy.jha.name, revision: copy.jha.revision, actor, request_id: requestId,
    notes, step_row: stepRow, work_changed: changed ? 1 : 0, observed_at: new Date().toISOString() }
  const item = await queueJhaObservation(values)
  if (navigator.onLine) {
    try { return { queued: false, result: await syncOfflineQueueItem(item.id) } }
    catch { /* Retain the durable queue item and display the pending state. */ }
  }
  return { queued: true, result: null }
}
