// VERTO_OFFLINE_DOCUMENT_SYNC_QUEUE_2026_08_24

import { withCsrfHeaders } from '../lib/csrf'
import { reportClientError } from '../lib/diagnostics'
import { fetchServerJson } from '../lib/connection'

export type OfflineQueueItemStatus = 'queued' | 'syncing' | 'synced' | 'failed'
export type OfflineQueueItemKind = 'mobile_document' | 'attachment_upload' | 'legacy_request' | 'jha_observation'
export type OfflineDocumentAction = 'create' | 'update'

export type OfflineAttachment = {
  id: string
  name: string
  type: string
  size: number
  last_modified: number
  blob: Blob
}

export type OfflineQueueItem = {
  id: string
  kind: OfflineQueueItemKind
  type: string
  created_at: string
  updated_at: string
  attempts: number
  status: OfflineQueueItemStatus
  last_error?: string
  last_error_retryable?: boolean
  next_retry_at?: number

  // Mobile document operations.
  action_type?: OfflineDocumentAction
  mobile_doctype?: string
  docname?: string
  values?: Record<string, any>
  attachments?: OfflineAttachment[]
  server_result?: Record<string, any> | null
  uploaded_attachment_ids?: string[]
  sync_owner?: string
  sync_expires_at?: number

  // Standalone attachment uploads for an existing document.
  target_doctype?: string
  target_name?: string
  attachment?: OfflineAttachment

  // Backwards compatibility with the original generic queue.
  url?: string
  method?: string
  headers?: Record<string, string>
  body?: any
}

export type OfflineQueueSummary = {
  queued: number
  syncing: number
  failed: number
  total: number
}

export type OfflineApiCacheEntry<T = any> = {
  key: string
  group: string
  value: T
  updated_at: string
}

export class OfflineSyncError extends Error {
  retryable: boolean
  auth: boolean
  busy: boolean

  constructor(message: string, options: { retryable?: boolean; auth?: boolean; busy?: boolean } = {}) {
    super(message)
    this.name = 'OfflineSyncError'
    this.retryable = Boolean(options.retryable)
    this.auth = Boolean(options.auth)
    this.busy = Boolean(options.busy)
  }
}

export function isRetryableOfflineSyncError(error: unknown) {
  return error instanceof TypeError ||
    (error instanceof OfflineSyncError && error.retryable) ||
    String((error as any)?.message || '').toLowerCase().includes('failed to fetch') ||
    String((error as any)?.message || '').toLowerCase().includes('network')
}

export function isOfflineSyncAuthError(error: unknown) {
  return error instanceof OfflineSyncError && error.auth
}

const DB_NAME = 'verto-mobile-offline-db'
const DB_VERSION = 3
const QUEUE_STORE = 'offline_queue'
const API_CACHE_STORE = 'api_cache'

function dispatchQueueUpdated() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('verto:offline-queue-updated'))
  }
}

export function createOfflineId(prefix = 'offline') {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `${prefix}-${crypto.randomUUID()}`
  }

  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function nowIso() {
  return new Date().toISOString()
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onerror = () => reject(request.error || new Error('Could not open the Verto offline database.'))

    request.onupgradeneeded = () => {
      const db = request.result
      const transaction = request.transaction

      let queueStore: IDBObjectStore

      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        queueStore = db.createObjectStore(QUEUE_STORE, {
          keyPath: 'id',
        })
      } else {
        queueStore = transaction!.objectStore(QUEUE_STORE)
      }

      if (!queueStore.indexNames.contains('status')) {
        queueStore.createIndex('status', 'status', { unique: false })
      }

      if (!queueStore.indexNames.contains('created_at')) {
        queueStore.createIndex('created_at', 'created_at', { unique: false })
      }

      if (!queueStore.indexNames.contains('type')) {
        queueStore.createIndex('type', 'type', { unique: false })
      }

      if (!queueStore.indexNames.contains('kind')) {
        queueStore.createIndex('kind', 'kind', { unique: false })
      }

      if (!db.objectStoreNames.contains(API_CACHE_STORE)) {
        const cacheStore = db.createObjectStore(API_CACHE_STORE, {
          keyPath: 'key',
        })

        cacheStore.createIndex('group', 'group', { unique: false })
        cacheStore.createIndex('updated_at', 'updated_at', { unique: false })
      }
    }

    request.onsuccess = () => resolve(request.result)
  })
}

