// VERTO_PWA_STAGE2_OFFLINE_QUEUE_2026_06_10

export type OfflineQueueItemStatus = 'queued' | 'syncing' | 'synced' | 'failed'

export type OfflineQueueItem = {
  id: string
  type: string
  url: string
  method: string
  headers?: Record<string, string>
  body?: any
  created_at: string
  updated_at: string
  attempts: number
  status: OfflineQueueItemStatus
  last_error?: string
}

export type OfflineQueueSummary = {
  queued: number
  syncing: number
  failed: number
  total: number
}

const DB_NAME = 'verto-mobile-offline-db'
const DB_VERSION = 1
const STORE_NAME = 'offline_queue'

function createId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }

  return `offline-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function nowIso() {
  return new Date().toISOString()
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onerror = () => reject(request.error || new Error('Could not open offline queue database.'))

    request.onupgradeneeded = () => {
      const db = request.result

      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, {
          keyPath: 'id',
        })

        store.createIndex('status', 'status', { unique: false })
        store.createIndex('created_at', 'created_at', { unique: false })
        store.createIndex('type', 'type', { unique: false })
      }
    }

    request.onsuccess = () => resolve(request.result)
  })
}

async function withStore<T>(mode: IDBTransactionMode, callback: (store: IDBObjectStore) => IDBRequest<T> | void): Promise<T | void> {
  const db = await openDatabase()

  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, mode)
    const store = tx.objectStore(STORE_NAME)
    const request = callback(store)
    let resolved = false

    if (request) {
      request.onsuccess = () => {
        resolved = true
        resolve(request.result)
      }

      request.onerror = () => reject(request.error || new Error('Offline queue request failed.'))
    }

    tx.oncomplete = () => {
      db.close()

      if (!request && !resolved) {
        resolve()
      }
    }

    tx.onerror = () => {
      db.close()
      reject(tx.error || new Error('Offline queue transaction failed.'))
    }
  })
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
    id: createId(),
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

  await withStore('readwrite', (store) => store.put(item))

  window.dispatchEvent(new CustomEvent('verto:offline-queue-updated'))

  return item
}

export async function getOfflineQueueItems() {
  const items = await withStore<OfflineQueueItem[]>('readonly', (store) => store.getAll())

  return (items || []).sort((a, b) => a.created_at.localeCompare(b.created_at))
}

export async function getOfflineQueueSummary(): Promise<OfflineQueueSummary> {
  const items = await getOfflineQueueItems()

  return {
    queued: items.filter((item) => item.status === 'queued').length,
    syncing: items.filter((item) => item.status === 'syncing').length,
    failed: items.filter((item) => item.status === 'failed').length,
    total: items.filter((item) => item.status !== 'synced').length,
  }
}

export async function updateOfflineQueueItem(item: OfflineQueueItem) {
  await withStore('readwrite', (store) => store.put({
    ...item,
    updated_at: nowIso(),
  }))

  window.dispatchEvent(new CustomEvent('verto:offline-queue-updated'))
}

export async function deleteOfflineQueueItem(id: string) {
  await withStore('readwrite', (store) => store.delete(id))

  window.dispatchEvent(new CustomEvent('verto:offline-queue-updated'))
}

export async function clearSyncedOfflineQueueItems() {
  const items = await getOfflineQueueItems()
  const synced = items.filter((item) => item.status === 'synced')

  await Promise.all(synced.map((item) => deleteOfflineQueueItem(item.id)))
}

async function replayQueueItem(item: OfflineQueueItem) {
  const headers = {
    ...(item.headers || {}),
  }

  let body: BodyInit | undefined

  if (item.body instanceof FormData) {
    body = item.body
  } else if (item.body !== null && item.body !== undefined) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json'
    body = typeof item.body === 'string' ? item.body : JSON.stringify(item.body)
  }

  const response = await fetch(item.url, {
    method: item.method,
    credentials: 'include',
    headers,
    body,
  })

  if (!response.ok) {
    throw new Error(`Sync failed with HTTP ${response.status}`)
  }

  return response
}

export async function syncOfflineQueue() {
  if (!navigator.onLine) {
    return {
      synced: 0,
      failed: 0,
      skipped: true,
    }
  }

  const items = await getOfflineQueueItems()
  const pending = items.filter((item) => item.status === 'queued' || item.status === 'failed')

  let synced = 0
  let failed = 0

  for (const item of pending) {
    const syncingItem: OfflineQueueItem = {
      ...item,
      status: 'syncing',
      attempts: item.attempts + 1,
      last_error: '',
    }

    await updateOfflineQueueItem(syncingItem)

    try {
      await replayQueueItem(syncingItem)

      synced += 1

      await updateOfflineQueueItem({
        ...syncingItem,
        status: 'synced',
        last_error: '',
      })

      await deleteOfflineQueueItem(syncingItem.id)
    } catch (err) {
      failed += 1

      await updateOfflineQueueItem({
        ...syncingItem,
        status: 'failed',
        last_error: err instanceof Error ? err.message : 'Sync failed.',
      })
    }
  }

  window.dispatchEvent(new CustomEvent('verto:offline-queue-synced', {
    detail: {
      synced,
      failed,
    },
  }))

  return {
    synced,
    failed,
    skipped: false,
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
