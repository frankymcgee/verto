/// <reference lib="webworker" />

import { clientsClaim } from 'workbox-core'
import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching'

declare let self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{
    url: string
    revision?: string | null
  }>
}

const SW_VERSION = 'VERTO_SW_RAVEN_STYLE_STAGE_1_2026_06_10'
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

self.addEventListener('fetch', (event) => {
  const request = event.request

  if (request.method !== 'GET') {
    return
  }

  const url = new URL(request.url)

  if (url.origin !== self.location.origin) {
    return
  }

  // Keep API requests network-first for now. Offline form queuing will be added explicitly later.
  if (url.pathname.startsWith('/api/')) {
    return
  }

  if (request.mode === 'navigate' && url.pathname.startsWith('/verto-mobile')) {
    event.respondWith(
      fetch(request).catch(async () => {
        const fallbackResponse = new Response(OFFLINE_HTML, {
          status: 200,
          headers: {
            'Content-Type': 'text/html; charset=utf-8',
            'Cache-Control': 'no-store',
          },
        })

        return fallbackResponse
      })
    )
  }
})