function requestToPromise<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error || new Error('IndexedDB request failed.'))
  })
}

async function withStore<T>(
  storeName: string,
  mode: IDBTransactionMode,
  callback: (store: IDBObjectStore) => Promise<T> | T
): Promise<T> {
  const db = await openDatabase()

  try {
    const transaction = db.transaction(storeName, mode)
    const store = transaction.objectStore(storeName)
    const result = await callback(store)

    await new Promise<void>((resolve, reject) => {
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error || new Error('IndexedDB transaction failed.'))
      transaction.onabort = () => reject(transaction.error || new Error('IndexedDB transaction was aborted.'))
    })

    return result
  } finally {
    db.close()
  }
}

export async function cacheApiResponse<T>(
  key: string,
  value: T,
  group = 'api'
) {
  const entry: OfflineApiCacheEntry<T> = {
    key,
    group,
    value,
    updated_at: nowIso(),
  }

  await withStore(API_CACHE_STORE, 'readwrite', async (store) => {
    await requestToPromise(store.put(entry))
  })

  return entry
}

export async function getCachedApiResponse<T>(key: string): Promise<T | null> {
  const entry = await withStore<OfflineApiCacheEntry<T> | undefined>(
    API_CACHE_STORE,
    'readonly',
    (store) => requestToPromise(store.get(key))
  )

  return entry?.value ?? null
}

export async function getApiCacheEntriesByGroup<T = any>(group: string) {
  return withStore<OfflineApiCacheEntry<T>[]>(API_CACHE_STORE, 'readonly', async (store) => {
    const index = store.index('group')
    return requestToPromise(index.getAll(IDBKeyRange.only(group)))
  })
}

export async function mergeCachedLinkOptions(
  doctype: string,
  options: Array<{ name: string; description?: string }>
) {
  const group = `link-options:${doctype}`
  const key = group
  const existing = await getCachedApiResponse<Array<{ name: string; description?: string }>>(key) || []
  const merged = new Map<string, { name: string; description?: string }>()

  for (const option of [...existing, ...(options || [])]) {
    const name = String(option?.name || '').trim()

    if (!name) continue

    merged.set(name, {
      name,
      description: option?.description,
    })
  }

  const values = Array.from(merged.values())
    .sort((a, b) => a.name.localeCompare(b.name))
    .slice(0, 500)

  await cacheApiResponse(key, values, group)
  return values
}

export async function getCachedLinkOptions(doctype: string, txt = '') {
  const values = await getCachedApiResponse<Array<{ name: string; description?: string }>>(
    `link-options:${doctype}`
  ) || []

  const search = String(txt || '').trim().toLowerCase()

  if (!search) {
    return values.slice(0, 20)
  }

  return values
    .filter((option) => {
      return option.name.toLowerCase().includes(search) ||
        String(option.description || '').toLowerCase().includes(search)
    })
    .slice(0, 20)
}

function toDateKey(value?: string | null) {
  if (!value) return ''
  return String(value).slice(0, 10)
}

function shiftOverlapsRange(shift: any, startDate: string, endDate: string) {
  const start = toDateKey(shift?.start_date)
  const end = toDateKey(shift?.end_date || shift?.start_date)

  return Boolean(start && end && start <= endDate && end >= startDate)
}

export async function getCachedShiftCalendar(startDate: string, endDate: string) {
  const entries = await getApiCacheEntriesByGroup<any>('shift-calendar')
  const shiftMap = new Map<string, any>()
  const timesheetMap = new Map<string, any>()
  let user = ''
  let userFullname = ''

  for (const entry of entries) {
    const payload = entry.value?.message || entry.value

    if (!payload || typeof payload !== 'object') continue

    user = user || payload.user || ''
    userFullname = userFullname || payload.user_fullname || ''

    for (const shift of payload.shifts || []) {
      if (!shiftOverlapsRange(shift, startDate, endDate)) continue
      const key = String(shift.name || `${shift.start_date}:${shift.end_date}:${shift.shift_type}`)
      shiftMap.set(key, shift)
    }

    for (const timesheet of payload.timesheets || []) {
      const date = toDateKey(timesheet?.date)
      if (!date || date < startDate || date > endDate) continue
      const key = String(timesheet.name || `${date}:${timesheet.start_time || ''}`)
      timesheetMap.set(key, timesheet)
    }
  }

  const timesheets = await mergePendingTimesheets(Array.from(timesheetMap.values()), startDate, endDate, user)

  if (!shiftMap.size && !timesheets.length && !user && !userFullname) {
    return null
  }

  return {
    message: {
      user,
      user_fullname: userFullname,
      shifts: Array.from(shiftMap.values()),
      timesheets,
      offline_cached: true,
    },
  }
}

