// VERTO_PWA_STAGE_1_SERVICE_WORKER_2026_06_10

const CACHE_VERSION = 'verto-mobile-stage-1-v1'
const APP_SHELL_CACHE = `${CACHE_VERSION}-app-shell`
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`

const OFFLINE_URL = '/verto-mobile-offline.html'
const APP_SCOPE = '/verto-mobile/'

const APP_SHELL_URLS = [
  OFFLINE_URL,
  APP_SCOPE,
  '/assets/verto/images/verto-icon.png',
]

self.addEventListener('install', (event) => {
  console.info('[verto sw] install', CACHE_VERSION)

  event.waitUntil(
    caches
      .open(APP_SHELL_CACHE)
      .then((cache) => cache.addAll(APP_SHELL_URLS))
      .then(() => self.skipWaiting())
  )
})

self.addEventListener('activate', (event) => {
  console.info('[verto sw] activate', CACHE_VERSION)

  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((cacheName) => cacheName.startsWith('verto-mobile-') && !cacheName.startsWith(CACHE_VERSION))
            .map((cacheName) => caches.delete(cacheName))
        )
      })
      .then(() => self.clients.claim())
  )
})

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  const url = new URL(request.url)

  if (url.origin !== self.location.origin) {
    return
  }

  if (request.method !== 'GET') {
    return
  }

  if (url.pathname.startsWith('/api/')) {
    return
  }

  if (url.pathname.startsWith('/verto-mobile/')) {
    event.respondWith(networkFirstPage(request))
    return
  }

  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(staleWhileRevalidate(request))
    return
  }
})

async function networkFirstPage(request) {
  try {
    const response = await fetch(request)

    if (response && response.ok) {
      const cache = await caches.open(RUNTIME_CACHE)
      cache.put(request, response.clone())
    }

    return response
  } catch (error) {
    const cachedResponse = await caches.match(request)

    if (cachedResponse) {
      return cachedResponse
    }

    const offlineResponse = await caches.match(OFFLINE_URL)

    if (offlineResponse) {
      return offlineResponse
    }

    return new Response('Verto Mobile is offline.', {
      status: 503,
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
      },
    })
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(RUNTIME_CACHE)
  const cachedResponse = await cache.match(request)

  const fetchPromise = fetch(request)
    .then((networkResponse) => {
      if (networkResponse && networkResponse.ok) {
        cache.put(request, networkResponse.clone())
      }

      return networkResponse
    })
    .catch(() => cachedResponse)

  return cachedResponse || fetchPromise
}
