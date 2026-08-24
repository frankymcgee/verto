/// <reference lib="webworker" />

import { clientsClaim } from 'workbox-core'
import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching'

declare let self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{
    url: string
    revision?: string | null
  }>
}

type VertoPushPayload = {
  title?: string
  body?: string
  url?: string
  tag?: string
  icon?: string
  badge?: string
}

type OfflineAttachment = {
  id: string
  name: string
  type: string
  size: number
  last_modified: number
  blob: Blob
}

type OfflineQueueItem = {
  id: string
  kind: string
  type: string
  action_type?: string
  mobile_doctype?: string
  docname?: string
  values?: Record<string, any>
  attachments?: OfflineAttachment[]
  created_at: string
  updated_at: string
  attempts: number
  status: string
  last_error?: string
  [key: string]: any
}

const SW_VERSION = 'VERTO_SW_OFFLINE_FORMS_2026_08_24'
const DEFAULT_NOTIFICATION_URL = '/verto-mobile/'
const DEFAULT_NOTIFICATION_ICON = '/assets/verto/manifest/mss-pwa-192.png'
const DEFAULT_NOTIFICATION_BADGE = '/assets/verto/manifest/mss-pwa-maskable-192.png'
const PAGE_CACHE = 'verto-mobile-page-shell-v1'
const DB_NAME = 'verto-mobile-offline-db'
const DB_VERSION = 3
const QUEUE_STORE = 'offline_queue'
const API_CACHE_STORE = 'api_cache'
const OFFLINE_USER_KEY = '__verto_offline_user'