export async function mergePendingTimesheets(timesheets: any[], startDate: string, endDate: string, actor: string) {
  const timesheetMap = new Map<string, any>(timesheets.map((row) => [row.name, row]))
  // Reflect unsynced Daily Timesheets in the calendar immediately. This keeps
  // an offline submission visible after the create page routes back to Shifts
  // and prevents the user from submitting the same date a second time.
  const queuedItems = await getOfflineQueueItems()

  for (const item of queuedItems) {
    if (
      item.kind !== 'mobile_document' ||
      item.mobile_doctype !== 'daily-timesheet' ||
      !actor || item.values?.__verto_offline_user !== actor ||
      item.status === 'synced'
    ) {
      continue
    }

    const values = item.values || {}
    const date = toDateKey(values.date || values.timesheet_date || values.attendance_date)

    if (!date || date < startDate || date > endDate) continue

    if (item.action_type === 'update' && item.docname) {
      const current = timesheetMap.get(item.docname) || { name: item.docname }

      timesheetMap.set(item.docname, {
        ...current,
        ...values,
        name: item.docname,
        date,
        offline_queued: true,
        offline_operation_id: item.id,
      })
      continue
    }

    if (item.action_type === 'create') {
      const name = String(item.server_result?.name || item.id)
      timesheetMap.set(name, {
        ...values,
        name,
        date,
        offline_queued: true,
        offline_operation_id: item.id,
      })
    }
  }

  return Array.from(timesheetMap.values())
}

export async function getCachedShiftForDate(date: string, shiftAllocation = '') {
  const calendar = await getCachedShiftCalendar(date, date)
  const payload = calendar?.message

  if (!payload) return null

  const shift = (payload.shifts || []).find((item: any) => {
    return (!shiftAllocation || item.name === shiftAllocation) && shiftOverlapsRange(item, date, date)
  })

  return {
    shift: shift || null,
    user: payload.user || '',
    user_fullname: payload.user_fullname || '',
  }
}

export async function addOfflineQueueItem(input: {
  type: string
  url: string
  method?: string
  headers?: Record<string, string>
  body?: any
}) {
  const timestamp = nowIso()

  const item: OfflineQueueItem = {
    id: createOfflineId('legacy'),
    kind: 'legacy_request',
    type: input.type,
    url: input.url,
    method: input.method || 'POST',
    headers: input.headers || {},
    body: input.body ?? null,
    created_at: timestamp,
    updated_at: timestamp,
    attempts: 0,
    status: 'queued',
  }

  await putOfflineQueueItem(item)
  return item
}

export async function queueMobileDocumentAction(input: {
  actionType: OfflineDocumentAction
  mobileDoctype: string
  values: Record<string, any>
  docname?: string
  operationId?: string
  attachments?: OfflineAttachment[]
}) {
  const timestamp = nowIso()

  const item: OfflineQueueItem = {
    id: input.operationId || createOfflineId('document'),
    kind: 'mobile_document',
    type: `mobile_document_${input.actionType}`,
    action_type: input.actionType,
    mobile_doctype: input.mobileDoctype,
    docname: input.docname,
    values: input.values || {},
    attachments: input.attachments || [],
    server_result: null,
    created_at: timestamp,
    updated_at: timestamp,
    attempts: 0,
    status: 'queued',
  }

  const queued = await withStore(QUEUE_STORE, 'readwrite', async (store) => {
    const existing: OfflineQueueItem | undefined = await requestToPromise(store.get(item.id))
    if (existing) {
      if (existing.mobile_doctype !== item.mobile_doctype ||
          existing.action_type !== item.action_type || existing.docname !== item.docname ||
          existing.values?.__verto_offline_user !== item.values?.__verto_offline_user) {
        throw new Error('This submission belongs to another document or signed-in user.')
      }
      if (existing.status === 'failed' && existing.last_error_retryable === false && !existing.server_result) {
        // Validation rejected the original write. A corrected form can reuse
        // its ID because no document/receipt was committed for that attempt.
        await requestToPromise(store.put(item))
        return item
      }
      if (JSON.stringify(existing.values) !== JSON.stringify(item.values)) {
        throw new Error('This submission is already saved or waiting to sync. Open it from Forms or Shifts to make changes.')
      }
      // A retry must keep the original payload and attachment IDs once sent.
      return existing
    }
    await requestToPromise(store.put(item))
    return item
  })
  dispatchQueueUpdated()
  return queued
}

