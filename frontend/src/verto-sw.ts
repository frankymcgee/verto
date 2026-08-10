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

const SW_VERSION = 'VERTO_SW_PUSH_NOTIFICATIONS_2026_08_09'
const DEFAULT_NOTIFICATION_URL = '/verto-mobile/'
const DEFAULT_NOTIFICATION_ICON = '/assets/verto/manifest/mss-pwa-192.png'
const DEFAULT_NOTIFICATION_BADGE = '/assets/verto/manifest/mss-pwa-maskable-192.png'
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
    <p>The app shell is installed, but this page was not available in the offline cache yet. Reconnect and try again.</p>
    <button onclick="location.reload()">Retry</button>
  </main>
</body>
</html>`

console.log('[verto pwa] service worker loading', SW_VERSION)

precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()
self.skipWaiting()
clientsClaim()

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

  if (request.method !== 'GET') {
    return
  }

  const url = new URL(request.url)

  if (url.origin !== self.location.origin) {
    return
  }

  // Keep API requests network-first. Push subscriptions and form writes should
  // never be satisfied by the application-shell cache.
  if (url.pathname.startsWith('/api/')) {
    return
  }

  if (request.mode === 'navigate' && url.pathname.startsWith('/verto-mobile')) {
    event.respondWith(
      fetch(request).catch(async () => {
        return new Response(OFFLINE_HTML, {
          status: 200,
          headers: {
            'Content-Type': 'text/html; charset=utf-8',
            'Cache-Control': 'no-store',
          },
        })
      })
    )
  }
})