const OFFLINE_HTML = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Verto Mobile Offline</title>
  <style>
    :root { color-scheme: light; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f8fafc;
      color: #111827;
    }
    main {
      width: min(28rem, calc(100vw - 2rem));
      border: 1px solid #e5e7eb;
      border-radius: 1rem;
      background: #fff;
      padding: 1.25rem;
      box-shadow: 0 20px 45px rgba(15, 23, 42, 0.08);
    }
    h1 { margin: 0; font-size: 1.125rem; }
    p { margin: 0.75rem 0 0; color: #64748b; line-height: 1.45; }
    button {
      margin-top: 1rem;
      width: 100%;
      border: 0;
      border-radius: 0.75rem;
      padding: 0.75rem 1rem;
      background: #111827;
      color: #fff;
      font-weight: 700;
    }
  </style>
</head>
<body>
  <main>
    <h1>Verto Mobile is offline</h1>
    <p>This device has not cached the Verto application shell yet. Reconnect once, open Verto, then offline forms and shifts will be available.</p>
    <button onclick="location.reload()">Retry</button>
  </main>
</body>
</html>`

console.log('[verto pwa] service worker loading', SW_VERSION)

precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()
self.skipWaiting()
clientsClaim()

function createId(prefix = 'offline') {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `${prefix}-${crypto.randomUUID()}`
  }

  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function nowIso() {
  return new Date().toISOString()
}

function openOfflineDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onerror = () => reject(request.error || new Error('Could not open offline database.'))
    request.onsuccess = () => resolve(request.result)

    request.onupgradeneeded = () => {
      const db = request.result
      const transaction = request.transaction

      let queueStore: IDBObjectStore

      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        queueStore = db.createObjectStore(QUEUE_STORE, { keyPath: 'id' })
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
        const cacheStore = db.createObjectStore(API_CACHE_STORE, { keyPath: 'key' })
        cacheStore.createIndex('group', 'group', { unique: false })
        cacheStore.createIndex('updated_at', 'updated_at', { unique: false })
      }
    }
  })
}

function idbRequest<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error || new Error('IndexedDB request failed.'))
  })
}

async function withOfflineStore<T>(
  storeName: string,
  mode: IDBTransactionMode,
  callback: (store: IDBObjectStore) => Promise<T>
) {
  const db = await openOfflineDatabase()

  try {
    const transaction = db.transaction(storeName, mode)
    const store = transaction.objectStore(storeName)
    const result = await callback(store)

    await new Promise<void>((resolve, reject) => {
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error || new Error('Offline transaction failed.'))
      transaction.onabort = () => reject(transaction.error || new Error('Offline transaction aborted.'))
    })

    return result
  } finally {
    db.close()
  }
}

async function getQueueItem(id: string) {
  return withOfflineStore<OfflineQueueItem | undefined>(QUEUE_STORE, 'readonly', (store) => {
    return idbRequest(store.get(id))
  })
}

async function getQueueItems() {
  return withOfflineStore<OfflineQueueItem[]>(QUEUE_STORE, 'readonly', (store) => {
    return idbRequest(store.getAll())
  })
}

async function putQueueItem(item: OfflineQueueItem) {
  return withOfflineStore(QUEUE_STORE, 'readwrite', async (store) => {
    await idbRequest(store.put({
      ...item,
      updated_at: nowIso(),
    }))
    return undefined
  })
}

async function getOfflineActor() {
  const entry = await withOfflineStore<any>(API_CACHE_STORE, 'readonly', (store) => {
    return idbRequest(store.get('offline-bootstrap:latest'))
  })

  return String(entry?.value?.message?.user || entry?.value?.message?.shift_calendar?.user || '').trim()
}

function mobileSlugFromDoctype(doctype: string) {
  return String(doctype || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
}

function makeOfflineAttachment(file: Blob, fileName?: string): OfflineAttachment {
  const possibleFile = file as File

  return {
    id: createId('file'),
    name: fileName || possibleFile.name || `attachment-${Date.now()}`,
    type: file.type || 'application/octet-stream',
    size: file.size,
    last_modified: possibleFile.lastModified || Date.now(),
    blob: file,
  }
}

async function findDocumentOperation(docname: string) {
  const direct = await getQueueItem(docname)

  if (direct?.kind === 'mobile_document') {
    return direct
  }

  const items = await getQueueItems()

  return items
    .filter((item) => {
      return item.kind === 'mobile_document' &&
        item.docname === docname &&
        ['queued', 'syncing', 'failed'].includes(item.status)
    })
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
}

async function notifyOfflineQueueUpdated() {
  const clients = await self.clients.matchAll({
    type: 'window',
    includeUncontrolled: true,
  })

  for (const client of clients) {
    client.postMessage({ type: 'VERTO_OFFLINE_QUEUE_UPDATED' })
  }
}

async function queueUploadRequest(request: Request) {
  const formData = await request.formData()
  const value = formData.get('file')
  const doctype = String(formData.get('doctype') || '').trim()
  const docname = String(formData.get('docname') || '').trim()

  if (!(value instanceof Blob) || !doctype || !docname) {
    throw new Error('Offline attachment request is incomplete.')
  }

  const attachment = makeOfflineAttachment(value, (value as File).name)
  let operation = await findDocumentOperation(docname)

  if (!operation) {
    const actor = await getOfflineActor()

    if (!actor) {
      throw new Error('Offline data is not initialised for this user yet.')
    }

    const timestamp = nowIso()
    operation = {
      id: createId('document'),
      kind: 'mobile_document',
      type: 'mobile_document_update',
      action_type: 'update',
      mobile_doctype: mobileSlugFromDoctype(doctype),
      docname,
      values: {
        [OFFLINE_USER_KEY]: actor,
      },
      attachments: [],
      server_result: null,
      created_at: timestamp,
      updated_at: timestamp,
      attempts: 0,
      status: 'queued',
    }
  }

  operation.attachments = [...(operation.attachments || []), attachment]
  operation.status = operation.status === 'synced' ? 'queued' : operation.status
  await putQueueItem(operation)
  await notifyOfflineQueueUpdated()

  return new Response(JSON.stringify({
    message: {
      offline_queued: true,
      operation_id: operation.id,
      file_name: attachment.name,
    },
  }), {
    status: 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
    },
  })
}

async function handleUploadRequest(request: Request) {
  try {
    return await fetch(request.clone())
  } catch {
    return queueUploadRequest(request.clone())
  }
}

async function handleVertoNavigation(request: Request) {
  const cache = await caches.open(PAGE_CACHE)

  try {
    const response = await fetch(request)

    if (response.ok) {
      await cache.put(request, response.clone())

      const rootUrl = new URL('/verto-mobile/', self.location.origin).href
      const requestUrl = new URL(request.url)

      if (requestUrl.pathname === '/verto-mobile' || requestUrl.pathname === '/verto-mobile/') {
        await cache.put(rootUrl, response.clone())
      }
    }

    return response
  } catch {
    const exact = await cache.match(request)

    if (exact) {
      return exact
    }

    const rootUrl = new URL('/verto-mobile/', self.location.origin).href
    const root = await cache.match(rootUrl)

    if (root) {
      return root
    }

    return new Response(OFFLINE_HTML, {
      status: 200,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store',
      },
    })
  }
}

function parsePushPayload(event: PushEvent): VertoPushPayload {
  if (!event.data) {
    return {}
  }

  try {
    const parsed = event.data.json()

    if (parsed && typeof parsed === 'object') {
      return parsed.notification || parsed
    }
  } catch {
    return {
      body: event.data.text(),
    }
  }

  return {}
}

function getSafeAppUrl(value?: string) {
  const fallback = new URL(DEFAULT_NOTIFICATION_URL, self.location.origin)

  try {
    const url = new URL(value || DEFAULT_NOTIFICATION_URL, self.location.origin)

    if (url.origin !== self.location.origin || !url.pathname.startsWith('/verto-mobile')) {
      return fallback.href
    }

    return url.href
  } catch {
    return fallback.href
  }
}

self.addEventListener('install', () => {
  console.log('[verto pwa] service worker installed', SW_VERSION)
})

self.addEventListener('activate', (event) => {
  console.log('[verto pwa] service worker activated', SW_VERSION)
  event.waitUntil(self.clients.claim())
})

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})

self.addEventListener('push', (event) => {
  const payload = parsePushPayload(event)
  const title = payload.title || 'Verto'
  const targetUrl = getSafeAppUrl(payload.url)
  const notificationOptions: NotificationOptions & { renotify?: boolean } = {
    body: payload.body || 'A new update is available.',
    icon: payload.icon || DEFAULT_NOTIFICATION_ICON,
    badge: payload.badge || DEFAULT_NOTIFICATION_BADGE,
    tag: payload.tag,
    renotify: Boolean(payload.tag),
    data: {
      url: targetUrl,
    },
  }

  event.waitUntil(
    self.registration.showNotification(title, notificationOptions)
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()

  const targetUrl = getSafeAppUrl(event.notification.data?.url)

  event.waitUntil((async () => {
    const appClients = await self.clients.matchAll({
      type: 'window',
      includeUncontrolled: true,
    })

    const existingClient = appClients.find((client) => {
      try {
        return new URL(client.url).pathname.startsWith('/verto-mobile')
      } catch {
        return false
      }
    }) as WindowClient | undefined

    if (existingClient) {
      await existingClient.navigate(targetUrl)
      await existingClient.focus()
      return
    }

    await self.clients.openWindow(targetUrl)
  })())
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  const url = new URL(request.url)

  if (url.origin !== self.location.origin) {
    return
  }

  if (
    request.method === 'POST' &&
    url.pathname === '/api/method/upload_file'
  ) {
    event.respondWith(handleUploadRequest(request))
    return
  }

  if (request.method !== 'GET') {
    return
  }

  // API reads/writes are managed by the IndexedDB-aware frontend API layer.
  if (url.pathname.startsWith('/api/')) {
    return
  }

  if (request.mode === 'navigate' && url.pathname.startsWith('/verto-mobile')) {
    event.respondWith(handleVertoNavigation(request))
  }
})