export async function queueJhaObservation(values: Record<string, any>) {
  if (!values.actor || !values.jha_name || !values.request_id) throw new Error('The JHA observation is incomplete.')
  const timestamp = nowIso()
  const item: OfflineQueueItem = {
    id: `jha-observation-${values.request_id}`, kind: 'jha_observation', type: 'JHA observation',
    values, created_at: timestamp, updated_at: timestamp, attempts: 0, status: 'queued',
  }
  await putOfflineQueueItem(item)
  return item
}

export async function queueAttachmentUpload(input: {
  targetDoctype: string
  targetName: string
  file: File | Blob
  fileName?: string
  contentType?: string
  lastModified?: number
}) {
  const timestamp = nowIso()
  const attachment = makeOfflineAttachment(
    input.file,
    input.fileName,
    input.contentType,
    input.lastModified
  )

  const item: OfflineQueueItem = {
    id: createOfflineId('attachment'),
    kind: 'attachment_upload',
    type: 'attachment_upload',
    target_doctype: input.targetDoctype,
    target_name: input.targetName,
    attachment,
    created_at: timestamp,
    updated_at: timestamp,
    attempts: 0,
    status: 'queued',
  }

  await putOfflineQueueItem(item)
  return item
}

export function makeOfflineAttachment(
  blob: File | Blob,
  fileName?: string,
  contentType?: string,
  lastModified?: number
): OfflineAttachment {
  const possibleFile = blob as File
  const name = fileName || possibleFile.name || `attachment-${Date.now()}`

  return {
    id: createOfflineId('file'),
    name,
    type: contentType || blob.type || 'application/octet-stream',
    size: blob.size,
    last_modified: lastModified || possibleFile.lastModified || Date.now(),
    blob,
  }
}

export async function attachFileToDocumentOperation(
  operationId: string,
  attachment: OfflineAttachment
) {
  const item = await getOfflineQueueItem(operationId)

  if (!item || item.kind !== 'mobile_document') {
    throw new Error('The offline document queue item could not be found.')
  }

  const attachments = [...(item.attachments || [])]
  attachments.push(attachment)

  await putOfflineQueueItem({
    ...item,
    attachments,
    updated_at: nowIso(),
  })
}

// Retained for compatibility with any callers from the first offline queue
// implementation.
export const attachFileToCreateOperation = attachFileToDocumentOperation

export async function getOfflineQueueItem(id: string) {
  return withStore<OfflineQueueItem | undefined>(QUEUE_STORE, 'readonly', (store) => {
    return requestToPromise(store.get(id))
  })
}

export async function getOfflineQueueItems() {
  const items = await withStore<OfflineQueueItem[]>(QUEUE_STORE, 'readonly', (store) => {
    return requestToPromise(store.getAll())
  })

  return (items || []).sort((a, b) => a.created_at.localeCompare(b.created_at))
}

export async function getOfflineQueueSummary(user: string): Promise<OfflineQueueSummary> {
  const items = await getPendingOfflineQueueItems(user)
  const counts = { queued: 0, syncing: 0, failed: 0, total: items.length }
  for (const item of items) {
    if (hasActiveSyncLease(item)) counts.syncing += 1
    else if (item.status === 'failed') counts.failed += 1
    else counts.queued += 1
  }
  return counts
}

export async function putOfflineQueueItem(item: OfflineQueueItem) {
  await withStore(QUEUE_STORE, 'readwrite', async (store) => {
    await requestToPromise(store.put({
      ...item,
      updated_at: nowIso(),
    }))
  })

  dispatchQueueUpdated()
}

export async function updateOfflineQueueItem(item: OfflineQueueItem) {
  await putOfflineQueueItem(item)
}

export async function deleteOfflineQueueItem(id: string) {
  await withStore(QUEUE_STORE, 'readwrite', async (store) => {
    await requestToPromise(store.delete(id))
  })

  dispatchQueueUpdated()
}

function queueItemBelongsToUser(item: OfflineQueueItem, user: string) {
  const owner = item.values?.__verto_offline_user || (item.kind === 'jha_observation' ? item.values?.actor : '')
  // Older queue entries and standalone attachments have no stored identity.
  return Boolean(user && user !== 'Guest' && (!owner || owner === user))
}

export async function getPendingOfflineQueueItems(user: string) {
  if (!user || user === 'Guest') return []
  return (await getOfflineQueueItems()).filter((item) => {
    return item.status !== 'synced' && queueItemBelongsToUser(item, user)
  })
}

export function hasActiveSyncLease(item: OfflineQueueItem) {
  return Boolean(item.sync_owner && (item.sync_expires_at || 0) > Date.now())
}

export async function discardFailedOfflineQueueItem(id: string, user: string) {
  // Re-read and delete in one transaction. Auto-sync can claim a failure at
  // any time; a stale screen must never delete an upload that is in progress.
  await withStore(QUEUE_STORE, 'readwrite', async (store) => {
    const item: OfflineQueueItem | undefined = await requestToPromise(store.get(id))
    if (!item) return
    if (!queueItemBelongsToUser(item, user)) {
      throw new Error('This upload belongs to another signed-in user.')
    }
    if (item.status !== 'failed' || hasActiveSyncLease(item)) {
      throw new Error('This upload is no longer failed or is syncing. Refresh the list and try again.')
    }
    await requestToPromise(store.delete(id))
  })

  dispatchQueueUpdated()
}

export async function clearSyncedOfflineQueueItems() {
  const items = await getOfflineQueueItems()
  await Promise.all(
    items
      .filter((item) => item.status === 'synced')
      .map((item) => deleteOfflineQueueItem(item.id))
  )
}

function extractServerError(data: any, fallback: string) {
  const raw = data?._server_messages || data?.exception || data?.exc || data?.message

  if (!raw) return fallback

  if (typeof raw !== 'string') {
    return typeof raw?.message === 'string' ? raw.message : fallback
  }

  try {
    const parsed = JSON.parse(raw)

    if (Array.isArray(parsed)) {
      return parsed
        .map((entry) => {
          try {
            const value = typeof entry === 'string' ? JSON.parse(entry) : entry
            return value?.message || value?.title || String(entry)
          } catch {
            return String(entry)
          }
        })
        .filter(Boolean)
        .join('\n')
    }
  } catch {
    // Use the raw server error below.
  }

  return raw
}

async function ensureSyncResponse(response: Response, data: any, fallbackMessage = `Sync failed with HTTP ${response.status}.`) {
  const serverMessage = response.status === 413 ? fallbackMessage : extractServerError(data, fallbackMessage)
  const normalisedMessage = String(serverMessage || '').toLowerCase()
  const isAuthFailure = response.status === 401 || (
    response.status === 403 && [
      'login required',
      'not permitted in guest mode',
      'session expired',
      'session has expired',
      'not logged in',
      'please login',
      'please log in',
    ].some((message) => normalisedMessage.includes(message))
  )

  if (isAuthFailure) {
    throw new OfflineSyncError('Login required before offline items can sync.', {
      auth: true,
    })
  }

  if (response.ok && (!data || typeof data !== 'object')) {
    throw new OfflineSyncError('The server response could not be confirmed. The saved item will retry safely.', {
      retryable: true,
    })
  }

  if (!response.ok) {
    void reportClientError({
      message: serverMessage,
      source: 'offline.sync.http',
      details: {
        endpoint: new URL(response.url || window.location.href).pathname,
        status: response.status,
        status_text: response.statusText,
      },
    })
    throw new OfflineSyncError(
      serverMessage,
      {
        retryable: [408, 425, 429, 500, 502, 503, 504].includes(response.status),
      }
    )
  }

  if (data?.message?.ok === false) {
    void reportClientError({
      message: data.message.error || 'The server rejected the offline item.',
      source: 'offline.sync.rejected',
      details: {
        endpoint: new URL(response.url || window.location.href).pathname,
        status: response.status,
      },
    })
    throw new OfflineSyncError(
      data.message.error || 'The server rejected the offline item.'
    )
  }

  return data?.message ?? data
}

async function sendSyncRequest(
  url: string,
  options: RequestInit,
  { attachmentName, legacy = false }: { attachmentName?: string; legacy?: boolean } = {},
) {
  const { response, data } = await fetchServerJson(url, options, attachmentName ? 600_000 : 30_000)
  const fallback = attachmentName && response.status === 413
    ? `${attachmentName} exceeds the server's upload size limit.`
    : undefined
  const result = await ensureSyncResponse(response, data, fallback)
  return legacy ? response : result
}

async function uploadQueuedAttachment(input: {
  operationId: string
  attachment: OfflineAttachment
  targetDoctype: string
  targetName: string
}) {
  const { blob, name } = input.attachment
  const metadata = encodeURIComponent(JSON.stringify({
    operation_id: input.operationId,
    attachment_id: input.attachment.id,
    target_doctype: input.targetDoctype,
    target_name: input.targetName,
    file_name: name,
  }))

  // Frappe applies System Settings to this route's entire request body.
  // Send a plain Blob so multipart overhead and restored WebKit Files cannot interfere.
  return sendSyncRequest('/api/method/upload_file?method=verto.api.mobile.offline.upload_attachment', {
    method: 'POST',
    headers: withCsrfHeaders({
      'Content-Type': 'application/octet-stream',
      'X-Verto-Attachment': metadata,
    }, 'POST'),
    body: blob.slice(0, blob.size, blob.type),
  }, { attachmentName: name })
}

async function queuePhotoAnalysis(targetDoctype: string, targetName: string) {
  const formData = new FormData()
  formData.append('doctype', targetDoctype)
  formData.append('docname', targetName)

  return sendSyncRequest(
    '/api/method/verto.api.mobile.ai_photo_analysis.queue_submitted_form_review',
    {
      method: 'POST',
      headers: withCsrfHeaders(undefined, 'POST'),
      body: formData,
    }
  )
}

async function syncMobileDocumentItem(item: OfflineQueueItem, owner: string) {
  if (!item.action_type || !item.mobile_doctype) {
    throw new Error('Offline document action is incomplete.')
  }

  const formData = new FormData()
  formData.append('operation_id', item.id)
  formData.append('action_type', item.action_type)
  formData.append('mobile_doctype', item.mobile_doctype)
  formData.append('values', JSON.stringify(item.values || {}))
  formData.append('client_created_at', item.created_at)

  if (item.docname) {
    formData.append('docname', item.docname)
  }

  let result: Record<string, any> = item.server_result || {}
  if (!result?.doctype || !result?.name) {
    const message = await sendSyncRequest('/api/method/verto.api.mobile.offline.sync_action', {
      method: 'POST',
      headers: withCsrfHeaders(undefined, 'POST'),
      body: formData,
    })

    result = message?.result || message || {}
  }
  const targetDoctype = String(result.doctype || item.server_result?.doctype || '')
  const targetName = String(result.name || item.server_result?.name || item.docname || '')

  if (!targetDoctype || !targetName) {
    throw new OfflineSyncError('The server did not return the synced document details.', { retryable: true })
  }

  item.server_result = result
  await updateClaimedItem(item.id, owner, () => ({ server_result: result }))

  for (const attachment of item.attachments || []) {
    if (item.uploaded_attachment_ids?.includes(attachment.id)) continue
    await uploadQueuedAttachment({
      operationId: item.id,
      attachment,
      targetDoctype,
      targetName,
    })
    item.uploaded_attachment_ids = [...(item.uploaded_attachment_ids || []), attachment.id]
    await updateClaimedItem(item.id, owner, () => ({ uploaded_attachment_ids: item.uploaded_attachment_ids }))
  }

  if ((item.attachments || []).length) {
    await queuePhotoAnalysis(targetDoctype, targetName)
  }

  return result
}

async function syncAttachmentUploadItem(item: OfflineQueueItem) {
  if (!item.target_doctype || !item.target_name || !item.attachment) {
    throw new Error('Offline attachment upload is incomplete.')
  }

  const result = await uploadQueuedAttachment({
    operationId: item.id,
    attachment: item.attachment,
    targetDoctype: item.target_doctype,
    targetName: item.target_name,
  })

  await queuePhotoAnalysis(item.target_doctype, item.target_name)
  return result
}

async function replayLegacyQueueItem(item: OfflineQueueItem) {
  if (!item.url) {
    throw new Error('Legacy offline request is missing its URL.')
  }

  const headers = withCsrfHeaders({
    ...(item.headers || {}),
  }, item.method || 'POST')

  let body: BodyInit | undefined

  if (item.body !== null && item.body !== undefined) {
    if (!headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    body = typeof item.body === 'string' ? item.body : JSON.stringify(item.body)
  }

  return sendSyncRequest(item.url, {
    method: item.method || 'POST',
    headers,
    body,
  }, { legacy: true })
}

async function replayQueueItem(item: OfflineQueueItem, owner: string) {
  if (item.kind === 'jha_observation') {
    return sendSyncRequest('/api/method/verto.api.mobile.voice_jha_workpack.record_jha_observation', {
      method: 'POST',
      headers: withCsrfHeaders({ 'Content-Type': 'application/json' }, 'POST'),
      body: JSON.stringify(item.values),
    })
  }
  if (item.kind === 'mobile_document') {
    return syncMobileDocumentItem(item, owner)
  }

  if (item.kind === 'attachment_upload') {
    return syncAttachmentUploadItem(item)
  }

  return replayLegacyQueueItem(item)
}

const activeItemSyncs = new Map<string, Promise<any>>()
const SYNC_LEASE_MS = 120_000

type SyncItemOptions = { deleteOnPermanentFailure?: boolean; user?: string }

function itemBusyError() {
  return new OfflineSyncError('This item is already syncing in another window.', { retryable: true, busy: true })
}

async function updateClaimedItem(
  id: string,
  owner: string,
  update: (current: OfflineQueueItem) => Partial<OfflineQueueItem> | null,
) {
  await withStore(QUEUE_STORE, 'readwrite', async (store) => {
    const current: OfflineQueueItem | undefined = await requestToPromise(store.get(id))
    if (current?.sync_owner !== owner) throw itemBusyError()
    const changes = update(current)
    if (changes) {
      await requestToPromise(store.put({ ...current, ...changes, updated_at: nowIso() }))
    } else {
      await requestToPromise(store.delete(id))
    }
  })
  dispatchQueueUpdated()
}

export function syncOfflineQueueItem(id: string, options: SyncItemOptions = {}) {
  const active = activeItemSyncs.get(id)
  if (active) return active
  const run = () => performItemSync(id, options)
  const pending = (typeof navigator !== 'undefined' && navigator.locks
    ? navigator.locks.request(`verto:offline-sync:${id}`, { ifAvailable: true }, (lock) => {
        if (!lock) throw itemBusyError()
        return run()
      })
    : run()).finally(() => { activeItemSyncs.delete(id) })
  activeItemSyncs.set(id, pending)
  return pending
}

async function performItemSync(id: string, options: SyncItemOptions) {
  const owner = createOfflineId('sync')
  const item = await withStore<OfflineQueueItem | undefined>(QUEUE_STORE, 'readwrite', async (store) => {
    const current: OfflineQueueItem | undefined = await requestToPromise(store.get(id))
    if (current && options.user !== undefined && !queueItemBelongsToUser(current, options.user)) {
      throw new Error('This upload belongs to another signed-in user.')
    }
    if (!current || current.status === 'synced') return current
    if (hasActiveSyncLease(current)) throw itemBusyError()
    current.sync_owner = owner
    current.sync_expires_at = Date.now() + SYNC_LEASE_MS
    current.status = 'syncing'
    current.attempts = (current.attempts || 0) + 1
    current.last_error = ''
    current.updated_at = nowIso()
    await requestToPromise(store.put(current))
    return current
  })

  if (!item) {
    throw new Error('The offline queue item could not be found.')
  }
  if (item.status === 'synced') return item.server_result

  dispatchQueueUpdated()
  const heartbeat = setInterval(() => {
    void withStore(QUEUE_STORE, 'readwrite', async (store) => {
      const current: OfflineQueueItem | undefined = await requestToPromise(store.get(id))
      if (current?.sync_owner !== owner) return
      current.sync_expires_at = Date.now() + SYNC_LEASE_MS
      await requestToPromise(store.put(current))
    }).catch(() => { /* Server receipts also protect a replay after storage failure. */ })
  }, SYNC_LEASE_MS / 4)

  try {
    const result = await replayQueueItem(item, owner)
    await updateClaimedItem(id, owner, (current) => {
      if (item.kind !== 'mobile_document') return null
      const hasNewAttachments = current.attachments?.some(
        attachment => !current.uploaded_attachment_ids?.includes(attachment.id)
      )
      // Keep the receipt result for a retry, including photos added while a sync was running.
      return {
        status: hasNewAttachments ? 'queued' : 'synced',
        server_result: result,
        attachments: hasNewAttachments ? current.attachments : [],
        uploaded_attachment_ids: hasNewAttachments ? current.uploaded_attachment_ids : [],
        sync_owner: undefined,
        sync_expires_at: undefined,
        next_retry_at: undefined,
      }
    })
    return result
  } catch (error) {
    if (error instanceof OfflineSyncError && error.busy) throw error
    const shouldDelete = Boolean(options.deleteOnPermanentFailure) &&
      !item.server_result &&
      !isRetryableOfflineSyncError(error) &&
      !isOfflineSyncAuthError(error)

    const retryable = isRetryableOfflineSyncError(error)
    await updateClaimedItem(id, owner, () => shouldDelete ? null : ({
      status: retryable ? 'queued' : 'failed',
      sync_owner: undefined,
      sync_expires_at: undefined,
      last_error: error instanceof Error ? error.message : 'Sync failed.',
      last_error_retryable: isRetryableOfflineSyncError(error) || isOfflineSyncAuthError(error),
      next_retry_at: retryable ? Date.now() + Math.min(15_000 * 2 ** Math.min(item.attempts - 1, 5), 300_000) : undefined,
    }))

    throw error
  } finally {
    clearInterval(heartbeat)
  }
}

let queueSyncPromise: Promise<{ synced: number; failed: number; skipped: boolean }> | null = null

export function syncOfflineQueue(user: string) {
  if (queueSyncPromise) return queueSyncPromise
  queueSyncPromise = performQueueSync(user).finally(() => { queueSyncPromise = null })
  return queueSyncPromise
}

async function performQueueSync(user: string) {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return {
      synced: 0,
      failed: 0,
      skipped: true,
    }
  }

  const pending = await getPendingOfflineQueueItems(user)

  let synced = 0
  let failed = 0
  let interrupted = false

  for (const item of pending) {
    // Validation/permission failures need a user's correction. Connectivity
    // failures keep their payload/photos and wait with a bounded retry delay.
    if ((item.next_retry_at || 0) > Date.now() ||
      (item.status === 'failed' && item.last_error_retryable === false)) continue
    if (!navigator.onLine) { interrupted = true; break }
    try {
      await syncOfflineQueueItem(item.id, { user })
      synced += 1
    } catch (err) {
      if (err instanceof OfflineSyncError && err.busy) continue
      failed += 1

      if (isRetryableOfflineSyncError(err)) {
        interrupted = true
        break
      }
      if (isOfflineSyncAuthError(err)) {
        break
      }
    }
  }

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('verto:offline-queue-synced', {
      detail: {
        synced,
        failed,
      },
    }))
  }

  return {
    synced,
    failed,
    skipped: interrupted,
  }
}

export async function queueJsonPostWhenOffline<T>(input: {
  type: string
  url: string
  payload: T
  headers?: Record<string, string>
}) {
  return addOfflineQueueItem({
    type: input.type,
    url: input.url,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(input.headers || {}),
    },
    body: input.payload,
  })
}
